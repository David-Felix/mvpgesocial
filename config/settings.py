from decouple import config, Csv
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

#SECRET_KEY = 'django-insecure-MUDE-ISSO-EM-PRODUCAO'
SECRET_KEY = config('SECRET_KEY')

#DEBUG = False
DEBUG = config('DEBUG', default=False, cast=bool)

#ALLOWED_HOSTS = ['benefix.duckdns.org', 'www.benefix.duckdns.org', '136.116.125.87', 'localhost', '127.0.0.1']
ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=Csv())

FIELD_ENCRYPTION_KEY = config('ENCRYPTION_KEY')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'beneficios',  # seu app
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

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'beneficios.context_processors.beneficios_ativos',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'beneficios_db',
        'USER': 'beneficios_user',
        'PASSWORD': 'SuaSenhaForte123',
        'HOST': 'localhost',
        'PORT': '5432',
	'OPTIONS': {
            'sslmode': 'prefer',  # Tenta SSL mas acerita sem se for necessario
        }

    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Security
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'SAMEORIGIN'

# CSRF (HTTP por enquanto, HTTPS depois)
CSRF_COOKIE_SECURE = True  # Mude para True após configurar SSL
SESSION_COOKIE_SECURE = True  # Mude para True após configurar SSL
CSRF_TRUSTED_ORIGINS = ['http://benefix.duckdns.org', 'http://136.116.125.87']
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'beneficios.User'

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'
