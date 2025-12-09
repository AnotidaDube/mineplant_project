from django import template

register = template.Library()

@register.filter
def index(sequence, position):
    """
    Returns the item at the given position from a list/tuple.
    Usage: {{ mylist|index:forloop.counter0 }}
    """
    try:
        return sequence[position]
    except (IndexError, TypeError):
        return None
