from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary using bracket notation."""
    return dictionary.get(key, '')


@register.filter
def get_day(dictionary, day):
    """Get a day's data from a row dictionary."""
    if isinstance(dictionary, dict):
        return dictionary.get(day)
    return None


@register.filter
def get_key(obj, key):
    """Get a key from a dict-like object."""
    if isinstance(obj, dict):
        return obj.get(key, '')
    return ''