FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy project files
COPY . /app

# Install system packages required for some pip dependencies (e.g. pycairo / WeasyPrint)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        pkg-config \
        libcairo2-dev \
        libpango1.0-dev \
        libgdk-pixbuf2.0-dev \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && python manage.py collectstatic --noinput

# Run migrations and start Gunicorn server
CMD bash -c "python manage.py migrate --noinput && gunicorn learnflow_ai.wsgi:application --bind 0.0.0.0:$PORT"