import os
import traceback
from celery import shared_task
from django.core.cache import cache
from django.utils import timezone
import openpyxl
from django.conf import settings

from .models import Company, Province, City, District


def _update_progress(task_id, status, progress, success=0, skipped=0, errors=None, total=0):
    if errors is None:
        errors = []
    cache_key = f"import_task_{task_id}"
    cache.set(cache_key, {
        "status": status,
        "progress": progress,
        "success": success,
        "skipped": skipped,
        "errors": errors[:100],  # 只保留前 100 个错误避免缓存过大
        "total": total,
    }, timeout=3600)


@shared_task
def import_companies_task(file_path, task_id):
    """
    异步处理 Excel 批量导入企业任务
    1. 读预热缓存（省市区 3 次 DB → 0 次）
    2. 流式读取 Excel（read_only=True 防止 OOM）
    3. bulk_create 批量写入（2000条/批）
    """
    _update_progress(task_id, status="processing", progress=1)
    errors = []
    success_count = 0
    skipped_count = 0
    total_count = 0

    try:
        # ==========================================
        # Step 1: 从预热缓存加载省市区字典
        # ==========================================
        _update_progress(task_id, status="processing", progress=5)

        from companies.warmup import get_area_data_from_cache
        _provinces, _cities, _districts = get_area_data_from_cache()

        # 将列表转为查找字典（value 为 dict，含 id / latitude / longitude）
        # 注意：find 函数直接返回 dict，FK 赋值用 province_id= 避免额外 DB 查询
        prov_dict = {p['name']: p for p in _provinces}
        city_dict  = {(c['province_id'], c['name']): c for c in _cities}
        dist_dict  = {(d['city_id'], d['name']): d for d in _districts}

        def find_province(name):
            if not name: return None
            for p_name, p_data in prov_dict.items():
                if name in p_name or p_name in name:
                    return p_data
            return None

        def find_city(p_id, name):
            if not name or not p_id: return None
            for (pid, c_name), c_data in city_dict.items():
                if pid == p_id and (name in c_name or c_name in name):
                    return c_data
            return None

        def find_district(c_id, name):
            if not name or not c_id: return None
            for (cid, d_name), d_data in dist_dict.items():
                if cid == c_id and (name in d_name or d_name in name):
                    return d_data
            return None

        # 预加载现有信用代码，用于查重（1 次 DB）
        existing_codes = set(Company.objects.values_list('credit_code', flat=True))

        # ==========================================
        # Step 2: 流式读取 Excel（read_only=True 防 OOM）
        # ==========================================
        _update_progress(task_id, status="processing", progress=10)
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        ws = wb.active

        rows_iter = ws.iter_rows(values_only=True)
        try:
            header_row = next(rows_iter)
        except StopIteration:
            _update_progress(task_id, status="failed", progress=100, errors=["文件为空"])
            return

        headers = [str(c).strip() if c else '' for c in header_row]
        col_map = {
            'name': -1, 'credit_code': -1, 'legal_person': -1,
            'province': -1, 'city': -1, 'district': -1,
            'region_full': -1, 'latitude': -1, 'longitude': -1,
            'contact': -1, 'address': -1
        }

        for i, h in enumerate(headers):
            if h in ['企业名称*', '企业名称', '起草单位/企业名称']:       col_map['name'] = i
            elif h in ['统一社会信用代码*', '统一社会信用代码']:           col_map['credit_code'] = i
            elif h in ['法人', '法定代表人']:                             col_map['legal_person'] = i
            elif h in ['省份']:                                          col_map['province'] = i
            elif h in ['城市']:                                          col_map['city'] = i
            elif h in ['区县']:                                          col_map['district'] = i
            elif h in ['行政区划']:                                       col_map['region_full'] = i
            elif h in ['纬度']:                                          col_map['latitude'] = i
            elif h in ['经度']:                                          col_map['longitude'] = i
            elif h in ['联系方式']:                                       col_map['contact'] = i
            elif h in ['详细地址', '注册地址']:                            col_map['address'] = i

        # 列头全未识别时按位置降级
        if all(v == -1 for v in col_map.values()):
            col_map = {
                'name': 0, 'credit_code': 1, 'legal_person': 2,
                'province': 3, 'city': 4, 'district': 5,
                'latitude': 6, 'longitude': 7, 'contact': 8,
                'address': 9, 'region_full': -1
            }

        # read_only 模式下 max_row 仅作参考
        estimated_total = ws.max_row if ws.max_row else 10000

        # ==========================================
        # Step 3 & 4: 解析行数据，batch bulk_create
        # ==========================================
        batch_size = 2000
        companies_batch = []

        for row_idx, row in enumerate(rows_iter, start=2):
            if not any(row):
                continue
            total_count += 1

            def get_val(key):
                idx = col_map.get(key, -1)
                if idx != -1 and idx < len(row):
                    val = row[idx]
                    return str(val).strip() if val else ''
                return ''

            name        = get_val('name')
            credit_code = get_val('credit_code')

            if not name:
                errors.append(f"第{row_idx}行: 企业名称不能为空")
                continue
            if not credit_code:
                errors.append(f"第{row_idx}行: 统一社会信用代码不能为空")
                continue
            if credit_code in existing_codes:
                skipped_count += 1
                continue

            # 行政区划解析（find 函数返回 dict，不触发额外 DB 查询）
            p_data = c_data = d_data = None
            region_full = get_val('region_full')

            if region_full and region_full != 'nan' and '-' in region_full:
                geo_parts = region_full.split('-')
                if len(geo_parts) >= 1:
                    p_data = find_province(geo_parts[0].replace('省', ''))
                if len(geo_parts) == 2 and p_data:
                    # 直辖市两级结构兼容
                    c_data = (find_city(p_data['id'], '市辖区')
                              or find_city(p_data['id'], p_data['name'].replace('省', '').replace('市', '')))
                    if c_data:
                        d_data = find_district(c_data['id'], geo_parts[1])
                else:
                    if len(geo_parts) >= 2 and p_data:
                        c_data = find_city(p_data['id'], geo_parts[1].replace('市', ''))
                    if len(geo_parts) >= 3 and c_data:
                        d_data = find_district(c_data['id'], geo_parts[2])

            if not p_data:
                p_data = find_province(get_val('province'))
            if not c_data and p_data:
                c_data = find_city(p_data['id'], get_val('city'))
            if not d_data and c_data:
                d_data = find_district(c_data['id'], get_val('district'))

            # 经纬度：优先 Excel 中的值，缺失时降级取区→市中心
            latitude = longitude = None
            try:
                lat_str = get_val('latitude')
                if lat_str: latitude = float(lat_str)
                lng_str = get_val('longitude')
                if lng_str: longitude = float(lng_str)
            except (ValueError, TypeError):
                errors.append(f"第{row_idx}行: 经纬度格式有误")

            if latitude is None and longitude is None:
                if d_data and d_data.get('latitude') and d_data.get('longitude'):
                    latitude  = d_data['latitude']
                    longitude = d_data['longitude']
                elif c_data and c_data.get('latitude') and c_data.get('longitude'):
                    latitude  = c_data['latitude']
                    longitude = c_data['longitude']

            now = timezone.now()
            company = Company(
                name=name,
                credit_code=credit_code,
                legal_person=get_val('legal_person'),
                province_id=p_data['id'] if p_data else None,  # 直接赋 FK id，0 次额外查询
                city_id=c_data['id']     if c_data else None,
                district_id=d_data['id'] if d_data else None,
                latitude=latitude,
                longitude=longitude,
                contact=get_val('contact'),
                address=get_val('address'),
                status='active',
                is_deleted=False,
                created_at=now,
                updated_at=now,
            )
            companies_batch.append(company)
            existing_codes.add(credit_code)  # 防当前批次内重复

            if len(companies_batch) >= batch_size:
                Company.objects.bulk_create(companies_batch, ignore_conflicts=True)
                success_count += len(companies_batch)
                companies_batch = []
                progress = min(10 + int((total_count / estimated_total) * 85), 95)
                _update_progress(task_id, status="processing", progress=progress,
                                 success=success_count, skipped=skipped_count,
                                 errors=errors, total=total_count)

        # 插入剩余不满一批的数据
        if companies_batch:
            Company.objects.bulk_create(companies_batch, ignore_conflicts=True)
            success_count += len(companies_batch)

        wb.close()

        # 删除临时上传文件
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass

        _update_progress(task_id, status="done", progress=100,
                         success=success_count, skipped=skipped_count,
                         errors=errors, total=total_count)

    except Exception as e:
        traceback.print_exc()
        errors.append(f"系统错误: {str(e)}")
        _update_progress(task_id, status="failed", progress=100,
                         success=success_count, skipped=skipped_count,
                         errors=errors, total=total_count)


# ============================================================
# Celery Beat 定时预热任务
# ============================================================

@shared_task(name='companies.tasks.warm_area_dict_task')
def warm_area_dict_task():
    """
    Celery Beat 定时任务：每 24 小时刷新省市区字典缓存。
    对应 settings.CELERY_BEAT_SCHEDULE 中的 'warm-area-dict-daily'。
    """
    from companies.warmup import warm_area_dict
    warm_area_dict()
    return 'area dict cache warmed'


@shared_task(name='companies.tasks.warm_dashboard_stats_task')
def warm_dashboard_stats_task():
    """
    Celery Beat 定时任务：每 30 分钟刷新 Dashboard 统计数据缓存。
    对应 settings.CELERY_BEAT_SCHEDULE 中的 'warm-dashboard-stats-30m'。
    """
    try:
        total_companies  = Company.objects.filter(is_deleted=False).count()
        active_companies = Company.objects.filter(is_deleted=False, status='active').count()
        cache.set('dashboard:stats', {
            'total_companies':  total_companies,
            'active_companies': active_companies,
        }, timeout=1800)  # 30 分钟
    except Exception as e:
        import logging
        logging.getLogger('companies.tasks').warning(f'[warm_dashboard] 失败: {e}')
    return 'dashboard stats cache warmed'
