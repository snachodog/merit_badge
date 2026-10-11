"""Owner-scoped lookups. Every plan and progress query for a user goes through here.

Someone else's object gives a 404, never a 403, so its existence is not revealed.
"""
from django.shortcuts import get_object_or_404

from .models import LearningPlan, RequirementProgress


def plans_for(user):
    return LearningPlan.objects.filter(user=user)


def get_plan_for(user, pk):
    return get_object_or_404(plans_for(user), pk=pk)


def progress_for(user):
    return RequirementProgress.objects.filter(learning_plan__user=user)


def get_progress_for(user, pk):
    return get_object_or_404(progress_for(user).select_related("learning_plan"), pk=pk)
