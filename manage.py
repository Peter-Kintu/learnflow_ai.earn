#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'learnflow_ai.settings')
    # Guard: ensure INSTALLED_APPS has unique entries before Django initializes
    try:
        from importlib import import_module
        settings_mod = import_module(os.environ['DJANGO_SETTINGS_MODULE'])
        if hasattr(settings_mod, 'INSTALLED_APPS'):
            settings_mod.INSTALLED_APPS = list(dict.fromkeys(settings_mod.INSTALLED_APPS))
    except Exception:
        pass
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
