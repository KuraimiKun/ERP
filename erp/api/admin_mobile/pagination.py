"""Pagination for the admin mobile API.

Tighter defaults than the web API because mobile screens render short
lists and each kilobyte over the cellular link matters.
"""

from rest_framework.pagination import PageNumberPagination


class AdminMobilePagination(PageNumberPagination):
    """Page-number pagination with mobile-friendly bounds.

    * ``page_size`` defaults to 25 (half of DRF's default).
    * Clients can opt into larger pages via ``?page_size=`` up to 100.
    * Response shape is the DRF default — ``{count, next, previous, results}``.
    """

    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100
