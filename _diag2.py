import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','erpproject.settings')
django.setup()
from tenants.models import TenantDatabase
from tenants.routers import add_tenant_database, TenantDatabaseContext
from django.db.models import Min, Max, Count, Avg
from erp.models.crm import Lead
db = add_tenant_database(TenantDatabase.objects.get(name='erp_tenant_797cca0a123242c9'))
with TenantDatabaseContext(db):
    leads = Lead.objects.using(db).all()
    print('=== Lead status counts ===')
    for r in leads.values('status').annotate(n=Count('id')):
        print(r)
    print('=== Leads by status (won/lost focus) ===')
    for st in ['won','lost','open','qualified','new','contacted','converted','closed_won','closed_lost']:
        qs = leads.filter(status=st).annotate(act_n=Count('activities'))
        n = qs.count()
        if not n: continue
        avg_act = qs.aggregate(a=Avg('act_n'))['a']
        rows = qs.exclude(last_contact_date__isnull=True).values_list('created_at','last_contact_date')
        diffs = [(lc - (ca.date() if hasattr(ca,'date') else ca)).days for ca,lc in rows]
        mean_diff = sum(diffs)/len(diffs) if diffs else None
        print(f'{st}: n={n} mean_activities={avg_act} mean_days_lc-created={mean_diff} (over {len(diffs)})')
