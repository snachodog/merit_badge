from django import forms

from . import providers


class AISettingsForm(forms.Form):
    enabled = forms.BooleanField(required=False, label="Enable the AI tutor")
    base_url = forms.CharField(
        required=False, max_length=500, label="Endpoint URL",
        help_text="An OpenAI-compatible base URL, for example http://ollama:11434/v1",
    )
    model = forms.CharField(required=False, max_length=200, label="Model name")
    api_key = forms.CharField(
        required=False, label="API key",
        widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}),
    )
    clear_api_key = forms.BooleanField(required=False, label="Remove the saved key")

    def __init__(self, *args, key_set=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.key_set = key_set
        self.fields["api_key"].help_text = (
            "A key is set. Leave this blank to keep it." if key_set
            else "No key is set. Local models often need none."
        )

    def clean_base_url(self):
        url = self.cleaned_data["base_url"].strip()
        if url:
            problem = providers.base_url_problem(url)
            if problem:
                raise forms.ValidationError(problem)
        return url

    def clean(self):
        data = super().clean()
        if data.get("enabled"):
            missing = [n for n, k in (("endpoint URL", "base_url"), ("model name", "model")) if not data.get(k, "").strip()]
            if missing:
                raise forms.ValidationError("To enable the AI tutor, enter the " + " and ".join(missing) + ".")
        return data


class MessageForm(forms.Form):
    message = forms.CharField(
        max_length=2000, label="Your message",
        widget=forms.Textarea(attrs={"rows": 3}),
    )
