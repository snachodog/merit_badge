"""Display, search, authoring views and permissions."""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from programs.models import Award, AwardVersion, Program, ProgramOwner
from requirements import services
from requirements.models import RequirementActionTag, RequirementNode, SourceRecord

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return get_user_model().objects.create_user("me", password="pw-long-enough-1")


@pytest.fixture
def logged(client, user):
    client.force_login(user)
    return client


@pytest.fixture
def version():
    owner = ProgramOwner.objects.create(name="Me", slug="self", owner_type="individual")
    program = Program.objects.create(owner=owner, name="Gardening Club", slug="gc", is_custom=True, visibility="all")
    award = Award.objects.create(program=program, name="Herb Grower", slug="herb", description="Grow herbs")
    return AwardVersion.objects.create(award=award, version_label="v1")


def add(version, num, parent=None, order=0, **kw):
    kw.setdefault("text", f"Text {num}")
    return RequirementNode.objects.create(
        award_version=version, parent=parent, sort_order=order, display_number=num, **kw
    )


# Display ----------------------------------------------------------------------

def test_nested_display_shows_numbers_logic_tags_and_labels(logged, version):
    src = SourceRecord.objects.create(title="My notes", source_type="user_authored")
    root = add(version, "1", completion_logic="choose_n", completion_count=2,
               text="Do two of these.")
    a = add(version, "1a", root, 0, text="Plant basil.", text_origin="official_source", source=src)
    add(version, "1b", root, 1, text="Water it.", text_origin="app_authored")
    add(version, "1c", root, 2, text="Harvest.")
    RequirementActionTag.objects.create(node=a, tag="plan", reviewed=True)
    cond = add(version, "2", order=1, completion_logic="conditional", text="Extra.",
               condition_expression={"key": "age", "equals": "10"})
    add(version, "2a", cond, 0)
    html = logged.get(reverse("version_detail", args=[version.pk])).content.decode()
    assert "Choose 2 of these" in html
    assert "If age is 10, complete these" in html
    assert "1a" in html and "Plant basil." in html
    assert "Official text" in html
    assert "Not official text" not in html
    assert "Action tag" not in html
    assert "My notes" in html
    assert "Unverified" in html  # content review label
    assert html.count("<ol") >= 3  # nested lists


def test_login_required_everywhere(client, version):
    node = add(version, "1")
    urls = [
        reverse("catalog"), reverse("program_create"), reverse("import_program"),
        reverse("program_detail", args=[version.award.program_id]),
        reverse("award_detail", args=[version.award_id]),
        reverse("award_create", args=[version.award.program_id]),
        reverse("version_create", args=[version.award_id]),
        reverse("version_detail", args=[version.pk]),
        reverse("version_edit", args=[version.pk]),
        reverse("version_meta", args=[version.pk]),
        reverse("node_add", args=[version.pk]),
        reverse("node_edit", args=[node.pk]),
        reverse("node_delete", args=[node.pk]),
    ]
    for url in urls:
        r = client.get(url)
        assert r.status_code == 302 and r.url.startswith("/accounts/login/"), url


def test_anonymous_posts_change_nothing(client, version):
    node = add(version, "1")
    for url in [
        reverse("node_delete", args=[node.pk]),
        reverse("node_move", args=[node.pk]),
        reverse("version_action", args=[version.pk, "submit"]),
        reverse("program_create"),
    ]:
        r = client.post(url, {"name": "x", "direction": "down"})
        assert r.status_code == 302 and "/accounts/login/" in r.url
    assert RequirementNode.objects.filter(pk=node.pk).exists()
    version.refresh_from_db()
    assert version.status == "draft"
    assert Program.objects.count() == 1


# Search -----------------------------------------------------------------------

def test_search_by_name_description_and_requirement_text(logged, version):
    add(version, "1", text="Identify three kinds of mint")
    other = Award.objects.create(program=version.award.program, name="Knots", slug="knots")
    AwardVersion.objects.create(award=other, version_label="v1")
    url = reverse("catalog")
    assert "Herb Grower" in logged.get(url, {"q": "herb"}).content.decode()
    assert "Herb Grower" in logged.get(url, {"q": "grow"}).content.decode()  # description
    r = logged.get(url, {"q": "mint"}).content.decode()
    assert "Herb Grower" in r and "Matches requirement text" in r and "Knots" not in r
    assert "Herb Grower" in logged.get(url, {"q": "kinds"}).content.decode()
    assert "Nothing matches" in logged.get(url, {"q": "zzzz"}).content.decode()
    both = logged.get(url).content.decode()
    assert "Herb Grower" in both and "Knots" in both


def test_catalog_shows_status_and_review(logged, version):
    html = logged.get(reverse("catalog")).content.decode()
    assert "Draft" in html and "Source: Unverified" in html and "Rights: Unknown" in html


# Authoring --------------------------------------------------------------------

def test_create_program_award_version_and_nodes(logged):
    r = logged.post(reverse("program_create"), {"name": "Home Skills", "description": "d"})
    program = Program.objects.get()
    assert r.status_code == 302 and program.is_custom and program.owner.slug == "self"
    logged.post(reverse("award_create", args=[program.pk]), {"name": "Baker", "award_type": "custom"})
    award = Award.objects.get()
    logged.post(
        reverse("version_create", args=[award.pk]),
        {"version_label": "v1", "source_status": "unverified", "rights_status": "user_authored"},
    )
    version = AwardVersion.objects.get()
    assert version.status == "draft"
    base = {"node_type": "atomic", "text_origin": "user_provided", "completion_logic": "all"}
    logged.post(reverse("node_add", args=[version.pk]), {**base, "display_number": "1", "text": "Bake bread."})
    root = RequirementNode.objects.get()
    logged.post(
        reverse("node_add", args=[version.pk]) + f"?parent={root.pk}",
        {**base, "completion_logic": "single", "display_number": "1a", "text": "Knead.", "action_tags": ["make"]},
    )
    child = RequirementNode.objects.get(display_number="1a")
    assert child.parent_id == root.pk
    assert list(child.action_tags.values_list("tag", flat=True)) == ["make"]
    # edit
    logged.post(reverse("node_edit", args=[child.pk]), {**base, "completion_logic": "single",
                "display_number": "1a", "text": "Knead well."})
    child.refresh_from_db()
    assert child.text == "Knead well." and child.action_tags.count() == 0
    # edit page lists no problems; full workflow
    page = logged.get(reverse("version_edit", args=[version.pk])).content.decode()
    assert "No problems found" in page
    logged.post(reverse("version_action", args=[version.pk, "submit"]))
    logged.post(reverse("version_action", args=[version.pk, "publish"]))
    version.refresh_from_db()
    assert version.status == "published"
    # published: edits refused
    r = logged.post(reverse("node_edit", args=[child.pk]), {**base, "display_number": "1a", "text": "Changed"})
    assert r.status_code == 302
    child.refresh_from_db()
    assert child.text == "Knead well."
    logged.post(reverse("node_delete", args=[child.pk]))
    assert RequirementNode.objects.filter(pk=child.pk).exists()


def test_node_form_shows_errors(logged, version):
    r = logged.post(reverse("node_add", args=[version.pk]),
                    {"node_type": "atomic", "text_origin": "user_provided", "completion_logic": "choose_n", "text": "x"})
    assert r.status_code == 200
    assert "Choose N needs a count" in r.content.decode()
    assert RequirementNode.objects.count() == 0


def test_move_reorders_siblings(logged, version):
    a, b, c = add(version, "1"), add(version, "2", order=1), add(version, "3", order=2)
    logged.post(reverse("node_move", args=[c.pk]), {"direction": "up"})
    order = [n.display_number for n, _ in services.iter_tree(version)]
    assert order == ["1", "3", "2"]
    logged.post(reverse("node_move", args=[a.pk]), {"direction": "up"})  # already first
    assert [n.display_number for n, _ in services.iter_tree(version)] == ["1", "3", "2"]
    assert services.validate_version_tree(version) == []


def test_delete_removes_children(logged, version):
    root = add(version, "1", completion_logic="all")
    add(version, "1a", root)
    logged.post(reverse("node_delete", args=[root.pk]))
    assert RequirementNode.objects.count() == 0


def test_publish_failure_lists_every_problem(logged, version):
    add(version, "1", completion_logic="all")  # group without children
    add(version, "2", order=0)  # duplicate sort order
    add(version, "3", order=1, text_origin="official_source")  # no source, rights unknown
    version.source_status = "reviewed"
    version.save()
    page = logged.get(reverse("version_edit", args=[version.pk])).content.decode()
    assert "needs at least one child" in page
    assert "Sort order 0 is used by more than one sibling" in page
    assert "no source record" in page
    logged.post(reverse("version_action", args=[version.pk, "submit"]))
    r = logged.post(reverse("version_action", args=[version.pk, "publish"]), follow=True)
    html = r.content.decode()
    assert "cannot be published" in html and "needs at least one child" in html
    version.refresh_from_db()
    assert version.status == "review"


def test_revision_from_published(logged, version):
    add(version, "1")
    services.submit_for_review(version)
    services.publish_version(version)
    r = logged.post(reverse("version_action", args=[version.pk, "revise"]))
    draft = AwardVersion.objects.exclude(pk=version.pk).get()
    assert r.url == reverse("version_edit", args=[draft.pk]) and draft.status == "draft"
    assert draft.nodes.count() == 1
