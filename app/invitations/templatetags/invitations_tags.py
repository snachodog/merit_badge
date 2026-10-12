from django import template

from invitations.forms import CreateInvitationForm
from invitations.models import Invitation

register = template.Library()


@register.inclusion_tag("invitations/_section.html", takes_context=True)
def invitations_section(context):
    return {
        "csrf_token": context.get("csrf_token"),
        "form": CreateInvitationForm(),
        "invitations": Invitation.objects.select_related("used_by", "created_by")[:50],
    }
