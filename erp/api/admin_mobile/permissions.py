"""Admin-mobile permission re-exports.

Kept as a thin shim so future admin-mobile-only permissions can be added
here without touching the global ``erp.api.permissions`` module.
"""

from erp.api.permissions import (  # noqa: F401
    DefaultDbTokenAuthentication,
    IsCompanyAdmin,
)

__all__ = ["DefaultDbTokenAuthentication", "IsCompanyAdmin"]
