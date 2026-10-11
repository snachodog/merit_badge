from django import forms

from .models import RequirementProgress


class PlanStartForm(forms.Form):
    title_override = forms.CharField(
        required=False, max_length=200, label="Plan title (optional)",
        help_text="Leave blank to use the award name.",
    )
    target_date = forms.DateField(
        required=False, label="Target date (optional)",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    notes = forms.CharField(
        required=False, label="Plan notes (optional)", widget=forms.Textarea(attrs={"rows": 3})
    )


class StatusForm(forms.Form):
    status = forms.ChoiceField(label="New status")

    def __init__(self, *args, allowed=(), **kwargs):
        super().__init__(*args, **kwargs)
        labels = dict(RequirementProgress.Status.choices)
        self.fields["status"].choices = [(s, labels[s]) for s in allowed]


class PriorKnowledgeForm(forms.Form):
    prior_knowledge_claim = forms.BooleanField(
        required=False, label="I already know this."
    )
    prior_work_notes = forms.CharField(
        required=False, label="Prior work notes", widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Describe what you already know or did before. This is a note only.",
    )


class NotesForm(forms.Form):
    learner_notes = forms.CharField(
        required=False, label="Your notes", widget=forms.Textarea(attrs={"rows": 5})
    )
