from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .forms import AwardForm, ProgramForm, VersionForm, unique_slug
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
    awards, text_hits = search_awards(q)
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
        empty_programs = Program.objects.exclude(pk__in=[p.pk for p in programs])
    return render(
        request,
        "catalog/catalog.html",
        {"q": q, "programs": programs, "empty_programs": empty_programs,
         "result_count": sum(len(a) for a in programs.values())},
    )


@login_required
def program_detail(request, pk):
    program = get_object_or_404(Program.objects.select_related("owner"), pk=pk)
    awards = program.awards.prefetch_related("versions")
    return render(request, "catalog/program_detail.html", {"program": program, "awards": awards})


@login_required
@require_http_methods(["GET", "POST"])
def program_create(request):
    form = ProgramForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        owner = personal_owner()
        program = form.save(commit=False)
        program.owner = owner
        program.is_custom = True
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
    return render(request, "catalog/award_detail.html", {"award": award, "versions": award.versions.all()})


@login_required
@require_http_methods(["GET", "POST"])
def version_create(request, pk):
    award = get_object_or_404(Award, pk=pk)
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
