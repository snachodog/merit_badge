import datetime

from django import forms

from .models import EvidenceRecord
from .validation import ALLOWED_UPLOADS, max_upload_bytes

ET = EvidenceRecord.EvidenceType


class TextEvidenceForm(forms.Form):
    evidence_type = forms.ChoiceField(
        label="Kind of record",
        choices=[(ET.NOTE, "Note"), (ET.TEXT_RESPONSE, "Text response (your own answer)")],
    )
    title = forms.CharField(required=False, max_length=200, label="Title (optional)")
    description = forms.CharField(
        label="What you did or wrote", widget=forms.Textarea(attrs={"rows": 6})
    )


class LinkEvidenceForm(forms.Form):
    external_url = forms.URLField(label="Link (http:// or https://)", assume_scheme="https")
    title = forms.CharField(required=False, max_length=200, label="Title (optional)")
    description = forms.CharField(
        required=False, label="Why this link matters (optional)",
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class FileEvidenceForm(forms.Form):
    file = forms.FileField(label="File")
    title = forms.CharField(required=False, max_length=200, label="Title (optional)")
    description = forms.CharField(
        required=False, label="What this shows (optional)",
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["file"].help_text = (
            f"Largest file: {max_upload_bytes() // (1024 * 1024)} MB. "
            f"Allowed types: {', '.join(sorted(ALLOWED_UPLOADS))}."
        )


class TimeLogForm(forms.Form):
    date = forms.DateField(
        label="Date", widget=forms.DateInput(attrs={"type": "date"}),
        initial=datetime.date.today,
    )
    minutes = forms.IntegerField(label="Minutes", min_value=1, max_value=1440)
    note = forms.CharField(
        required=False, label="What you did (optional)", widget=forms.Textarea(attrs={"rows": 3})
    )

    def clean_date(self):
        value = self.cleaned_data["date"]
        if value > datetime.date.today():
            raise forms.ValidationError("The date cannot be in the future.")
        return value


class ObservationForm(forms.Form):
    reviewer_label = forms.CharField(
        max_length=200, label="Who observed this? (name or role)",
        help_text="Required. Use the name or role of a real person, such as 'Aunt Jo, nurse'.",
    )
    notes = forms.CharField(
        required=False, label="What they observed (optional)",
        widget=forms.Textarea(attrs={"rows": 3}),
    )
