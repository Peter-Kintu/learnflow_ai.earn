import os
from pathlib import Path
import dj_database_url
from decouple import config


BASE_DIR = Path(__file__).resolve().parent.parent

# --- CORE SECURITY & ENVIRONMENT CONFIGURATION ---
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-fallback-key')
DEBUG = os.environ.get('DJANGO_DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost,learnflow-ai-0fdz.onrender.com').split(',')

CSRF_TRUSTED_ORIGINS = ['https://learnflow-ai-0fdz.onrender.com']

#  Installed Apps
INSTALLED_APPS = [
    # --- ADDED: CSP ---
    'csp',
    # ------------------
    'legalpages',
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'cloudinary_storage',
    'cloudinary',
    'aiapp',
    'video',
    'user',
    'book',
]

#  Middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # Middleware case corrected
    'csp.middleware.CSPMiddleware', 
    # ---------------------------------------------
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    # 'django.middleware.clickjacking.XFrameOptionsMiddleware', # REMOVED: Replaced by CSP_FRAME_ANCESTORS
]

ROOT_URLCONF = 'learnflow_ai.urls'

#  Templates (Cleaned up context_processors to fix admin.E404)
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [os.path.join(BASE_DIR, 'user', 'templates'),
             os.path.join(BASE_DIR, 'templates'), 
             ],
    
    'APP_DIRS': True,
    'OPTIONS': {
        # 🚨 BUILD FIX: Clean rewrite of context processors list to fix admin.E404
        'context_processors': [
            'django.template.context_processors.debug',
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
        ],
    },
}]

WSGI_APPLICATION = 'learnflow_ai.wsgi.application'

#  Database (Neon.tech or fallback)
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    DATABASES = {
        'default': {
            # Syntax corrected for OPTIONS merging
            **dj_database_url.config(
                default=DATABASE_URL,
                conn_max_age=600,
                ssl_require=True,
            ),
            # Add connection timeout for resilience in cloud environments
            'OPTIONS': {
                'connect_timeout': 10,
            },
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# 🔐 Password Validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
DEBUG_PROPAGATE_EXCEPTIONS = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- SECURITY HEADERS ---
SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True # Adds X-Content-Type-Options: nosniff
SECURE_BROWSER_XSS_FILTER = True # Adds X-XSS-Protection
SESSION_COOKIE_HTTPONLY = True # Adds httponly directive to session cookie
CSRF_COOKIE_HTTPONLY = True    # Adds httponly directive to CSRF cookie
USE_ETAGS = True               # Helps with Cache-Control/Expires warnings

SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Pro-Level Additions for Enhanced Security
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin' # Mitigates referrer leakage
SECURE_PERMISSIONS_POLICY = { # Limits access to sensitive browser features
    "geolocation": "()",
    "camera": "()",
    "microphone": "()",
    "payment": "()", # Common feature to disable
}

# Elite Enhancement: Session Expiry Settings for tighter security
SESSION_EXPIRE_AT_BROWSER_CLOSE = True # Forces users to log in after closing the browser
SESSION_COOKIE_AGE = 3600             # Sets session to expire after 1 hour of inactivity

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

#  Localization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Kampala'
USE_I18N = True
USE_TZ = True

# Static & Media
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

# Logging (for template/static errors)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG',
    },
}

#  Auth Redirects
LOGIN_URL = 'user:login'
LOGIN_REDIRECT_URL = 'video:video_list'
LOGOUT_REDIRECT_URL = 'user:login'

# External API Configurations
BACKEND_API_URL = os.environ.get('BACKEND_API_URL', 'https://secretary-ai-backend.onrender.com')
WHITENOISE_ROOT = os.path.join(BASE_DIR, 'public')


# --- Content Security Policy (CSP) Configuration (django-csp v4.0+ format) ---
CONTENT_SECURITY_POLICY = {
    'DIRECTIVES': {
        'default-src': ("'self'",),
        'script-src': (
            "'self'",
            "'unsafe-inline'", 
            # ✅ CSP FIX: Allows 'eval()' for external scripts like Google Ads.
            "'unsafe-eval'", 
            'https://pagead2.googlesyndication.com', 
            'https://fundingchoicesmessages.google.com', 
            'https://cdn.tailwindcss.com',
            'https://unpkg.com',
            'https://cdnjs.cloudflare.com',
            'https://ep1.adtrafficquality.google',
            'https://ep2.adtrafficquality.google', 
            'https://googleads.g.doubleclick.net',
            # Re-added core Google domains
            'https://www.google.com',
            'https://www.gstatic.com',
        ),
        'style-src': (
            "'self'",
            "'unsafe-inline'",
            'https://unpkg.com',
            'https://cdnjs.cloudflare.com',
            'https://fonts.googleapis.com', 
        ),
        'font-src': (
            "'self'",
            'https://fonts.gstatic.com',
        ),
        'frame-src': (
            "'self'",
            'https://www.youtube.com',
            'https://tpc.googlesyndication.com', 
            'https://googleads.g.doubleclick.net',
            'https://fundingchoicesmessages.google.com',
            'https://www.google.com',
            'https://ep2.adtrafficquality.google',
        ),
        'img-src': (
            "'self'",
            'data:',
            'https://pagead2.googlesyndication.com',
            'https://i.ytimg.com',
            'https://ep1.adtrafficquality.google',
            'https://ep2.adtrafficquality.google', 
        ),
        'connect-src': (
            "'self'",
            'https://generativelanguage.googleapis.com', 
            'https://fundingchoicesmessages.google.com',
            'https://pagead2.googlesyndication.com',
            'https://ep1.adtrafficquality.google',
            'https://ep2.adtrafficquality.google', 
            BACKEND_API_URL,
            'https://www.google.com',
            'https://www.gstatic.com',
        ),
        'frame-ancestors': ("'self'",),
    }
}
#  Jazzmin Admin
JAZZMIN_SETTINGS = {
    "site_title": "LearnFlow Admin",
    "site_header": "LearnFlow",
    "site_brand": "LearnFlow",
    "site_logo": "static/images/learnflow_logo.png",
    "site_icon": "static/images/favicon.ico",
    "welcome_sign": "Welcome to LearnFlow — where every click is a step toward wisdom.",
    "search_model": ["auth.User", "aiapp.Question", "video.Video", "book.Book"],
    "user_avatar": None,
    "topmenu_links": [
        {"name": "Dashboard", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "Support", "url": "https://github.com/farkasgabor/django-jazzmin/issues", "new_window": True},
        {"model": "auth.User"},
        {"model": "aiapp.Question"},
        {"model": "video.Video"},
        {"model": "book.Book"},
    ],
    "show_sidebar": True,
    "navigation_expanded": True,
    "order_with_respect_to": ["auth", "aiapp", "video", "user", "book"],
    "hide_apps": ["contenttypes", "sessions"],
    "hide_models": [],
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "aiapp.Choice": "fas fa-check-square",
        "aiapp.Question": "fas fa-question-circle",
        "aiapp.Quiz": "fas fa-puzzle-piece",
        "aiapp.StudentAnswer": "fas fa-edit",
        "video.Video": "fas fa-video",
        "book.Book": "fas fa-book-open",
    },
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
    "related_modal_active": False
}

#  Jazzmin UI Tweaks
JAZZMIN_UI_TWEAKS = {
    "theme": "darkly",
    "dark_mode_theme": "darkly",
    "accent": "accent-primary",
    "navbar": "navbar-dark",
    "sidebar": "sidebar-dark-primary",
    "button_classes": {
        "primary": "btn-outline-primary",
        "secondary": "btn-outline-secondary",
        "info": "btn-outline-info",
        "warning": "btn-outline-warning",
        "danger": "btn-outline-danger",
        "success": "btn-outline-success"
    },
    "actions_button_classes": {
        "add": "btn-success",
        "change": "btn-info",
        "delete": "btn-danger",
        "save": "btn-primary",
        "submit": "btn-primary",
    },
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "no_navbar_border": False,
    "navbar_fixed": False,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": False,
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": False,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'