from allauth.account.adapter import DefaultAccountAdapter
from django.db import transaction
from travel.models import Profile

from .models import MobileNumber
from .sms import send_code


class SMSAccountAdapter(DefaultAccountAdapter):
    def get_login_stages(self):
        return [
            "accounts.stages.SMSVerificationStage" if path == "allauth.account.stages.PhoneVerificationStage" else path
            for path in super().get_login_stages()
        ]

    def phone_form_field(self, **kwargs):
        from .forms import MobileField
        return MobileField(**kwargs)

    def set_phone(self, user, phone, verified):
        MobileNumber.objects.update_or_create(user=user, defaults={"number": phone, "verified": verified})
        Profile.objects.update_or_create(user=user, defaults={"phone": phone})

    def get_phone(self, user):
        mobile = MobileNumber.objects.filter(user=user).first()
        return (mobile.number, mobile.verified) if mobile else None

    def get_user_by_phone(self, phone):
        mobile = MobileNumber.objects.select_related("user").filter(number=phone, verified=True).first()
        return mobile.user if mobile else None

    def set_phone_verified(self, user, phone):
        with transaction.atomic():
            mobile = MobileNumber.objects.select_for_update().get(user=user, number=phone)
            mobile.verified = True
            mobile.save(update_fields=["verified"])

    def send_verification_code_sms(self, user, phone, code, **kwargs):
        send_code(phone, code)
