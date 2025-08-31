from django import template

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Retrieves an item from a dictionary by key.
    Usage: {{ my_dictionary|get_item:my_key }}
    """
    return dictionary.get(key)