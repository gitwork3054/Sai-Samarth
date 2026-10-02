"""Import the supplied catalogue without rewriting or guessing source content."""
import json
import re
from collections import defaultdict
from pathlib import Path
from django.utils.text import slugify


def import_catalogue(apps, using='default'):
    Package = apps.get_model('travel', 'Package')
    Destination = apps.get_model('travel', 'Destination')
    ItineraryDay = apps.get_model('travel', 'ItineraryDay')
    data = json.loads((Path(__file__).parent / 'data/akhilbharat_group_tours.json').read_text(encoding='utf-8'))
    by_url = defaultdict(list)
    for row in data['itinerary_days']:
        by_url[row['package_url']].append(row)
    imported = []
    for row in data['packages']:
        url = row['package_url']
        slug = 'group-' + url.rstrip('/').rsplit('/', 1)[-1]
        location = next((part for part in row['destinations'].split(' | ') if 'Special Package' not in part), row['name'])
        dest, _ = Destination.objects.using(using).get_or_create(name=location, defaults={
            'slug': slugify(location), 'region': 'international' if location in ('Bhutan', 'Nepal') else 'domestic',
            'state_or_country': location})
        days = int(re.search(r'\d+', row['duration'])[0])
        price = int(re.sub(r'[^0-9]', '', row['price']) or 0)
        package, _ = Package.objects.using(using).update_or_create(slug=slug, defaults={
            'title': row['name'], 'destination': dest, 'tour_type': 'group', 'days': days, 'nights': 0,
            'short_description': row['destinations'], 'overview': row['destinations'],
            'base_price': price, 'price_on_request': not row['price'], 'source_details': row,
            'cover_url': row['image_url'], 'cover_image': '', 'is_active': True, 'discount_percent': 0,
            'child_price': 0, 'deluxe_upgrade': 0, 'premium_upgrade': 0,
            'inclusions': '', 'exclusions': '', 'tour_info': '', 'departure_dates': '',
        })
        if not package.tour_code:
            Package.objects.using(using).filter(pk=package.pk).update(tour_code=f'SSG-{package.pk:04d}')
        ItineraryDay.objects.using(using).filter(package=package).delete()
        ItineraryDay.objects.using(using).bulk_create([
            ItineraryDay(package=package, day_number=int(re.search(r'\d+', day['day'])[0]),
                         title=day['title'], description=day['description']) for day in by_url[url]])
        imported.append(package.pk)
    # Preserve old records for saved trips/bookings, but replace the visible group catalogue.
    Package.objects.using(using).filter(tour_type='group').exclude(pk__in=imported).update(is_active=False)
    return len(imported), sum(len(v) for v in by_url.values())
