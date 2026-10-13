from django import template

from .. import services
from ..models import TutoringSession

register = template.Library()


@register.inclusion_tag("tutoring/_panel.html", takes_context=True)
def tutor_panel(context, progress):
    return {
        "available": services.is_available(),
        "progress": progress,
        "modes": TutoringSession.Mode.choices,
        "csrf_token": context.get("csrf_token"),
    }


@register.inclusion_tag("tutoring/_admin_section.html", takes_context=True)
def ai_admin_section(context):
    from ..views import settings_form

    return {"ai_form": context.get("ai_form") or settings_form(), "csrf_token": context.get("csrf_token")}
