import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'learnflow_ai.settings')
app = Celery('learnflow_ai')
app.config_from_object('django.conf:settings', namespace='CELERY')
# Avoid running autodiscover at import time (prevents side-effects during manage.py startup)
# app.autodiscover_tasks()