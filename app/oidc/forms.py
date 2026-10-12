from django import forms

from . import services


class OIDCSettingsForm(forms.Form):
    enabled = forms.BooleanField(required=False, label="Enable OIDC sign-in")
    issuer_url = forms.CharField(required=False, max_length=500, label="Issuer URL")
    client_id = forms.CharField(required=False, max_length=255, label="Client ID")
    client_secret = forms.CharField(
        required=False,
        label="Client secret",
        widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}),
    )
    scopes = forms.CharField(max_length=255, label="Scopes")
    button_label = forms.CharField(max_length=60, label="Button label")

    def __init__(self, *args, secret_set=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.secret_set = secret_set
        self.fields["client_secret"].help_text = (
            "A secret is set. Leave this blank to keep it." if secret_set else "No secret is set."
        )

    def clean_issuer_url(self):
        url = self.cleaned_data["issuer_url"].strip()
        if url:
            problem = services.issuer_problem(url)
            if problem:
                raise forms.ValidationError(problem)
        return url

    def clean_scopes(self):
        scopes = " ".join(self.cleaned_data["scopes"].split())
        if "openid" not in scopes.split():
            raise forms.ValidationError("Scopes must include openid.")
        return scopes

    def clean(self):
        data = super().clean()
        if data.get("enabled"):
            missing = []
            if not data.get("issuer_url"):
                missing.append("issuer URL")
            if not data.get("client_id", "").strip():
                missing.append("client ID")
            if not data.get("client_secret") and not self.secret_set:
                missing.append("client secret")
            if missing:
                raise forms.ValidationError(
                    "To enable OIDC sign-in, enter the " + ", ".join(missing) + "."
                )
        return data
