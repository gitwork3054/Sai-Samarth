from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

User = get_user_model()


class SignUpForm(UserCreationForm):
    first_name = forms.CharField(max_length=60, label="Full name")
    email = forms.EmailField()
    phone = forms.CharField(max_length=20, required=False)

    class Meta:
        model = User
        fields = ("first_name", "email", "phone", "password1", "password2")

    def clean_email(self):
        e = self.cleaned_data["email"].lower()
        if User.objects.filter(username__iexact=e).exists() or User.objects.filter(email__iexact=e).exists():
            raise forms.ValidationError("An account with this email already exists. Try logging in.")
        return e

    def save(self, commit=True):
        u = super().save(commit=False)
        u.username = u.email = self.cleaned_data["email"]
        if commit:
            u.save()
            u.profile.phone = self.cleaned_data.get("phone", "")
            u.profile.save()
        return u


class EmailLoginForm(AuthenticationForm):
    username = forms.EmailField(label="Email")

    def clean_username(self):
        return self.cleaned_data["username"].lower()
