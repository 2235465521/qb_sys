import sys
import os

sys.path.insert(0, '.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.db import connections
from companies.models import Company
from companies.views.standard_sync_views import CompanyFederatedStandardsAPIView

def debug_stsc():
    with connections['stsc_db'].cursor() as cursor:
        cursor.execute("SET NAMES utf8mb4;")
        # Find a company with high count
        query = """
            SELECT u.unit_name, COUNT(DISTINCT v.std_id), COUNT(v.std_id), COUNT(DISTINCT v.id), COUNT(v.id)
            FROM mydate.unit_dict u
            JOIN mydate.std_unit_relation r ON u.unit_id = r.unit_id
            JOIN mydate.view_std_full v ON r.base_id = v.id
            GROUP BY u.unit_name
            ORDER BY COUNT(DISTINCT v.std_id) DESC
            LIMIT 5
        """
        cursor.execute(query)
        for row in cursor.fetchall():
            print(f"Name: {row[0]}, COUNT(DISTINCT std_id): {row[1]}, COUNT(std_id): {row[2]}, COUNT(DISTINCT id): {row[3]}, COUNT(id): {row[4]}")

debug_stsc()
