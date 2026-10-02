"""Generate 100+ demo packages so the site looks alive on day one.

    python manage.py generate_demo            # add demo data (safe to re-run)
    python manage.py generate_demo --reset    # delete all packages first

Everything created here can be edited or deleted from the admin panel.
"""
import random
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from travel import models as m

THEMES = [("Beach & Islands", "🏖️"), ("Adventure & Wildlife", "🧗"), ("Heritage & Culture", "🏰"), ("Hills & Nature", "🏔️"),
          ("Spiritual & Pilgrimage", "🕉️"), ("City & Shopping", "🌆"), ("Luxury & Honeymoon", "💎")]
AUDIENCES = [("Gen-Z", "⚡", "Hostels, hikes, nightlife and reels-worthy spots"), ("Family", "👨‍👩‍👧", "Kid-friendly pace, comfy stays"),
             ("Couple", "💞", "Romantic stays and private experiences"), ("Senior", "🌿", "Relaxed pace, easy access, comfort first")]
B, A, H, HL, S, C, L = "Beach & Islands", "Adventure & Wildlife", "Heritage & Culture", "Hills & Nature", "Spiritual & Pilgrimage", "City & Shopping", "Luxury & Honeymoon"

# name, region, state/country, tagline, price per day (INR), spots, themes, (event name, month)
D = [
 ("Goa", "d", "Goa", "Sun, sand and susegad", 4200, ["Baga & Calangute Beach", "Old Goa Churches", "Fort Aguada", "Dudhsagar Falls", "Anjuna Flea Market"], [B, C], ("Goa Carnival", 2)),
 ("Kerala Backwaters", "d", "Kerala", "Houseboats, spice hills and Ayurveda", 5200, ["Alleppey Houseboat Cruise", "Munnar Tea Gardens", "Periyar Wildlife Sanctuary", "Kovalam Beach", "Kathakali Show"], [HL, B, L], None),
 ("Jaipur", "d", "Rajasthan", "The Pink City of palaces", 4600, ["Amber Fort", "City Palace", "Hawa Mahal", "Jantar Mantar", "Chokhi Dhani Village"], [H, C], ("Diwali in Jaipur", 11)),
 ("Udaipur", "d", "Rajasthan", "City of Lakes", 5400, ["Lake Pichola Boat Ride", "City Palace Udaipur", "Saheliyon Ki Bari", "Sajjangarh Monsoon Palace", "Bagore Ki Haveli"], [H, L], None),
 ("Jaisalmer", "d", "Rajasthan", "Golden fort and desert nights", 4800, ["Jaisalmer Fort", "Sam Sand Dunes", "Patwon Ki Haveli", "Gadisar Lake", "Desert Camp Cultural Night"], [H, A], ("Desert Festival", 2)),
 ("Jodhpur", "d", "Rajasthan", "The Blue City", 4500, ["Mehrangarh Fort", "Umaid Bhawan Palace", "Jaswant Thada", "Clock Tower Market", "Bishnoi Village Safari"], [H], None),
 ("Pushkar", "d", "Rajasthan", "Sacred lake and camel fair", 4300, ["Brahma Temple", "Pushkar Lake Ghats", "Savitri Temple Ropeway", "Camel Safari", "Pushkar Bazaar"], [S, H], ("Pushkar Camel Fair", 11)),
 ("Ranthambore", "d", "Rajasthan", "Tiger country", 6800, ["Tiger Safari Zone 1-5", "Ranthambore Fort", "Padam Talao", "Surwal Lake", "Village Walk"], [A], None),
 ("Kashmir", "d", "Jammu & Kashmir", "Paradise on earth", 6200, ["Dal Lake Shikara", "Mughal Gardens", "Gulmarg Gondola", "Pahalgam Valley", "Sonmarg Glacier"], [HL, L], ("Tulip Festival", 4)),
 ("Ladakh", "d", "Ladakh", "Land of high passes", 7200, ["Pangong Lake", "Nubra Valley", "Khardung La", "Thiksey Monastery", "Magnetic Hill"], [A, HL], None),
 ("Manali", "d", "Himachal Pradesh", "Snow, cafes and adventure", 4400, ["Solang Valley", "Rohtang / Atal Tunnel", "Hadimba Temple", "Old Manali Cafes", "Beas River Rafting"], [HL, A], None),
 ("Shimla", "d", "Himachal Pradesh", "Colonial charm in the hills", 4300, ["Mall Road", "Kufri", "Jakhu Temple", "Christ Church", "Toy Train Ride"], [HL, C], None),
 ("Spiti Valley", "d", "Himachal Pradesh", "Cold desert road-trip", 6500, ["Key Monastery", "Chandratal Lake", "Kaza Village", "Pin Valley", "Langza Fossil Village"], [A, HL], None),
 ("Rishikesh", "d", "Uttarakhand", "Yoga capital and river rafting", 4000, ["Ganga Aarti Triveni Ghat", "Laxman Jhula", "White Water Rafting", "Beatles Ashram", "Neelkanth Mahadev"], [A, S], None),
 ("Jim Corbett", "d", "Uttarakhand", "Jungle safaris in the Himalayan foothills", 5600, ["Jeep Safari Dhikala", "Corbett Falls", "Garjia Devi Temple", "Kosi River Walk", "Jungle Canter Safari"], [A], None),
 ("Andaman Islands", "d", "Andaman & Nicobar", "Turquoise seas and coral reefs", 7000, ["Radhanagar Beach", "Cellular Jail Light & Sound", "Elephant Beach Snorkelling", "Ross Island", "Neil Island"], [B, A, L], None),
 ("Darjeeling & Gangtok", "d", "West Bengal & Sikkim", "Tea estates and Himalayan views", 5000, ["Tiger Hill Sunrise", "Toy Train Joyride", "Tsomgo Lake", "Nathula Pass", "Rumtek Monastery"], [HL], None),
 ("Meghalaya", "d", "Meghalaya", "Living root bridges and waterfalls", 5300, ["Living Root Bridge", "Dawki River", "Mawlynnong Village", "Nohkalikai Falls", "Elephant Falls"], [A, HL], None),
 ("Kaziranga", "d", "Assam", "One-horned rhino safari", 5900, ["Elephant Safari", "Jeep Safari Central Range", "Tea Estate Visit", "Kakochang Waterfalls", "Orchid Park"], [A], None),
 ("Varanasi", "d", "Uttar Pradesh", "The spiritual heart of India", 3900, ["Ganga Aarti Dashashwamedh", "Kashi Vishwanath", "Sarnath", "Sunrise Boat Ride", "Ramnagar Fort"], [S, H], ("Dev Deepawali", 11)),
 ("Golden Triangle", "d", "Delhi, Agra, Jaipur", "Three icons in one trip", 4700, ["Taj Mahal Sunrise", "Red Fort", "Qutub Minar", "Agra Fort", "Fatehpur Sikri"], [H, C], None),
 ("Rann of Kutch", "d", "Gujarat", "White salt desert under the full moon", 5200, ["White Rann Sunset", "Kalo Dungar", "Bhujodi Craft Village", "Mandvi Beach", "Tent City Cultural Night"], [H, A], ("Rann Utsav", 12)),
 ("Gir & Somnath", "d", "Gujarat", "Asiatic lion safari and temples", 4800, ["Gir Lion Safari", "Somnath Temple", "Diu Beach", "Junagadh Fort", "Devalia Safari Park"], [A, S], None),
 ("Mysore & Coorg", "d", "Karnataka", "Palaces and coffee plantations", 4500, ["Mysore Palace", "Chamundi Hills", "Abbey Falls", "Dubare Elephant Camp", "Coffee Plantation Walk"], [H, HL], ("Mysore Dasara", 10)),
 ("Hampi", "d", "Karnataka", "Boulder-strewn ruins of Vijayanagara", 4100, ["Virupaksha Temple", "Vittala Temple Stone Chariot", "Matanga Hill Sunrise", "Coracle Ride", "Lotus Mahal"], [H], None),
 ("Ooty & Coonoor", "d", "Tamil Nadu", "Blue mountains and toy trains", 4200, ["Nilgiri Mountain Railway", "Botanical Gardens", "Doddabetta Peak", "Sim's Park", "Tea Factory"], [HL], None),
 ("Pondicherry", "d", "Puducherry", "French quarter and beaches", 4300, ["White Town Walk", "Auroville", "Paradise Beach", "Promenade Beach", "Sri Aurobindo Ashram"], [B, C], None),
 ("Amritsar", "d", "Punjab", "Golden Temple and Wagah", 3800, ["Golden Temple", "Wagah Border Ceremony", "Jallianwala Bagh", "Partition Museum", "Amritsari Food Trail"], [S, H], None),
 ("Lakshadweep", "d", "Lakshadweep", "Untouched coral atolls", 8500, ["Agatti Lagoon", "Bangaram Island", "Glass-bottom Boat", "Scuba Diving", "Kadmat Beach"], [B, L], None),
 ("Dubai", "i", "UAE", "Skyscrapers, souks and desert safaris", 9500, ["Burj Khalifa At The Top", "Desert Safari with BBQ Dinner", "Dubai Marina Dhow Cruise", "Abu Dhabi Sheikh Zayed Mosque", "Palm Jumeirah & Atlantis"], [C, L], ("Dubai Shopping Festival", 1)),
 ("Bangkok & Pattaya", "i", "Thailand", "Street food, temples and island hopping", 8200, ["Grand Palace & Wat Pho", "Coral Island", "Floating Market", "Alcazar Show", "Sanctuary of Truth"], [C, B], None),
 ("Phuket & Krabi", "i", "Thailand", "Andaman Sea beaches", 9000, ["Phi Phi Island Tour", "James Bond Island", "Big Buddha", "Phuket Old Town", "Four Islands Krabi"], [B, A], ("Songkran Water Festival", 4)),
 ("Bali", "i", "Indonesia", "Island of the Gods", 10500, ["Uluwatu Temple Kecak Dance", "Ubud Rice Terraces", "Nusa Penida", "Tanah Lot Sunset", "Mount Batur Sunrise Trek"], [B, L, A], None),
 ("Singapore", "i", "Singapore", "Garden city with Sentosa fun", 11000, ["Gardens by the Bay", "Universal Studios", "Marina Bay Sands", "Night Safari", "Sentosa Island"], [C], None),
 ("Malaysia", "i", "Malaysia", "Kuala Lumpur, Genting and Langkawi", 8800, ["Petronas Twin Towers", "Genting Highlands", "Batu Caves", "Langkawi Sky Bridge", "Putrajaya"], [C, B], None),
 ("Maldives", "i", "Maldives", "Overwater villas and coral lagoons", 16000, ["Sandbank Picnic", "Snorkelling with Turtles", "Sunset Dolphin Cruise", "Overwater Spa", "Local Island Visit"], [B, L], None),
 ("Sri Lanka", "i", "Sri Lanka", "Ramayana trail, tea hills and beaches", 8000, ["Sigiriya Rock", "Kandy Temple of the Tooth", "Nuwara Eliya Tea Country", "Galle Fort", "Yala Safari"], [H, B], None),
 ("Vietnam", "i", "Vietnam", "Ha Long Bay to the Mekong", 9200, ["Ha Long Bay Cruise", "Hoi An Lantern Town", "Cu Chi Tunnels", "Ba Na Hills Golden Bridge", "Hanoi Old Quarter"], [C, H, A], None),
 ("Nepal", "i", "Nepal", "Kathmandu, Pokhara and Himalayan vistas", 6800, ["Pashupatinath Temple", "Phewa Lake", "Sarangkot Sunrise", "Boudhanath Stupa", "Paragliding Pokhara"], [S, A, HL], None),
 ("Bhutan", "i", "Bhutan", "Land of happiness and dzongs", 10800, ["Tiger's Nest Monastery", "Punakha Dzong", "Dochula Pass", "Thimphu Buddha Point", "Paro Valley"], [HL, S], ("Paro Tsechu", 3)),
 ("Japan", "i", "Japan", "Tokyo, Kyoto and Mount Fuji", 22000, ["Fushimi Inari Shrine", "Shibuya Crossing", "Mount Fuji & Hakone", "Arashiyama Bamboo Grove", "Bullet Train Experience"], [C, H], ("Cherry Blossom Season", 3)),
 ("South Korea", "i", "South Korea", "K-culture, palaces and Jeju", 17500, ["Gyeongbokgung Palace", "Nami Island", "Myeongdong Street Food", "Jeju Island", "Han River Picnic"], [C, H], None),
 ("Turkey", "i", "Turkey", "Istanbul, Cappadocia and Pamukkale", 14000, ["Hot Air Balloon Cappadocia", "Hagia Sophia", "Bosphorus Cruise", "Pamukkale Terraces", "Grand Bazaar"], [H, L], None),
 ("Egypt", "i", "Egypt", "Pyramids and Nile cruise", 15500, ["Pyramids of Giza", "Nile Felucca", "Valley of the Kings", "Egyptian Museum", "Luxor Karnak Temple"], [H], None),
 ("Switzerland", "i", "Switzerland", "Alpine trains and snow peaks", 26000, ["Jungfraujoch Top of Europe", "Lucerne Chapel Bridge", "Mount Titlis", "Interlaken", "Glacier Express Ride"], [HL, L], None),
 ("Paris & Amsterdam", "i", "Europe", "Iconic Western Europe", 24000, ["Eiffel Tower", "Louvre Museum", "Keukenhof Gardens", "Canal Cruise Amsterdam", "Versailles Palace"], [C, H, L], ("Christmas Markets", 12)),
 ("Greece", "i", "Greece", "Santorini sunsets and Athens history", 23000, ["Oia Sunset Santorini", "Acropolis Athens", "Mykonos Windmills", "Caldera Boat Tour", "Delphi"], [B, H, L], None),
 ("Mauritius", "i", "Mauritius", "Tropical island escape", 15000, ["Ile Aux Cerfs", "Seven Coloured Earths", "Catamaran Cruise", "Chamarel Waterfall", "Port Louis Market"], [B, L], None),
 ("Seychelles", "i", "Seychelles", "Granite boulders and powder beaches", 21000, ["Anse Lazio Beach", "Vallee de Mai", "La Digue Island", "Praslin Island", "Island Hopping"], [B, L], None),
 ("Australia", "i", "Australia", "Sydney, Melbourne and Great Barrier Reef", 24500, ["Sydney Opera House", "Great Ocean Road", "Phillip Island Penguins", "Blue Mountains", "Reef Cruise"], [C, A], None),
 ("New Zealand", "i", "New Zealand", "Adventure capital of the world", 26500, ["Milford Sound", "Queenstown Bungy", "Hobbiton", "Rotorua Geothermal", "TSS Earnslaw Cruise"], [A, HL], None),
 ("Hong Kong & Macau", "i", "Hong Kong", "Skylines, Disneyland and casinos", 16500, ["Victoria Peak", "Disneyland", "Ngong Ping 360", "Macau Venetian", "Star Ferry"], [C], None),
 ("Kenya Safari", "i", "Kenya", "Big Five and the great migration", 23500, ["Masai Mara Game Drive", "Hot Air Balloon Safari", "Lake Nakuru", "Amboseli & Kilimanjaro Views", "Maasai Village"], [A], None),
 ("Azerbaijan (Baku)", "i", "Azerbaijan", "Flame towers and Caspian charm", 11500, ["Flame Towers", "Gobustan", "Old City Icheri Sheher", "Shahdag Cable Car", "Yanar Dag Fire Mountain"], [C, H], None),
 ("USA - East Coast", "i", "USA", "New York, Washington and Niagara", 30000, ["Statue of Liberty", "Times Square", "Niagara Falls", "White House Tour", "Empire State Building"], [C], None),
]
VARIANTS = [  # label, tour_type, audiences, extra theme, price multiplier, days delta
    ("Signature", "individual", ["Family", "Couple"], None, 1.0, 0),
    ("Family Fun", "individual", ["Family"], None, 1.05, 1),
    ("Romantic Retreat", "individual", ["Couple"], L, 1.2, 0),
    ("Gen-Z Escape", "individual", ["Gen-Z"], None, 0.85, -1),
    ("Senior Comfort", "individual", ["Senior", "Family"], None, 1.1, 1),
    ("Group Departure", "group", ["Family", "Senior", "Gen-Z"], None, 0.9, 0),
    ("Corporate Offsite", "corporate", [], None, 1.15, 0),
]
ACTS = {A: [("Guided nature walk", 1200), ("Adventure sports package", 3200), ("Sunrise photography session", 2200)],
        B: [("Water sports combo", 2500), ("Sunset cruise with dinner", 3200), ("Snorkelling / diving", 3600)],
        H: [("Heritage walk with local historian", 1500), ("Folk dance & dinner evening", 2400), ("Cooking class", 2000)],
        HL: [("Cable car / scenic ride", 1800), ("Bonfire & barbecue night", 1500), ("Guided trek", 2200)],
        S: [("Priority darshan / aarti seat", 1500), ("Guided temple trail", 1200), ("Yoga & meditation session", 1400)],
        C: [("Theme park / attraction ticket", 3200), ("Street-food night tour", 1800), ("Shopping tour with guide", 900)],
        L: [("Private candle-light dinner", 5500), ("Couple spa session", 4200), ("Private transfer upgrade", 3000)]}
CITIES = [("Mumbai", 0), ("Delhi", 1500), ("Ahmedabad", 500), ("Vadodara", 500), ("Bengaluru", 2500), ("Hyderabad", 2000), ("Kolkata", 3500)]
TITLES = {"Signature": "{d} Signature Escape", "Family Fun": "{d} Family Holiday", "Romantic Retreat": "{d} Romantic Retreat", "Gen-Z Escape": "{d} Gen-Z Squad Trip",
          "Senior Comfort": "{d} Relaxed Holiday for Seniors", "Group Departure": "{d} Group Tour", "Corporate Offsite": "{d} Corporate Getaway"}
INC = ["Accommodation on twin-sharing basis with daily breakfast", "Private air-conditioned vehicle for transfers and sightseeing", "All sightseeing as per itinerary",
       "Airport / station pick-up and drop", "Assistance of our tour manager", "All applicable hotel taxes"]
EXC = ["Airfare / train fare to and from the destination unless mentioned", "Lunches and dinners unless specified", "Personal expenses, tips and porterage",
       "Entry tickets not mentioned in the itinerary", "Travel insurance", "Anything not listed under inclusions"]


def r500(x):
    return int(round(x / 500.0) * 500)


class Command(BaseCommand):
    help = "Create demo themes, traveller categories, destinations and 100+ full packages"

    def add_arguments(self, p):
        p.add_argument("--reset", action="store_true", help="Delete existing packages/destinations first")

    @transaction.atomic
    def handle(self, *args, **o):
        random.seed(2026)
        if o["reset"]:
            m.Package.objects.all().delete()
        m.SiteSettings.get()
        themes = {n: m.Theme.objects.get_or_create(name=n, defaults={"icon": i, "order": k})[0] for k, (n, i) in enumerate(THEMES)}
        auds = {n: m.Audience.objects.get_or_create(name=n, defaults={"icon": i, "description": d, "order": k})[0] for k, (n, i, d) in enumerate(AUDIENCES)}
        today = date.today()
        created = 0
        for i, (name, reg, place, tag, ppd, spots, th, event) in enumerate(D):
            dest, _ = m.Destination.objects.get_or_create(name=name, defaults={
                "region": "domestic" if reg == "d" else "international", "state_or_country": place, "tagline": tag, "is_popular": i % 3 == 0})
            base_days = 4 if reg == "d" else 5
            picks = [0, 1 + (i * 2) % 6, 1 + (i * 2 + 1) % 6]
            if reg == "d" and i % 4 == 0:
                picks.append(6)  # corporate offsite for some
            for v in dict.fromkeys(picks):
                label, ttype, aud_names, extra, mult, delta = VARIANTS[v]
                if ttype == "group":
                    continue  # Group catalogue comes from the supplied source data.
                title = TITLES[label].format(d=name)
                if m.Package.objects.filter(title=title).exists():
                    continue
                days = max(3, base_days + delta + (i % 3))
                base = r500(ppd * days * mult / 1.6)
                disc = random.choice([0, 0, 0, 10, 12, 15, 20]) if v else random.choice([0, 0, 10])
                is_event = bool(event) and label == "Signature"
                evd = date(today.year if event and event[1] >= today.month else today.year + 1, event[1], 15) if event else None
                pkg = m.Package.objects.create(
                    title=title, destination=dest, tour_type=ttype, days=days, nights=days - 1,
                    short_description=f"{days} days in {name}: {tag.lower()}. Handpicked stays, guided sightseeing and effortless planning.",
                    overview=(f"Discover {name} on this {days}-day {label.lower()} holiday. {tag}. You'll visit {', '.join(spots[:3])} and more, "
                              f"staying in hand-picked hotels with daily breakfast and private transfers. This is a demo description: edit it in the admin panel."),
                    base_price=base, child_price=r500(base * 0.75), deluxe_upgrade=r500(base * 0.18), premium_upgrade=r500(base * 0.4),
                    discount_percent=disc, offer_label=random.choice(["Early-bird deal", "Festive offer", "Weekend flash sale", "Limited seats"]) if disc else "",
                    offer_valid_till=today + timedelta(days=random.choice([30, 45, 60, 90])) if disc else None,
                    is_event=is_event, event_name=event[0] if is_event else "", event_date=evd if is_event else None,
                    departure_dates="\n".join((today + timedelta(days=21 + 30 * k)).strftime("%d %b %Y") for k in range(4)) if ttype == "group" else "",
                    inclusions="\n".join(INC), exclusions="\n".join(EXC),
                    tour_info="Best time to visit: October to March\nDocuments: Valid government photo ID" + ("; passport with 6 months validity" if reg == "i" else "")
                              + "\nCancellation: As per company policy; see terms at booking\nPace: " + ("Relaxed" if "Senior" in aud_names else "Balanced"),
                    is_featured=(v == 0 and i % 2 == 0))
                pkg.themes.set([themes[t] for t in th] + ([themes[extra]] if extra else []))
                pkg.audiences.set([auds[a] for a in aud_names])
                # itinerary
                for d in range(1, days + 1):
                    if d == 1:
                        t, desc = f"Arrival in {name}", f"Arrive at {name}, meet our representative and transfer to your hotel. Check in, relax and enjoy a welcome drink. Evening at leisure."
                    elif d == days:
                        t, desc = "Departure", "Enjoy a leisurely breakfast, check out and transfer to the airport / station with wonderful memories."
                    else:
                        s1, s2 = spots[(d - 2) % len(spots)], spots[(d - 1) % len(spots)]
                        t, desc = f"{s1}" + (f" & {s2}" if d % 2 else ""), f"After breakfast, head out to explore {s1}. " + (f"Later, visit {s2}. " if d % 2 else "Spend the afternoon at leisure or shop for souvenirs. ") + "Return to the hotel in the evening."
                    m.ItineraryDay.objects.create(package=pkg, day_number=d, title=t, description=desc,
                                                  meals="Breakfast" if d < days else "Breakfast", stay=name if d < days else "")
                for k, s in enumerate(spots):
                    m.Sightseeing.objects.create(package=pkg, name=s, description=f"One of the highlights of {name}.", order=k)
                tiers = [("standard", f"{name} Comfort Inn", 3, "Standard Room"), ("deluxe", f"Grand {name} Resort", 4, "Deluxe Room with view"), ("premium", f"The {name} Luxe Palace", 5, "Premium Suite")]
                for tier, hn, stars, room in tiers:
                    m.Hotel.objects.create(package=pkg, tier=tier, name=hn, city=name, star_rating=stars, room_category=room, nights=days - 1)
                for th_name in th[:2]:
                    for an, ap in ACTS[th_name][:2]:
                        m.OptionalActivity.objects.create(package=pkg, name=an, description="Optional add-on, pay only if you select it.", adult_price=ap, child_price=r500(ap * 0.7))
                for city, sc in CITIES:
                    m.DepartureCity.objects.create(package=pkg, city=city, surcharge=sc if reg == "d" else sc * 4)
                created += 1
        if o["reset"]:
            from django.core.management import call_command
            call_command("import_group_tours")
        total = m.Package.objects.count()
        self.stdout.write(self.style.SUCCESS(f"Created {created} packages. Total packages now: {total}."))
