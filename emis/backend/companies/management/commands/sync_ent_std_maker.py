import logging
from django.core.management.base import BaseCommand
from django.db import transaction, connections
from companies.models import Company, Province, City, District
from django.utils import timezone

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
        # 按分号、逗号、空格、竖线等常见分隔符拆分
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
        self.stdout.write(self.style.SUCCESS("=== 开始同步 compare_conp.ent_std_maker 数据 ==="))

        # 1. 预加载所有行政区划字典表数据到内存，避免 N+1 查询
        provinces_by_name = {p.name: p for p in Province.objects.all()}
        cities_by_name = {c.name: c for c in City.objects.all()}
        districts_by_name = {d.name: d for d in District.objects.all()}
        
        provinces_by_code = {p.code: p for p in Province.objects.all()}
        cities_by_code = {c.code: c for c in City.objects.all()}
        districts_by_code = {d.code: d for d in District.objects.all()}

        self.stdout.write(self.style.SUCCESS("字典表加载完毕。开始读取源数据库..."))

        # 2. 读取 compare_conp 数据
        created_count = 0
        updated_count = 0
        error_count = 0

        try:
            with connections['compare_conp'].cursor() as cursor:
                cursor.execute("SELECT * FROM ent_std_maker")
                columns = [col[0] for col in cursor.description]
                
                rows = cursor.fetchall()
                total_rows = len(rows)
                self.stdout.write(self.style.SUCCESS(f"源表共计找到 {total_rows} 条数据。正在处理..."))
                
                # 开始在默认主数据库中开启事务批量处理
                with transaction.atomic():
                    for idx, row in enumerate(rows):
                        row_dict = dict(zip(columns, row))
                        
                        company_name = (row_dict.get('company_name') or '').strip()
                        credit_code = (row_dict.get('unified_social_credit_code') or '').strip()
                        
                        if not company_name and not credit_code:
                            continue
                        
                        # 第一优先级：按名称查；第二优先级：按信用代码查
                        company = None
                        if company_name:
                            company = Company.objects.filter(name=company_name).first()
                        if not company and credit_code:
                            company = Company.objects.filter(credit_code=credit_code).first()
                        
                        # 数据映射封装
                        mapped_data = {
                            'name': self.safe_trunc(company_name, 200),
                            'credit_code': self.safe_trunc(credit_code, 25),
                            'legal_person': self.safe_trunc(row_dict.get('legal_representative') or '', 50),
                            'established_date': row_dict.get('establishment_date') if row_dict.get('establishment_date') else None,
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
                            
                            # 新增 5 个字段
                            'website_url': self.safe_trunc(row_dict.get('website_url') or '', 500),
                            'mailing_address': self.safe_trunc(row_dict.get('mailing_address') or '', 500),
                            'mailing_address_zip': self.safe_trunc(row_dict.get('mailing_address_zip') or '', 20),
                            'business_scope': row_dict.get('business_scope') or '',
                            'registration_status': self.safe_trunc(row_dict.get('registration_status') or '', 100),
                        }
                        
                        # 兼容处理 contact 字段 (界面上的“联系方式”)
                        if not company or not company.contact:
                            mapped_data['contact'] = self.safe_trunc(row_dict.get('mobile_phone') or row_dict.get('other_phones') or '', 100)
                        
                        # 兼容处理 address 字段 (界面上的“详细地址”)
                        if not company or not company.address:
                            mapped_data['address'] = self.safe_trunc(row_dict.get('registered_address') or '', 500)
                            
                        # === 行政区划解析逻辑 ===
                        p_name = row_dict.get('province')
                        c_name = row_dict.get('city')
                        d_name = row_dict.get('district')
                        
                        p_id = provinces_by_name.get(p_name).id if p_name and p_name in provinces_by_name else None
                        c_id = cities_by_name.get(c_name).id if c_name and c_name in cities_by_name else None
                        d_id = districts_by_name.get(d_name).id if d_name and d_name in districts_by_name else None
                        
                        # 核心解析补充：如果没有地址信息，且存在统一社会信用代码
                        if (not p_id or not c_id or not d_id) and credit_code and len(credit_code) == 18:
                            # 根据统一社会信用代码标准，第 3-8 位是行政区划代码
                            admin_code = credit_code[2:8] 
                            
                            if not p_id:
                                p_code = admin_code[:2]
                                p_obj = provinces_by_code.get(p_code)
                                if p_obj: p_id = p_obj.id
                                
                            if not c_id:
                                c_code = admin_code[:4]
                                c_obj = cities_by_code.get(c_code)
                                if c_obj: c_id = c_obj.id
                                    
                            if not d_id:
                                d_obj = districts_by_code.get(admin_code)
                                if d_obj: d_id = d_obj.id

                        mapped_data['province_id'] = p_id
                        mapped_data['city_id'] = c_id
                        mapped_data['district_id'] = d_id
                        
                        # 兼容处理脏时间数据（如 "-"），防止 django DateField 报错
                        est_date = mapped_data.get('established_date')
                        if isinstance(est_date, str):
                            est_date = est_date.strip()
                            if not est_date or est_date == '-' or len(est_date) < 10:
                                mapped_data['established_date'] = None
                            else:
                                mapped_data['established_date'] = est_date[:10]
                        
                        if company:
                            # 执行强制覆盖更新 (Update)
                            for key, val in mapped_data.items():
                                if val is not None:
                                    setattr(company, key, val)
                            company.save()
                            updated_count += 1
                        else:
                            # 没找到则新增 (Insert)
                            Company.objects.create(**mapped_data)
                            created_count += 1
                        
                        # 打印进度
                        if (idx + 1) % 500 == 0:
                            self.stdout.write(f"已处理 {idx + 1}/{total_rows} 条数据...")

            self.stdout.write(self.style.SUCCESS(f"=== 对冲结束 ==="))
            self.stdout.write(self.style.SUCCESS(f"总计找到 {total_rows} 条源数据"))
            self.stdout.write(self.style.SUCCESS(f"【成功新建】公司: {created_count} 条"))
            self.stdout.write(self.style.SUCCESS(f"【成功覆盖】公司: {updated_count} 条"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"同步过程中发生错误: {str(e)}"))
            logger.error(f"sync_ent_std_maker error: {str(e)}", exc_info=True)
