"""
Selectors – Journal Entries
"""

from erp.models import JournalEntry, Account

__all__ = [
    'get_journal_entry_list',
    'get_journal_entry_stats',
    'get_journal_entry_detail_context',
    'get_active_accounts',
]


def get_journal_entry_list(
    company, *, status=None, entry_type=None, date_from=None, date_to=None, limit=50,
):
    qs = JournalEntry.objects.filter(company=company).order_by('-entry_date', '-entry_number')
    if status:
        qs = qs.filter(status=status)
    if entry_type:
        qs = qs.filter(entry_type=entry_type)
    if date_from:
        qs = qs.filter(entry_date__gte=date_from)
    if date_to:
        qs = qs.filter(entry_date__lte=date_to)
    return qs[:limit]


def get_journal_entry_stats(entries_qs):
    """Return counts from an already-filtered JournalEntry queryset."""
    return {
        'total_entries': entries_qs.count(),
        'posted_count': entries_qs.filter(status='posted').count(),
        'draft_count': entries_qs.filter(status='draft').count(),
    }


def get_journal_entry_detail_context(entry):
    return {
        'lines': entry.lines.all().select_related('account'),
    }


def get_active_accounts(company):
    """Return active accounts ordered by code (for form dropdowns)."""
    return Account.objects.filter(company=company, is_active=True).order_by('code')
