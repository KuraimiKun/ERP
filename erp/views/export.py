"""
ERP Views – Data Export (CSV / Excel)

Single view handling bulk export for all list entities.
URL: /erp/export/<entity>/?format=csv|excel&<existing filters>
"""

from django.http import Http404

from erp.services.export import (
    EXPORT_REGISTRY,
    get_export_queryset,
    export_csv,
    export_excel,
    _versioned_cache_key,
)
from ._common import get_user_company, staff_member_required


@staff_member_required
def export_data(request, entity):
    """Export filtered data for *entity* as CSV or Excel."""
    if entity not in EXPORT_REGISTRY:
        raise Http404

    company = get_user_company(request.user)
    queryset, config = get_export_queryset(entity, request, company)

    if queryset is None:
        raise Http404

    fmt = request.GET.get("format", "csv")
    filename = config["filename"]
    ck = _versioned_cache_key(entity, company.pk, fmt, request.GET)

    if fmt == "excel":
        return export_excel(queryset, config, filename, cache_key=ck)
    return export_csv(queryset, config, filename, cache_key=ck)
