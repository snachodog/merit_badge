from django import forms

from .models import Role


class RoleForm(forms.Form):
    role = forms.ChoiceField(choices=Role.choices)


class PasswordResetForm(forms.Form):
    new_password = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))

    def clean(self):
        data = super().clean()
        if data.get("new_password") != data.get("confirm_password"):
            raise forms.ValidationError("The two passwords do not match.")
        return data
