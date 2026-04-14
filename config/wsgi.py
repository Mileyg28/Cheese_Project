"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os
from django.core.wsgi import get_wsgi_application

env = os.getenv('DJANGO_ENV', 'local')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', f'config.settings.{env}')

application = get_wsgi_application()
