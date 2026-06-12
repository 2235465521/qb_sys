import os
import sys
import django

# Set up Django environment
sys.path.insert(0, '.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from companies.models import Company
from django.core.cache import cache

def main():
    # 查找垃圾公司数据（名称为“有限公司”或“分公司”，或对应的信用代码）
    wrong_companies = Company.objects.filter(
        name__in=['有限公司', '分公司']
    ) | Company.objects.filter(
        credit_code__in=['TEMP_43F50120528E44', '91440904MA5874CA0F']
    )
    
    count = wrong_companies.count()
    if count == 0:
        print("No matching wrong companies found in the database.")
        # 依然清除一下缓存以防万一
        try:
            cache.clear()
            print("Django cache cleared successfully!")
        except Exception:
            pass
        return

    print(f"Found {count} wrong companies to delete:")
    for c in wrong_companies:
        print(f" - ID: {c.id}, Name: {c.name}, Credit Code: {c.credit_code}")
        
    # 物理删除垃圾数据
    deleted_count, _ = wrong_companies.delete()
    print(f"Deleted {deleted_count} records successfully!")

    # 清除 Django/Redis 缓存
    try:
        cache.clear()
        print("Django cache cleared successfully!")
    except Exception as e:
        print(f"Error clearing cache: {e}")

if __name__ == '__main__':
    main()
