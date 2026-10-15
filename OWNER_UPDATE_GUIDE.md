# State-wise project update

This update extends the original state-wise project and its existing appearance.
Existing imported itineraries and tour PDFs remain intact.

## Install

For an existing installation, back up the database and media, install requirements,
run `python manage.py migrate` and `python manage.py collectstatic --noinput`, then
restart the app. Keep your existing database and uploads. The ZIP contains source
and bundled assets, not customer data. For a fresh local setup, extract and run
START_LOCAL.bat; create an owner login using `python manage.py createsuperuser`.

## Owner controls

- Site settings: state/country order (one name per line), slideshow interval,
  preview length, corporate/contact introductions, Google review link, booking
  terms, optional analytics and guided trip helper.
- Home slides: edit photos, headings, captions, order and visibility. The existing
  five slides are seeded by migration.
- Domestic shows states first. International shows countries. Group tours have
  Domestic/International links. Add partner URLs to destinations or packages.
- Packages retain full content with expandable previews. Set related packages
  manually or use automatic state/country, theme and price recommendations.
- Sightseeing: enter opening hours, closed days, tickets, best time, photos,
  website, YouTube link and FAQs (`Question | Answer`, one pair per line).
- Hotels: multiple options per tier, room options (one per line), photos and
  websites. Activities support photos and the existing adult/child rates.
- Corporate services and Customer reviews: add approved copy and genuine reviews.
  Empty sections remain hidden. Google reviews are linked, not automatically synced.
- Contact requests hold submitted enquiries. Saved packages show signed-in users'
  supplied contacts. Visit events provide consented tour/PDF activity with admin
  filters. They do not reveal anonymous visitors' phone numbers or emails.
  Visitors can change consent using Privacy preferences in the footer.

## Staff quotations

Open an enquiry, choose travellers, hotel, departure and extras. Enter a markup
percentage (e.g. 9 or 10), optional confirmed base override, itinerary and notes.
Select the enquiry and run **Generate quotation**, then use its download link.
The authoritative calculator creates a stored snapshot. Customer PDFs show the
final price and extras; internal base cost and markup remain in admin. Regenerate
after editing. Generation does not send messages or change public package prices.
Only staff with enquiry viewing permission can download quotations.

Approved booking terms entered in Site settings require acceptance at enquiry time.
Acceptance and the exact wording are saved with the enquiry.

## Integration and content inputs

- Email/WhatsApp require real environment credentials and approved templates.
- Optional read-only CRM exports: set a strong CRM_API_TOKEN environment value,
  then send `Authorization: Bearer <token>` to `/api/crm/v1/packages/` or
  `/api/crm/v1/enquiries/`. Version 1 responses paginate 50 records per page using
  `?page=2`. Enquiry exports contain private contacts: protect the token. Blank
  token disables token access. Staff access requires the relevant view permission.
- The trip helper searches existing tours; it is not AI. Full CRM integration,
  supplier catalogue synchronization and advertising require separate setup.
- Add actual international packages/supplier URLs, corporate text, hotel and
  sightseeing facts, genuine reviews and approved terms in admin. Missing business
  facts have not been invented. Existing adult/child pricing remains; extra-adult
  and infant categories were not introduced.
- Sitemap, robots and entered FAQ structured data are included; rankings are not
  guaranteed.

## Verification

32 automated tests cover existing flows and new filters, quotations, terms,
consented events, contacts, SEO and protected CRM exports. Desktop and 390px mobile
checks found no JavaScript errors or horizontal overflow. Quotation PDF inspected.
