"""Roles, profiles, the last-admin rule, permissions and audit records."""
import importlib

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from accounts import services
from accounts.models import AuditRecord, Profile, Role
from evidence import services as ev
from learning import services as learning
from learning.models import RequirementProgress
from programs.models import Award, AwardVersion, Program, ProgramOwner
from requirements import services as req
from requirements.models import RequirementNode

pytestmark = pytest.mark.django_db
User = get_user_model()
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture(autouse=True)
def private_storage(settings, tmp_path):
    settings.STORAGES = {
        **settings.STORAGES,
        "evidence": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": str(tmp_path / "evidence")},
        },
    }


@pytest.fixture
def admin():
    return User.objects.create_user("boss", password="pw-long-enough-1")


@pytest.fixture
def alice(admin):
    return User.objects.create_user("alice", password="pw-long-enough-1")


@pytest.fixture
def bob(admin):
    return User.objects.create_user("bob", password="pw-long-enough-1")


def make_progress(user):
    owner, _ = ProgramOwner.objects.get_or_create(slug="me", defaults={"name": "Me", "owner_type": "individual"})
    program, _ = Program.objects.get_or_create(owner=owner, slug="c", defaults={"name": "C", "is_custom": True, "visibility": "all"})
    award, _ = Award.objects.get_or_create(program=program, slug="a", defaults={"name": "A"})
    v = AwardVersion.objects.filter(award=award).first()
    if v is None:
        v = AwardVersion.objects.create(award=award, version_label="1")
        RequirementNode.objects.create(award_version=v, display_number="1", text="t")
        req.submit_for_review(v)
        req.publish_version(v)
    plan = learning.start_plan(learning.create_plan(user, v))
    return RequirementProgress.objects.get(learning_plan=plan)


# Profiles -----------------------------------------------------------------------

def test_every_new_user_gets_a_profile(admin, alice):
    assert admin.profile.role == Role.ADMIN  # first user
    assert alice.profile.role == Role.USER


def test_staff_user_is_admin(admin):
    staff = User.objects.create_user("staffer", password="x", is_staff=True)
    assert staff.profile.role == Role.ADMIN


def test_migration_gives_existing_users_profiles():
    mod = importlib.import_module("accounts.migrations.0002_profiles_for_existing_users")
    first = User.objects.create_user("first", password="x")
    second = User.objects.create_user("second", password="x")
    Profile.objects.all().delete()

    class Apps:
        @staticmethod
        def get_model(app, name):
            return {"User": User, "Profile": Profile}[name]

    mod.create_profiles(Apps, None)
    assert Profile.objects.get(user=first).role == Role.ADMIN
    assert Profile.objects.get(user=second).role == Role.USER


def test_bootstrap_admin_creates_admin(monkeypatch):
    from django.core.management import call_command

    monkeypatch.setenv("BOOTSTRAP_ADMIN_USERNAME", "root")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "pw-long-enough-1")
    User.objects.create_user("earlier", password="x")  # already an admin (first user)
    call_command("bootstrap_admin")
    assert User.objects.get(username="root").profile.role == Role.ADMIN


# Last-admin rule ----------------------------------------------------------------

def test_last_admin_cannot_be_demoted_deactivated_or_deleted(admin, alice):
    with pytest.raises(services.AccountError):
        services.set_role(admin, admin, Role.USER)
    with pytest.raises(services.AccountError):
        services.deactivate(admin, admin)
    with pytest.raises(services.AccountError):
        services.delete_user(alice, admin)
    admin.refresh_from_db()
    assert admin.is_active and admin.profile.role == Role.ADMIN


def test_admin_can_be_changed_when_another_exists(admin, alice):
    services.set_role(admin, alice, Role.ADMIN)
    services.set_role(alice, admin, Role.USER)
    assert not services.is_admin(admin)
    with pytest.raises(services.AccountError):
        services.deactivate(admin, alice)  # alice is now the last one
    services.set_role(alice, admin, Role.ADMIN)
    services.deactivate(admin, alice)
    assert not User.objects.get(pk=alice.pk).is_active
    services.reactivate(admin, alice)
    assert User.objects.get(pk=alice.pk).is_active


def test_inactive_admin_does_not_count(admin, alice):
    services.set_role(admin, alice, Role.ADMIN)
    alice.is_active = False
    alice.save()
    with pytest.raises(services.AccountError):
        services.set_role(admin, admin, Role.USER)


def test_demote_through_view_shows_error(client, admin):
    client.force_login(admin)
    r = client.post(reverse("user_role", args=[admin.pk]), {"role": "user"}, follow=True)
    assert "last active admin" in r.content.decode()
    assert User.objects.get(pk=admin.pk).profile.role == Role.ADMIN


# Permissions --------------------------------------------------------------------

ADMIN_URLS = [("user_list", [])]


def test_anonymous_is_redirected(client):
    for name, args in ADMIN_URLS:
        r = client.get(reverse(name, args=args))
        assert r.status_code == 302 and "/accounts/login/" in r["Location"]


def test_non_admin_gets_403_on_admin_pages(client, admin, alice):
    client.force_login(alice)
    urls = [reverse("user_list")] + [
        reverse(n, args=[admin.pk]) for n in ("user_role", "user_active", "user_password")
    ]
    for url in urls:
        assert client.get(url).status_code == 403, url
        assert client.post(url, {"role": "admin"}).status_code == 403, url
    assert not services.is_admin(alice)


def test_non_admin_can_browse_and_see_settings_without_admin_sections(client, alice):
    client.force_login(alice)
    assert client.get(reverse("catalog")).status_code == 200
    assert client.get(reverse("my_learning")).status_code == 200
    assert client.get(reverse("achievement_list")).status_code == 200
    html = client.get(reverse("settings")).content.decode()
    assert "Export your data" in html
    assert 'id="users-h"' not in html and "Invitations" not in html
    home = client.get("/").content.decode()
    assert "New custom program" in home and "Import JSON" in home


def test_admin_sees_admin_sections_and_nav(client, admin, alice):
    client.force_login(admin)
    html = client.get(reverse("settings")).content.decode()
    assert 'id="users-h"' in html and "alice" in html and "Invitations" in html and "OIDC" in html
    assert "New custom program" in client.get("/").content.decode()
    assert client.get(reverse("program_create")).status_code == 200


def test_inactive_user_cannot_sign_in(client, admin, alice):
    services.deactivate(admin, alice)
    assert not client.login(username="alice", password="pw-long-enough-1")


# Privacy between users ----------------------------------------------------------

def test_user_cannot_read_another_users_data(client, admin, alice, bob):
    progress = make_progress(alice)
    rec = ev.add_file_evidence(
        alice, progress, SimpleUploadedFile("p.png", PNG, content_type="image/png"), title="mine"
    )
    plan = progress.learning_plan
    client.force_login(bob)
    assert client.get(reverse("plan_detail", args=[plan.pk])).status_code == 404
    assert client.get(reverse("progress_detail", args=[progress.pk])).status_code == 404
    assert client.get(reverse("evidence_download", args=[rec.pk])).status_code == 404
    assert client.post(reverse("evidence_delete", args=[rec.pk])).status_code == 404
    assert client.get(reverse("my_learning")).context["has_plans"] is False
    # an admin has no route to it either
    client.force_login(admin)
    assert client.get(reverse("plan_detail", args=[plan.pk])).status_code == 404
    assert client.get(reverse("evidence_download", args=[rec.pk])).status_code == 404


def test_achievement_and_export_are_per_user(client, alice, bob):
    from achievements.models import AchievementRecord

    progress = make_progress(alice)
    plan = progress.learning_plan
    plan.status = "personally_completed"
    plan.save(update_fields=["status"])
    record = AchievementRecord.objects.create(
        learning_plan=plan, achievement_type="custom", display_title="T", program_name="P",
        requirement_version_label="1", completed_at=timezone.now(), completion_basis="self_attested",
        disclaimer_text_version="1", learner_display_name="alice", issuer_name="alice",
    )
    client.force_login(bob)
    assert client.get(reverse("certificate", args=[record.pk])).status_code == 404
    assert record.pk not in [r.pk for r in client.get(reverse("achievement_list")).context["records"]]
    assert "alice" not in client.get(reverse("export_json")).content.decode()


# Audit and password reset -------------------------------------------------------

def test_audit_records_written(admin, alice):
    services.set_role(admin, alice, Role.ADMIN)
    services.deactivate(admin, alice)
    services.reactivate(admin, alice)
    services.reset_password(admin, alice, "another-long-pw-9")
    events = list(AuditRecord.objects.values_list("event", flat=True))
    for e in ("role_changed", "user_deactivated", "user_reactivated", "password_reset"):
        assert e in events
    rec = AuditRecord.objects.get(event="role_changed")
    assert rec.actor == admin and rec.target == alice and rec.detail == {"old": "user", "new": "admin"}


def test_admin_resets_password_through_form(client, admin, alice):
    client.force_login(admin)
    url = reverse("user_password", args=[alice.pk])
    bad = client.post(url, {"new_password": "short", "confirm_password": "short"})
    assert bad.status_code == 200 and "too short" in bad.content.decode()
    mismatch = client.post(url, {"new_password": "another-long-pw-9", "confirm_password": "different-pw-99"})
    assert "do not match" in mismatch.content.decode()
    ok = client.post(url, {"new_password": "another-long-pw-9", "confirm_password": "another-long-pw-9"})
    assert ok.status_code == 302
    alice.refresh_from_db()
    assert alice.check_password("another-long-pw-9")
    assert AuditRecord.objects.filter(event="password_reset", target=alice).exists()


def test_create_user_service(admin):
    u = services.create_user(admin, "newbie", password=None, role=Role.USER)
    assert u.profile.role == Role.USER and not u.has_usable_password()
    with pytest.raises(services.AccountError):
        services.create_user(admin, "NEWBIE")
    assert AuditRecord.objects.filter(event="user_created", target=u).exists()


# Program visibility and editing -------------------------------------------------

def make_program(creator, name="Mine", visibility="private", published=True):
    owner, _ = ProgramOwner.objects.get_or_create(slug="self", defaults={"name": "Me", "owner_type": "individual"})
    program = Program.objects.create(
        owner=owner, name=name, slug=name.lower(), is_custom=True, created_by=creator, visibility=visibility
    )
    award = Award.objects.create(program=program, name="A", slug="a")
    version = AwardVersion.objects.create(award=award, version_label="1")
    RequirementNode.objects.create(award_version=version, display_number="1", text="t")
    if published:
        req.submit_for_review(version)
        req.publish_version(version)
    return program, award, version


def authoring_urls(program, award, version):
    node = RequirementNode.objects.filter(award_version=version).first()
    return [
        reverse("award_create", args=[program.pk]),
        reverse("version_create", args=[award.pk]),
        reverse("version_edit", args=[version.pk]),
        reverse("version_meta", args=[version.pk]),
        reverse("version_delete", args=[version.pk]),
        reverse("node_add", args=[version.pk]),
        reverse("node_edit", args=[node.pk]),
        reverse("node_delete", args=[node.pk]),
    ]


def test_user_authors_own_program(client, alice):
    client.force_login(alice)
    assert client.get(reverse("program_create")).status_code == 200
    assert client.get(reverse("import_program")).status_code == 200
    r = client.post(reverse("program_create"), {"name": "Birding", "program_type": "", "description": ""})
    assert r.status_code == 302
    program = Program.objects.get(name="Birding")
    assert program.created_by == alice and program.visibility == "private"
    p, a, v = make_program(alice, "Hiking", published=False)
    for url in authoring_urls(p, a, v):
        assert client.get(url).status_code == 200, url


def test_user_cannot_see_another_users_private_program(client, admin, alice, bob):
    p, a, v = make_program(alice)
    client.force_login(bob)
    assert client.get(reverse("program_detail", args=[p.pk])).status_code == 404
    assert client.get(reverse("award_detail", args=[a.pk])).status_code == 404
    assert client.get(reverse("version_detail", args=[v.pk])).status_code == 404
    assert client.get(reverse("plan_start", args=[v.pk])).status_code == 404
    for url in authoring_urls(p, a, v):
        assert client.get(url).status_code == 404, url
    assert "Mine" not in client.get(reverse("catalog")).content.decode()
    assert client.get(reverse("catalog"), {"q": "Mine"}).context["result_count"] == 0


def test_admin_cannot_edit_or_see_another_users_private_program(client, admin, alice):
    p, a, v = make_program(alice)
    client.force_login(admin)
    assert client.get(reverse("program_detail", args=[p.pk])).status_code == 404
    for url in authoring_urls(p, a, v):
        assert client.get(url).status_code == 404, url
    assert client.post(reverse("program_sharing", args=[p.pk]), {"visibility": "all"}).status_code == 404
    p.refresh_from_db()
    assert p.visibility == "private"


def test_user_cannot_change_visibility(client, alice):
    p, a, v = make_program(alice)
    client.force_login(alice)
    r = client.post(reverse("program_sharing", args=[p.pk]), {"visibility": "all"})
    assert r.status_code == 403
    p.refresh_from_db()
    assert p.visibility == "private"
    assert "Sharing" not in client.get(reverse("program_detail", args=[p.pk])).content.decode()


def test_admin_shares_with_chosen_user_and_with_all(client, admin, alice, bob):
    carol = User.objects.create_user("carol", password="pw-long-enough-1")
    p, a, v = make_program(admin, "Shared")
    client.force_login(admin)
    assert "Sharing" in client.get(reverse("program_detail", args=[p.pk])).content.decode()
    url = reverse("program_sharing", args=[p.pk])
    assert client.post(url, {"visibility": "shared", "users": [alice.pk]}).status_code == 302
    assert Program.objects.visible_to(alice).filter(pk=p.pk).exists()
    assert not Program.objects.visible_to(bob).filter(pk=p.pk).exists()
    client.force_login(alice)
    assert client.get(reverse("program_detail", args=[p.pk])).status_code == 200
    assert client.get(reverse("plan_start", args=[v.pk])).status_code == 200
    assert client.get(reverse("version_edit", args=[v.pk])).status_code == 403  # read only
    client.force_login(bob)
    assert client.get(reverse("program_detail", args=[p.pk])).status_code == 404
    client.force_login(admin)
    client.post(url, {"visibility": "all"})
    client.force_login(bob)
    assert client.get(reverse("program_detail", args=[p.pk])).status_code == 200
    assert AuditRecord.objects.filter(event="program_visibility_changed").count() == 2


def test_plan_survives_when_program_becomes_private(client, admin, alice):
    p, a, v = make_program(admin, "Temp", visibility="all")
    plan = learning.start_plan(learning.create_plan(alice, v))
    from programs import services as ps
    ps.set_visibility(admin, p, "private")
    client.force_login(alice)
    assert client.get(reverse("plan_detail", args=[plan.pk])).status_code == 200


def test_seeded_programs_visible_to_all(client, alice, admin):
    from programs.management.commands.seed_scouting_catalog import seed
    from django.core.management import call_command

    seed()
    call_command("seed_tutorial")
    assert Program.objects.filter(created_by=None).exclude(visibility="all").count() == 0
    assert Program.objects.visible_to(alice).count() == Program.objects.count() > 0
    client.force_login(alice)
    tut = Program.objects.get(slug="merit-badge-help")
    assert client.get(reverse("program_detail", args=[tut.pk])).status_code == 200
    assert client.get(reverse("award_create", args=[tut.pk])).status_code == 403


def test_admin_edits_system_program(client, admin):
    p, a, v = make_program(None, "System", visibility="all", published=False)
    client.force_login(admin)
    assert client.get(reverse("version_edit", args=[v.pk])).status_code == 200


def test_import_into_another_users_program_is_refused(alice, bob):
    from requirements import importer
    from programs import tutorial

    data = tutorial.tutorial_data()
    data["program"]["owner"] = "self"
    data["import_key"] = "k/one"
    importer.commit_import(data, user=alice)
    data2 = tutorial.tutorial_data()
    data2["program"]["owner"] = "self"
    data2["award"]["slug"] = "other"
    data2["import_key"] = "k/two"
    _, report = importer.plan_import(data2, user=bob)
    assert not report.can_commit
