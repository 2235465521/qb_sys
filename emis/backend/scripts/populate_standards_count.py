import os
import sys
import django
import time
import concurrent.futures

sys.path.insert(0, '.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from companies.models import Company
from companies.services import FederatedStandardService

def main():
    start_time = time.time()
    companies = list(Company.objects.all())
    total = len(companies)
    print(f"Start updating standards_count for {total} companies using FederatedStandardService...")

    updated_companies = []

    def process_company(company):
        try:
            summary = FederatedStandardService.get_company_standards_summary(company, scope='expanded')
            company.standards_count = summary.get('total_standards', 0)
        except Exception as e:
            print(f"Error for company {company.id}: {e}")
        return company

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(process_company, c) for c in companies]
        for future in concurrent.futures.as_completed(futures):
            updated_companies.append(future.result())

    if updated_companies:
        Company.objects.bulk_update(updated_companies, ['standards_count'], batch_size=1000)

    elapsed = time.time() - start_time
    print(f"Successfully updated all {total} companies' standards_count in {elapsed:.2f} seconds!")

if __name__ == '__main__':
    main()
