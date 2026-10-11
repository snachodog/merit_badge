from django import forms


class SettingsForm(forms.Form):
    display_name = forms.CharField(
        max_length=100, required=False, label="Display name",
        help_text="Printed on your certificates. Leave blank to use your username.",
    )
