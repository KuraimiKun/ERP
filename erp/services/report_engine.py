"""
Report Execution Engine

Takes a validated report configuration and produces:
  1. A queryset of results (for preview / JSON)
  2. Rendered output files (CSV / Excel / PDF)

All field access is validated against the data source registry before
any ORM operation — no arbitrary field traversal is possible.
"""

import csv
import io
import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.db.models import (
    Sum,
    Count,
    Avg,
    Min,
    Max,
)
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from .report_builder import (
    get_data_source,
    MAX_REPORT_ROWS,
    TYPE_DATE,
    TYPE_DATETIME,
    TYPE_DECIMAL,
    TYPE_INTEGER,
    TYPE_BOOLEAN,
)

logger = logging.getLogger("erp.report_engine")

# ── ORM operator mapping ───────────────────────────────────────────────────

_OPERATOR_MAP = {
    "eq": "",  # field=value
    "neq": "__ne",  # handled with exclude()
    "gt": "__gt",
    "gte": "__gte",
    "lt": "__lt",
    "lte": "__lte",
    "contains": "__icontains",
    "startswith": "__istartswith",
    "in": "__in",
    "isnull": "__isnull",
    "range": "__range",
}

_AGGREGATE_MAP = {
    "sum": Sum,
    "count": Count,
    "avg": Avg,
    "min": Min,
    "max": Max,
}


def _coerce_value(value, field_type, operator):
    """Cast a user-supplied filter value to the correct Python type."""
    if operator == "isnull":
        return str(value).lower() in ("true", "1", "yes")

    if operator == "in":
        if isinstance(value, str):
            return [v.strip() for v in value.split(",")]
        return list(value)

    if operator == "range":
        if isinstance(value, (list, tuple)) and len(value) == 2:
            return [_coerce_single(value[0], field_type), _coerce_single(value[1], field_type)]
        return value

    return _coerce_single(value, field_type)


def _coerce_single(value, field_type):
    if field_type == TYPE_DECIMAL:
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return value
    if field_type == TYPE_INTEGER:
        try:
            return int(value)
        except (ValueError, TypeError):
            return value
    if field_type == TYPE_DATE:
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value))
        except (ValueError, TypeError):
            return value
    if field_type == TYPE_DATETIME:
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value))
        except (ValueError, TypeError):
            return value
    if field_type == TYPE_BOOLEAN:
        return str(value).lower() in ("true", "1", "yes")
    return value


# ── Query builder ──────────────────────────────────────────────────────────


def build_queryset(configuration, company, limit=None):
    """Build a Django ORM queryset from a report configuration.

    Returns (queryset, column_labels, is_grouped).
    """
    source_key = configuration["data_source"]
    source = get_data_source(source_key)
    if source is None:
        raise ValueError(f"Unknown data source: {source_key}")

    model = source["model"]
    allowed_fields = set(source["fields"].keys())

    # Base queryset — tenant-isolated
    qs = model.objects.all()
    company_field = source.get("company_field", "company")
    qs = qs.filter(**{company_field: company})

    # select_related for efficiency
    sr = source.get("select_related", [])
    if sr:
        qs = qs.select_related(*sr)

    # ── Filters ─────────────────────────────────────────────────────────
    for flt in configuration.get("filters", []):
        field = flt.get("field")
        operator = flt.get("operator", "eq")
        value = flt.get("value")

        if field not in allowed_fields:
            continue  # silently skip invalid (validated upstream)

        field_type = source["fields"][field]["type"]
        coerced = _coerce_value(value, field_type, operator)

        if operator == "neq":
            qs = qs.exclude(**{field: coerced})
        else:
            suffix = _OPERATOR_MAP.get(operator, "")
            qs = qs.filter(**{f"{field}{suffix}": coerced})

    # ── Grouping + Aggregates ───────────────────────────────────────────
    columns = configuration.get("columns", [])
    grouping = configuration.get("grouping", [])

    has_aggregates = any(c.get("aggregate") for c in columns)
    is_grouped = bool(grouping) or has_aggregates

    column_labels = []

    if is_grouped and grouping:
        safe_grouping = [g for g in grouping if g in allowed_fields]
        qs = qs.values(*safe_grouping)

        annotations = {}
        for col in columns:
            field = col.get("field")
            aggregate = col.get("aggregate")
            label = col.get("label", field)

            if field not in allowed_fields:
                continue

            if aggregate and aggregate in _AGGREGATE_MAP:
                agg_name = f"{field}__{aggregate}"
                annotations[agg_name] = _AGGREGATE_MAP[aggregate](field)
                column_labels.append((agg_name, f"{label} ({aggregate.upper()})"))
            elif field in safe_grouping:
                column_labels.append((field, label))

        if annotations:
            qs = qs.annotate(**annotations)
    else:
        for col in columns:
            field = col.get("field")
            label = col.get("label", field)
            if field in allowed_fields:
                column_labels.append((field, label))

    # ── Ordering ────────────────────────────────────────────────────────
    ordering = configuration.get("ordering", [])
    safe_ordering = []
    for o in ordering:
        bare = o.lstrip("-")
        if bare in allowed_fields:
            safe_ordering.append(o)
        # Also allow ordering by annotation names
        elif is_grouped and any(bare == cl[0] for cl in column_labels):
            safe_ordering.append(o)
    if safe_ordering:
        qs = qs.order_by(*safe_ordering)

    # ── Limit ───────────────────────────────────────────────────────────
    row_limit = limit or configuration.get("limit", MAX_REPORT_ROWS)
    row_limit = min(row_limit, MAX_REPORT_ROWS)
    qs = qs[:row_limit]

    return qs, column_labels, is_grouped


def execute_to_list(configuration, company, limit=None):
    """Execute and return a list of dicts + column info.

    Used for JSON preview and as input to renderers.
    """
    qs, column_labels, is_grouped = build_queryset(configuration, company, limit)

    if is_grouped:
        # qs is already a ValuesQuerySet → list of dicts
        rows = list(qs)
    else:
        field_keys = [cl[0] for cl in column_labels]
        rows = list(qs.values(*field_keys))

    # Serialise values for JSON safety
    clean_rows = []
    for row in rows:
        clean = {}
        for key, value in row.items():
            if isinstance(value, Decimal):
                clean[key] = float(value)
            elif isinstance(value, (date, datetime)):
                clean[key] = value.isoformat()
            elif value is None:
                clean[key] = None
            else:
                clean[key] = value
            # Boolean display
            if isinstance(value, bool):
                clean[key] = value
        clean_rows.append(clean)

    return {
        "columns": [{"key": k, "label": l} for k, l in column_labels],
        "rows": clean_rows,
        "row_count": len(clean_rows),
    }


# ── Output renderers ──────────────────────────────────────────────────────


def _format_cell(value):
    """Stringify a value for CSV / display."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def render_csv(result_data):
    """Render report data to CSV bytes."""
    output = io.StringIO()
    output.write("\ufeff")  # BOM for Excel compatibility

    columns = result_data["columns"]
    writer = csv.writer(output)
    writer.writerow([c["label"] for c in columns])

    for row in result_data["rows"]:
        writer.writerow([_format_cell(row.get(c["key"])) for c in columns])

    return output.getvalue().encode("utf-8")


def render_excel(result_data, report_name="Report"):
    """Render report data to .xlsx bytes."""
    wb = Workbook()
    ws = wb.active
    ws.title = report_name[:31]  # Excel limit

    columns = result_data["columns"]

    # Header styling
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_align = Alignment(horizontal="center", vertical="center")
    thin_border = Border(
        bottom=Side(style="thin", color="E2E8F0"),
    )

    # Write header
    for col_idx, col in enumerate(columns, 1):
        cell = ws.cell(row=1, column=col_idx, value=col["label"])
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align

    # Write data
    for row_idx, row in enumerate(result_data["rows"], 2):
        for col_idx, col in enumerate(columns, 1):
            value = row.get(col["key"])
            if isinstance(value, float):
                cell = ws.cell(row=row_idx, column=col_idx, value=value)
                cell.number_format = "#,##0.00"
            elif isinstance(value, bool):
                cell = ws.cell(row=row_idx, column=col_idx, value="Yes" if value else "No")
            else:
                cell = ws.cell(row=row_idx, column=col_idx, value=_format_cell(value))
            cell.border = thin_border

    # Auto-width columns
    for col_idx, col in enumerate(columns, 1):
        max_len = len(col["label"])
        for row_idx in range(2, min(len(result_data["rows"]) + 2, 100)):
            cell_val = str(ws.cell(row=row_idx, column=col_idx).value or "")
            max_len = max(max_len, len(cell_val))
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = min(max_len + 4, 50)

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()


def render_html_table(result_data):
    """Render report data as an HTML table string (for PDF embedding)."""
    columns = result_data["columns"]
    lines = [
        '<table class="report-table" style="width:100%;border-collapse:collapse;font-family:Tajawal,sans-serif;font-size:11px;">'
    ]
    lines.append("<thead><tr>")
    for col in columns:
        lines.append(
            f'<th style="background:#1E293B;color:#fff;padding:8px 12px;text-align:left;'
            f'border-bottom:2px solid #0D6EFD;">{col["label"]}</th>'
        )
    lines.append("</tr></thead><tbody>")

    for i, row in enumerate(result_data["rows"]):
        bg = "#f8fafc" if i % 2 == 0 else "#ffffff"
        lines.append(f'<tr style="background:{bg};">')
        for col in columns:
            val = _format_cell(row.get(col["key"]))
            lines.append(f'<td style="padding:6px 12px;border-bottom:1px solid #e2e8f0;">{val}</td>')
        lines.append("</tr>")

    lines.append("</tbody></table>")
    return "\n".join(lines)


def render_pdf(result_data, report_name="Report", date_range=None):
    """Render report data to PDF bytes using xhtml2pdf."""
    from xhtml2pdf import pisa

    table_html = render_html_table(result_data)
    date_str = ""
    if date_range:
        date_str = f"<p style='color:#64748b;margin:0;'>{date_range}</p>"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page {{ size: A4 landscape; margin: 1.5cm; }}
            body {{ font-family: Tajawal, Helvetica, sans-serif; color: #1e293b; }}
            h1 {{ font-size: 18px; margin: 0 0 4px 0; }}
            .meta {{ font-size: 11px; color: #64748b; margin-bottom: 16px; }}
        </style>
    </head>
    <body>
        <h1>{report_name}</h1>
        {date_str}
        <p class="meta">Generated {timezone.now().strftime("%Y-%m-%d %H:%M")} &bull; {result_data["row_count"]} rows</p>
        {table_html}
    </body>
    </html>
    """

    output = io.BytesIO()
    pisa.pisaDocument(io.BytesIO(html.encode("utf-8")), output, encoding="utf-8")
    return output.getvalue()
