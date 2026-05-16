"""
WSGI config for learnflow_ai project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'learnflow_ai.settings')
# Ensure INSTALLED_APPS has unique entries before Django initializes (prevents duplicate app labels)
try:
	import importlib
	settings_mod = importlib.import_module(os.environ['DJANGO_SETTINGS_MODULE'])
	if hasattr(settings_mod, 'INSTALLED_APPS'):
		settings_mod.INSTALLED_APPS = list(dict.fromkeys(settings_mod.INSTALLED_APPS))
except Exception:
	pass

application = get_wsgi_application()
