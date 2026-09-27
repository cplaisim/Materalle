from django import template

register = template.Library()

@register.filter
def get(dictionary, key):
    """Get a value from a dictionary using a key."""
    return dictionary.get(key, '')

@register.filter
def index(list_obj, i):
    """Get an item from a list by index."""
    try:
        return list_obj[i]
    except (IndexError, TypeError):
        return ''

@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary using bracket notation."""
    return dictionary.get(key, None)

@register.filter
def zip(a, b):
    return zip(a, b) 