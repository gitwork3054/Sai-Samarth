import re

from allauth.account.forms import SignupForm, VerifyPhoneForm
from django import forms
from django.contrib.auth import get_user_model

from .models import MobileNumber


class MobileField(forms.CharField):
    def __init__(self, **kwargs):
        kwargs.setdefault("label", "Mobile number")
        kwargs.setdefault("max_length", 30)
        kwargs.setdefault("widget", forms.TextInput(attrs={
            "type": "tel", "autocomplete": "tel", "placeholder": "+91 9876543210",
        }))
        super().__init__(**kwargs)

    def clean(self, value):
        value = super().clean(value)
        number = re.sub(r"[\s()-]", "", value)
        if re.fullmatch(r"[6-9]\d{9}", number):
            number = "+91" + number
        elif re.fullmatch(r"91[6-9]\d{9}", number):
            number = "+" + number
        if not re.fullmatch(r"\+[1-9]\d{7,14}", number):
            raise forms.ValidationError("Enter a mobile number with its country code, for example +91 9876543210.")
        return number


class SignUpForm(SignupForm):
    first_name = forms.CharField(max_length=60, label="Full name")

    def clean_email(self):
        email = super().clean_email()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists. Try logging in.")
        return email


class EnrollmentForm(forms.Form):
    phone = MobileField(required=True)

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_phone(self):
        phone = self.cleaned_data["phone"]
        if MobileNumber.objects.filter(number=phone, verified=True).exclude(user=self.user).exists():
            raise forms.ValidationError("This number is already linked to another account.")
        return phone


class SMSCodeForm(VerifyPhoneForm):
    code = forms.RegexField(
        regex=r"^\d{6}$", label="Six-digit code",
        widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "one-time-code",
                                      "maxlength": "6", "pattern": "[0-9]{6}", "autofocus": True}),
        error_messages={"invalid": "Enter the six-digit code from your text message."},
    )
