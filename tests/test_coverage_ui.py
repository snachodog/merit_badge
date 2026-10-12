"""Coverage is visible in the catalog UI and never claims completeness by default."""
import pytest
from django.contrib.auth import get_user_model

from programs.models import Award, AwardVersion, Program, ProgramOwner
from requirements.models import RequirementNode, SourceRecord

pytestmark = pytest.mark.django_db


def page(client, url):
    return " ".join(client.get(url).content.decode().split())


@pytest.fixture
def program(client):
    user = get_user_model().objects.create_user("u", password="x")
    client.force_login(user)
    owner = ProgramOwner.objects.create(name="O", slug="o", owner_type="organization")
    p = Program.objects.create(owner=owner, name="Prog", slug="prog")
    for i in range(2):
        a = Award.objects.create(program=p, name=f"A{i}", slug=f"a{i}", award_type="merit_badge")
        v = AwardVersion.objects.create(award=a, version_label="v1")
        if i == 0:
            src = SourceRecord.objects.create(title="s", url="https://example.org/src")
            RequirementNode.objects.create(award_version=v, text="x", source=src)
    return p


def test_catalog_list_shows_incomplete(client, program):
    html = page(client, "/catalog/")
    assert "Incomplete catalog coverage" in html
    assert "Complete (validated)" not in html
    assert "2 entries in the catalog: 0 validated, 2 not validated" in html
    assert "Expected total: unknown" in html


def test_program_detail_shows_counts_and_reasons(client, program):
    html = page(client, f"/programs/{program.pk}/")
    assert "Incomplete catalog coverage" in html
    assert "Complete (validated)" not in html
    assert "0 validated, 2 not validated" in html
    assert "The number of entries in the program is unknown." in html


def test_expected_count_shown(client, program):
    Program.objects.filter(pk=program.pk).update(catalog_expected_count=5)
    html = page(client, f"/programs/{program.pk}/")
    assert "Expected total: 5" in html
    assert "Entries missing: 3" in html


def test_award_detail_shows_source_url(client, program):
    a = Award.objects.get(slug="a0")
    html = page(client, f"/awards/{a.pk}/")
    assert "https://example.org/src" in html
    assert "Unverified" in html and "Unknown" in html


def test_award_detail_lists_requirements_without_personal_learning_callouts(client, program):
    from django.urls import reverse

    award = Award.objects.get(slug="a0")
    html = page(client, reverse("award_detail", args=[award.pk]))
    assert "<h2>Requirements" in html and 'class="text">x</span>' in html
    assert "This app records personal learning" not in html
    assert "written by you" not in html


def test_draft_version_can_be_deleted_and_published_cannot(client, program):
    from django.urls import reverse

    draft = AwardVersion.objects.get(award__slug="a0")
    r = client.post(reverse("version_delete", args=[draft.pk]))
    assert r.status_code == 302
    assert not AwardVersion.objects.filter(pk=draft.pk).exists()
    assert Award.objects.filter(slug="a0").exists()

    locked = AwardVersion.objects.get(award__slug="a1")
    AwardVersion.objects.filter(pk=locked.pk)  # status change bypasses guards only for drafts
    AwardVersion.objects.get(pk=locked.pk)
    from django.db import connection

    with connection.cursor() as cur:
        cur.execute("UPDATE programs_awardversion SET status='published' WHERE id=%s", [locked.pk])
    client.post(reverse("version_delete", args=[locked.pk]))
    assert AwardVersion.objects.filter(pk=locked.pk).exists()
