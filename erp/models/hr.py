from django.utils.translation import gettext_lazy as _
"""
Human Resources (HR) models for the ERP system.
"""

import uuid
import secrets

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal
from .base import ERPBaseModel, TimeStampedModel


class Employee(ERPBaseModel):
    """Employee records."""
    class EmploymentStatus(models.TextChoices):
        ACTIVE = 'active', 'Active'
        ON_LEAVE = 'on_leave', 'On Leave'
        SUSPENDED = 'suspended', 'Suspended'
        TERMINATED = 'terminated', 'Terminated'
        RESIGNED = 'resigned', 'Resigned'

    class EmploymentType(models.TextChoices):
        FULL_TIME = 'full_time', 'Full Time'
        PART_TIME = 'part_time', 'Part Time'
        CONTRACT = 'contract', 'Contract'
        INTERN = 'intern', 'Intern'
        FREELANCE = 'freelance', 'Freelance'

    class Gender(models.TextChoices):
        MALE = 'male', 'Male'
        FEMALE = 'female', 'Female'

    # Link to user account (optional)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employee_profile'
    )
    
    # Employee ID
    employee_id = models.CharField(max_length=20)
    
    # Personal Information
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    first_name_ar = models.CharField(max_length=100, blank=True)
    last_name_ar = models.CharField(max_length=100, blank=True)
    gender = models.CharField(max_length=10, choices=Gender.choices)
    date_of_birth = models.DateField()
    nationality = models.CharField(max_length=100)
    
    # Contact
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)
    
    # Address
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    
    # Documents
    national_id = models.CharField(max_length=50, blank=True)
    passport_number = models.CharField(max_length=50, blank=True)
    passport_expiry = models.DateField(null=True, blank=True)
    photo = models.ImageField(upload_to='employees/photos/', null=True, blank=True)
    
    # Employment Details
    company = models.ForeignKey(
        'erp.Company',
        on_delete=models.CASCADE,
        related_name='employees'
    )
    department = models.ForeignKey(
        'erp.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employees'
    )
    branch = models.ForeignKey(
        'erp.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employees'
    )
    job_title = models.CharField(max_length=100)
    employment_type = models.CharField(max_length=20, choices=EmploymentType.choices, default=EmploymentType.FULL_TIME)
    employment_status = models.CharField(max_length=20, choices=EmploymentStatus.choices, default=EmploymentStatus.ACTIVE)
    hire_date = models.DateField()
    termination_date = models.DateField(null=True, blank=True)
    
    # Reporting
    reports_to = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subordinates'
    )
    
    # Salary & Compensation
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.ForeignKey(
        'erp.Currency',
        on_delete=models.PROTECT,
        related_name='employee_salaries'
    )
    
    # Bank Details
    bank_name = models.CharField(max_length=100, blank=True)
    bank_account = models.CharField(max_length=50, blank=True)
    iban = models.CharField(max_length=50, blank=True)
    
    # Leave Balance
    annual_leave_balance = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    sick_leave_balance = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # Self-registration & approval
    class ApprovalStatus(models.TextChoices):
        APPROVED = 'approved', 'Approved'
        PENDING = 'pending', 'Pending Approval'
        REJECTED = 'rejected', 'Rejected'

    approval_status = models.CharField(
        max_length=20,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.APPROVED,
        help_text=_('Employees created by owner are auto-approved; self-registered start as pending.'),
    )
    registered_via = models.CharField(
        max_length=64, blank=True,
        help_text=_('Invite token used during self-registration.'),
    )
    registration_password_hash = models.CharField(
        max_length=255, blank=True,
        help_text=_('Temporary password hash stored until owner approves.'),
    )

    # ── Portal Permissions ──────────────────────────────────────────────
    # Each boolean controls whether the employee can access that portal
    # section.  Defaults to True so existing employees keep full access.
    portal_can_scan_qr = models.BooleanField(
        default=True,
        verbose_name=_('Can Scan QR'),
        help_text=_('Allow the employee to use the QR attendance scanner.'),
    )
    portal_can_view_attendance = models.BooleanField(
        default=True,
        verbose_name=_('Can View Attendance'),
        help_text=_('Allow the employee to see their attendance history.'),
    )
    portal_can_manage_leaves = models.BooleanField(
        default=True,
        verbose_name=_('Can Manage Leaves'),
        help_text=_('Allow the employee to view and submit leave requests.'),
    )
    portal_can_view_payslips = models.BooleanField(
        default=True,
        verbose_name=_('Can View Payslips'),
        help_text=_('Allow the employee to view their payslips.'),
    )
    portal_can_edit_profile = models.BooleanField(
        default=True,
        verbose_name=_('Can Edit Profile'),
        help_text=_('Allow the employee to edit their personal profile.'),
    )
    portal_can_view_tasks = models.BooleanField(
        default=True,
        verbose_name=_('Can View Tasks'),
        help_text=_('Allow the employee to see tasks assigned to them.'),
    )
    portal_can_use_pos = models.BooleanField(
        default=False,
        verbose_name=_('Can Use POS'),
        help_text=_('Allow the employee to access the Point of Sale terminal.'),
    )

    class Meta:
        verbose_name=_('Employee')
        verbose_name_plural = 'Employees'
        ordering = ['first_name', 'last_name']
        unique_together = [('company', 'employee_id')]
        indexes = [
            models.Index(fields=['company', 'employment_status'], name='idx_emp_company_status'),
            models.Index(fields=['company', 'department'], name='idx_emp_company_dept'),
            models.Index(fields=['company', 'branch'], name='idx_emp_company_branch'),
            models.Index(fields=['company', 'approval_status'], name='idx_emp_company_approval'),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.employee_id})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name_ar(self):
        if self.first_name_ar and self.last_name_ar:
            return f"{self.first_name_ar} {self.last_name_ar}"
        return self.full_name


class EmployeeDocument(ERPBaseModel):
    """Employee documents storage."""
    class DocumentType(models.TextChoices):
        CONTRACT = 'contract', 'Employment Contract'
        ID_COPY = 'id_copy', 'ID Copy'
        PASSPORT = 'passport', 'Passport Copy'
        VISA = 'visa', 'Work Visa'
        CERTIFICATE = 'certificate', 'Certificate'
        RESUME = 'resume', 'Resume/CV'
        OTHER = 'other', 'Other'

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    document_type = models.CharField(max_length=20, choices=DocumentType.choices)
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='employees/documents/')
    expiry_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name=_('Employee Document')
        verbose_name_plural = 'Employee Documents'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.employee.full_name} - {self.title}"


class LeaveType(TimeStampedModel):
    """Types of leaves available."""
    name = models.CharField(max_length=100)
    name_ar = models.CharField(max_length=100, blank=True)
    code = models.CharField(max_length=20, unique=True)
    days_allowed = models.PositiveIntegerField(default=0, help_text=_('Annual days allowed (0 = unlimited)'))
    is_paid = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    color = models.CharField(max_length=7, default='#3498db', help_text=_('Hex color for calendar'))

    class Meta:
        verbose_name=_('Leave Type')
        verbose_name_plural = 'Leave Types'
        ordering = ['name']

    def __str__(self):
        return self.name


class LeaveRequest(ERPBaseModel):
    """Employee leave requests."""
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        CANCELLED = 'cancelled', 'Cancelled'

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='leave_requests'
    )
    leave_type = models.ForeignKey(
        LeaveType,
        on_delete=models.PROTECT,
        related_name='requests'
    )
    start_date = models.DateField()
    end_date = models.DateField()
    days_requested = models.DecimalField(max_digits=5, decimal_places=2)
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    
    # Approval
    approved_by = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_leaves'
    )
    approval_date = models.DateTimeField(null=True, blank=True)
    approval_notes = models.TextField(blank=True)

    class Meta:
        verbose_name=_('Leave Request')
        verbose_name_plural = 'Leave Requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['employee', 'status'], name='idx_lr_employee_status'),
            models.Index(fields=['employee', 'start_date'], name='idx_lr_employee_startdate'),
            models.Index(fields=['status', 'start_date'], name='idx_lr_status_startdate'),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({'end_date': _('تاريخ الانتهاء لا يمكن أن يكون قبل تاريخ البداية')})

    def __str__(self):
        return f"{self.employee.full_name} - {self.leave_type.name} ({self.start_date})"


class Attendance(TimeStampedModel):
    """Employee attendance records."""
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='attendances'
    )
    date = models.DateField()
    check_in = models.TimeField(null=True, blank=True)
    check_out = models.TimeField(null=True, blank=True)
    
    # Calculated
    hours_worked = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    overtime_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Status
    is_present = models.BooleanField(default=True)
    is_late = models.BooleanField(default=False)
    late_minutes = models.PositiveIntegerField(default=0)
    
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name=_('Attendance')
        verbose_name_plural = 'Attendances'
        unique_together = ['employee', 'date']
        ordering = ['-date', 'employee']
        indexes = [
            models.Index(fields=['date', 'is_present'], name='idx_att_date_present'),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.check_in and self.check_out and self.check_out < self.check_in:
            raise ValidationError({'check_out': _('وقت الخروج لا يمكن أن يكون قبل وقت الدخول')})

    def __str__(self):
        return f"{self.employee.full_name} - {self.date}"


class Payroll(ERPBaseModel):
    """Monthly payroll records."""
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        CALCULATED = 'calculated', 'Calculated'
        APPROVED = 'approved', 'Approved'
        PAID = 'paid', 'Paid'

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='payrolls'
    )
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Legacy hardcoded fields kept for backward compatibility / summary
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    housing_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    transport_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_allowances = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overtime_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bonus = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    absence_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    late_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    loan_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    social_insurance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Totals
    gross_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Status & Payment
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    payment_date = models.DateField(null=True, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)
    
    currency = models.ForeignKey(
        'erp.Currency',
        on_delete=models.PROTECT,
        related_name='payrolls'
    )
    
    # Link to journal entry (created on pay)
    journal_entry = models.ForeignKey(
        'erp.JournalEntry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payrolls'
    )
    
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name=_('Payroll')
        verbose_name_plural = 'Payrolls'
        unique_together = ['employee', 'period_start', 'period_end']
        ordering = ['-period_end', 'employee']
        indexes = [
            models.Index(fields=['employee', 'status'], name='idx_payroll_employee_status'),
            models.Index(fields=['status', 'period_start'], name='idx_payroll_status_period'),
        ]

    def __str__(self):
        return f"{self.employee.full_name} - {self.period_start} to {self.period_end}"

    def calculate_totals(self):
        """Calculate gross salary, deductions, and net salary from line items."""
        from django.db.models import Sum
        from django.db.models.functions import Coalesce

        # Sum from PayrollEarning line items
        earning_total = self.earning_lines.aggregate(
            total=Coalesce(Sum('amount'), Decimal('0'))
        )['total']

        # Sum from PayrollDeduction line items
        deduction_total = self.deduction_lines.aggregate(
            total=Coalesce(Sum('amount'), Decimal('0'))
        )['total']

        self.gross_salary = earning_total
        self.total_deductions = deduction_total
        self.net_salary = self.gross_salary - self.total_deductions

        # Sync legacy summary fields from line items
        self._sync_legacy_fields()

    def _sync_legacy_fields(self):
        """Sync the legacy hardcoded fields from line-item data."""
        from django.db.models import Sum
        from django.db.models.functions import Coalesce

        ZERO = Decimal('0')
        earning_map = {
            'basic_salary': 'basic_salary',
            'housing_allowance': 'housing_allowance',
            'transport_allowance': 'transport_allowance',
            'overtime': 'overtime_amount',
            'bonus': 'bonus',
        }
        # Sum other_allowances for types that don't map directly
        for etype, field_name in earning_map.items():
            val = self.earning_lines.filter(earning_type=etype).aggregate(
                total=Coalesce(Sum('amount'), ZERO)
            )['total']
            setattr(self, field_name, val)
        # Everything else goes to other_allowances
        other = self.earning_lines.exclude(
            earning_type__in=list(earning_map.keys())
        ).aggregate(total=Coalesce(Sum('amount'), ZERO))['total']
        self.other_allowances = other

        deduction_map = {
            'absence': 'absence_deduction',
            'late': 'late_deduction',
            'loan': 'loan_deduction',
            'social_insurance': 'social_insurance',
            'income_tax': 'tax_deduction',
        }
        for dtype, field_name in deduction_map.items():
            val = self.deduction_lines.filter(deduction_type=dtype).aggregate(
                total=Coalesce(Sum('amount'), ZERO)
            )['total']
            setattr(self, field_name, val)
        other_ded = self.deduction_lines.exclude(
            deduction_type__in=list(deduction_map.keys())
        ).aggregate(total=Coalesce(Sum('amount'), ZERO))['total']
        self.other_deductions = other_ded

    def create_journal_entry(self, user, salary_expense_account=None, salary_payable_account=None):
        """Create a journal entry for this payroll when it is paid.

        Creates a balanced double-entry:
          DR  Salary Expense Account   = gross_salary
          CR  Salary Payable / Cash    = net_salary
          CR  Social Insurance Payable = social_insurance  (if > 0)
          CR  Income Tax Payable       = tax_deduction     (if > 0)
          CR  Other Deductions         = remaining deductions (if > 0)

        If specific accounts are not provided, it tries to find them by code
        convention (5100 = Salary Expense, 2100 = Salary Payable) or uses
        the first expense / liability account.
        """
        from erp.models.finance import JournalEntry, JournalEntryLine, Account
        from erp.models.core import FiscalYear
        from erp.services.sequence import SequenceService
        from django.db import transaction

        company = self.employee.company

        # Resolve accounts using standard chart codes:
        #   6100 = Salary Expense (مصاريف الرواتب)
        #   2300 = Salary Payable (رواتب مستحقة)
        if not salary_expense_account:
            salary_expense_account = Account.objects.filter(
                company=company, code='6100', is_active=True
            ).first()
        if not salary_payable_account:
            salary_payable_account = Account.objects.filter(
                company=company, code='2300', is_active=True
            ).first()

        if not salary_expense_account:
            raise ValueError(
                'Salary Expense account (code 6100 - مصاريف الرواتب) not found. '
                'Please create it in Chart of Accounts first.'
            )
        if not salary_payable_account:
            raise ValueError(
                'Salary Payable account (code 2300 - رواتب مستحقة) not found. '
                'Please create it in Chart of Accounts first.'
            )

        # Get fiscal year
        fiscal_year = FiscalYear.objects.filter(
            company=company, is_current=True
        ).first()

        entry_number = SequenceService.get_next_number(company, 'journal_entry')

        with transaction.atomic():
            je = JournalEntry.objects.create(
                company=company,
                entry_number=entry_number,
                entry_date=self.payment_date or timezone.now().date(),
                entry_type='payroll',
                description=f'Payroll - {self.employee.full_name} ({self.period_start} to {self.period_end})',
                reference=f'PAY-{self.employee.employee_id}-{self.period_start.strftime("%Y%m")}',
                fiscal_year=fiscal_year,
                status='draft',
                created_by=user,
            )

            # DR: Salary Expense = gross_salary
            JournalEntryLine.objects.create(
                journal_entry=je,
                account=salary_expense_account,
                description=f'Salary expense - {self.employee.full_name}',
                debit_amount=self.gross_salary,
                credit_amount=Decimal('0'),
                reference_type='payroll',
                reference_id=self.pk,
            )

            # CR: breakdown by deduction type for proper accounting
            remaining_credit = self.gross_salary

            # Social Insurance payable
            if self.social_insurance > 0:
                si_account = (
                    Account.objects.filter(company=company, code='2310', is_active=True).first()
                    or salary_payable_account
                )
                JournalEntryLine.objects.create(
                    journal_entry=je,
                    account=si_account,
                    description=f'Social insurance - {self.employee.full_name}',
                    debit_amount=Decimal('0'),
                    credit_amount=self.social_insurance,
                    reference_type='payroll',
                    reference_id=self.pk,
                )
                remaining_credit -= self.social_insurance

            # Income Tax payable
            if self.tax_deduction > 0:
                tax_account = (
                    Account.objects.filter(company=company, code='2320', is_active=True).first()
                    or salary_payable_account
                )
                JournalEntryLine.objects.create(
                    journal_entry=je,
                    account=tax_account,
                    description=f'Income tax - {self.employee.full_name}',
                    debit_amount=Decimal('0'),
                    credit_amount=self.tax_deduction,
                    reference_type='payroll',
                    reference_id=self.pk,
                )
                remaining_credit -= self.tax_deduction

            # Net salary payable (remaining after statutory deductions)
            JournalEntryLine.objects.create(
                journal_entry=je,
                account=salary_payable_account,
                description=f'Net salary payable - {self.employee.full_name}',
                debit_amount=Decimal('0'),
                credit_amount=remaining_credit,
                reference_type='payroll',
                reference_id=self.pk,
            )

            # Recalculate JE totals
            je.calculate_totals()
            je.save(update_fields=['total_debit', 'total_credit'])

            # Auto-post the journal entry
            je.post(user)

            # Link to payroll
            self.journal_entry = je
            self.save(update_fields=['journal_entry'])

        return je


class PayrollEarning(TimeStampedModel):
    """Individual earning line items for a payroll record."""
    class EarningType(models.TextChoices):
        BASIC_SALARY = 'basic_salary', 'Basic Salary'
        HOUSING_ALLOWANCE = 'housing_allowance', 'Housing Allowance'
        TRANSPORT_ALLOWANCE = 'transport_allowance', 'Transport Allowance'
        PHONE_ALLOWANCE = 'phone_allowance', 'Phone Allowance'
        FOOD_ALLOWANCE = 'food_allowance', 'Food Allowance'
        OVERTIME = 'overtime', 'Overtime'
        BONUS = 'bonus', 'Bonus'
        COMMISSION = 'commission', 'Commission'
        END_OF_SERVICE = 'end_of_service', 'End of Service'
        OTHER = 'other', 'Other'

    payroll = models.ForeignKey(
        Payroll,
        on_delete=models.CASCADE,
        related_name='earning_lines'
    )
    earning_type = models.CharField(
        max_length=30,
        choices=EarningType.choices,
        default=EarningType.BASIC_SALARY,
    )
    description = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal('0'))],
    )

    class Meta:
        verbose_name=_('Payroll Earning')
        verbose_name_plural = 'Payroll Earnings'
        ordering = ['id']

    def __str__(self):
        return f"{self.get_earning_type_display()}: {self.amount}"

    @property
    def display_name(self):
        return self.description or self.get_earning_type_display()


class PayrollDeduction(TimeStampedModel):
    """Individual deduction line items for a payroll record."""
    class DeductionType(models.TextChoices):
        ABSENCE = 'absence', 'Absence Deduction'
        LATE = 'late', 'Late Deduction'
        LOAN = 'loan', 'Loan Repayment'
        SOCIAL_INSURANCE = 'social_insurance', 'Social Insurance (GOSI)'
        INCOME_TAX = 'income_tax', 'Income Tax'
        HEALTH_INSURANCE = 'health_insurance', 'Health Insurance'
        ADVANCE_SALARY = 'advance_salary', 'Advance Salary'
        PENALTY = 'penalty', 'Penalty'
        OTHER = 'other', 'Other'

    payroll = models.ForeignKey(
        Payroll,
        on_delete=models.CASCADE,
        related_name='deduction_lines'
    )
    deduction_type = models.CharField(
        max_length=30,
        choices=DeductionType.choices,
        default=DeductionType.OTHER,
    )
    description = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal('0'))],
    )

    class Meta:
        verbose_name=_('Payroll Deduction')
        verbose_name_plural = 'Payroll Deductions'
        ordering = ['id']

    def __str__(self):
        return f"{self.get_deduction_type_display()}: {self.amount}"

    @property
    def display_name(self):
        return self.description or self.get_deduction_type_display()


def _generate_device_secret():
    return secrets.token_hex(32)


def _generate_device_token():
    return secrets.token_urlsafe(48)


class AttendanceDevice(ERPBaseModel):
    """
    Authenticated device (TV screen / kiosk) for QR-based attendance.

    Each device gets a unique ``device_id`` and ``device_secret``.
    The kiosk display page uses ``device_id`` in its URL, and the
    ``device_secret`` is used to sign QR payloads so they can't be
    forged or replayed.

    Physical-device binding
    ~~~~~~~~~~~~~~~~~~~~~~~
    When a physical device (TV / tablet) first visits the kiosk URL it
    receives a unique ``device_token`` stored as an HTTP-only cookie.
    Until the owner **approves** the device from the management page the
    kiosk shows a "pending approval" screen.  After approval only the
    browser that holds the matching cookie can display the QR codes.
    """
    device_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    company = models.ForeignKey(
        'erp.Company',
        on_delete=models.CASCADE,
        related_name='attendance_devices',
    )
    name = models.CharField(max_length=100, help_text='e.g. "Main Office TV"')
    location = models.CharField(max_length=255, blank=True, help_text=_('Physical location'))
    device_secret = models.CharField(
        max_length=64,
        default=_generate_device_secret,
        help_text=_('HMAC secret for signing QR codes (auto-generated).'),
    )

    # ── Physical-device binding ──────────────────────────────────────────
    device_token = models.CharField(
        max_length=128,
        blank=True,
        default='',
        db_index=True,
        help_text=_('Cookie token assigned to the physical device.'),
    )
    is_device_approved = models.BooleanField(
        default=False,
        help_text=_('Whether the physical device has been approved by the owner.'),
    )
    device_user_agent = models.TextField(
        blank=True,
        default='',
        help_text=_('User-Agent string of the physical device.'),
    )
    device_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text=_('IP address of the physical device.'),
    )
    approval_requested_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('When the device first connected and requested approval.'),
    )

    # ── Attendance configuration ─────────────────────────────────────────
    work_start_time = models.TimeField(default='08:00', help_text=_('Expected work start time'))
    work_end_time = models.TimeField(default='17:00', help_text=_('Expected work end time'))
    late_threshold_minutes = models.PositiveIntegerField(
        default=15,
        help_text=_('Minutes after start time before marking as late'),
    )
    qr_refresh_seconds = models.PositiveIntegerField(
        default=30,
        help_text=_('How often the QR code refreshes on the kiosk (seconds)'),
    )

    is_active = models.BooleanField(default=True)
    last_heartbeat = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name=_('Attendance Device')
        verbose_name_plural = 'Attendance Devices'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.location})"

    def generate_qr_payload(self):
        """
        Generate a signed QR payload valid for ``qr_refresh_seconds``.

        Returns a dict with:
        - ``data``: The string to encode in the QR image.
        - ``expires``: Unix timestamp when it expires.
        """
        import hmac
        import hashlib
        import time

        ts = int(time.time())
        msg = f"{self.device_id}:{ts}"
        sig = hmac.new(
            self.device_secret.encode(),
            msg.encode(),
            hashlib.sha256,
        ).hexdigest()[:16]
        return {
            'data': f"{self.device_id}:{ts}:{sig}",
            'expires': ts + self.qr_refresh_seconds,
        }

    @staticmethod
    def verify_qr_payload(raw_data, max_age=120):
        """
        Verify a scanned QR payload.

        Returns the ``AttendanceDevice`` if valid, or raises ``ValueError``.
        """
        import hmac as _hmac
        import hashlib
        import time

        parts = raw_data.split(':')
        if len(parts) != 3:
            raise ValueError('Invalid QR format')

        device_id_str, ts_str, sig = parts
        try:
            ts = int(ts_str)
        except (ValueError, TypeError):
            raise ValueError('Invalid timestamp')

        if abs(time.time() - ts) > max_age:
            raise ValueError('QR code expired')

        try:
            device = AttendanceDevice.objects.get(
                device_id=device_id_str, is_active=True,
            )
        except AttendanceDevice.DoesNotExist:
            raise ValueError('Device not found or inactive')

        msg = f"{device_id_str}:{ts_str}"
        expected = _hmac.new(
            device.device_secret.encode(),
            msg.encode(),
            hashlib.sha256,
        ).hexdigest()[:16]

        if not _hmac.compare_digest(sig, expected):
            raise ValueError('Invalid QR signature')

        return device
