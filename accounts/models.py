from django.conf import settings
from django.db import models
from django.db.models import Q


class MobileNumber(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sms_mobile")
    number = models.CharField(max_length=16, db_index=True)
    verified = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["number"], condition=Q(verified=True), name="unique_verified_mobile")
        ]
