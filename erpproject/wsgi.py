"""
WSGI config for ERP project.

It exposes the WSGI callable as a module-level variable named ``application``.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "erpproject.settings")

# Initialise New Relic APM agent before the WSGI application is created
# so that it can instrument Django and all downstream libraries.
_nr_license = os.getenv("NEW_RELIC_LICENSE_KEY", "")
_nr_debug = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")
if _nr_license and not _nr_debug:
    import newrelic.agent

    newrelic.agent.initialize(os.path.join(os.path.dirname(os.path.dirname(__file__)), "newrelic.ini"))

application = get_wsgi_application()
