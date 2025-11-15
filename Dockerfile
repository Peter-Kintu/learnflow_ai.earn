FROM python:3.11-slim

WORKDIR /app

COPY . /app

RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && python manage.py migrate --noinput \
    && python manage.py collectstatic --noinput

CMD gunicorn learnflow_ai.wsgi --bind 0.0.0.0:$PORT