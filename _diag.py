import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','erpproject.settings')
django.setup()
from tenants.models import TenantDatabase
from tenants.routers import add_tenant_database, TenantDatabaseContext
from django.db.models import Min, Max, Count, Avg
from erp.models.hr import Employee, Attendance, Payroll
from erp.models.crm import Lead
db = add_tenant_database(TenantDatabase.objects.get(name='erp_tenant_797cca0a123242c9'))
with TenantDatabaseContext(db):
    emps = Employee.objects.using(db).filter(employee_id__startswith='IBM-')
    print('=== Employees IBM- by status ===')
    for s in emps.values('employment_status').annotate(n=Count('id')):
        print(s)
    print('=== Attendance by status ===')
    for st in ['active','terminated','resigned']:
        ids = list(emps.filter(employment_status=st).values_list('id', flat=True))
        if not ids:
            print(st, 'no emps'); continue
        agg = Attendance.objects.using(db).filter(employee_id__in=ids).aggregate(mn=Min('date'), mx=Max('date'), n=Count('id'))
        nn = agg['n']
        print(f'{st}: emps={len(ids)} att_n={nn} mean={nn/len(ids):.1f} min={agg["mn"]} max={agg["mx"]}')
    print('=== Payroll by status ===')
    for st in ['active','terminated','resigned']:
        ids = list(emps.filter(employment_status=st).values_list('id', flat=True))
        if not ids:
            print(st,'no emps'); continue
        agg = Payroll.objects.using(db).filter(employee_id__in=ids).aggregate(mn=Min('period_end'), mx=Max('period_end'), n=Count('id'))
        nn = agg['n']
        print(f'{st}: emps={len(ids)} pay_n={nn} mean={nn/len(ids):.2f} min={agg["mn"]} max={agg["mx"]}')
    print('=== Leads by status ===')
    leads = Lead.objects.using(db).all()
    for st in ['won','lost','open','qualified','new','contacted']:
        qs = leads.filter(status=st)
        n = qs.count()
        if not n: continue
        avg_act = qs.aggregate(a=Avg('activity_count'))['a']
        rows = qs.exclude(last_contact_date__isnull=True).values_list('created_at','last_contact_date')
        diffs = [(lc - (ca.date() if hasattr(ca,'date') else ca)).days for ca,lc in rows]
        mean_diff = sum(diffs)/len(diffs) if diffs else None
        print(f'{st}: n={n} mean_activity={avg_act} mean_days={mean_diff} (over {len(diffs)})')
