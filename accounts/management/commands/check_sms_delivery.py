from django.core.management.base import BaseCommand
from accounts.sms import check_provider


class Command(BaseCommand):
    help = "Report SMS configuration and credential readiness without sending texts or exposing secrets."

    def handle(self, *args, **options):
        status, details = check_provider()
        self.stdout.write("SMS readiness: " + status + (" details=" + ",".join(details) if details else ""))
