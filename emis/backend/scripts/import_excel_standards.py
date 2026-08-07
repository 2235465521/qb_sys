import os
import sys
import pandas as pd
from django.db import transaction

# 1. 自动设置并初始化 Django 运行环境
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from companies.models import Company, Province, City, District
from standards.models import Standard
from standards.services import generate_clean_id  # 🔴 引入系统业务清洗规则

def run_import(excel_path):
    print(f"开始读取并分析企标 Excel 文件: {excel_path}")
    
    if not os.path.exists(excel_path):
        print(f"错误：未找到 Excel 文件 {excel_path}，请检查路径是否正确。")
        return
        
    # 读取 Excel
    try:
        df = pd.read_excel(excel_path)
        print(f"成功加载 Excel，数据共包含 {len(df)} 行记录。")
    except Exception as e:
        print(f"错误：加载 Excel 失败: {str(e)}")
        return

    # 自动获取当前日期，符合 pdf_upload_path 物理分层规范
    from django.utils import timezone
    today_str = timezone.now().strftime("%Y/%m/%d")
    
    standards_to_create = []
    companies_created_count = 0
    companies_updated_count = 0
    skipped_duplicates_count = 0
    
    # 开启数据库原子事务，若中间出错全自动回滚，确保数据一致性
    with transaction.atomic():
        for idx, row in df.iterrows():
            credit_code = str(row.get('统一社会信用代码', '')).strip()
            company_name = str(row.get('起草单位/企业名称', '')).strip()
            
            # 过滤无效空行
            if not credit_code or credit_code == 'nan' or not company_name or company_name == 'nan':
                continue
                
            # --- 步骤 A: 级联匹配省市区外键 ---
            province = None
            city = None
            district = None
            
            geo_str = str(row.get('行政区划', '')).strip()
            if geo_str and geo_str != 'nan' and '-' in geo_str:
                geo_parts = geo_str.split('-')
                if len(geo_parts) >= 1:
                    province = Province.objects.filter(name__icontains=geo_parts[0].replace("省", "")).first()
                
                # 🔴 核心对齐：处理直辖市两级行政区划 (如北京市-海淀区)
                if len(geo_parts) == 2 and province:
                    city = City.objects.filter(name__in=["市辖区", province.name.replace("市", "")], province=province).first()
                    if not city:
                        city = City.objects.filter(province=province).first()
                    if city:
                        district = District.objects.filter(name__icontains=geo_parts[1], city=city).first()
                else:
                    # 标准三级区划结构 (如安徽省-安庆市-桐城市)
                    if len(geo_parts) >= 2 and province:
                        city = City.objects.filter(name__icontains=geo_parts[1].replace("市", ""), province=province).first()
                    if len(geo_parts) >= 3 and city:
                        district = District.objects.filter(name__icontains=geo_parts[2], city=city).first()
            
            # --- 步骤 B: 根据大字典自动获取 LBS 中心经纬度，进行零成本落位 ---
            company_lat = None
            company_lng = None
            if district and district.latitude and district.longitude:
                company_lat = district.latitude
                company_lng = district.longitude
            elif city and city.latitude and city.longitude:
                company_lat = city.latitude
                company_lng = city.longitude

            # --- 步骤 C: 新建或安全更新企业信息（按照信用代码去重） ---
            legal_person = str(row.get('法定代表人', '')).strip()
            if not legal_person or legal_person == 'nan':
                legal_person = ''
                
            address = str(row.get('注册地址', '')).strip()
            if not address or address == 'nan':
                address = ''

            company, created = Company.objects.get_or_create(
                credit_code=credit_code,
                defaults={
                    'name': company_name,
                    'legal_person': legal_person,
                    'address': address,
                    'province': province,
                    'city': city,
                    'district': district,
                    'latitude': company_lat,
                    'longitude': company_lng,
                    'status': 'active'
                }
            )
            
            if created:
                companies_created_count += 1
            else:
                # 仅当已存在企业的经纬度或行政区划为空时，才更新为大字典中心点，绝不覆盖人工校准数据
                updated = False
                if not company.latitude and company_lat:
                    company.latitude = company_lat
                    company.longitude = company_lng
                    updated = True
                # 🔴 核心业务升级：如果之前导入的直辖市企业缺少 district 绑定，我们在此处为它精准补齐绑定！
                if not company.district and district:
                    company.province = province
                    company.city = city
                    company.district = district
                    updated = True
                if updated:
                    company.save()
                    companies_updated_count += 1
            
            # --- 步骤 D: 拼装标准记录并建立外键绑定 ---
            standard_no = str(row.get('标准编号', '')).strip()
            standard_title = str(row.get('标准名称', '')).strip()
            if standard_title.startswith('《') and standard_title.endswith('》'):
                standard_title = standard_title[1:-1].strip()
            
            if not standard_no or standard_no == 'nan':
                continue
                
            # 🔴 使用系统核心业务清洗逻辑生成唯一的 clean_id
            clean_id = generate_clean_id(standard_no)
            
            # 强力查重：若系统中已有此 clean_id 的标准，跳过导入，防止主键冲突
            if Standard.objects.filter(clean_id=clean_id).exists():
                skipped_duplicates_count += 1
                continue
                
            # 解析发布日期（优先查找明确的发布日期列，不将平台“公开时间”当作标准发布时间）
            publish_date = None
            pub_date_val = row.get('发布日期') if '发布日期' in row else row.get('发布时间')
            if pd.notnull(pub_date_val):
                try:
                    publish_date = pd.to_datetime(pub_date_val).date()
                except:
                    pass

            
            # 映射标准状态
            status_str = str(row.get('标准状态', ''))
            standard_status = 'active'
            if '废止' in status_str:
                standard_status = 'deprecated'
            elif '草案' in status_str:
                standard_status = 'draft'

            # 绑定 PDF 物理存储相对路径，直接映射到磁盘整合目录，不再使用违背物理分布的 pdfs/ 前缀
            pdf_filename = str(row.get('PDF文件名', '')).strip()
            pdf_db_path = f"整合/{pdf_filename}" if pdf_filename and pdf_filename != 'nan' else ''
            
            new_standard = Standard(
                standard_no=standard_no,
                clean_id=clean_id,
                type='enterprise', # 企标为企业标准类型
                title=standard_title if standard_title != 'nan' else '',
                company=company,   # 🔴 外键完美对齐企业！
                pdf_file=pdf_db_path,
                publish_date=publish_date,
                status=standard_status
            )
            standards_to_create.append(new_standard)
            
        # --- 步骤 E: bulk_create 极速批量写入 ---
        if standards_to_create:
            created_objs = Standard.objects.bulk_create(standards_to_create, batch_size=1000)
            print("\n数据导入圆满成功！")
            print(f"  -> 成功创建新企业并建档: {companies_created_count} 家")
            print(f"  -> 成功补充更新旧企业定位: {companies_updated_count} 家")
            print(f"  -> 成功导入企标标准资产: {len(created_objs)} 条")
            print(f"  -> 过滤重复已存在企标: {skipped_duplicates_count} 条")
        else:
            print("\n无新数据需要导入（所有标准已存在或文件为空）。")

if __name__ == '__main__':
    excel_file = r"E:\企标记录\企标文件集合\企业标准下载记录.xlsx"
    run_import(excel_file)
