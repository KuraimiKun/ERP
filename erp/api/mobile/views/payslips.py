"""Payslip list and detail endpoints."""

from rest_framework.decorators import api_view
from rest_framework.response import Response

from erp.models import Payroll, PayrollDeduction, PayrollEarning

from ..base import _error, _get_employee


@api_view(["GET"])
def mobile_payslip_list(request):
    """List payslips (approved/paid only)."""
    employee = _get_employee(request.user)
    if not employee:
        return _error("No employee profile found.", 404)

    if not employee.portal_can_view_payslips:
        return _error("Permission denied.", 403)

    payrolls = Payroll.objects.filter(
        employee=employee,
        status__in=["approved", "paid"],
    ).order_by("-period_end")

    return Response(
        {
            "payslips": [
                {
                    "id": p.pk,
                    "period_start": p.period_start.isoformat(),
                    "period_end": p.period_end.isoformat(),
                    "basic_salary": str(p.basic_salary),
                    "gross_salary": str(p.gross_salary),
                    "total_deductions": str(p.total_deductions),
                    "net_salary": str(p.net_salary),
                    "status": p.status,
                    "payment_date": p.payment_date.isoformat() if p.payment_date else None,
                }
                for p in payrolls
            ],
        }
    )


@api_view(["GET"])
def mobile_payslip_detail(request, pk):
    """Payslip detail with earnings and deductions breakdown."""
    employee = _get_employee(request.user)
    if not employee:
        return _error("No employee profile found.", 404)

    if not employee.portal_can_view_payslips:
        return _error("Permission denied.", 403)

    try:
        payroll = Payroll.objects.get(
            pk=pk,
            employee=employee,
            status__in=["approved", "paid"],
        )
    except Payroll.DoesNotExist:
        return _error("Payslip not found.", 404)

    earnings = PayrollEarning.objects.filter(payroll=payroll)
    deductions = PayrollDeduction.objects.filter(payroll=payroll)

    return Response(
        {
            "payslip": {
                "id": payroll.pk,
                "period_start": payroll.period_start.isoformat(),
                "period_end": payroll.period_end.isoformat(),
                "basic_salary": str(payroll.basic_salary),
                "gross_salary": str(payroll.gross_salary),
                "total_deductions": str(payroll.total_deductions),
                "net_salary": str(payroll.net_salary),
                "status": payroll.status,
                "payment_date": payroll.payment_date.isoformat() if payroll.payment_date else None,
                "payment_reference": payroll.payment_reference or "",
            },
            "earnings": [
                {
                    "type": e.get_earning_type_display(),
                    "description": e.description or "",
                    "amount": str(e.amount),
                }
                for e in earnings
            ],
            "deductions": [
                {
                    "type": d.get_deduction_type_display(),
                    "description": d.description or "",
                    "amount": str(d.amount),
                }
                for d in deductions
            ],
        }
    )
