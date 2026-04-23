"""
ERP Admin Package

Imports all admin registrations so Django discovers them.
"""

from .core import *  # noqa: F401,F403
from .hr import *  # noqa: F401,F403
from .finance import *  # noqa: F401,F403
from .supplier import *  # noqa: F401,F403
from .crm import *  # noqa: F401,F403
from .services import *  # noqa: F401,F403
from .reporting import *  # noqa: F401,F403
from .audit import *  # noqa: F401,F403
