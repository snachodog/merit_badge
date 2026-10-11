from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from . import services
from .models import AchievementRecord


def _records_for(user):
    return AchievementRecord.objects.filter(learning_plan__user=user).select_related(
        "learning_plan__award_version__award"
    )


@login_required
def achievement_list(request):
    return render(request, "achievements/list.html", {"records": _records_for(request.user)})


@login_required
def certificate(request, pk):
    """Printable certificate. Another account's record gives a 404."""
    record = get_object_or_404(_records_for(request.user), pk=pk)
    return render(request, "achievements/certificate.html", services.certificate_context(record))
