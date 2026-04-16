# core/templatetags/filters.py

from django import template

register = template.Library()

@register.filter
def pesos(value):
    """Formatea un valor numérico como pesos colombianos.
    Muestra decimales solo si son distintos de cero.
    Ej: 1234567    → $ 1.234.567
        1234567.50 → $ 1.234.567,50
    """
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "$ 0"

    entero = int(value)
    centavos = round((value - entero) * 100)

    entero_formateado = f"{entero:,}".replace(",", ".")

    if centavos:
        return f"$ {entero_formateado},{centavos:02d}"
    return f"$ {entero_formateado}"