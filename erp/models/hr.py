"""
Human Resources (HR) models for the ERP system.
"""

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
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
    employee_id = models.CharField(max_length=20, unique=True)
    
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

    class Meta:
        verbose_name = 'Employee'
        verbose_name_plural = 'Employees'
        ordering = ['first_name', 'last_name']

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
        verbose_name = 'Employee Document'
        verbose_name_plural = 'Employee Documents'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.employee.full_name} - {self.title}"


class LeaveType(TimeStampedModel):
    """Types of leaves available."""
    name = models.CharField(max_length=100)
    name_ar = models.CharField(max_length=100, blank=True)
    code = models.CharField(max_length=20, unique=True)
    days_allowed = models.PositiveIntegerField(default=0, help_text='Annual days allowed (0 = unlimited)')
    is_paid = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    color = models.CharField(max_length=7, default='#3498db', help_text='Hex color for calendar')

    class Meta:
        verbose_name = 'Leave Type'
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
        verbose_name = 'Leave Request'
        verbose_name_plural = 'Leave Requests'
        ordering = ['-created_at']

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
        verbose_name = 'Attendance'
        verbose_name_plural = 'Attendances'
        unique_together = ['employee', 'date']
        ordering = ['-date', 'employee']

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
    
    # Earnings
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    housing_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    transport_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_allowances = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overtime_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bonus = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Deductions
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
    
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Payroll'
        verbose_name_plural = 'Payrolls'
        unique_together = ['employee', 'period_start', 'period_end']
        ordering = ['-period_end', 'employee']

    def __str__(self):
        return f"{self.employee.full_name} - {self.period_start} to {self.period_end}"

    def calculate_totals(self):
        """Calculate gross salary, deductions, and net salary."""
        self.gross_salary = (
            self.basic_salary +
            self.housing_allowance +
            self.transport_allowance +
            self.other_allowances +
            self.overtime_amount +
            self.bonus
        )
        self.total_deductions = (
            self.absence_deduction +
            self.late_deduction +
            self.loan_deduction +
            self.social_insurance +
            self.tax_deduction +
            self.other_deductions
        )
        self.net_salary = self.gross_salary - self.total_deductions
