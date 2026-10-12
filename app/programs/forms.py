from django import forms
from django.utils.text import slugify

from .models import Award, AwardVersion, Program


def unique_slug(queryset, name, fallback):
    """A slug from `name` that is not used in `queryset`."""
    base = slugify(name)[:90] or fallback
    slug, n = base, 2
    while queryset.filter(slug=slug).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


class ProgramForm(forms.ModelForm):
    class Meta:
        model = Program
        fields = ["name", "program_type", "description"]
        labels = {"program_type": "Kind of program (optional)"}
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class AwardForm(forms.ModelForm):
    class Meta:
        model = Award
        fields = ["name", "award_type", "category", "description", "eligibility_notes"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "eligibility_notes": forms.Textarea(attrs={"rows": 2}),
        }


class VersionForm(forms.ModelForm):
    class Meta:
        model = AwardVersion
        fields = [
            "version_label", "effective_from", "effective_until", "source_status",
            "rights_status", "change_summary",
        ]
        labels = {"version_label": "Version label"}
        widgets = {
            "effective_from": forms.DateInput(attrs={"type": "date"}),
            "effective_until": forms.DateInput(attrs={"type": "date"}),
            "change_summary": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, award=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.award = award or self.instance.award

    def clean_version_label(self):
        label = self.cleaned_data["version_label"].strip()
        clash = AwardVersion.objects.filter(award=self.award, version_label=label)
        if self.instance.pk:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError("This award already has a version with that label.")
        return label


class SharingForm(forms.Form):
    visibility = forms.ChoiceField(choices=Program.Visibility.choices, label="Who can see this program")
    users = forms.ModelMultipleChoiceField(
        queryset=None, required=False, label="Shared with these users",
        help_text="Used only when sharing with chosen users.",
    )

    def __init__(self, *args, program, **kwargs):
        super().__init__(*args, **kwargs)
        from django.contrib.auth import get_user_model

        self.fields["users"].queryset = (
            get_user_model().objects.filter(is_active=True).exclude(pk=program.created_by_id).order_by("username")
        )
        self.initial = {
            "visibility": program.visibility,
            "users": list(program.shares.values_list("user_id", flat=True)),
        }
