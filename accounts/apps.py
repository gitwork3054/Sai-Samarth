from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "accounts"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from django.contrib.auth import get_user_model
        from django.db.models.signals import post_save
        from travel.models import Profile

        def make_profile(sender, instance, created, **kw):
            if created:
                Profile.objects.get_or_create(user=instance)
        post_save.connect(make_profile, sender=get_user_model(), weak=False)
