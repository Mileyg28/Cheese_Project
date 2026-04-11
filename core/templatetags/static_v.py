import os
from django import template
from django.templatetags.static import static
from django.conf import settings

register = template.Library()

@register.simple_tag
def static_v(path):
    """
    Igual que {% static %} pero agrega ?v=<timestamp> para forzar
    que el navegador descargue el archivo cuando cambie.
    """
    url = static(path)
    full_path = os.path.join(settings.BASE_DIR, "core", "static", path)

    try:
        mtime = int(os.path.getmtime(full_path))
    except OSError:
        mtime = 0

    return f"{url}?v={mtime}"