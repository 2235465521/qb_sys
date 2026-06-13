import sys
import os

sys.path.insert(0, '.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.db import connections
from companies.models import Company
from companies.views.standard_sync_views import CompanyFederatedStandardsAPIView

def check():
    companies = list(Company.objects.all()[:100])
    names = [c.name.strip() for c in companies if c.name.strip()]
    if not names:
        return
        
    federated_counts = {}
    with connections['stsc_db'].cursor() as cursor:
        cursor.execute("SET NAMES utf8mb4;")
        placeholders = ', '.join(['%s'] * len(names))
        query = f"""
            SELECT u.unit_name, COUNT(DISTINCT v.std_id)
            FROM mydate.unit_dict u
            JOIN mydate.std_unit_relation r ON u.unit_id = r.unit_id
            JOIN mydate.view_std_full v ON r.base_id = v.id
            WHERE u.unit_name IN ({placeholders})
            GROUP BY u.unit_name
        """
        cursor.execute(query, names)
        for name, count in cursor.fetchall():
            federated_counts[name] = count
            
    view = CompanyFederatedStandardsAPIView()
    for company in companies:
        name = company.name.strip()
        if not name:
            continue
        db_count = federated_counts.get(name, 0)
        
        # emulate view
        try:
            with connections['stsc_db'].cursor() as cursor:
                cursor.execute("SET NAMES utf8mb4;")
                query = """
                    SELECT 
                        v.std_id, 
                        v.std_chinesename, 
                        v.std_type, 
                        v.release_date, 
                        v.implement_date, 
                        v.ex_state as status, 
                        h.draft_unit as drafter,
                        f.file_path,
                        r.rank_order
                    FROM mydate.unit_dict u
                    JOIN mydate.std_unit_relation r ON u.unit_id = r.unit_id
                    JOIN mydate.view_std_full v ON r.base_id = v.id
                    LEFT JOIN mydate.std_extend_h h ON v.id = h.base_id
                    LEFT JOIN mydate.std_filepath f ON v.id = f.base_id
                    WHERE u.unit_name = %s
                    ORDER BY v.release_date DESC
                """
                cursor.execute(query, [name])
                columns = [col[0] for col in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception:
            results = []
            
        formatted_results = []
        for row in results:
            drafters_raw = row.get('drafter', '')
            drafters_list = view.clean_draft_units(drafters_raw)
            formatted_results.append({
                'standard_no': row.get('std_id', ''),
            })
            
        unique_results = []
        seen_stds = set()
        for item in formatted_results:
            if item['standard_no'] not in seen_stds:
                seen_stds.add(item['standard_no'])
                unique_results.append(item)
                
        api_count = len(unique_results)
        
        if db_count != api_count:
            print(f"Mismatch for {name}: db_count={db_count}, api_count={api_count}")

check()
