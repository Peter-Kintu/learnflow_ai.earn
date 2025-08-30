# learnflow_ai/settings.py
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-**********************************'
DEBUG = True
# To fix the DisallowedHost error, we need to add the domain
# 'learnflow-ai-0fdz.onrender.com' to the list of allowed hosts.
ALLOWED_HOSTS = [
    '127.0.0.1', 
    'localhost',
    'learnflow-ai-0fdz.onrender.com'
    ]

# Application definition
INSTALLED_APPS = [
    'jazzmin',  # 🎷 Jazzmin admin theme
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'aiapp',
    'video',
    'user',
    'book',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'learnflow_ai.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'learnflow_ai.wsgi.application'

# CORRECTED: This section is updated to use your Neon.tech PostgreSQL database.
# Be sure to install the required library with: pip install psycopg2-binary
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'neondb',
        'USER': 'neondb_owner',
        'PASSWORD': 'npg_Irxs8L1cVhlW',
        'HOST': 'ep-green-shape-aexq3vr8-pooler.c-2.us-east-2.aws.neon.tech',
        'PORT': '5432', # 5432 is the default PostgreSQL port
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'user:login'
LOGIN_REDIRECT_URL = 'video:video_list'
LOGOUT_REDIRECT_URL = 'user:login' # FIX: Added this to redirect to the correct login page

# 🎨 Jazzmin Styling
JAZZMIN_SETTINGS = {
    "site_title": "LearnFlow Admin",
    "site_header": "LearnFlow Dashboard",
    "site_brand": "LearnFlow",
    "welcome_sign": "Welcome to LearnFlow Admin",
    "copyright": "KINTU",
    "search_model": ["user.User", "video.Video"],
    "topmenu_links": [
        {"name": "Home", "url": "/", "permissions": ["auth.view_user"]},
        {"model": "user.User"},
        {"model": "video.Video"},
    ],
    "show_sidebar": True,
    "navigation_expanded": True,
    "icons": {
        "user.User": "fas fa-user",
        "video.Video": "fas fa-video",
        "book.Book": "fas fa-book",
    },
    "changeform_format": "horizontal_tabs",
    "related_modal_active": True,
    # This setting is for the interactive UI builder, remove it for production
    "show_ui_builder": True,
}

# 🎨 Jazzmin UI Tweaks for a more beautiful look
JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "navbar_fixed": True,
    "sidebar_fixed": True,
    "brand_small_text": False,
    "body_small_text": False,
    "sidebar_nav_small_text": False,
    "sidebar_nav_flat_style": True,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_disable_expand": False,
    "theme": "darkly",  # A sleek dark theme
    "dark_mode_theme": "darkly", # Use the same theme for dark mode
    "button_classes": {
        "primary": "btn-outline-primary",
        "secondary": "btn-outline-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
    },
    "actions_button_classes": {
        "outline-primary": "btn-primary",
        "primary": "btn-primary",
        "info": "btn-info",
        "success": "btn-success",
        "danger": "btn-danger"
    },
    "brand_color": "navbar-dark",
    "accent": "accent-indigo",
    "navbar": "navbar-dark navbar-indigo",
    "sidebar": "sidebar-dark-indigo",
    "footer_small_text": True,
}
