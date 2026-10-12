from django.contrib import messages
from django.db.models import ProtectedError
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from programs import services as program_services
from programs.forms import VersionForm
from programs.models import AwardVersion, ImmutableVersionError

from . import authoring, importer, services
from .forms import NodeForm
from .models import RequirementNode

Status = AwardVersion.Status


def _version(request, pk, edit=True):
    """Fetch a version the user may see (404 otherwise) and, for edits, may change (403)."""
    version = get_object_or_404(AwardVersion.objects.select_related("award", "award__program"), pk=pk)
    program = version.award.program
    (program_services.require_edit if edit else program_services.require_view)(request.user, program)
    return version


def _origin_counts(version):
    counts = {}
    for row in RequirementNode.objects.filter(award_version=version).values_list("text_origin", flat=True):
        counts[row] = counts.get(row, 0) + 1
    labels = dict(RequirementNode.TextOrigin.choices)
    return [(labels[k], v) for k, v in counts.items()]


@login_required
def version_detail(request, pk):
    """Learner view: the requirement tree with its source and review labels."""
    version = _version(request, pk, edit=False)
    return render(
        request,
        "requirements/version_detail.html",
        {
            "version": version,
            "award": version.award,
            "tree": services.get_tree(version),
            "origin_counts": _origin_counts(version),
            "can_edit": program_services.can_edit(request.user, version.award.program),
            "editing": False,
        },
    )


@login_required
def version_edit(request, pk):
    """Authoring view: the same tree with edit controls, and the publish workflow."""
    version = _version(request, pk)
    problems = []
    if version.status in (Status.DRAFT, Status.REVIEW):
        problems = services.publish_problems(version)
    return render(
        request,
        "requirements/version_edit.html",
        {
            "version": version,
            "award": version.award,
            "tree": services.get_tree(version),
            "origin_counts": _origin_counts(version),
            "editing": version.status == Status.DRAFT,
            "problems": problems,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def version_meta(request, pk):
    version = _version(request, pk)
    if version.status != Status.DRAFT:
        messages.error(request, f"The version is {version.status}. Only a draft can be edited.")
        return redirect("version_edit", pk=pk)
    form = VersionForm(request.POST or None, instance=version)
    if request.method == "POST" and form.is_valid():
        try:
            form.save()
        except ImmutableVersionError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Version details saved.")
        return redirect("version_edit", pk=pk)
    return render(
        request, "catalog/form.html",
        {"form": form, "title": "Version details", "back_url": reverse("version_edit", args=[version.pk])},
    )


def _refuse_if_not_draft(request, version):
    try:
        authoring.assert_editable(version)
    except ImmutableVersionError as exc:
        messages.error(request, str(exc))
        return redirect("version_edit", pk=version.pk)
    return None


@login_required
@require_http_methods(["GET", "POST"])
def node_add(request, pk):
    version = _version(request, pk)
    refused = _refuse_if_not_draft(request, version)
    if refused:
        return refused
    parent = None
    if request.GET.get("parent"):
        parent = get_object_or_404(RequirementNode, pk=request.GET["parent"], award_version=version)
    node = RequirementNode(award_version=version, parent=parent)
    form = NodeForm(request.POST or None, instance=node)
    if request.method == "POST" and form.is_valid():
        try:
            authoring.save_node(form.instance, version, parent, form.cleaned_data["action_tags"])
        except ImmutableVersionError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Requirement added.")
        return redirect("version_edit", pk=pk)
    title = f"Add a requirement under {parent.display_number or 'the selected group'}" if parent else "Add a top-level requirement"
    return render(
        request, "requirements/node_form.html",
        {"form": form, "title": title, "version": version},
    )


@login_required
@require_http_methods(["GET", "POST"])
def node_edit(request, pk):
    node = get_object_or_404(RequirementNode.objects.select_related("award_version__award__program"), pk=pk)
    program_services.require_edit(request.user, node.award_version.award.program)
    version = node.award_version
    refused = _refuse_if_not_draft(request, version)
    if refused:
        return refused
    form = NodeForm(request.POST or None, instance=node)
    if request.method == "POST" and form.is_valid():
        try:
            authoring.save_node(form.instance, version, node.parent, form.cleaned_data["action_tags"])
        except ImmutableVersionError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Requirement saved.")
        return redirect("version_edit", pk=version.pk)
    return render(
        request, "requirements/node_form.html",
        {"form": form, "title": f"Edit requirement {node.display_number}".strip(), "version": version},
    )


@login_required
@require_http_methods(["GET", "POST"])
def node_delete(request, pk):
    node = get_object_or_404(RequirementNode.objects.select_related("award_version__award__program"), pk=pk)
    program_services.require_edit(request.user, node.award_version.award.program)
    version = node.award_version
    refused = _refuse_if_not_draft(request, version)
    if refused:
        return refused
    if request.method == "POST":
        try:
            authoring.delete_node(node)
        except ImmutableVersionError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Requirement deleted.")
        return redirect("version_edit", pk=version.pk)
    return render(
        request, "requirements/node_delete.html",
        {"node": node, "version": version, "child_count": node.children.count()},
    )


@login_required
@require_POST
def node_move(request, pk):
    node = get_object_or_404(RequirementNode.objects.select_related("award_version__award__program"), pk=pk)
    program_services.require_edit(request.user, node.award_version.award.program)
    direction = request.POST.get("direction")
    if direction not in ("up", "down"):
        messages.error(request, "The direction must be up or down.")
    else:
        try:
            authoring.move_node(node, direction)
        except ImmutableVersionError as exc:
            messages.error(request, str(exc))
    return redirect("version_edit", pk=node.award_version_id)


@login_required
@require_http_methods(["GET", "POST"])
def version_delete(request, pk):
    """Delete a draft or review version. Published and archived versions stay."""
    version = _version(request, pk)
    award = version.award
    if version.status in AwardVersion.LOCKED_STATUSES:
        messages.error(
            request,
            "Published and archived versions cannot be deleted. Plans and records may depend on them.",
        )
        return redirect("version_edit", pk=version.pk)
    if request.method == "POST":
        try:
            version.delete()
        except (ImmutableVersionError, ProtectedError) as exc:
            messages.error(request, f"This version cannot be deleted: {exc}")
            return redirect("version_edit", pk=version.pk)
        messages.success(request, f"Version {version.version_label} deleted.")
        return redirect("award_detail", pk=award.pk)
    return render(
        request,
        "requirements/version_delete.html",
        {"version": version, "award": award, "node_count": version.nodes.count()},
    )


WORKFLOW = {
    "submit": (services.submit_for_review, "Submitted for review."),
    "return": (services.return_to_draft, "Returned to draft."),
    "publish": (services.publish_version, "Published. This version can no longer be edited."),
    "archive": (services.archive_version, "Archived."),
}


@login_required
@require_POST
def version_action(request, pk, action):
    version = _version(request, pk)
    if action == "revise":
        try:
            draft = services.create_revision(version)
        except services.WorkflowError as exc:
            messages.error(request, str(exc))
            return redirect("version_edit", pk=pk)
        messages.success(request, "A new draft revision was created from the published version.")
        return redirect("version_edit", pk=draft.pk)
    if action not in WORKFLOW:
        messages.error(request, "Unknown action.")
        return redirect("version_edit", pk=pk)
    func, done = WORKFLOW[action]
    try:
        if action == "submit":
            # Show every problem now, so the review step is not a surprise.
            problems = services.publish_problems(version)
            if problems:
                messages.warning(
                    request,
                    "Submitted for review with open problems. They must be fixed before publishing.",
                )
        func(version)
    except services.PublishError as exc:
        messages.error(request, "The version cannot be published. See the list of problems below.")
        for problem in exc.problems:
            messages.error(request, problem)
    except (services.WorkflowError, ImmutableVersionError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, done)
    return redirect("version_edit", pk=pk)


# Import ---------------------------------------------------------------------------

SESSION_KEY = "import_pending"


@login_required
@require_http_methods(["GET", "POST"])
def import_program(request):
    context = {"max_kib": importer.MAX_BYTES // 1024, "report": None}
    if request.method == "POST":
        if request.POST.get("action") == "commit":
            pending = request.session.get(SESSION_KEY)
            if not pending:
                messages.error(request, "There is no checked file to import. Upload it again.")
                return redirect("import_program")
            try:
                version = importer.commit_import(pending, user=request.user)
            except importer.ImportRefused as exc:
                context["report"] = exc.report
                messages.error(request, "The import was refused. See the report.")
                return render(request, "requirements/import.html", context, status=409)
            request.session.pop(SESSION_KEY, None)
            messages.success(request, "Imported as a draft version. Check it, then submit it for review.")
            return redirect("version_edit", pk=version.pk)
        upload = request.FILES.get("file")
        request.session.pop(SESSION_KEY, None)
        if upload is None:
            messages.error(request, "Choose a JSON file to check.")
            return render(request, "requirements/import.html", context, status=400)
        if upload.size > importer.MAX_BYTES:
            report = importer.Report()
            report.error("", f"The file is larger than {importer.MAX_BYTES // 1024} KiB.")
            context["report"] = report
            return render(request, "requirements/import.html", context, status=400)
        raw = upload.read(importer.MAX_BYTES + 1)
        data, report = importer.plan_import(raw, user=request.user)
        context["report"] = report
        context["filename"] = upload.name
        if report.can_commit:
            request.session[SESSION_KEY] = data
        return render(request, "requirements/import.html", context, status=400 if report.errors else 200)
    return render(request, "requirements/import.html", context)
