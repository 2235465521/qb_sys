import os
import sys
import django

# 设置 Django 环境
sys.path.append(r'e:\企标记录\emis\backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from companies.models import Company, Province, City, District
from standards.models import Standard

def seed_data():
    print("正在初始化企业与企业标准数据...")

    # 获取行政区划
    beijing_p = Province.objects.filter(name="北京市").first()
    beijing_c = City.objects.filter(name="北京市", province=beijing_p).first()
    chaoyang_d = District.objects.filter(name="朝阳区", city=beijing_c).first()

    guangdong_p = Province.objects.filter(name="广东省").first()
    shenzhen_c = City.objects.filter(name="深圳市", province=guangdong_p).first()
    futian_d = District.objects.filter(name="福田区", city=shenzhen_c).first()
    nanshan_d = District.objects.filter(name="南山区", city=shenzhen_c).first()

    guangzhou_c = City.objects.filter(name="广州市", province=guangdong_p).first()
    tianhe_d = District.objects.filter(name="天河区", city=guangzhou_c).first()

    # 清除旧数据，确保重新生成
    Company.objects.all().delete()
    Standard.objects.all().delete()

    # 1. 腾讯科技(深圳)有限公司
    tencent, _ = Company.objects.get_or_create(
        credit_code="91440300708461136T",
        defaults={
            "name": "腾讯科技(深圳)有限公司",
            "legal_person": "马化腾",
            "province": guangdong_p,
            "city": shenzhen_c,
            "district": nanshan_d,
            "latitude": 22.5273,
            "longitude": 113.9348,
            "contact": "0755-86013388",
            "address": "深圳市南山区深南大道10000号",
            "status": "active"
        }
    )

    # 给腾讯创建标准
    Standard.objects.create(
        standard_no="Q/TX 001-2026",
        clean_id="Q/TX001-2026",
        type="enterprise",
        title="云计算多活数据库分布式架构规范",
        company=tencent,
        ics="35.240.50",
        ccs="L70",
        status="active"
    )

    Standard.objects.create(
        standard_no="Q/TX 002-2026",
        clean_id="Q/TX002-2026",
        type="enterprise",
        title="社交网络平台内容分类与推荐系统安全规范",
        company=tencent,
        ics="35.020",
        ccs="L01",
        status="active"
    )

    # 2. 百度在线网络技术(北京)有限公司
    baidu, _ = Company.objects.get_or_create(
        credit_code="9111000071788347XQ",
        defaults={
            "name": "百度在线网络技术(北京)有限公司",
            "legal_person": "李彦宏",
            "province": beijing_p,
            "city": beijing_c,
            "district": chaoyang_d,
            "latitude": 39.9042,
            "longitude": 116.4074,
            "contact": "010-59928888",
            "address": "北京市朝阳区百度大厦",
            "status": "active"
        }
    )

    # 给百度创建标准
    Standard.objects.create(
        standard_no="新Q/BD 005-2026",
        clean_id="新Q/BD005-2026",
        type="enterprise",
        title="自动驾驶高精地图数据格式技术规范",
        company=baidu,
        ics="43.020",
        ccs="T40",
        status="active"
    )

    Standard.objects.create(
        standard_no="Q/BD 009-2026",
        clean_id="Q/BD009-2026",
        type="enterprise",
        title="工业级智能搜索自然语言处理规范",
        company=baidu,
        ics="35.240.50",
        ccs="L70",
        status="active"
    )

    # 3. 阿里巴巴(广州)软件服务有限公司
    alibaba, _ = Company.objects.get_or_create(
        credit_code="91440101708892189U",
        defaults={
            "name": "阿里巴巴(广州)软件服务有限公司",
            "legal_person": "张勇",
            "province": guangdong_p,
            "city": guangzhou_c,
            "district": tianhe_d,
            "latitude": 23.1291,
            "longitude": 113.3960,
            "contact": "020-83968888",
            "address": "广州市天河区高唐路阿里巴巴大厦",
            "status": "active"
        }
    )

    # 给阿里创建标准
    Standard.objects.create(
        standard_no="Q/AL 012-2026",
        clean_id="Q/AL012-2026",
        type="enterprise",
        title="移动电商平台支付接口协议及安全准则",
        company=alibaba,
        ics="35.240.50",
        ccs="L01",
        status="active"
    )

    print("✅ 企业及标准数据初始化完成")

if __name__ == "__main__":
    seed_data()
