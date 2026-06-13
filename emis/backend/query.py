import sys
sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.db import connections

cursor=connections["stsc_db"].cursor()
cursor.execute("SELECT COUNT(v.std_id), COUNT(DISTINCT v.std_id) FROM mydate.unit_dict u JOIN mydate.std_unit_relation r ON u.unit_id = r.unit_id JOIN mydate.view_std_full v ON r.base_id = v.id WHERE u.unit_name='中国互联网络信息中心'")
print(cursor.fetchone())
