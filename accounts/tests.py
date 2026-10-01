from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from urllib.parse import parse_qs, urlparse

GOOGLE = {"google": {"APP": {"client_id": "test.apps.googleusercontent.com", "secret": "test-secret", "key": ""}, "SCOPE": ["profile", "email"], "OAUTH_PKCE_ENABLED": True}}

class AuthenticationIntegrationTests(TestCase):
    def test_email_signup_still_logs_in_and_rejects_external_redirect(self):
        response = self.client.post(reverse("signup") + "?next=https://example.com/", {
            "first_name": "Traveller", "email": "traveller@example.com", "phone": "",
            "password1": "TravelTest-739!", "password2": "TravelTest-739!",
        })
        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)
        self.assertIn("_auth_user_id", self.client.session)

    def test_existing_google_email_cannot_register_another_native_account(self):
        from .forms import SignUpForm
        get_user_model().objects.create_user(username="google-traveller", email="traveller@example.com")
        form = SignUpForm(data={"first_name": "Traveller", "email": "traveller@example.com", "phone": "", "password1": "TravelTest-739!", "password2": "TravelTest-739!"})
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    @override_settings(SOCIALACCOUNT_PROVIDERS={"google": {"APP": {"client_id": "", "secret": "", "key": ""}}})
    def test_local_auth_pages_render_without_google_credentials(self):
        for name in ["login", "signup"]:
            response = self.client.get(reverse(name))
            self.assertContains(response, "Continue with Google")
            self.assertContains(response, "disabled")

    @override_settings(SOCIALACCOUNT_PROVIDERS=GOOGLE)
    def test_google_start_requires_csrf_and_uses_correct_callback_and_pkce(self):
        client = Client(enforce_csrf_checks=True)
        page = client.get(reverse("login"))
        self.assertContains(page, reverse("google_login"))
        self.assertEqual(client.post(reverse("google_login")).status_code, 403)
        response = client.post(reverse("google_login"), HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)
        self.assertEqual(response.status_code, 302)
        target = urlparse(response.url)
        self.assertEqual(target.hostname, "accounts.google.com")
        query = parse_qs(target.query)
        self.assertEqual(query["redirect_uri"], ["http://testserver/auth/google/login/callback/"])
        self.assertIn("code_challenge", query)
