# Sai Samarth Holidays Pvt. Ltd.: Django tours & travel website

Beach-and-sunset styled travel site with 100+ demo packages, live price calculator, enquiry popup,
email + WhatsApp notifications, PDF itineraries, user accounts and a no-code owner admin panel.

## Run it
```bash
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py generate_demo                        # 170+ demo packages (edit/delete freely in admin)
python manage.py add_photos                           # fetch Commons photos for cards, galleries and sightseeing
python manage.py createsuperuser
python manage.py runserver
```
Site: http://127.0.0.1:8000/  |  Owner panel: http://127.0.0.1:8000/manage-console/  (change `ADMIN_URL` in `.env`)

## Logo
The supplied Sai Samarth logo is included at `static/img/sai-samarth-logo.png`.
You can replace it later through **Admin > Site settings > Logo**.
Also set phone, WhatsApp number and email there; they drive every button and message.

## What the owner manages (Admin, no code)
| Where | What |
|---|---|
| Packages > open a package | Title, tour code (auto if blank), destination, tour type (individual / group / corporate), interests, traveller categories (Gen-Z, Family, Couple, Senior), days/nights, overview, YouTube link, cover image |
| Same page, sections | Day-wise itinerary, Sightseeing, Gallery photos, Hotels & room categories (Standard/Deluxe/Premium), Optional experiences (adult/child price), Departure cities & surcharges |
| Pricing block | Adult price, child price, Deluxe/Premium upgrade per person, discount %, offer label, offer expiry |
| Events block | Festival tour flag, event name/date, group departure dates |
| Package list actions | Duplicate a package with everything inside, show/hide in bulk; edit price/discount/featured inline |
| Destinations, Themes, Traveller categories | Add or rename places and categories; they appear in filters automatically |
| Enquiries & bookings | Every enquiry with the exact configuration chosen. Set status to **Booked / Confirmed** and the customer instantly gets an email + WhatsApp confirmation |
| Notification log | Delivery status of every email/WhatsApp |
| Site settings | Logo, contact details, hero text, social links |

## Notifications
* Email: set SMTP values in `.env` (default prints emails to the console in development).
* WhatsApp: Meta WhatsApp Cloud API. Set `WHATSAPP_TOKEN` and `WHATSAPP_PHONE_ID`; without them messages are only logged.
  Business-initiated messages outside a 24h customer window must use pre-approved templates: create them in Meta
  Business Manager and put the names in `WHATSAPP_TEMPLATE_ENQUIRY` / `WHATSAPP_TEMPLATE_BOOKING`
  (body variables in order: name, tour title, tour code, booking ref, travel date, total).
* Customer sends enquiry: customer gets an acknowledgement (email + WhatsApp) and the owner is alerted.
* Owner marks Booked: customer gets the confirmation (email + WhatsApp), sent once per booking.

## Verify
```bash
python manage.py check && python manage.py makemigrations --check && python manage.py test
```

## Going live
For a Render preview, choose **New → Blueprint** in Render and connect this GitHub repository. The root `render.yaml`
creates a Python web service and a PostgreSQL database. It sets the secret key and host automatically; `build.sh`
collects static files, and `start.sh` migrates the database and generates demo packages on first start. The admin URL is
`/manage-console/`. Create an admin user from a Render shell with `python manage.py createsuperuser`.

Free Render PostgreSQL expires after 30 days. For a lasting client site, choose a persistent database plan and configure
durable object storage for `/media/` uploads, since Render's web-service filesystem resets on redeploy. Set email and
WhatsApp credentials in Render environment variables; the default email backend only logs messages. Do not commit `.env`,
`db.sqlite3`, or uploaded customer files.

## Content note
Demo packages contain placeholder text, prices and hotel names. Run `python manage.py add_photos` with an internet connection
to download freely licensed travel photos to `media/travel/`; the site links to their authors and licenses at `/photo-credits/`.
The importer shares each image between packages for the same destination, can be rerun safely, and leaves owner uploads untouched.
Review the automatically matched sightseeing photos before publishing; some landmarks have no suitable image and keep their placeholder.

## October homepage and Google update

Windows: extract the ZIP and run `START_LOCAL.bat`. See `LOCAL_SETUP.txt`.
The homepage uses five bundled photographs in a looping horizontal slideshow.
Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env` locally or Render environment settings to enable Google login.
Local redirect URI: `http://127.0.0.1:8000/auth/google/login/callback/`.
Production redirect URI: `https://YOUR-DOMAIN/auth/google/login/callback/`.
