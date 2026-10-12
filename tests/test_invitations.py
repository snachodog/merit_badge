"""Invitation links: hashing, single use, expiry, revoke, permissions, audit."""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from accounts.models import AuditRecord, Role
from accounts.services import AccountError
from invitations import services
from invitations.models import Invitation

pytestmark = pytest.mark.django_db
User = get_user_model()
GOOD = "Tr0ub4dor&3-long-pass"


@pytest.fixture
def admin():
    return User.objects.create_user("boss", password="pw-long-enough-1")


@pytest.fixture
def plain(admin):
    return User.objects.create_user("pat", password="pw-long-enough-2")


def make(admin, role=Role.USER, days=7, label=""):
    return services.create_invitation(admin, role, days, label)


def test_token_stored_hashed(admin):
    inv, raw = make(admin)
    assert len(raw) >= 43
    assert inv.token_hash == services.hash_token(raw)
    assert raw not in inv.token_hash
    assert not Invitation.objects.filter(token_hash=raw).exists()


def test_days_limits(admin):
    for bad in (0, 31, "x"):
        with pytest.raises(AccountError):
            make(admin, days=bad)


def test_accept_creates_user_with_role_and_is_single_use(admin, client):
    inv, raw = make(admin, Role.ADMIN)
    user = services.accept(raw, "newbie", GOOD)
    assert user.profile.role == Role.ADMIN
    inv.refresh_from_db()
    assert inv.status == "used" and inv.used_by == user
    with pytest.raises(services.InvitationError) as e:
        services.accept(raw, "other", GOOD)
    assert e.value.reason == "used"
    assert not User.objects.filter(username="other").exists()


def test_user_role_invitation(admin):
    _, raw = make(admin, Role.USER)
    assert services.accept(raw, "u1", GOOD).profile.role == Role.USER


def test_expired(admin):
    inv, raw = make(admin)
    Invitation.objects.filter(pk=inv.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
    with pytest.raises(services.InvitationError) as e:
        services.get_valid(raw)
    assert e.value.reason == "expired"


def test_revoke(admin):
    inv, raw = make(admin)
    services.revoke(admin, inv)
    with pytest.raises(services.InvitationError) as e:
        services.accept(raw, "x1", GOOD)
    assert e.value.reason == "revoked"
    with pytest.raises(AccountError):
        services.revoke(admin, inv)


def test_unknown_token_same_message(admin):
    with pytest.raises(services.InvitationError) as e:
        services.get_valid("nope")
    assert e.value.reason == "invalid" and e.value.message == services.GENERIC_MESSAGE


def test_failed_accept_does_not_use_invitation(admin):
    inv, raw = make(admin)
    with pytest.raises(AccountError):
        services.accept(raw, "x1", "123")
    inv.refresh_from_db()
    assert inv.status == "active"


def test_accept_with_user_hook(admin):
    inv, raw = make(admin)
    oidc_user = User.objects.create_user("oidc", password=None)
    services.accept_with_user(raw, oidc_user)
    inv.refresh_from_db()
    assert inv.used_by == oidc_user
    with pytest.raises(services.InvitationError):
        services.accept_with_user(raw, oidc_user)


def test_audit_records_without_token(admin):
    inv, raw = make(admin, label="for Sam")
    services.accept(raw, "sam", GOOD)
    inv2, raw2 = make(admin)
    services.revoke(admin, inv2)
    events = set(AuditRecord.objects.values_list("event", flat=True))
    assert {"invitation_created", "invitation_used", "invitation_revoked", "user_created"} <= events
    for rec in AuditRecord.objects.all():
        assert raw not in str(rec.detail) and raw2 not in str(rec.detail)
        assert inv.token_hash not in str(rec.detail)


def test_user_cannot_create_or_see(client, plain):
    client.force_login(plain)
    assert client.post(reverse("invitation_create"), {"role": "user", "days": 7}).status_code == 403
    inv, _ = make(User.objects.get(username="boss"), label="secret-note")
    assert client.post(reverse("invitation_revoke", args=[inv.pk])).status_code == 403
    page = client.get(reverse("settings"))
    assert b"secret-note" not in page.content and b"Invitations" not in page.content


def test_admin_creates_and_link_shown_once(client, admin):
    client.force_login(admin)
    r = client.post(reverse("invitation_create"), {"role": "user", "days": 3, "label": "for Sam"})
    assert r.status_code == 200
    link = r.context["link"]
    assert "/invite/" in link and link.startswith("http")
    token = link.rstrip("/").rsplit("/", 1)[1]
    assert token.encode() in r.content
    page = client.get(reverse("settings"))
    assert token.encode() not in page.content
    assert b"for Sam" in page.content and b"Active" in page.content


def test_admin_revoke_button(client, admin):
    inv, _ = make(admin)
    client.force_login(admin)
    client.post(reverse("invitation_revoke", args=[inv.pk]))
    inv.refresh_from_db()
    assert inv.status == "revoked"
    assert b"Revoked" in client.get(reverse("settings")).content


def test_accept_page_flow(client, admin):
    inv, raw = make(admin)
    url = reverse("invitation_accept", args=[raw])
    r = client.get(url)
    assert r.status_code == 200
    assert b"You were invited to Merit Badge" in r.content and b"boss" not in r.content
    assert client.session["invite_token"] == raw
    r = client.post(url, {"username": "sam", "password": GOOD, "confirm_password": GOOD})
    assert r.status_code == 302 and r["Location"] == reverse("home")
    assert client.get(reverse("home")).wsgi_request.user.username == "sam"
    again = client.get(url)
    assert again.status_code == 410 and services.GENERIC_MESSAGE.encode() in again.content


def test_accept_page_shows_password_errors(client, admin):
    _, raw = make(admin)
    url = reverse("invitation_accept", args=[raw])
    r = client.post(url, {"username": "sam", "password": "123", "confirm_password": "123"})
    assert r.status_code == 200 and b"errorlist" in r.content
    r = client.post(url, {"username": "sam", "password": GOOD, "confirm_password": GOOD + "x"})
    assert b"do not match" in r.content
    assert not User.objects.filter(username="sam").exists()


def test_bad_links_give_410(client):
    r = client.get(reverse("invitation_accept", args=["unknown-token"]))
    assert r.status_code == 410 and b"unknown-token" not in r.content


def test_second_concurrent_accept_fails(admin, monkeypatch):
    """The row lock makes the second accept see a used invitation."""
    _, raw = make(admin)
    services.accept(raw, "first", GOOD)
    with pytest.raises(services.InvitationError):
        services.accept(raw, "second", GOOD)
    assert User.objects.filter(username__in=["first", "second"]).count() == 1


def test_login_page_has_no_register_link(client):
    html = client.get(reverse("login")).content.lower()
    assert b"register" not in html and b"sign up" not in html and b"/invite/" not in html
