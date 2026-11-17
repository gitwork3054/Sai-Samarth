from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

GOOGLE = {"google": {"APP": {"client_id": "test.apps.googleusercontent.com", "secret": "test-secret", "key": ""}, "SCOPE": ["profile", "email"], "OAUTH_PKCE_ENABLED": True}}

class AuthenticationIntegrationTests(TestCase):
    @patch("accounts.adapter.send_code")
    def test_signup_signs_in_without_sms_and_rejects_external_redirect(self, sender):
        response = self.client.post(reverse("signup") + "?next=https://example.com/", {
            "first_name": "Traveller", "email": "traveller@example.com", "phone": "+919876543210",
            "password1": "TravelTest-739!", "password2": "TravelTest-739!",
        })
        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)
        self.assertIn("_auth_user_id", self.client.session)
        sender.assert_not_called()

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


    @patch("allauth.socialaccount.views.flows.signup.get_pending_signup")
    def test_google_signup_page_uses_site_layout(self, pending):
        from allauth.socialaccount.models import SocialAccount, SocialLogin
        user = get_user_model()(email="google@example.com")
        pending.return_value = SocialLogin(user=user, account=SocialAccount(provider="google", uid="test-google-id"))
        response = self.client.get(reverse("socialaccount_signup"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "socialaccount/signup.html")
        self.assertContains(response, "One more step")
        self.assertContains(response, "auth-box")
        from travel.models import SiteSettings
        self.assertContains(response, SiteSettings.get().brand_name)
        self.assertContains(response, 'name="phone"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
