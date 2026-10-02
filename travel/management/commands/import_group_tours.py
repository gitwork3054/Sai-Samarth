from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import transaction
from travel.group_import import import_catalogue

class Command(BaseCommand):
    help = 'Replace visible group tours with all supplied AkhilBharat details and itinerary days'

    @transaction.atomic
    def handle(self, *args, **options):
        packages, days = import_catalogue(apps)
        self.stdout.write(self.style.SUCCESS(f'Imported {packages} group tours and {days} itinerary days.'))
