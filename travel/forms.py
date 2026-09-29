from django import forms

from .models import Hotel


class EnquiryForm(forms.Form):
    name = forms.CharField(max_length=100)
    email = forms.EmailField()
    phone = forms.RegexField(r"^[+\d][\d\s\-]{7,17}$", error_messages={"invalid": "Enter a valid phone number"})
    travel_date = forms.DateField(required=False)
    adults = forms.IntegerField(min_value=1, max_value=40, initial=2)
    children = forms.IntegerField(min_value=0, max_value=20, initial=0)
    hotel_tier = forms.ChoiceField(choices=Hotel.TIERS)
    departure_city = forms.CharField(required=False, max_length=80)
    activities = forms.CharField(required=False)  # comma separated ids
    message = forms.CharField(required=False, max_length=1500)
    website = forms.CharField(required=False)  # honeypot

    def clean_activities(self):
        raw = self.cleaned_data.get("activities", "")
        return [int(x) for x in raw.split(",") if x.strip().isdigit()]
