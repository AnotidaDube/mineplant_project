from django import template

register = template.Library()

@register.filter
def zip_list(a, b):
    """Zip two lists together for template iteration"""
    try:
        return zip(a, b)
    except Exception:
        return []