"""
ERP Selectors Package

Pure read-only query functions organised by domain.  Each function
accepts a ``Company`` instance (and optional filter kwargs) and returns
a QuerySet or scalar value.  Views should delegate *all* database
fetching to these selectors.
"""

from erp.selectors.dashboard import *  # noqa: F401,F403
from erp.selectors.customers import *  # noqa: F401,F403
from erp.selectors.finance import *  # noqa: F401,F403
from erp.selectors.hr import *  # noqa: F401,F403
from erp.selectors.crm import *  # noqa: F401,F403
from erp.selectors.suppliers import *  # noqa: F401,F403
from erp.selectors.services import *  # noqa: F401,F403
from erp.selectors.products import *  # noqa: F401,F403
from erp.selectors.journal import *  # noqa: F401,F403
