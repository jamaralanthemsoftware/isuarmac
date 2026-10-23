from django import forms

from .models import Lead

US_STATES = [
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware",
    "District of Columbia", "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa",
    "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
    "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey",
    "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon",
    "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah",
    "Vermont", "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming",
]
# ISU-ARMAC does not pursue hospital business in New Jersey or New York.
HOSPITAL_STATES = [s for s in US_STATES if s not in ("New Jersey", "New York")]
MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def choices(values, blank="Select…"):
    return [("", blank)] + [(v, v) for v in values]


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


class BaseLeadForm(forms.Form):
    form_type = forms.CharField(widget=forms.HiddenInput)
    page_url = forms.CharField(widget=forms.HiddenInput, required=False)
    website = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}),
    )  # honeypot
    name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={"autocomplete": "name"}),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"autocomplete": "email"})
    )
    phone = forms.CharField(
        max_length=40,
        required=False,
        widget=forms.TextInput(attrs={"autocomplete": "tel", "type": "tel"}),
    )

    detail_fields = []

    def details(self):
        return {
            f: self.cleaned_data.get(f)
            for f in self.detail_fields
            if self.cleaned_data.get(f) not in (None, "", [])
        }


class GeneralQuoteForm(BaseLeadForm):
    quote_type = forms.ChoiceField(
        label="Type of insurance",
        choices=choices([
            "Personal (home, auto)",
            "Private client",
            "Business",
            "Employee benefits",
            "Health or Medicare",
            "Life or annuities",
        ]),
    )
    zip_code = forms.CharField(
        label="ZIP code",
        max_length=10,
        required=False,
        widget=forms.TextInput(attrs={"autocomplete": "postal-code", "inputmode": "numeric"}),
    )
    state = forms.ChoiceField(choices=choices(US_STATES), required=False)
    message = forms.CharField(
        label="How can we help?",
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
    )
    detail_fields = ["quote_type", "zip_code"]


class ContractorQuoteForm(BaseLeadForm):
    company = forms.CharField(max_length=200)
    state = forms.ChoiceField(choices=choices(["California", "Nevada", "Arizona"]))
    trade = forms.ChoiceField(
        choices=choices([
            "Roofing",
            "Concrete & masonry",
            "Electrical",
            "Plumbing & HVAC",
            "Framing & carpentry",
            "Solar",
            "Grading & paving",
            "Painting & drywall",
            "Landscaping",
            "General contractor",
            "Other",
        ])
    )
    employees = forms.ChoiceField(
        label="Employees",
        choices=choices(["Just me", "2 to 10", "11 to 50", "51+"]),
    )
    renewal_month = forms.ChoiceField(
        label="Renewal month",
        choices=choices(MONTHS),
        required=False,
    )
    needs = forms.MultipleChoiceField(
        label="What do you need?",
        required=False,
        widget=forms.CheckboxSelectMultiple,
        choices=[
            (v, v)
            for v in [
                "General liability",
                "Workers' comp",
                "Auto",
                "Bonds",
                "Equipment",
                "Builder's risk",
                "Employee benefits",
                "Free workers' comp review",
            ]
        ],
    )
    detail_fields = ["trade", "employees", "renewal_month", "needs"]


class HospitalForm(BaseLeadForm):
    title = forms.CharField(max_length=120, required=False)
    company = forms.CharField(label="Hospital or group name", max_length=200)
    state = forms.ChoiceField(choices=choices(HOSPITAL_STATES))
    beds = forms.ChoiceField(
        label="Number of beds",
        choices=choices(["Under 25", "25 to 99", "100 to 249", "250+"]),
    )
    employees = forms.ChoiceField(
        label="Number of employees",
        choices=choices(["Under 300", "300 to 999", "1,000 to 2,999", "3,000+"]),
    )
    interests = forms.MultipleChoiceField(
        label="Interested in",
        required=False,
        widget=forms.CheckboxSelectMultiple,
        choices=[
            (v, v)
            for v in [
                "Property & casualty",
                "Employee benefits",
                "Self-insured plan management",
                "Stop-loss",
                "Benchmark report",
            ]
        ],
    )
    renewal_month = forms.ChoiceField(
        label="Next renewal month",
        choices=choices(MONTHS),
        required=False,
    )
    detail_fields = ["title", "beds", "employees", "interests", "renewal_month"]


class BenefitsQuoteForm(BaseLeadForm):
    company = forms.CharField(max_length=200)
    state = forms.ChoiceField(choices=choices(US_STATES))
    employees = forms.ChoiceField(
        label="Number of employees",
        choices=choices(["2 to 9", "10 to 49", "50 to 99", "100 to 499", "500+"]),
    )
    renewal_month = forms.ChoiceField(
        label="Renewal month",
        choices=choices(MONTHS),
        required=False,
    )
    message = forms.CharField(
        label="Anything else?",
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
    )
    detail_fields = ["employees", "renewal_month"]


class ContactForm(BaseLeadForm):
    message = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}))


FORMS = {
    "general": GeneralQuoteForm,
    "contractor": ContractorQuoteForm,
    "hospital": HospitalForm,
    "benefits": BenefitsQuoteForm,
    "contact": ContactForm,
}


def form_for(form_type, data=None):
    form_class = FORMS.get(form_type, GeneralQuoteForm)
    return form_class(data, initial={"form_type": form_type}, prefix=None)
