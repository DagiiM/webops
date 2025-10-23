from django import template

register = template.Library()

@register.filter
def js_array(value):
    """Convert a Python list to a JavaScript array string."""
    if not value:
        return '[]'
    
    # Convert each item to a properly escaped JavaScript string
    js_items = []
    for item in value:
        # Escape backslashes and quotes for JavaScript
        escaped = str(item).replace('\\', '\\\\').replace('"', '\\"')
        js_items.append(f'"{escaped}"')
    
    return f'[{", ".join(js_items)}]'