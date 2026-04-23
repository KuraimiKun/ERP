"""
ERP Views – AJAX helpers

Lightweight JSON endpoints used by form templates to fetch product/service
pricing data without a full page reload.
"""

from django.http import JsonResponse

from erp.models import Product, ServicePricing
from ._common import get_user_company, staff_member_required


@staff_member_required
def ajax_item_price(request):
    """
    GET /erp/ajax/item-price/?type=product&id=123
    GET /erp/ajax/item-price/?type=service&id=456

    Returns JSON:
      { "price": "120.00", "description": "Widget X", "tax_rate_id": 5 }
    """
    company = get_user_company(request.user)
    item_type = request.GET.get("type", "")
    item_id = request.GET.get("id", "")

    if not item_id:
        return JsonResponse({"error": "Missing id"}, status=400)

    try:
        if item_type == "product":
            product = Product.objects.get(pk=item_id, company=company, is_active=True)
            return JsonResponse(
                {
                    "price": str(product.selling_price),
                    "cost_price": str(product.cost_price),
                    "description": product.name,
                    "tax_rate_id": product.tax_rate_id or "",
                }
            )
        elif item_type == "service":
            service = ServicePricing.objects.get(pk=item_id, company=company, is_active=True)
            return JsonResponse(
                {
                    "price": str(service.base_price),
                    "cost_price": str(service.cost_price),
                    "description": service.name,
                    "tax_rate_id": service.tax_rate_id or "",
                }
            )
        else:
            return JsonResponse({"error": "Invalid type"}, status=400)
    except (Product.DoesNotExist, ServicePricing.DoesNotExist):
        return JsonResponse({"error": "Not found"}, status=404)
