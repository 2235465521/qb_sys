import os
import sys
import django
import concurrent.futures

# Set up Django environment
sys.path.insert(0, '.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connections, transaction
from companies.models import Company

def fetch_and_update_company(company):
    # 1. 计算本地标准数量
    local_count = company.standards.filter(type__in=['enterprise', 'group']).count()

    # 2. 查询外部联邦库标准数量
    federated_count = 0
    search_name = company.name.strip()
    if search_name:
        try:
            with connections['stsc_db'].cursor() as cursor:
                cursor.execute("SET NAMES utf8mb4;")
                query = """
                    SELECT COUNT(DISTINCT v.std_id)
                    FROM unit_dict u
                    JOIN std_unit_relation r ON u.unit_id = r.unit_id
                    JOIN view_std_full v ON r.base_id = v.id
                    WHERE u.unit_name = %s
                """
                cursor.execute(query, [search_name])
                row = cursor.fetchone()
                if row:
                    federated_count = row[0]
        except Exception as e:
            print(f"Error querying stsc_db for {company.name}: {e}")

    total_count = local_count + federated_count
    
    # 3. 更新数据库
    company.standards_count = total_count
    company.save(update_fields=['standards_count'])
    return company.name, total_count

def main():
    companies = list(Company.objects.all())
    total = len(companies)
    print(f"Start updating standards_count for {total} companies...")

    completed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        futures = {executor.submit(fetch_and_update_company, c): c for c in companies}
        for future in concurrent.futures.as_completed(futures):
            try:
                name, count = future.result()
                completed += 1
                if completed % 50 == 0 or completed == total:
                    print(f"Progress: {completed}/{total} updated. Latest: {name} ({count})")
            except Exception as e:
                print(f"Thread failed: {e}")

    print("All companies updated successfully!")

if __name__ == '__main__':
    main()
