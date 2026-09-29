from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from travel.models import Enquiry, Profile, SavedPackage

from .forms import SignUpForm


def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect(request.GET.get("next") or "dashboard")
    return render(request, "registration/signup.html", {"form": form})


@login_required
def dashboard(request):
    Profile.objects.get_or_create(user=request.user)
    return render(request, "registration/dashboard.html", {
        "enquiries": Enquiry.objects.filter(user=request.user).select_related("package", "package__destination"),
        "saved": SavedPackage.objects.filter(user=request.user).select_related("package", "package__destination"),
        "tab": request.GET.get("tab", "saved"),
    })
