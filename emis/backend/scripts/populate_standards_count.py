import os
import sys
import django

# Set up Django environment
sys.path.insert(0, '.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connections
from django.db.models import Count
from companies.models import Company
from standards.models import Standard
import time

def main():
    start_time = time.time()
    companies = list(Company.objects.all())
    total = len(companies)
    print(f"Start updating standards_count for {total} companies using high-speed batching...")

    # 1. 批量统计本地标准数
    print("Step 1: Counting local standards in batch...")
    local_counts = {
        item['company_id']: item['count']
        for item in Standard.objects.filter(type__in=['enterprise', 'group'])
                                    .values('company_id')
                                    .annotate(count=Count('id'))
    }

    # 2. 批量查询外部联邦库标准数 (每 1000 个企业一批，单次 SQL 批量查回)
    print("Step 2: Querying federated database in batches of 1000...")
    federated_counts = {}
    names = list(set(c.name.strip() for c in companies if c.name.strip()))
    
    batch_size = 1000
    for i in range(0, len(names), batch_size):
        batch_names = names[i:i+batch_size]
        if not batch_names:
            continue
        try:
            with connections['stsc_db'].cursor() as cursor:
                cursor.execute("SET NAMES utf8mb4;")
                placeholders = ', '.join(['%s'] * len(batch_names))
                query = f"""
                    SELECT u.unit_name, COUNT(DISTINCT v.std_id)
                    FROM unit_dict u
                    JOIN std_unit_relation r ON u.unit_id = r.unit_id
                    JOIN view_std_full v ON r.base_id = v.id
                    WHERE u.unit_name IN ({placeholders})
                    GROUP BY u.unit_name
                """
                cursor.execute(query, batch_names)
                for name, count in cursor.fetchall():
                    federated_counts[name] = count
        except Exception as e:
            print(f"Error querying stsc_db batch: {e}")

    # 3. 内存中合并数据，并执行 bulk_update 批量写入本地库
    print("Step 3: Merging data and writing to database...")
    updated_companies = []
    for company in companies:
        name = company.name.strip()
        l_count = local_counts.get(company.id, 0)
        f_count = federated_counts.get(name, 0)
        company.standards_count = l_count + f_count
        updated_companies.append(company)

    if updated_companies:
        Company.objects.bulk_update(updated_companies, ['standards_count'], batch_size=1000)

    elapsed = time.time() - start_time
    print(f"Successfully updated all {total} companies' standards_count in {elapsed:.2f} seconds!")

if __name__ == '__main__':
    main()
