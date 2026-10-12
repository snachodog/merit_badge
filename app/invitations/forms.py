from django import forms
from django.contrib.auth.password_validation import validate_password

from accounts.models import Role

from .services import DEFAULT_DAYS, MAX_DAYS


class CreateInvitationForm(forms.Form):
    role = forms.ChoiceField(choices=Role.choices, initial=Role.USER)
    days = forms.IntegerField(
        label="Valid for (days)", min_value=1, max_value=MAX_DAYS, initial=DEFAULT_DAYS,
        help_text=f"1 to {MAX_DAYS} days.",
    )
    label = forms.CharField(label="Note (optional)", max_length=100, required=False,
                            help_text="Who the link is for. Only admins see this.")


class AcceptForm(forms.Form):
    username = forms.CharField(max_length=150, widget=forms.TextInput(attrs={"autocomplete": "username"}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))

    def clean(self):
        data = super().clean()
        p, c = data.get("password"), data.get("confirm_password")
        if p and c and p != c:
            self.add_error("confirm_password", "The two passwords do not match.")
        return data
