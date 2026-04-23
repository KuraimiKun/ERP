"""
PDF Generation Service

Uses xhtml2pdf to render HTML templates into PDF responses.
"""

import io
from django.http import HttpResponse
from django.template.loader import render_to_string
from xhtml2pdf import pisa


def render_to_pdf(template_path, context, filename="document.pdf"):
    """Render an HTML template to a PDF HttpResponse."""
    html = render_to_string(template_path, context)
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html.encode("utf-8")), result, encoding="utf-8")

    if pdf.err:
        return HttpResponse("Error generating PDF", status=500)

    response = HttpResponse(result.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response
