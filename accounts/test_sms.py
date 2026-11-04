import time
from unittest.mock import patch

import requests
from allauth.account.models import Login
from allauth.account.stages import LoginStageController
from allauth.core import context
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.messages.middleware import MessageMiddleware
from django.core.cache import cache
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse

from .forms import MobileField
from .models import MobileNumber
from .sms import SMSDeliveryError, send_code


class SMSAuthenticationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.password = "TravelTest-739!"
        self.user = get_user_model().objects.create_user(
            username="traveller@example.com", email="traveller@example.com", password=self.password)
        self.mobile = MobileNumber.objects.create(user=self.user, number="+919876543210", verified=True)
        self.patcher = patch("accounts.adapter.send_code")
        self.sender = self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def start_login(self, path=None):
        response = self.client.post(path or reverse("login"), {"login": self.user.email, "password": self.password})
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)
        return response

    def code(self):
        return self.sender.call_args.args[1]

    def verify(self, code):
        return self.client.post(reverse("account_verify_phone"), {"code": code, "action": "verify"})

    def test_password_login_requires_sms_and_code_cannot_be_replayed(self):
        self.assertEqual(self.start_login().url, reverse("account_verify_phone"))
        self.assertRegex(self.code(), r"^[0-9]{6}$")
        response = self.verify(self.code())
        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)
        self.assertIn("_auth_user_id", self.client.session)
        self.client.post(reverse("logout"))
        self.assertEqual(self.verify(self.code()).status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_incorrect_codes_lock_pending_login_after_three_attempts(self):
        self.start_login()
        correct = self.code()
        wrong = "000000" if correct != "000000" else "111111"
        for _ in range(3):
            self.verify(wrong)
        self.verify(correct)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_expired_code_and_other_session_are_rejected(self):
        self.start_login()
        code = self.code()
        other = Client()
        other.post(reverse("account_verify_phone"), {"code": code})
        self.assertNotIn("_auth_user_id", other.session)
        future = time.time() + 301
        with patch("allauth.account.internal.flows.code_verification.time.time", return_value=future):
            self.verify(code)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_wrong_password_does_not_send_sms(self):
        response = self.client.post(reverse("login"), {"login": self.user.email, "password": "wrong"})
        self.assertEqual(response.status_code, 200)
        self.sender.assert_not_called()
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_existing_account_enrols_phone_only_after_password(self):
        self.mobile.delete()
        self.assertEqual(self.start_login().url, reverse("enroll_mobile"))
        response = self.client.post(reverse("enroll_mobile"), {"phone": "98765 43210"})
        self.assertRedirects(response, reverse("account_verify_phone"), fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.verify(self.code())
        self.assertTrue(MobileNumber.objects.get(user=self.user).verified)
        self.assertIn("_auth_user_id", self.client.session)

    def test_verified_second_factor_cannot_be_replaced_during_login(self):
        self.start_login()
        self.client.post(reverse("enroll_mobile"), {"phone": "+919999999999"})
        self.mobile.refresh_from_db()
        self.assertEqual(self.mobile.number, "+919876543210")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_resend_is_rate_limited(self):
        self.start_login()
        self.client.post(reverse("account_verify_phone"), {"action": "resend"})
        self.assertEqual(self.sender.call_count, 1)
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(ACCOUNT_RATE_LIMITS={"verify_phone": None})
    @patch("accounts.adapter.SMSAccountAdapter.generate_phone_verification_code", side_effect=["123456", "654321"])
    def test_resend_replaces_old_code(self, generator):
        self.start_login()
        self.client.post(reverse("account_verify_phone"), {"action": "resend"})
        self.verify("123456")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.verify("654321")
        self.assertIn("_auth_user_id", self.client.session)

    def test_delivery_failure_never_authenticates(self):
        self.sender.side_effect = SMSDeliveryError("unavailable")
        self.start_login()
        self.assertNotIn("_auth_user_id", self.client.session)
        response = self.client.get(reverse("account_verify_phone"))
        self.assertContains(response, "couldn’t send a text")

    def test_alternate_allauth_login_url_also_requires_sms(self):
        self.start_login(reverse("account_login"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(self.sender.call_count, 1)

    def test_mobile_is_not_optional_at_signup(self):
        response = self.client.post(reverse("signup"), {
            "first_name": "New User", "email": "new@example.com",
            "password1": self.password, "password2": self.password,
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(email="new@example.com").exists())

    def test_stage_requires_sms_even_for_verified_social_account(self):
        request = RequestFactory().get("/")
        request.user = self.user
        SessionMiddleware(lambda r: None).process_request(request)
        request.session.save()
        MessageMiddleware(lambda r: None).process_request(request)
        login = Login(user=self.user, email_verification="none")
        with context.request_context(request):
            response = LoginStageController(request, login).handle()
        self.assertEqual(response.url, reverse("account_verify_phone"))
        self.assertEqual(self.sender.call_count, 1)

    def test_phone_normalisation(self):
        self.assertEqual(MobileField().clean("98765 43210"), "+919876543210")
        self.assertEqual(MobileField().clean("+44 7700 900123"), "+447700900123")


@override_settings(TWILIO_ACCOUNT_SID="AC" + "1" * 32, TWILIO_AUTH_TOKEN="test-only",
                   TWILIO_MESSAGING_SERVICE_SID="MG" + "2" * 32, TWILIO_SMS_FROM="")
class SMSTransportTests(TestCase):
    @patch("accounts.sms.requests.post")
    def test_sends_sms_with_fixed_https_endpoint_and_service(self, post):
        post.return_value.json.return_value = {"status": "queued"}
        send_code("+919876543210", "123456")
        args, kwargs = post.call_args
        self.assertTrue(args[0].startswith("https://api.twilio.com/"))
        self.assertEqual(kwargs["data"]["To"], "+919876543210")
        self.assertIn("MessagingServiceSid", kwargs["data"])
        self.assertEqual(kwargs["timeout"], (3, 10))

    @patch("accounts.sms.requests.post", side_effect=requests.Timeout("sensitive provider data"))
    def test_provider_errors_do_not_leak_details(self, post):
        with self.assertRaises(SMSDeliveryError) as error:
            send_code("+919876543210", "123456")
        self.assertNotIn("sensitive", str(error.exception))

    @override_settings(TWILIO_AUTH_TOKEN="")
    @patch("accounts.sms.requests.post")
    def test_missing_credentials_do_not_send(self, post):
        with self.assertRaises(SMSDeliveryError):
            send_code("+919876543210", "123456")
        post.assert_not_called()
