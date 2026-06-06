build: pip install -r requirements.txt && python manage.py collectstatic --noinput --clear && python manage.py migrate
web: daphne -b 0.0.0.0 -p 8000 learnflow_ai.asgi:application
