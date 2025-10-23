"""
Template tags for rendering database installer interfaces.

These tags provide consistent installer interfaces across all templates,
following the pattern established in setup.sh.
"""

from django import template
from django.utils.safestring import mark_safe
from django.urls import reverse
from ..installer import DatabaseInstaller, DatabaseServiceInstaller
from ..adapters.base import DatabaseType

register = template.Library()


@register.inclusion_tag('databases/tags/dependency_status.html')
def dependency_status(db_type):
    """
    Render dependency status for a database type.
    
    Args:
        db_type: The database type to check
        
    Returns:
        Context for the dependency status template
    """
    try:
        db_type_enum = DatabaseType(db_type)
        dep_info = DatabaseInstaller.get_dependency_info(db_type_enum)
        
        return {
            'db_type': db_type,
            'dependencies': dep_info['dependencies'],
            'missing_deps': dep_info['missing'],
            'all_installed': dep_info['all_installed'],
            'install_commands': dep_info['install_commands'],
            'check_url': reverse('check_dependencies') + f'?db_type={db_type}'
        }
    except ValueError:
        return {
            'db_type': db_type,
            'dependencies': [],
            'missing_deps': [],
            'all_installed': True,
            'install_commands': {},
            'check_url': reverse('check_dependencies') + f'?db_type={db_type}',
            'error': f'Invalid database type: {db_type}'
        }


@register.inclusion_tag('databases/tags/install_button.html')
def install_button(db_type, dep=None, text=None, css_class=None):
    """
    Render an install button for a database type or specific dependency.
    
    Args:
        db_type: The database type
        dep: Optional specific dependency to install
        text: Optional button text
        css_class: Optional additional CSS classes
        
    Returns:
        Context for the install button template
    """
    if text is None:
        text = f"Install {dep}" if dep else f"Install {db_type.title()} Dependencies"
    
    if css_class is None:
        css_class = "webops-btn webops-btn-sm webops-btn-primary"
    
    return {
        'db_type': db_type,
        'dep': dep,
        'text': text,
        'css_class': css_class,
        'install_url': reverse('install_dependencies_ajax')
    }


@register.inclusion_tag('databases/tags/service_status.html')
def service_status(service_name):
    """
    Render status for a system service.
    
    Args:
        service_name: The name of the service to check
        
    Returns:
        Context for the service status template
    """
    is_running, status_output = DatabaseServiceInstaller.check_service_status(service_name)
    
    return {
        'service_name': service_name,
        'is_running': is_running,
        'status_output': status_output
    }


@register.inclusion_tag('databases/tags/addon_list.html')
def addon_list(db_type):
    """
    Render a list of available addons for a database type.
    
    Args:
        db_type: The database type to get addons for
        
    Returns:
        Context for the addon list template
    """
    from apps.addons.models import Addon
    
    available_addons = Addon.objects.filter(
        capabilities__contains=['database', db_type]
    )
    
    return {
        'db_type': db_type,
        'available_addons': available_addons
    }


@register.simple_tag
def dependency_check_url(db_type):
    """
    Get the URL for checking dependencies for a database type.
    
    Args:
        db_type: The database type
        
    Returns:
        The URL for checking dependencies
    """
    return reverse('check_dependencies') + f'?db_type={db_type}'


@register.simple_tag
def install_command(dependency):
    """
    Get the pip install command for a dependency.
    
    Args:
        dependency: The dependency to get the command for
        
    Returns:
        The pip install command
    """
    return DatabaseInstaller.get_install_command(dependency)


@register.filter
def dependency_status_class(all_installed):
    """
    Get the CSS class for dependency status.
    
    Args:
        all_installed: Whether all dependencies are installed
        
    Returns:
        The CSS class for the status
    """
    return 'webops-badge-success' if all_installed else 'webops-badge-warning'


@register.filter
def service_status_class(is_running):
    """
    Get the CSS class for service status.
    
    Args:
        is_running: Whether the service is running
        
    Returns:
        The CSS class for the status
    """
    return 'webops-badge-success' if is_running else 'webops-badge-error'


@register.simple_tag
def dependency_icon(all_installed):
    """
    Get the Material icon for dependency status.
    
    Args:
        all_installed: Whether all dependencies are installed
        
    Returns:
        The Material icon name
    """
    return 'check_circle' if all_installed else 'error'


@register.simple_tag
def service_icon(is_running):
    """
    Get the Material icon for service status.
    
    Args:
        is_running: Whether the service is running
        
    Returns:
        The Material icon name
    """
    return 'check_circle' if is_running else 'error'