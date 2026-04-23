"""
ERP Views – Journal Entries (القيود اليومية)
"""

from django.utils import timezone

from erp.models import JournalEntry, Account
from erp.forms import JournalEntryForm, JournalEntryLineFormSet
from ._common import (
    render,
    get_object_or_404,
    redirect,
    messages,
    reverse,
    get_user_company,
    staff_member_required,
    paginate_qs,
    apply_sorting,
)


@staff_member_required
def journal_entry_list(request):
    """قائمة القيود اليومية"""
    company = get_user_company(request.user)
    entries = JournalEntry.objects.filter(company=company)

    status = request.GET.get("status")
    entry_type = request.GET.get("type")
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")

    if status:
        entries = entries.filter(status=status)
    if entry_type:
        entries = entries.filter(entry_type=entry_type)
    if date_from:
        entries = entries.filter(entry_date__gte=date_from)
    if date_to:
        entries = entries.filter(entry_date__lte=date_to)

    total_entries = entries.count()
    posted_count = entries.filter(status="posted").count()
    draft_count = entries.filter(status="draft").count()

    entries, current_sort, current_order = apply_sorting(
        request,
        entries,
        allowed_fields=["entry_number", "entry_date", "entry_type", "status", "total_debit"],
        default="-entry_date",
    )
    page_obj, query_string = paginate_qs(request, entries)

    context = {
        "entries": page_obj,
        "page_obj": page_obj,
        "query_string": query_string,
        "total_entries": total_entries,
        "posted_count": posted_count,
        "draft_count": draft_count,
        "status_choices": JournalEntry.Status.choices,
        "type_choices": JournalEntry.EntryType.choices,
        "current_sort": current_sort,
        "current_order": current_order,
    }
    return render(request, "erp/journal_entries/list.html", context)


@staff_member_required
def journal_entry_create(request):
    """إنشاء قيد يومية جديد"""
    company = get_user_company(request.user)

    if request.method == "POST":
        form = JournalEntryForm(request.POST, company=company)
        formset = JournalEntryLineFormSet(request.POST, company=company)

        if form.is_valid() and formset.is_valid():
            journal_entry = form.save(commit=False)
            journal_entry.company = company
            journal_entry.created_by = request.user
            journal_entry.save()

            formset.instance = journal_entry
            formset.save()

            journal_entry.calculate_totals()
            journal_entry.save()

            messages.success(request, f"تم إنشاء القيد رقم {journal_entry.entry_number} بنجاح")
            return redirect("erp:journal_entry_detail", pk=journal_entry.pk)
    else:
        today = timezone.now().date()
        last_entry = JournalEntry.objects.filter(company=company).order_by("-id").first()
        next_num = 1 if not last_entry else int(last_entry.entry_number.split("-")[-1]) + 1
        initial_number = f"JE-{today.year}-{next_num:05d}"

        form = JournalEntryForm(
            company=company,
            initial={
                "entry_number": initial_number,
                "entry_date": today,
            },
        )
        formset = JournalEntryLineFormSet(company=company)

    return render(
        request,
        "erp/journal_entries/form.html",
        {
            "form": form,
            "formset": formset,
            "accounts": Account.objects.filter(company=company, is_active=True).order_by("code"),
        },
    )


@staff_member_required
def journal_entry_detail(request, pk):
    """عرض تفاصيل القيد"""
    company = get_user_company(request.user)
    entry = get_object_or_404(JournalEntry, pk=pk, company=company)

    return render(
        request,
        "erp/journal_entries/detail.html",
        {
            "entry": entry,
            "lines": entry.lines.all().select_related("account"),
        },
    )


@staff_member_required
def journal_entry_edit(request, pk):
    """تعديل قيد يومية"""
    company = get_user_company(request.user)
    entry = get_object_or_404(JournalEntry, pk=pk, company=company)

    if entry.status == "posted":
        messages.error(request, "لا يمكن تعديل قيد مرحّل")
        return redirect("erp:journal_entry_detail", pk=pk)

    if request.method == "POST":
        form = JournalEntryForm(request.POST, instance=entry, company=company)
        formset = JournalEntryLineFormSet(request.POST, instance=entry, company=company)

        if form.is_valid() and formset.is_valid():
            journal_entry = form.save()
            formset.save()

            journal_entry.calculate_totals()
            journal_entry.save()

            messages.success(request, "تم تحديث القيد بنجاح")
            return redirect("erp:journal_entry_detail", pk=pk)
    else:
        form = JournalEntryForm(instance=entry, company=company)
        formset = JournalEntryLineFormSet(instance=entry, company=company)

    return render(
        request,
        "erp/journal_entries/form.html",
        {
            "form": form,
            "formset": formset,
            "entry": entry,
            "accounts": Account.objects.filter(company=company, is_active=True).order_by("code"),
        },
    )


@staff_member_required
def journal_entry_delete(request, pk):
    """حذف قيد يومية"""
    company = get_user_company(request.user)
    entry = get_object_or_404(JournalEntry, pk=pk, company=company)

    if entry.status == "posted":
        messages.error(request, "لا يمكن حذف قيد مرحّل")
        return redirect("erp:journal_entry_detail", pk=pk)

    if request.method == "POST":
        entry_number = entry.entry_number
        entry.delete()
        messages.success(request, f"تم حذف القيد رقم {entry_number}")
        return redirect("erp:journal_entry_list")

    return render(
        request,
        "erp/confirm_delete.html",
        {
            "object": entry,
            "object_name": f"القيد رقم {entry.entry_number}",
            "cancel_url": reverse("erp:journal_entry_detail", args=[pk]),
        },
    )


@staff_member_required
def journal_entry_post(request, pk):
    """ترحيل القيد"""
    company = get_user_company(request.user)
    entry = get_object_or_404(JournalEntry, pk=pk, company=company)

    if request.method == "POST":
        try:
            entry.post(request.user)
            messages.success(request, f"تم ترحيل القيد رقم {entry.entry_number} بنجاح")
        except ValueError as e:
            messages.error(request, str(e))

    return redirect("erp:journal_entry_detail", pk=pk)
