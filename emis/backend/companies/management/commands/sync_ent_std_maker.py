import logging
from django.core.management.base import BaseCommand
from django.db import transaction, connections
from companies.models import Company, Province, City, District

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = '将 compare_conp 数据库中的 ent_std_maker 数据单向对冲（覆盖/新增）到 emis_db.Company'

    def safe_trunc(self, val, max_len):
        if not isinstance(val, str):
            return val
        return val[:max_len]

    def smart_extract_emails(self, email_str, max_len=254):
        if not email_str or not isinstance(email_str, str):
            return ''
        import re
        parts = re.split(r'[;,\s|]+', email_str.strip())
        valid_parts = [p.strip() for p in parts if p.strip()]
        
        result = ''
        for p in valid_parts:
            if not result:
                if len(p) <= max_len:
                    result = p
                else:
                    return p[:max_len]
            else:
                candidate = result + ',' + p
                if len(candidate) <= max_len:
                    result = candidate
                else:
                    break
        return result

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("=== 开始极速同步 compare_conp.ent_std_maker 数据 ==="))

        # 1. 预加载所有行政区划字典表数据到内存，避免 N+1 查询
        provinces_by_name = {p.name: p for p in Province.objects.all()}
        cities_by_name = {c.name: c for c in City.objects.all()}
        districts_by_name = {d.name: d for d in District.objects.all()}
        
        provinces_by_code = {p.code: p for p in Province.objects.all()}
        cities_by_code = {c.code: c for c in City.objects.all()}
        districts_by_code = {d.code: d for d in District.objects.all()}

        self.stdout.write(self.style.SUCCESS("字典表加载完毕。"))

        # 2. 预加载主库企业缓存索引（极大提速，彻底干掉内部 SELECT 查询）
        self.stdout.write(self.style.SUCCESS("开始将已有企业数据建立内存索引（约需数秒，请稍候）..."))
        companies_data = Company.objects.values('id', 'name', 'credit_code', 'contact', 'address')
        
        cache_by_name = {}
        cache_by_code = {}
        
        for c in companies_data:
            c_dict = {
                'id': c['id'],
                'contact': c['contact'] or '',
                'address': c['address'] or '',
                'credit_code': c['credit_code'] or ''
            }
            if c['name']:
                cache_by_name[c['name']] = c_dict
            if c['credit_code']:
                cache_by_code[c['credit_code']] = c_dict

        self.stdout.write(self.style.SUCCESS("主库企业索引建立完毕。开始读取源数据库..."))

        # 3. 读取 compare_conp 数据
        created_count = 0
        updated_count = 0

        try:
            with connections['compare_conp'].cursor() as cursor:
                cursor.execute("SELECT * FROM ent_std_maker")
                columns = [col[0] for col in cursor.description]
                
                rows = cursor.fetchall()
                total_rows = len(rows)
                self.stdout.write(self.style.SUCCESS(f"源表共计找到 {total_rows} 条数据。正在高速处理..."))
                
                batch_size = 5000
                
                for i in range(0, total_rows, batch_size):
                    batch_rows = rows[i:i+batch_size]
                    
                    # 每一小批开启一个事务，防止单一事务过大导致内存溢出和变慢
                    with transaction.atomic():
                        for row in batch_rows:
                            row_dict = dict(zip(columns, row))
                            
                            company_name = (row_dict.get('company_name') or '').strip()
                            credit_code = (row_dict.get('unified_social_credit_code') or '').strip()
                            
                            if not company_name and not credit_code:
                                continue
                            
                            # 基于内存缓存的高速匹配
                            cached_company = None
                            if company_name:
                                cached_company = cache_by_name.get(company_name)
                            if not cached_company and credit_code:
                                cached_company = cache_by_code.get(credit_code)
                            
                            # 数据映射封装
                            mapped_data = {
                                'name': self.safe_trunc(company_name, 200),
                                'credit_code': self.safe_trunc(credit_code, 25),
                                'legal_person': self.safe_trunc(row_dict.get('legal_representative') or '', 50),
                                'company_type': self.safe_trunc(row_dict.get('enterprise_type') or '', 100),
                                'registration_no': self.safe_trunc(row_dict.get('registration_no') or '', 100),
                                'organization_code': self.safe_trunc(row_dict.get('organization_code') or '', 100),
                                'registered_address': self.safe_trunc(row_dict.get('registered_address') or '', 500),
                                'registered_zipcode': self.safe_trunc(row_dict.get('registered_address_zip') or '', 20),
                                'valid_mobile': self.safe_trunc(row_dict.get('mobile_phone') or '', 50),
                                'more_phones': self.safe_trunc(row_dict.get('other_phones') or '', 200),
                                'email': self.smart_extract_emails(row_dict.get('email') or '', 254),
                                'industry_category': self.safe_trunc(row_dict.get('industry_category_l1') or '', 100),
                                'industry_major': self.safe_trunc(row_dict.get('industry_category_l2') or '', 100),
                                'industry_middle': self.safe_trunc(row_dict.get('industry_category_l3') or '', 100),
                                'industry_minor': self.safe_trunc(row_dict.get('industry_category_l4') or '', 100),
                                'company_size': self.safe_trunc(row_dict.get('enterprise_scale') or '', 50),
                                'former_names': self.safe_trunc(row_dict.get('former_name') or '', 500),
                                'english_name': self.safe_trunc(row_dict.get('english_name') or '', 200),
                                'website_url': self.safe_trunc(row_dict.get('website_url') or '', 500),
                                'mailing_address': self.safe_trunc(row_dict.get('mailing_address') or '', 500),
                                'mailing_address_zip': self.safe_trunc(row_dict.get('mailing_address_zip') or '', 20),
                                'business_scope': row_dict.get('business_scope') or '',
                                'registration_status': self.safe_trunc(row_dict.get('registration_status') or '', 100),
                            }
                            
                            # 兼容处理脏时间数据
                            est_date = row_dict.get('establishment_date')
                            if isinstance(est_date, str):
                                est_date = est_date.strip()
                                if not est_date or est_date == '-' or len(est_date) < 10:
                                    mapped_data['established_date'] = None
                                else:
                                    mapped_data['established_date'] = est_date[:10]
                            else:
                                mapped_data['established_date'] = None
                            
                            # 兼容处理 contact 与 address
                            if cached_company:
                                if not cached_company['contact']:
                                    mapped_data['contact'] = self.safe_trunc(row_dict.get('mobile_phone') or row_dict.get('other_phones') or '', 100)
                                if not cached_company['address']:
                                    mapped_data['address'] = self.safe_trunc(row_dict.get('registered_address') or '', 500)
                            else:
                                mapped_data['contact'] = self.safe_trunc(row_dict.get('mobile_phone') or row_dict.get('other_phones') or '', 100)
                                mapped_data['address'] = self.safe_trunc(row_dict.get('registered_address') or '', 500)
                                
                            # 行政区划解析
                            p_name = row_dict.get('province')
                            c_name = row_dict.get('city')
                            d_name = row_dict.get('district')
                            
                            p_id = provinces_by_name.get(p_name).id if p_name and p_name in provinces_by_name else None
                            c_id = cities_by_name.get(c_name).id if c_name and c_name in cities_by_name else None
                            d_id = districts_by_name.get(d_name).id if d_name and d_name in districts_by_name else None
                            
                            if (not p_id or not c_id or not d_id) and credit_code and len(credit_code) == 18:
                                admin_code = credit_code[2:8] 
                                if not p_id:
                                    p_code = admin_code[:2]
                                    if p_code in provinces_by_code: p_id = provinces_by_code[p_code].id
                                if not c_id:
                                    c_code = admin_code[:4]
                                    if c_code in cities_by_code: c_id = cities_by_code[c_code].id
                                if not d_id:
                                    if admin_code in districts_by_code: d_id = districts_by_code[admin_code].id

                            mapped_data['province_id'] = p_id
                            mapped_data['city_id'] = c_id
                            mapped_data['district_id'] = d_id
                            
                            # --- 高速防撞车与保存逻辑 ---
                            if cached_company:
                                if mapped_data['credit_code'] and mapped_data['credit_code'] != cached_company['credit_code']:
                                    conflict = cache_by_code.get(mapped_data['credit_code'])
                                    if conflict and conflict['id'] != cached_company['id']:
                                        cached_company = conflict
                                
                                # 直接执行 SQL UPDATE 规避 ORM 实例化开销
                                Company.objects.filter(id=cached_company['id']).update(**mapped_data)
                                updated_count += 1
                                
                                # 动态更新内存索引
                                cached_company['credit_code'] = mapped_data['credit_code']
                                if 'contact' in mapped_data: cached_company['contact'] = mapped_data['contact']
                                if 'address' in mapped_data: cached_company['address'] = mapped_data['address']
                                
                                if mapped_data['credit_code']:
                                    cache_by_code[mapped_data['credit_code']] = cached_company
                                if mapped_data['name']:
                                    cache_by_name[mapped_data['name']] = cached_company
                            else:
                                conflict = None
                                if mapped_data['credit_code']:
                                    conflict = cache_by_code.get(mapped_data['credit_code'])
                                    
                                if conflict:
                                    Company.objects.filter(id=conflict['id']).update(**mapped_data)
                                    updated_count += 1
                                    
                                    conflict['credit_code'] = mapped_data['credit_code']
                                    if 'contact' in mapped_data: conflict['contact'] = mapped_data['contact']
                                    if 'address' in mapped_data: conflict['address'] = mapped_data['address']
                                    if mapped_data['name']: cache_by_name[mapped_data['name']] = conflict
                                else:
                                    new_comp = Company.objects.create(**mapped_data)
                                    created_count += 1
                                    
                                    new_dict = {
                                        'id': new_comp.id,
                                        'contact': new_comp.contact or '',
                                        'address': new_comp.address or '',
                                        'credit_code': new_comp.credit_code or ''
                                    }
                                    if new_comp.name: cache_by_name[new_comp.name] = new_dict
                                    if new_comp.credit_code: cache_by_code[new_comp.credit_code] = new_dict
                                    
                    # 每批次打印进度
                    processed = min(i + batch_size, total_rows)
                    self.stdout.write(f"已极速处理 {processed}/{total_rows} 条数据...")

            self.stdout.write(self.style.SUCCESS(f"=== 对冲结束 ==="))
            self.stdout.write(self.style.SUCCESS(f"【极速新建】公司: {created_count} 条"))
            self.stdout.write(self.style.SUCCESS(f"【极速覆盖】公司: {updated_count} 条"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"同步过程中发生错误: {str(e)}"))
            logger.error(f"sync_ent_std_maker error: {str(e)}", exc_info=True)
