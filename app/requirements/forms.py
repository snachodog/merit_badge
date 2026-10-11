from django import forms

from .models import RequirementActionTag, RequirementNode


class NodeForm(forms.ModelForm):
    action_tags = forms.MultipleChoiceField(
        choices=RequirementActionTag.Tag.choices,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Hints about the kind of work. They do not replace the requirement text.",
    )
    condition_key = forms.CharField(
        required=False, max_length=100, label="Condition name",
        help_text="Conditional only. Example: age_group.",
    )
    condition_equals = forms.CharField(
        required=False, max_length=100, label="Condition value",
        help_text="Conditional only. The requirement group applies when the name has this value.",
    )

    class Meta:
        model = RequirementNode
        fields = [
            "display_number", "node_type", "text", "text_origin", "source",
            "completion_logic", "completion_count", "estimated_effort", "safety_notes",
        ]
        labels = {
            "display_number": "Number (as shown in the source)",
            "text": "Requirement text",
            "text_origin": "Where the text comes from",
            "source": "Source record",
            "completion_logic": "How this group is completed",
            "completion_count": "Count (Choose N only)",
            "estimated_effort": "Estimated effort (an estimate, not part of the requirement)",
        }
        widgets = {"text": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial["action_tags"] = list(self.instance.action_tags.values_list("tag", flat=True))
            cond = self.instance.condition_expression or {}
            self.initial["condition_key"] = cond.get("key", "")
            self.initial["condition_equals"] = cond.get("equals", "")
        self.fields["text"].required = True

    def clean(self):
        cleaned = super().clean()
        key = (cleaned.get("condition_key") or "").strip()
        equals = (cleaned.get("condition_equals") or "").strip()
        # Set before model validation runs, so the model rules see the condition.
        self.instance.condition_expression = (
            {"key": key, "equals": equals} if (key or equals) else None
        )
        return cleaned
