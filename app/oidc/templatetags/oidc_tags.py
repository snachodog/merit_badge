from django import template

from .. import services
from ..models import OIDCIdentity

register = template.Library()


@register.inclusion_tag("oidc/_login_button.html", takes_context=True)
def oidc_login_button(context):
    row = services.get_settings()
    return {"show": row.enabled and services.is_configured(row), "label": row.button_label}


@register.inclusion_tag("oidc/_invite_button.html", takes_context=True)
def oidc_invite_button(context):
    row = services.get_settings()
    return {"show": row.enabled and services.is_configured(row), "label": row.button_label}


@register.inclusion_tag("oidc/_admin_section.html", takes_context=True)
def oidc_admin_section(context):
    from ..views import settings_form

    request = context["request"]
    return {
        "oidc_form": context.get("oidc_form") or settings_form(),
        "oidc_redirect_uri": services.callback_uri(request),
        "csrf_token": context.get("csrf_token"),
    }


@register.inclusion_tag("oidc/_link_section.html", takes_context=True)
def oidc_link_section(context):
    user = context["request"].user
    row = services.get_settings()
    return {
        "available": row.enabled and services.is_configured(row),
        "linked": OIDCIdentity.objects.filter(user=user).exists(),
        "has_password": user.has_usable_password(),
        "csrf_token": context.get("csrf_token"),
    }
