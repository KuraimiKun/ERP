"""
ERP Admin – HR models
"""

from django.contrib import admin
from erp.models import (
    Employee, EmployeeDocument, LeaveType, LeaveRequest, Attendance, Payroll,
)


class EmployeeDocumentInline(admin.TabularInline):
    model = EmployeeDocument
    extra = 0


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['employee_id', 'full_name', 'department', 'job_title', 'employment_status', 'employment_type']
    list_filter = ['company', 'department', 'employment_status', 'employment_type']
    search_fields = ['employee_id', 'first_name', 'last_name', 'email']
    inlines = [EmployeeDocumentInline]

    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'employee_id', 'company', 'branch')
        }),
        ('Personal Details', {
            'fields': ('first_name', 'last_name', 'first_name_ar', 'last_name_ar', 'gender', 'date_of_birth', 'nationality')
        }),
        ('Contact', {
            'fields': ('email', 'phone', 'address', 'city', 'country')
        }),
        ('Emergency Contact', {
            'fields': ('emergency_contact_name', 'emergency_contact_phone')
        }),
        ('Documents', {
            'fields': ('national_id', 'passport_number', 'passport_expiry', 'photo')
        }),
        ('Employment', {
            'fields': ('department', 'job_title', 'reports_to', 'employment_type', 'employment_status', 'hire_date', 'termination_date')
        }),
        ('Compensation', {
            'fields': ('basic_salary', 'currency', 'bank_name', 'bank_account', 'iban')
        }),
        ('Leave Balance', {
            'fields': ('annual_leave_balance', 'sick_leave_balance')
        }),
    )


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'days_allowed', 'is_paid', 'is_active']
    list_filter = ['is_paid', 'is_active']
    search_fields = ['name', 'code']


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ['employee', 'leave_type', 'start_date', 'end_date', 'days_requested', 'status']
    list_filter = ['status', 'leave_type', 'start_date']
    search_fields = ['employee__first_name', 'employee__last_name']
    date_hierarchy = 'start_date'


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['employee', 'date', 'check_in', 'check_out', 'hours_worked', 'is_present', 'is_late']
    list_filter = ['is_present', 'is_late', 'date']
    search_fields = ['employee__first_name', 'employee__last_name']
    date_hierarchy = 'date'


@admin.register(Payroll)
class PayrollAdmin(admin.ModelAdmin):
    list_display = ['employee', 'period_start', 'period_end', 'gross_salary', 'net_salary', 'status']
    list_filter = ['status', 'period_start']
    search_fields = ['employee__first_name', 'employee__last_name']
