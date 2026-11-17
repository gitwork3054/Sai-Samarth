from allauth.account.adapter import get_adapter
from allauth.account.internal.decorators import login_stage_required
from allauth.account.internal.flows.phone_verification import PhoneVerificationStageProcess
from allauth.account.stages import PhoneVerificationStage
from allauth.account.views import LoginView, SignupView, verify_phone
from allauth.core.exceptions import RateLimited
from allauth.socialaccount.views import SignupView as SocialSignupView
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache

from travel.models import Enquiry, Profile, SavedPackage, SiteSettings
from .forms import EnrollmentForm
from .sms import SMSDeliveryError


class BrandContextMixin:
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # allauth's "site" is a Django RequestSite; our templates use SiteSettings.
        context["site"] = SiteSettings.get()
        return context


class BrandedSocialSignupView(BrandContextMixin, SocialSignupView):
    pass


class SMSLoginView(BrandContextMixin, LoginView):
    template_name = "registration/login.html"


class SMSSignupView(BrandContextMixin, SignupView):
    template_name = "registration/signup.html"


@login_stage_required(stage=PhoneVerificationStage.key, redirect_urlname="login")
def enroll_mobile(request):
    stage = request._login_stage
    user = stage.login.user
    if not user:
        return stage.abort()
    adapter = get_adapter()
    existing = adapter.get_phone(user)
    # A verified second factor cannot be replaced using only a password.
    if existing and existing[1]:
        return redirect("account_verify_phone")
    form = EnrollmentForm(request.POST or None, user=user)
    if request.method == "POST" and form.is_valid():
        adapter.set_phone(user, form.cleaned_data["phone"], False)
        try:
            PhoneVerificationStageProcess.initiate(stage=stage, phone=form.cleaned_data["phone"])
        except SMSDeliveryError as error:
            form.add_error(None, str(error))
        except RateLimited:
            form.add_error(None, "Please wait a minute before requesting another text.")
        else:
            return redirect("account_verify_phone")
    return render(request, "registration/enroll_mobile.html", {"form": form})


@never_cache
def confirm_sms(request):
    if request.method == "POST" and request.POST.get("action", "verify") == "verify" and request.session.get("sms_delivery_status") != "accepted":
        messages.error(request, "No code has been sent yet. Please request a text message first.")
        return redirect("account_verify_phone")
    try:
        response = verify_phone(request)
        if hasattr(response, "context_data") and response.context_data is not None:
            response.context_data["site"] = SiteSettings.get()
            response.context_data["sms_sent"] = request.session.get("sms_delivery_status") == "accepted"
        return response
    except SMSDeliveryError as error:
        messages.error(request, str(error))
        return redirect("account_verify_phone")


@login_required
def dashboard(request):
    Profile.objects.get_or_create(user=request.user)
    return render(request, "registration/dashboard.html", {
        "enquiries": Enquiry.objects.filter(user=request.user).select_related("package", "package__destination"),
        "saved": SavedPackage.objects.filter(user=request.user).select_related("package", "package__destination"),
        "saved_international": request.user.saved_international_trips.all(),
        "tab": request.GET.get("tab", "saved"),
    })
