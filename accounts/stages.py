from allauth.account.adapter import get_adapter
from allauth.account.internal.flows.phone_verification import PhoneVerificationStageProcess
from allauth.account.stages import PhoneVerificationStage
from allauth.core.exceptions import RateLimited
from django.contrib import messages
from django.shortcuts import redirect

from .sms import SMSDeliveryError


class SMSVerificationStage(PhoneVerificationStage):
    """Require a fresh text code for signup, password login and Google login."""
    def handle(self):
        if not self.login.user:
            return super().handle()
        mobile = get_adapter().get_phone(self.login.user)
        if not mobile:
            return redirect("enroll_mobile"), True
        try:
            PhoneVerificationStageProcess.initiate(stage=self, phone=mobile[0])
        except (SMSDeliveryError, RateLimited):
            # Preserve the pending login; no authenticated session is created.
            messages.error(self.request, "We couldn’t send a text right now. Please wait a minute and try again.")
        return redirect("account_verify_phone"), True
