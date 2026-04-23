"""
Deprecated shim — kept for backward compatibility.

The mobile API has moved to the ``erp.api.mobile`` package. Import from
``erp.api.mobile.views`` instead of ``erp.api.mobile_views``.
"""

from .mobile.views import *  # noqa: F401,F403
from .mobile.views import __all__  # noqa: F401
