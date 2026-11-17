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


class LoginWithoutOTPTests(TestCase):
    def setUp(self):
        cache.clear()
        self.password = "TravelTest-739!"
        self.user = get_user_model().objects.create_user(
            username="traveller@example.com", email="traveller@example.com", password=self.password)

    @patch("accounts.adapter.send_code")
    def test_password_login_does_not_require_mobile_or_send_sms(self, sender):
        for path in (reverse("login"), reverse("account_login")):
            response = self.client.post(path, {"login": self.user.email, "password": self.password})
            self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)
            self.assertIn("_auth_user_id", self.client.session)
            self.client.post(reverse("logout"))
        sender.assert_not_called()

    @patch("accounts.adapter.send_code")
    def test_wrong_password_does_not_authenticate(self, sender):
        response = self.client.post(reverse("login"), {"login": self.user.email, "password": "wrong"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        sender.assert_not_called()

    @patch("accounts.adapter.send_code")
    def test_social_login_stage_does_not_require_sms(self, sender):
        request = RequestFactory().get("/")
        request.user = self.user
        SessionMiddleware(lambda r: None).process_request(request)
        request.session.save()
        MessageMiddleware(lambda r: None).process_request(request)
        login = Login(user=self.user, email_verification="none")
        with context.request_context(request):
            response = LoginStageController(request, login).handle()
        self.assertTrue(response is None or response.url not in (reverse("account_verify_phone"), reverse("enroll_mobile")))
        sender.assert_not_called()

    def test_sign_in_and_signup_copy_does_not_mention_sms(self):
        for name in ("login", "signup", "account_login", "account_signup"):
            response = self.client.get(reverse(name))
            self.assertNotContains(response, "SMS verification")
            self.assertNotContains(response, "verification code")


@override_settings(TWILIO_ACCOUNT_SID="AC" + "1" * 32, TWILIO_AUTH_TOKEN="test-only",
                   TWILIO_MESSAGING_SERVICE_SID="MG" + "2" * 32, TWILIO_SMS_FROM="")
class SMSTransportTests(TestCase):
    @patch("accounts.sms.requests.post")
    def test_sends_sms_with_fixed_https_endpoint_and_service(self, post):
        post.return_value.status_code = 201
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

    @patch("accounts.sms.requests.post")
    def test_provider_rejection_is_diagnosable_without_logging_private_values(self, post):
        post.return_value.status_code = 400
        post.return_value.json.return_value = {"code": 21608, "message": "sensitive 123456 +919876543210"}
        with self.assertLogs("accounts.sms", level="ERROR") as logs:
            with self.assertRaises(SMSDeliveryError):
                send_code("+919876543210", "123456")
        output = " ".join(logs.output)
        self.assertIn("21608", output)
        self.assertNotIn("123456", output)
        self.assertNotIn("+919876543210", output)
        self.assertNotIn("test-only", output)

    @patch("accounts.sms.requests.get")
    @patch("accounts.sms.requests.post")
    def test_read_only_health_check_never_sends_text(self, post, get):
        from .sms import check_provider
        get.return_value.status_code = 401
        get.return_value.json.return_value = {"code": 20003, "message": "private"}
        self.assertEqual(check_provider(), ("provider_rejected", ["401", "20003"]))
        post.assert_not_called()
