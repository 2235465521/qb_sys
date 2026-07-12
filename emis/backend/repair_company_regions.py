import os
import sys
import django

# Add current directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from companies.models import Company, City, District

def run_repair():
    print("开始修复直辖市的『市辖区』和『县』对应关系...")
    
    # 1. 批量修复：有区县，但是城市为空的直辖市数据
    # 北京市
    bj_city = City.objects.filter(province__name='北京市', name='市辖区').first()
    if bj_city:
        updated = Company.objects.filter(province__name='北京市', city__isnull=True, district__isnull=False).update(city=bj_city)
        print(f"北京市：已补全 {updated} 家企业的『市辖区』关系。")
        
    # 天津市
    tj_city = City.objects.filter(province__name='天津市', name='市辖区').first()
    if tj_city:
        updated = Company.objects.filter(province__name='天津市', city__isnull=True, district__isnull=False).update(city=tj_city)
        print(f"天津市：已补全 {updated} 家企业的『市辖区』关系。")
        
    # 上海市
    sh_city = City.objects.filter(province__name='上海市', name='市辖区').first()
    if sh_city:
        updated = Company.objects.filter(province__name='上海市', city__isnull=True, district__isnull=False).update(city=sh_city)
        print(f"上海市：已补全 {updated} 家企业的『市辖区』关系。")
        
    # 重庆市
    cq_city_dist = City.objects.filter(province__name='重庆市', name='市辖区').first()
    cq_city_county = City.objects.filter(province__name='重庆市', name='县').first()
    if cq_city_dist:
        updated = Company.objects.filter(province__name='重庆市', city__isnull=True, district__name__contains='区').update(city=cq_city_dist)
        print(f"重庆市（区）：已补全 {updated} 家企业的『市辖区』关系。")
    if cq_city_county:
        updated = Company.objects.filter(province__name='重庆市', city__isnull=True, district__name__contains='县').update(city=cq_city_county)
        print(f"重庆市（县）：已补全 {updated} 家企业的『县』关系。")

    # 2. 深度匹配修复：城市和区县均为空，但省份为直辖市的企业，尝试通过『详细地址』或『企业名称』模糊匹配区县
    municipalities = ['北京市', '天津市', '上海市', '重庆市']
    districts = District.objects.filter(city__province__name__in=municipalities).select_related('city')
    
    companies_to_fix = Company.objects.filter(
        province__name__in=municipalities,
        city__isnull=True,
        district__isnull=True,
        is_deleted=False
    ).exclude(address='').exclude(address__isnull=True)
    
    to_update = []
    repaired_from_address = 0
    
    print("开始通过地址和企业名称模糊匹配区县...")
    for c in companies_to_fix:
        address = c.address or ''
        name = c.name or ''
        for d in districts:
            if d.city.province_id == c.province_id:
                d_short = d.name.replace('区', '').replace('县', '')
                if (d.name in address) or (d_short in address) or (d.name in name) or (d_short in name):
                    c.district = d
                    c.city = d.city
                    to_update.append(c)
                    repaired_from_address += 1
                    break
                    
    if to_update:
        Company.objects.bulk_update(to_update, fields=['city', 'district'], batch_size=1000)
        
    print(f"模糊匹配：已通过详细地址/企业名称补全了 {repaired_from_address} 家企业的区县与城市关系。")
    print("修复完成！")

if __name__ == '__main__':
    run_repair()
