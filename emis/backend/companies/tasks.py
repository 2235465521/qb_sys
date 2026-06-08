import os
import traceback
import datetime
from celery import shared_task
from django.core.cache import cache
from django.db import transaction, connection
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
    }, timeout=3600)  # 缓存1小时

@shared_task
def import_companies_task(file_path, task_id):
    """
    异步处理 Excel 批量导入企业任务
    1. 缓存预热
    2. 流式读取
    3. bulk_create 批量写入
    """
    _update_progress(task_id, status="processing", progress=1)
    errors = []
    success_count = 0
    skipped_count = 0
    total_count = 0

    try:
        # ==========================================
        # Step 1: 缓存预热
        # ==========================================
        _update_progress(task_id, status="processing", progress=5)

        # 从预热缓存加载省市区字典（相比每次直接查库，这里短路 3 次 DB Query 就变成 0 次）
        from companies.warmup import get_area_data_from_cache
        _provinces, _cities, _districts = get_area_data_from_cache()

        # 将列表转为查找字典
        provinces  = {p['name']: p for p in _provinces}
        cities     = {(c['province_id'], c['name']): c for c in _cities}
        districts  = {(d['city_id'], d['name']): d for d in _districts}

        def _find_obj(model_cls, data_dict, pk):
            """根据 id 从模型层返回实例（懒加载已命中的）"""
            return model_cls.objects.get(pk=pk)

        _prov_cache = {}
        _city_cache = {}
        _dist_cache = {}

        def find_province(name):
            if not name: return None
            for p_name, p_data in provinces.items():
                if name in p_name or p_name in name:
                    pid = p_data['id']
                    if pid not in _prov_cache:
                        _prov_cache[pid] = Province.objects.get(pk=pid)
                    return _prov_cache[pid]
            return None

        def find_city(p_id, name):
            if not name or not p_id: return None
            for (pid, c_name), c_data in cities.items():
                if pid == p_id and (name in c_name or c_name in name):
                    cid = c_data['id']
                    if cid not in _city_cache:
                        _city_cache[cid] = City.objects.get(pk=cid)
                    return _city_cache[cid]
            return None

        def find_district(c_id, name):
            if not name or not c_id: return None
            for (cid, d_name), d_data in districts.items():
                if cid == c_id and (name in d_name or d_name in name):
                    did = d_data['id']
                    if did not in _dist_cache:
                        _dist_cache[did] = District.objects.get(pk=did)
                    return _dist_cache[did]
            return None

        # 预加载现有信用代码，用于查重
        existing_codes = set(Company.objects.values_list('credit_code', flat=True))

        # ==========================================
        # Step 2: 流式读取 Excel
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
        col_map = {'name': -1, 'credit_code': -1, 'legal_person': -1, 'province': -1, 'city': -1, 'district': -1, 'region_full': -1, 'latitude': -1, 'longitude': -1, 'contact': -1, 'address': -1}

        for i, h in enumerate(headers):
            if h in ['企业名称*', '企业名称', '起草单位/企业名称']: col_map['name'] = i
            elif h in ['统一社会信用代码*', '统一社会信用代码']: col_map['credit_code'] = i
            elif h in ['法人', '法定代表人']: col_map['legal_person'] = i
            elif h in ['省份']: col_map['province'] = i
            elif h in ['城市']: col_map['city'] = i
            elif h in ['区县']: col_map['district'] = i
            elif h in ['行政区划']: col_map['region_full'] = i
            elif h in ['纬度']: col_map['latitude'] = i
            elif h in ['经度']: col_map['longitude'] = i
            elif h in ['联系方式']: col_map['contact'] = i
            elif h in ['详细地址', '注册地址']: col_map['address'] = i

        if all(v == -1 for v in col_map.values()):
            col_map = {'name': 0, 'credit_code': 1, 'legal_person': 2, 'province': 3, 'city': 4, 'district': 5, 'latitude': 6, 'longitude': 7, 'contact': 8, 'address': 9, 'region_full': -1}

        # 估算总行数用于进度条 (由于 read_only 模式 max_row 可能不准，我们只作为一个参考)
        estimated_total = ws.max_row if ws.max_row else 10000

        # ==========================================
        # Step 3 & 4: 解析并组装，使用 bulk_create
        # ==========================================
        batch_size = 2000
        companies_batch = []
        
        for row_idx, row in enumerate(rows_iter, start=2):
            if not any(row): continue
            total_count += 1
            
            def get_val(key):
                idx = col_map.get(key, -1)
                if idx != -1 and idx < len(row):
                    val = row[idx]
                    return str(val).strip() if val else ''
                return ''

            name = get_val('name')
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

            # 行政区划解析
            p_obj = c_obj = d_obj = None
            region_full = get_val('region_full')
            
            if region_full and region_full != 'nan' and '-' in region_full:
                geo_parts = region_full.split('-')
                if len(geo_parts) >= 1:
                    p_obj = find_province(geo_parts[0].replace('省', ''))
                if len(geo_parts) == 2 and p_obj:
                    c_obj = find_city(p_obj.id, '市辖区') or find_city(p_obj.id, p_obj.name.replace('省', '').replace('市', '')) or list(cities.values())[0] if cities else None
                    if c_obj:
                        d_obj = find_district(c_obj.id, geo_parts[1])
                else:
                    if len(geo_parts) >= 2 and p_obj:
                        c_obj = find_city(p_obj.id, geo_parts[1].replace('市', ''))
                    if len(geo_parts) >= 3 and c_obj:
                        d_obj = find_district(c_obj.id, geo_parts[2])

            if not p_obj:
                p_obj = find_province(get_val('province'))
            if not c_obj and p_obj:
                c_obj = find_city(p_obj.id, get_val('city'))
            if not d_obj and c_obj:
                d_obj = find_district(c_obj.id, get_val('district'))

            latitude = longitude = None
            try:
                lat_str = get_val('latitude')
                if lat_str: latitude = float(lat_str)
                lng_str = get_val('longitude')
                if lng_str: longitude = float(lng_str)
            except (ValueError, TypeError):
                errors.append(f"第{row_idx}行: 经纬度格式有误")

            if latitude is None and longitude is None:
                if d_obj and d_obj.latitude and d_obj.longitude:
                    latitude = d_obj.latitude
                    longitude = d_obj.longitude
                elif c_obj and c_obj.latitude and c_obj.longitude:
                    latitude = c_obj.latitude
                    longitude = c_obj.longitude

            now = timezone.now()
            company = Company(
                name=name,
                credit_code=credit_code,
                legal_person=get_val('legal_person'),
                province=p_obj,
                city=c_obj,
                district=d_obj,
                latitude=latitude,
                longitude=longitude,
                contact=get_val('contact'),
                address=get_val('address'),
                status='active',
                is_deleted=False,
                created_at=now,
                updated_at=now
            )
            companies_batch.append(company)
            existing_codes.add(credit_code) # 防止当前批次内重复

            if len(companies_batch) >= batch_size:
                Company.objects.bulk_create(companies_batch, ignore_conflicts=True)
                success_count += len(companies_batch)
                companies_batch = []
                
                # 更新进度
                progress = min(10 + int((total_count / estimated_total) * 85), 95)
                _update_progress(task_id, status="processing", progress=progress, success=success_count, skipped=skipped_count, errors=errors, total=total_count)

        # 插入剩余的
        if companies_batch:
            Company.objects.bulk_create(companies_batch, ignore_conflicts=True)
            success_count += len(companies_batch)

        wb.close()
        
        # 删除临时文件
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass

        _update_progress(task_id, status="done", progress=100, success=success_count, skipped=skipped_count, errors=errors, total=total_count)

    except Exception as e:
        traceback.print_exc()
        errors.append(f"系统错误: {str(e)}")
        _update_progress(task_id, status="failed", progress=100, success=success_count, skipped=skipped_count, errors=errors, total=total_count)


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
    from django.core.cache import cache
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
