"""
ERP Views – Data Import Wizard (CSV / Excel)

Three-step wizard:
  1. Upload – choose entity and file
  2. Preview – validate and show parsed rows with errors
  3. Confirm – execute the import and show results
"""

import json

from django.http import Http404
from django.shortcuts import redirect, render
from django.contrib import messages
from django.utils.translation import gettext as _

from erp.forms.import_data import ImportUploadForm
from erp.services.import_data import (
    IMPORT_REGISTRY, parse_file, validate_rows, execute_import, get_sample_headers,
)
from ._common import get_user_company, staff_member_required


@staff_member_required
def import_upload(request):
    """Step 1: Select entity and upload file."""
    if request.method == 'POST':
        form = ImportUploadForm(request.POST, request.FILES)
        if form.is_valid():
            entity = form.cleaned_data['entity']
            uploaded_file = form.cleaned_data['file']

            try:
                headers, rows = parse_file(uploaded_file)
            except ValueError as e:
                form.add_error('file', str(e))
                return render(request, 'erp/import/upload.html', {'form': form})

            if not rows:
                form.add_error('file', _('The file contains no data rows.'))
                return render(request, 'erp/import/upload.html', {'form': form})

            # Store parsed data in session for the next step
            request.session['import_entity'] = entity
            request.session['import_headers'] = headers
            request.session['import_rows'] = _serialise_rows(rows)
            request.session['import_filename'] = uploaded_file.name

            return redirect('erp:import_preview')
    else:
        initial = {}
        entity_param = request.GET.get('entity')
        if entity_param and entity_param in IMPORT_REGISTRY:
            initial['entity'] = entity_param
        form = ImportUploadForm(initial=initial)

    # Build sample headers for each entity (for the help section)
    sample_headers = {k: get_sample_headers(k) for k in IMPORT_REGISTRY}

    return render(request, 'erp/import/upload.html', {
        'form': form,
        'sample_headers': json.dumps(sample_headers),
    })


@staff_member_required
def import_preview(request):
    """Step 2: Show validation results and preview data."""
    entity = request.session.get('import_entity')
    headers = request.session.get('import_headers')
    rows_raw = request.session.get('import_rows')
    filename = request.session.get('import_filename', '')

    if not entity or not headers or rows_raw is None:
        messages.warning(request, _('No import data found. Please upload a file first.'))
        return redirect('erp:import_upload')

    if entity not in IMPORT_REGISTRY:
        raise Http404

    rows = _deserialise_rows(rows_raw)
    company = get_user_company(request.user)

    try:
        preview_rows, mapped_headers, has_errors = validate_rows(
            entity, headers, rows, company,
        )
    except ValueError as e:
        messages.error(request, str(e))
        return redirect('erp:import_upload')

    config = IMPORT_REGISTRY[entity]
    entity_label = entity.replace('_', ' ').title()

    # Build template-friendly cell data for each row
    display_rows = []
    for row in preview_rows:
        cells = []
        for _header, field in mapped_headers:
            if field:
                value = row['data'].get(field, '')
                error = row['errors'].get(field)
                # Convert model objects to string for display
                display_val = str(value) if value is not None else ''
                cells.append({
                    'value': display_val,
                    'error': error,
                })
            else:
                cells.append({'value': '', 'error': None})
        display_rows.append({
            'row_num': row['row_num'],
            'cells': cells,
            'errors': row['errors'],
            'is_update': row['data'].get('_is_update', False),
            'has_errors': bool(row['errors']),
        })

    return render(request, 'erp/import/preview.html', {
        'entity': entity,
        'entity_label': entity_label,
        'filename': filename,
        'display_rows': display_rows,
        'mapped_headers': mapped_headers,
        'has_errors': has_errors,
        'total_rows': len(display_rows),
        'new_rows': sum(1 for r in display_rows if not r['is_update']),
        'update_rows': sum(1 for r in display_rows if r['is_update']),
        'error_count': sum(1 for r in display_rows if r['has_errors']),
        'unique_field': config['unique_field'],
    })


@staff_member_required
def import_confirm(request):
    """Step 3: Execute the import and show results."""
    if request.method != 'POST':
        return redirect('erp:import_upload')

    entity = request.session.get('import_entity')
    headers = request.session.get('import_headers')
    rows_raw = request.session.get('import_rows')

    if not entity or not headers or rows_raw is None:
        messages.warning(request, _('No import data found. Please upload a file first.'))
        return redirect('erp:import_upload')

    if entity not in IMPORT_REGISTRY:
        raise Http404

    rows = _deserialise_rows(rows_raw)
    company = get_user_company(request.user)

    try:
        created, updated, error_rows = execute_import(
            entity, headers, rows, company, request.user,
        )
    except Exception as e:
        messages.error(request, _('Import failed: %(error)s') % {'error': str(e)})
        return redirect('erp:import_preview')

    # Clear session data
    for key in ('import_entity', 'import_headers', 'import_rows', 'import_filename'):
        request.session.pop(key, None)

    entity_label = entity.replace('_', ' ').title()

    return render(request, 'erp/import/results.html', {
        'entity': entity,
        'entity_label': entity_label,
        'created': created,
        'updated': updated,
        'error_rows': error_rows,
        'total_processed': created + updated + len(error_rows),
    })


# ── Serialisation helpers ───────────────────────────────────────────────────
# Session data must be JSON-serialisable. Convert date/datetime objects.

def _serialise_rows(rows):
    """Convert row data to JSON-safe format for session storage."""
    from datetime import date, datetime
    result = []
    for row in rows:
        serialised = []
        for cell in row:
            if isinstance(cell, (date, datetime)):
                serialised.append(cell.isoformat())
            elif cell is None:
                serialised.append(None)
            else:
                serialised.append(str(cell))
        result.append(serialised)
    return result


def _deserialise_rows(rows_raw):
    """Convert session-stored rows back to lists."""
    return rows_raw  # Already list of lists of strings/None
