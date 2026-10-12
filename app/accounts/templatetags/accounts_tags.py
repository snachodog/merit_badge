from django import template

from accounts.services import is_admin as _is_admin

register = template.Library()


@register.filter
def is_admin(user):
    """Use as {% if user|is_admin %}."""
    return _is_admin(user)
