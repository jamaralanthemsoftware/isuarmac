from django import forms

from .models import Lead


class LeadForm(forms.ModelForm):
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Lead
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone",
            "message",
            "consent_to_contact",
        ]
        labels = {
            "first_name": "First name",
            "last_name": "Last name",
        }
        widgets = {
            "first_name": forms.TextInput(
                attrs={"autocomplete": "given-name"}
            ),
            "last_name": forms.TextInput(
                attrs={"autocomplete": "family-name"}
            ),
            "message": forms.Textarea(attrs={"rows": 5}),
        }

    def clean_website(self):
        value = self.cleaned_data.get("website")
        if value:
            raise forms.ValidationError("Unable to submit this form.")
        return value
