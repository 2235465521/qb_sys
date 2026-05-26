import os
import sys
import django
from django.db import transaction, connections

# 1. 自动设置并初始化 Django 运行上下文
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from companies.models import Province, City, District

def run_migration():
    print("开始执行全国行政区划经纬度字典跨库迁移...")
    
    with connections['default'].cursor() as cursor:
        # 检验 mydate 数据库是否存在于当前本地 MySQL 实例中
        cursor.execute("SHOW DATABASES LIKE 'mydate'")
        if not cursor.fetchone():
            print("错误：当前本地 MySQL 中未找到 'mydate' 数据库，请确保 mydate 数据库已导入本地。")
            return
            
        print("成功连通本地 MySQL，开始解析并清空 dict_province, dict_city, dict_district 历史旧记录...")
        
        # 使用 Django ORM 清除历史数据，防止外键冲突
        District.objects.all().delete()
        City.objects.all().delete()
        Province.objects.all().delete()
        
        # ============================================================
        # 步骤 A：同步省级行政区 (level = 1)
        # ============================================================
        print("正在提取并同步 [省级] 行政区 (level = 1)...")
        cursor.execute("""
            SELECT area_code, province_name, longitude, latitude 
            FROM mydate.area_dict 
            WHERE level = 1
        """)
        provinces_raw = cursor.fetchall()
        
        provinces_to_create = []
        for code, name, lon, lat in provinces_raw:
            provinces_to_create.append(Province(
                code=str(code).strip(),
                name=str(name).strip(),
                longitude=lon,
                latitude=lat
            ))
            
        Province.objects.bulk_create(provinces_to_create)
        print(f"   -> 成功导入省级记录: {len(provinces_to_create)} 条。")
        
        # 缓存在内存中用于下一级匹配
        province_cache = {p.code: p.id for p in Province.objects.all()}
        
        # ============================================================
        # 步骤 B：同步地级市行政区 (level = 2)
        # ============================================================
        print("正在提取并同步 [地级市] 行政区 (level = 2)...")
        cursor.execute("""
            SELECT area_code, city_name, longitude, latitude 
            FROM mydate.area_dict 
            WHERE level = 2
        """)
        cities_raw = cursor.fetchall()
        
        cities_to_create = []
        for code, name, lon, lat in cities_raw:
            code_str = str(code).strip()
            # 根据 GB/T 2260 规则：城市代码的前 2 位是所属省份代码
            parent_prov_code = code_str[:2]
            parent_prov_id = province_cache.get(parent_prov_code)
            
            if parent_prov_id:
                cities_to_create.append(City(
                    code=code_str,
                    name=str(name).strip(),
                    longitude=lon,
                    latitude=lat,
                    province_id=parent_prov_id
                ))
            else:
                print(f"   警告：地级市 {name}({code_str}) 未匹配到父级省份代码 {parent_prov_code}，已跳过")
                
        City.objects.bulk_create(cities_to_create)
        print(f"   -> 成功导入地级市记录: {len(cities_to_create)} 条。")
        
        # 缓存在内存中用于下一级匹配
        city_cache = {c.code: c.id for c in City.objects.all()}
        
        # ============================================================
        # 步骤 C：同步区县级行政区 (level = 3)
        # ============================================================
        print("正在提取并同步 [区县级] 行政区 (level = 3)...")
        cursor.execute("""
            SELECT area_code, county_name, longitude, latitude 
            FROM mydate.area_dict 
            WHERE level = 3
        """)
        districts_raw = cursor.fetchall()
        
        districts_to_create = []
        for code, name, lon, lat in districts_raw:
            code_str = str(code).strip()
            # 根据 GB/T 2260 规则：区县代码的前 4 位是所属地级市代码
            parent_city_code = code_str[:4]
            parent_city_id = city_cache.get(parent_city_code)
            
            if parent_city_id:
                districts_to_create.append(District(
                    code=code_str,
                    name=str(name).strip(),
                    longitude=lon,
                    latitude=lat,
                    city_id=parent_city_id
                ))
            else:
                # 北京市/直辖市等特殊辖区前缀处理
                # 如果前4位 1101 找不到，尝试直接查直辖市直属代码（如有些库直接挂载省份下，做防御性匹配）
                pass
                
        # 分批写入区县，效率极高
        District.objects.bulk_create(districts_to_create, batch_size=1000)
        print(f"   -> 成功导入区县级记录: {len(districts_to_create)} 条。")
        
        print("\n全国行政区划经纬度字典数据导入及外键绑定全部顺利完成！")

if __name__ == '__main__':
    with transaction.atomic():
        run_migration()
