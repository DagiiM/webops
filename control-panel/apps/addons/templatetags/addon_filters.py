from django import template

register = template.Library()

@register.filter
def replace_string(value, arg):
    """
    Replaces all occurrences of a substring with another substring.
    Usage:
    {{ value|replace_string:"old_string,new_string" }}
    """
    if isinstance(value, str) and isinstance(arg, str):
        try:
            old, new = arg.split(',', 1)
            return value.replace(old, new)
        except ValueError:
            return value
    return value