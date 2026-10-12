"""Model, service and admin tests for programs and requirements."""
import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from programs.models import (
    Award,
    AwardVersion,
    ImmutableVersionError,
    Program,
    ProgramOwner,
)
from requirements import services
from requirements.models import RequirementActionTag, RequirementNode, SourceRecord

pytestmark = pytest.mark.django_db

Status = AwardVersion.Status


@pytest.fixture
def award():
    owner = ProgramOwner.objects.create(name="Me", slug="me", owner_type="individual")
    program = Program.objects.create(owner=owner, name="Custom", slug="custom", is_custom=True, visibility="all")
    return Award.objects.create(program=program, name="Bread", slug="bread")


@pytest.fixture
def version(award):
    return AwardVersion.objects.create(award=award, version_label="1")


def add(version, num, parent=None, order=0, logic="single", count=None, **kw):
    return RequirementNode.objects.create(
        award_version=version, parent=parent, sort_order=order, display_number=num,
        text=f"Text {num}", completion_logic=logic, completion_count=count, **kw,
    )


def build_tree(version):
    root = add(version, "1", logic="all")
    a = add(version, "1a", root, 0)
    b = add(version, "1b", root, 1, logic="choose_n", count=1)
    b1 = add(version, "1b(1)", b, 0)
    add(version, "1b(2)", b, 1)
    add(version, "2", order=1)
    RequirementActionTag.objects.create(node=a, tag="explain", reviewed=True)
    return root, a, b, b1


def publish(version):
    services.submit_for_review(version)
    return services.publish_version(version)


# Traversal ----------------------------------------------------------------

def test_nested_traversal_and_display_numbers(version):
    build_tree(version)
    walked = [(n.display_number, d) for n, d in services.iter_tree(version)]
    assert walked == [("1", 0), ("1a", 1), ("1b", 1), ("1b(1)", 2), ("1b(2)", 2), ("2", 0)]


def test_get_tree_nests_children(version):
    build_tree(version)
    roots = services.get_tree(version)
    assert [r.node.display_number for r in roots] == ["1", "2"]
    assert [c.node.display_number for c in roots[0].children] == ["1a", "1b"]
    assert roots[0].children[1].children[0].depth == 2


def test_parent_must_be_same_version(award, version):
    other = AwardVersion.objects.create(award=award, version_label="2")
    foreign = add(other, "1", logic="all")
    with pytest.raises(ValidationError):
        add(version, "1a", foreign)
    node = RequirementNode(award_version=version, parent=foreign)
    with pytest.raises(ValidationError):
        node.full_clean()


# Publishing ---------------------------------------------------------------

def test_publish_valid_tree(version):
    build_tree(version)
    publish(version)
    version.refresh_from_db()
    assert version.status == Status.PUBLISHED and version.published_at


def test_publish_requires_review_first(version):
    build_tree(version)
    with pytest.raises(services.WorkflowError):
        services.publish_version(version)


def test_publish_rejects_invalid_tree_and_lists_problems(version):
    add(version, "1", logic="choose_n", count=5)
    add(version, "1a", RequirementNode.objects.get(display_number="1"), 0)
    services.submit_for_review(version)
    with pytest.raises(services.PublishError) as exc:
        services.publish_version(version)
    assert any("only 1 children" in p for p in exc.value.problems)
    version.refresh_from_db()
    assert version.status == Status.REVIEW


def test_empty_version_cannot_publish(version):
    services.submit_for_review(version)
    with pytest.raises(services.PublishError):
        services.publish_version(version)


def test_status_cannot_be_set_to_published_directly(version):
    build_tree(version)
    version.status = Status.PUBLISHED
    with pytest.raises(ImmutableVersionError):
        version.save()


def test_status_cannot_skip_review(version):
    build_tree(version)
    services.submit_for_review(version)
    services.return_to_draft(version)
    version.refresh_from_db()
    assert version.status == Status.DRAFT


def test_official_text_without_source_blocks_publish_unless_unverified(version):
    add(version, "1", text_origin="official_source")
    version.source_status = "reviewed"
    version.rights_status = "licensed"
    version.save()
    services.submit_for_review(version)
    with pytest.raises(services.PublishError) as exc:
        services.publish_version(version)
    assert any("no source record" in p for p in exc.value.problems)


def test_official_text_with_unknown_rights_blocks_publish(version):
    src = SourceRecord.objects.create(title="Book")
    add(version, "1", text_origin="official_source", source=src)
    version.source_status = "verified"
    version.save()
    services.submit_for_review(version)
    with pytest.raises(services.PublishError) as exc:
        services.publish_version(version)
    assert any("rights status" in p for p in exc.value.problems)


def test_official_text_with_source_and_rights_publishes(version):
    src = SourceRecord.objects.create(title="Book")
    add(version, "1", text_origin="official_source", source=src)
    version.source_status = "reviewed"
    version.rights_status = "permission_confirmed"
    version.save()
    publish(version)
    assert version.status == Status.PUBLISHED


def test_official_text_marked_unverified_publishes(version):
    add(version, "1", text_origin="official_source")
    assert version.source_status == "unverified" and version.rights_status == "unknown"
    publish(version)
    assert version.status == Status.PUBLISHED


def test_custom_text_needs_no_source(version):
    add(version, "1", text_origin="user_provided")
    version.source_status = "reviewed"
    version.save()
    publish(version)


# Immutability -------------------------------------------------------------

@pytest.fixture
def published(version):
    root, a, b, b1 = build_tree(version)
    publish(version)
    return version


def test_published_version_fields_cannot_change(published):
    published.change_summary = "sneaky"
    with pytest.raises(ImmutableVersionError):
        published.save()


def test_published_version_cannot_go_back_to_draft(published):
    published.status = Status.DRAFT
    with pytest.raises(ImmutableVersionError):
        published.save()


def test_published_version_cannot_be_deleted(published):
    with pytest.raises(ImmutableVersionError):
        published.delete()
    with pytest.raises(ImmutableVersionError):
        AwardVersion.objects.filter(pk=published.pk).delete()
    with pytest.raises(ImmutableVersionError):
        AwardVersion.objects.filter(pk=published.pk).update(version_label="x")


def test_published_node_cannot_be_edited_or_deleted(published):
    node = RequirementNode.objects.get(display_number="1a")
    node.text = "changed"
    with pytest.raises(ImmutableVersionError):
        node.save()
    with pytest.raises(ImmutableVersionError):
        node.delete()
    with pytest.raises(ImmutableVersionError):
        RequirementNode.objects.filter(pk=node.pk).update(text="x")
    with pytest.raises(ImmutableVersionError):
        RequirementNode.objects.filter(pk=node.pk).delete()
    assert RequirementNode.objects.get(pk=node.pk).text == "Text 1a"


def test_published_version_cannot_gain_nodes(published):
    with pytest.raises(ImmutableVersionError):
        add(published, "9")
    with pytest.raises(ImmutableVersionError):
        RequirementNode.objects.bulk_create([RequirementNode(award_version=published)])


def test_stale_in_memory_version_does_not_bypass_guard(published):
    stale = AwardVersion.objects.get(pk=published.pk)
    stale.status = Status.DRAFT  # tamper with the in-memory copy only
    node = RequirementNode(award_version=stale, display_number="x")
    with pytest.raises(ImmutableVersionError):
        node.save()


def test_node_cannot_be_moved_out_of_published_version(published, award):
    draft = AwardVersion.objects.create(award=award, version_label="d")
    node = RequirementNode.objects.get(display_number="2")
    node.award_version = draft
    with pytest.raises(ImmutableVersionError):
        node.save()


def test_published_action_tags_are_locked(published):
    node = RequirementNode.objects.get(display_number="1a")
    with pytest.raises(ImmutableVersionError):
        RequirementActionTag.objects.create(node=node, tag="read")
    with pytest.raises(ImmutableVersionError):
        node.action_tags.get().delete()


def test_archive_only_changes_status(published):
    services.archive_version(published)
    published.refresh_from_db()
    assert published.status == Status.ARCHIVED
    published.change_summary = "x"
    with pytest.raises(ImmutableVersionError):
        published.save()
    with pytest.raises(ImmutableVersionError):
        add(published, "9")


def test_archive_cannot_hide_other_edits(published):
    published.status = Status.ARCHIVED
    published.change_summary = "also edited"
    with pytest.raises(ImmutableVersionError):
        published.save()


def test_award_with_versions_cannot_be_deleted(published, award):
    from django.db.models import ProtectedError

    with pytest.raises(ProtectedError):
        award.delete()


def test_draft_nodes_stay_editable(version):
    node = add(version, "1")
    node.text = "ok"
    node.save()
    node.delete()


# Revisions ----------------------------------------------------------------

def test_revision_copies_tree_tags_and_links_back(published):
    draft = services.create_revision(published, change_summary="Fix typo")
    assert draft.status == Status.DRAFT
    assert draft.previous_version == published
    assert draft.change_summary == "Fix typo"
    assert draft.version_label == "1-rev1"
    old = [(n.display_number, d, n.text) for n, d in services.iter_tree(published)]
    new = [(n.display_number, d, n.text) for n, d in services.iter_tree(draft)]
    assert old == new
    assert not set(draft.nodes.values_list("pk", flat=True)) & set(
        published.nodes.values_list("pk", flat=True)
    )
    copied_b1 = draft.nodes.get(display_number="1b(1)")
    assert copied_b1.parent.award_version_id == draft.pk
    assert draft.nodes.get(display_number="1a").action_tags.get().tag == "explain"
    assert draft.published_at is None


def test_revision_is_editable_and_original_untouched(published):
    draft = services.create_revision(published)
    node = draft.nodes.get(display_number="1a")
    node.text = "Corrected"
    node.save()
    assert published.nodes.get(display_number="1a").text == "Text 1a"


def test_revision_labels_do_not_collide(published):
    first = services.create_revision(published)
    second = services.create_revision(published)
    assert first.version_label != second.version_label


def test_revision_needs_published_source(version):
    with pytest.raises(services.WorkflowError):
        services.create_revision(version)


def test_revision_can_be_published(published):
    draft = services.create_revision(published)
    publish(draft)
    assert draft.status == Status.PUBLISHED


# Admin --------------------------------------------------------------------

ADMIN_URLS = [
    "/admin/programs/programowner/",
    "/admin/programs/program/",
    "/admin/programs/award/",
    "/admin/programs/awardversion/",
    "/admin/requirements/requirementnode/",
    "/admin/requirements/sourcerecord/",
]


@pytest.mark.parametrize("url", ADMIN_URLS)
def test_admin_denies_anonymous(client, url):
    r = client.get(url)
    assert r.status_code == 302 and "/admin/login/" in r["Location"]


@pytest.mark.parametrize("url", ADMIN_URLS)
def test_admin_denies_non_staff(client, url):
    user = get_user_model().objects.create_user("plain", password="pw-12345-xyz")
    client.force_login(user)
    r = client.get(url)
    assert r.status_code == 302 and "/admin/login/" in r["Location"]


@pytest.fixture
def superuser_client(client):
    user = get_user_model().objects.create_superuser("root", "r@example.com", "pw-12345-xyz")
    client.force_login(user)
    return client


@pytest.mark.parametrize("url", ADMIN_URLS)
def test_admin_pages_load_for_superuser(superuser_client, url):
    assert superuser_client.get(url).status_code == 200


def test_admin_draft_version_is_editable(superuser_client, version):
    build_tree(version)
    r = superuser_client.get(f"/admin/programs/awardversion/{version.pk}/change/")
    assert r.status_code == 200
    assert b"1b(1)" in r.content


def test_admin_published_version_is_read_only(superuser_client, published):
    r = superuser_client.get(f"/admin/programs/awardversion/{published.pk}/change/")
    assert r.status_code == 200
    assert b'name="_save"' not in r.content
    r = superuser_client.post(
        f"/admin/programs/awardversion/{published.pk}/change/", {"change_summary": "x"}
    )
    assert r.status_code == 403
    r = superuser_client.post(f"/admin/programs/awardversion/{published.pk}/delete/", {"post": "yes"})
    assert r.status_code == 403
    published.refresh_from_db()
    assert published.change_summary == ""


def test_admin_published_node_is_read_only(superuser_client, published):
    node = published.nodes.get(display_number="1a")
    url = f"/admin/requirements/requirementnode/{node.pk}/change/"
    assert superuser_client.post(url, {"text": "x"}).status_code == 403
    assert superuser_client.post(url.replace("change", "delete"), {"post": "yes"}).status_code == 403
    assert RequirementNode.objects.filter(pk=node.pk).exists()


def test_admin_publish_action_reports_problems(superuser_client, version):
    add(version, "1", logic="all")  # group with no children
    services.submit_for_review(version)
    r = superuser_client.post(
        "/admin/programs/awardversion/",
        {"action": "publish", "_selected_action": [version.pk]},
        follow=True,
    )
    assert b"needs at least one child" in r.content
    version.refresh_from_db()
    assert version.status == Status.REVIEW
