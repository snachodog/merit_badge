import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import NoReverseMatch, reverse

pytestmark = pytest.mark.django_db


def test_healthz_ok_without_auth(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_healthz_reports_db_failure(client, monkeypatch):
    from django.db import connection

    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(connection, "cursor", boom)
    assert client.get("/healthz").status_code == 503


def test_home_requires_login(client):
    r = client.get("/")
    assert r.status_code == 302
    assert r["Location"].startswith("/accounts/login/")


def test_home_for_logged_in_user(client):
    get_user_model().objects.create_user("scout", password="pw-for-tests-123")
    client.login(username="scout", password="pw-for-tests-123")
    assert client.get("/").status_code == 200


def test_login_and_logout_flow(client):
    get_user_model().objects.create_user("scout", password="pw-for-tests-123")
    r = client.post("/accounts/login/", {"username": "scout", "password": "pw-for-tests-123"})
    assert r.status_code == 302
    assert client.post("/accounts/logout/").status_code == 302
    assert client.get("/").status_code == 302


@pytest.mark.parametrize("path", ["/accounts/register/", "/accounts/signup/", "/register/", "/signup/"])
def test_no_registration_routes(client, path):
    assert client.get(path).status_code == 404
    assert client.post(path, {}).status_code == 404


def test_no_registration_url_names():
    for name in ("register", "signup"):
        with pytest.raises(NoReverseMatch):
            reverse(name)


def test_bootstrap_admin_idempotent(monkeypatch):
    monkeypatch.setenv("BOOTSTRAP_ADMIN_USERNAME", "boss")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "pw-for-tests-123")
    call_command("bootstrap_admin")
    call_command("bootstrap_admin")
    assert get_user_model().objects.filter(username="boss", is_superuser=True).count() == 1
