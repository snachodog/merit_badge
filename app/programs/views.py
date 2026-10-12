from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from accounts import services as account_services
from accounts.services import AccountError
from . import services as program_services
from .forms import AwardForm, ProgramForm, SharingForm, VersionForm, unique_slug
from requirements import services
from requirements.models import RequirementNode

from .coverage import coverage_for_programs, program_coverage
from .models import Award, AwardVersion, Program, ProgramOwner
from .search import MAX_QUERY, search_awards


def personal_owner():
    owner, _ = ProgramOwner.objects.get_or_create(
        slug="self",
        defaults={"name": "Me", "owner_type": ProgramOwner.OwnerType.INDIVIDUAL},
    )
    return owner


@login_required
def catalog(request):
    q = request.GET.get("q", "").strip()[:MAX_QUERY]
    awards, text_hits = search_awards(q, request.user)
    programs = {}
    for award in awards:
        programs.setdefault(award.program, []).append(award)
    for award_list in programs.values():
        for award in award_list:
            award.version_rows = [
                (v, v.pk in text_hits) for v in sorted(award.versions.all(), key=lambda v: -v.pk)
            ]
    empty_programs = []
    if not q:
        empty_programs = list(program_services.visible_programs(request.user).exclude(pk__in=[p.pk for p in programs]))
    cov = {c.program_id: c for c in coverage_for_programs(list(programs) + empty_programs)}
    for p in list(programs) + empty_programs:
        p.coverage = cov[p.pk]
    return render(
        request,
        "catalog/catalog.html",
        {"q": q, "programs": programs, "empty_programs": empty_programs,
         "result_count": sum(len(a) for a in programs.values())},
    )


@login_required
def program_detail(request, pk):
    program = get_object_or_404(Program.objects.select_related("owner"), pk=pk)
    program_services.require_view(request.user, program)
    awards = program.awards.prefetch_related("versions")
    can_share = program_services.can_share(request.user, program)
    context = {
        "program": program, "awards": awards, "coverage": program_coverage(program),
        "can_edit": program_services.can_edit(request.user, program), "can_share": can_share,
    }
    if can_share:
        context["sharing_form"] = SharingForm(program=program)
    return render(request, "catalog/program_detail.html", context)


@login_required
@require_POST
def program_sharing(request, pk):
    program = get_object_or_404(Program, pk=pk)
    program_services.require_view(request.user, program)
    if not program_services.can_share(request.user, program):
        raise PermissionDenied("Only an admin can change sharing.")
    form = SharingForm(request.POST, program=program)
    if form.is_valid():
        try:
            program_services.set_visibility(
                request.user, program, form.cleaned_data["visibility"], form.cleaned_data["users"]
            )
            messages.success(request, "Sharing saved.")
        except AccountError as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "Sharing was not saved. Check the choices and try again.")
    return redirect("program_detail", pk=program.pk)


@login_required
@require_http_methods(["GET", "POST"])
def program_create(request):
    form = ProgramForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        owner = personal_owner()
        program = form.save(commit=False)
        program.owner = owner
        program.is_custom = True
        program.created_by = request.user
        program.visibility = Program.Visibility.PRIVATE
        program.status = Program.Status.ACTIVE
        program.slug = unique_slug(Program.objects.filter(owner=owner), program.name, "program")
        program.save()
        messages.success(request, "Program created. Add an award next.")
        return redirect("program_detail", pk=program.pk)
    return render(request, "catalog/form.html", {"form": form, "title": "New custom program"})


@login_required
@require_http_methods(["GET", "POST"])
def award_create(request, pk):
    program = get_object_or_404(Program, pk=pk)
    program_services.require_edit(request.user, program)
    form = AwardForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        award = form.save(commit=False)
        award.program = program
        award.status = Award.Status.ACTIVE
        award.slug = unique_slug(Award.objects.filter(program=program), award.name, "award")
        award.save()
        messages.success(request, "Award created. Add a draft version next.")
        return redirect("award_detail", pk=award.pk)
    return render(
        request, "catalog/form.html",
        {"form": form, "title": f"New award in {program.name}", "back_url": reverse("program_detail", args=[program.pk])},
    )


@login_required
def award_detail(request, pk):
    award = get_object_or_404(Award.objects.select_related("program"), pk=pk)
    program_services.require_view(request.user, award.program)
    versions = list(award.versions.all())
    for v in versions:
        v.source_urls = sorted(
            set(
                RequirementNode.objects.filter(award_version=v, source__isnull=False)
                .exclude(source__url="")
                .values_list("source__url", flat=True)
            )
        )
    current = next((v for v in versions if v.status == "published"), versions[0] if versions else None)
    tree = services.get_tree(current) if current else []
    return render(
        request,
        "catalog/award_detail.html",
        {"award": award, "versions": versions, "current": current, "tree": tree,
         "can_edit": program_services.can_edit(request.user, award.program)},
    )


@login_required
@require_http_methods(["GET", "POST"])
def version_create(request, pk):
    award = get_object_or_404(Award.objects.select_related("program"), pk=pk)
    program_services.require_edit(request.user, award.program)
    form = VersionForm(request.POST or None, award=award, initial={"version_label": "v1"})
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            version = form.save(commit=False)
            version.award = award
            version.status = AwardVersion.Status.DRAFT
            version.save()
        messages.success(request, "Draft version created. Add requirements below.")
        return redirect("version_edit", pk=version.pk)
    return render(
        request, "catalog/form.html",
        {"form": form, "title": f"New draft version of {award.name}", "back_url": reverse("award_detail", args=[award.pk])},
    )
