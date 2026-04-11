# core/templatetags/filters.py

from django import template

register = template.Library()

@register.filter
def pesos(value):
    """Formatea un valor numérico como pesos colombianos. Ej: 1234567.89 → $ 1.234.567,89"""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "$ 0,00"

    # Separar parte entera y decimal
    entero = int(value)
    decimales = round((value - entero) * 100)

    # Formatear parte entera con puntos como separador de miles
    entero_formateado = f"{entero:,}".replace(",", ".")

    return f"$ {entero_formateado},{decimales:02d}"