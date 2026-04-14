from .base import *
import os

DEBUG = False

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '').split(',')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'Cheese23'),
        'USER': os.getenv('DB_USER', 'doadmin'),
        'PASSWORD': os.getenv('DB_PASSWORD', 'AVNS_e3HgoSglYvNL5InRatj'),
        'HOST': os.getenv('DB_HOST', 'db-cheese23-do-user-35853538-0.h.db.ondigitalocean.com'),
        'PORT': os.getenv('DB_PORT', '25060'),
        'OPTIONS': {
            'sslmode': 'require',
        },
    }
}

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
] + MIDDLEWARE