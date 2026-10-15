"""State-first navigation shared by the domestic menu and package filters."""
import re
from django.utils.text import slugify

ALIASES = {
    'kashmir': 'Jammu & Kashmir', 'jammu and kashmir': 'Jammu & Kashmir',
    'jammu & kashmir': 'Jammu & Kashmir', 'andaman': 'Andaman & Nicobar',
    'andaman islands': 'Andaman & Nicobar', 'andaman & nicobar': 'Andaman & Nicobar',
    'himachal packages': 'Himachal Pradesh', 'ayodhya prayagraj': 'Uttar Pradesh',
    'orissa': 'Odisha', 'pondicherry': 'Puducherry',
}
STATES = ('Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh', 'Goa',
          'Gujarat', 'Haryana', 'Himachal Pradesh', 'Jharkhand', 'Karnataka', 'Kerala',
          'Madhya Pradesh', 'Maharashtra', 'Manipur', 'Meghalaya', 'Mizoram', 'Nagaland',
          'Odisha', 'Punjab', 'Rajasthan', 'Sikkim', 'Tamil Nadu', 'Telangana', 'Tripura',
          'Uttar Pradesh', 'Uttarakhand', 'West Bengal', 'Delhi', 'Ladakh', 'Lakshadweep',
          'Puducherry', 'Chandigarh', 'Jammu & Kashmir', 'Andaman & Nicobar', 'South India')
LOOKUP = {name.casefold(): name for name in STATES}
LOOKUP.update(ALIASES)
CITIES = {'jaipur':'Rajasthan', 'udaipur':'Rajasthan', 'jaisalmer':'Rajasthan',
          'jodhpur':'Rajasthan', 'pushkar':'Rajasthan', 'ranthambore':'Rajasthan',
          'manali':'Himachal Pradesh', 'shimla':'Himachal Pradesh', 'spiti valley':'Himachal Pradesh',
          'amritsar':'Punjab', 'varanasi':'Uttar Pradesh', 'ayodhya':'Uttar Pradesh',
          'rishikesh':'Uttarakhand', 'jim corbett':'Uttarakhand', 'kerala backwaters':'Kerala',
          'mysore & coorg':'Karnataka', 'hampi':'Karnataka', 'ooty & coonoor':'Tamil Nadu',
          'rann of kutch':'Gujarat', 'gir & somnath':'Gujarat', 'kaziranga':'Assam'}


def destination_states(destination):
    raw = (destination.state_or_country or '').strip()
    exact = LOOKUP.get(raw.casefold()) or LOOKUP.get(destination.name.casefold())
    if exact:
        return [exact]
    # Multi-state circuits appear under every state explicitly named in their location.
    names = []
    for part in re.split(r'[,/&]|\band\b', raw, flags=re.I):
        name = LOOKUP.get(part.strip().casefold()) or CITIES.get(part.strip().casefold())
        if name and name not in names:
            names.append(name)
    if names:
        return names
    return [CITIES.get(destination.name.casefold(), 'Other domestic regions')]


def domestic_groups(packages):
    groups = {}
    for package in packages:
        if package.destination.region != 'domestic':
            continue
        for name in destination_states(package.destination):
            group = groups.setdefault(name, {'name': name, 'slug': slugify(name), 'destination_ids': set(), 'package_ids': set()})
            group['destination_ids'].add(package.destination_id)
            group['package_ids'].add(package.pk)
    result = []
    from .models import SiteSettings
    priority = {name.strip().casefold(): i for i, name in enumerate(SiteSettings.get().domestic_state_order.splitlines()) if name.strip()}
    for name in sorted(groups, key=lambda value: (priority.get(value.casefold(), 10000), value)):

        group = groups[name]
        group['count'] = len(group.pop('package_ids'))
        result.append(group)
    return result


def international_groups(packages):
    from .models import SiteSettings
    groups = {}
    for package in packages:
        if package.destination.region != "international":
            continue
        name = package.destination.state_or_country.strip() or package.destination.name
        group = groups.setdefault(name, {"name": name, "slug": slugify(name), "destination_ids": set(), "package_ids": set(), "source_urls": set()})
        group["destination_ids"].add(package.destination_id)
        group["package_ids"].add(package.pk)
        if package.destination.source_url:
            group["source_urls"].add(package.destination.source_url)
        if package.source_url:
            group["source_urls"].add(package.source_url)
    priority = {name.strip().casefold(): i for i, name in enumerate(SiteSettings.get().international_country_order.splitlines()) if name.strip()}
    result = []
    for name in sorted(groups, key=lambda value: (priority.get(value.casefold(), 10000), value)):
        group = groups[name]
        group["count"] = len(group.pop("package_ids"))
        group["source_urls"] = sorted(group["source_urls"])
        result.append(group)
    return result
