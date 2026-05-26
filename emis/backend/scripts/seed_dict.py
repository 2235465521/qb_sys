import os
import sys
import django

# 设置 Django 环境
sys.path.append(r'e:\企标记录\emis\backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from companies.models import Province, City, District

def seed_dict():
    print("正在初始化行政区划数据...")
    
    data = [
        {
            "name": "北京市", "code": "110000",
            "cities": [
                {"name": "北京市", "code": "110100", "districts": [
                    {"name": "东城区", "code": "110101"},
                    {"name": "西城区", "code": "110102"},
                    {"name": "朝阳区", "code": "110105"}
                ]}
            ]
        },
        {
            "name": "广东省", "code": "440000",
            "cities": [
                {"name": "广州市", "code": "440100", "districts": [
                    {"name": "越秀区", "code": "440104"},
                    {"name": "天河区", "code": "440106"}
                ]},
                {"name": "深圳市", "code": "440300", "districts": [
                    {"name": "福田区", "code": "440304"},
                    {"name": "南山区", "code": "440305"}
                ]}
            ]
        }
    ]

    for p_data in data:
        p, _ = Province.objects.get_or_create(code=p_data['code'], defaults={'name': p_data['name']})
        for c_data in p_data['cities']:
            c, _ = City.objects.get_or_create(code=c_data['code'], province=p, defaults={'name': c_data['name']})
            for d_data in c_data['districts']:
                District.objects.get_or_create(code=d_data['code'], city=c, defaults={'name': d_data['name']})
    
    print("✅ 数据初始化完成")

if __name__ == "__main__":
    seed_dict()
