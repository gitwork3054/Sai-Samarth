# SMS confirmation for customer accounts

Signup requires a mobile number. Email/password and Google login stop at an SMS
verification screen before an authenticated session is created. Existing users
enrol a mobile number after proving their password or Google identity. A verified
mobile number cannot be replaced during a pending login.

Codes contain six digits, expire after five minutes, allow three incorrect
attempts and two resends. SMS requests have per-number and per-IP limits. Codes
stay in the server-side login session; never use cookie-based sessions for this
flow. Keep the allauth dependency pinned and rerun the authentication tests when
upgrading: the custom stage extends its phone verification process.

## Delivery configuration before merging

The included transport uses Twilio Programmable Messaging over HTTPS. Set these
secrets in the existing Render service environment, not in Git or chat:

- TWILIO_ACCOUNT_SID
- TWILIO_AUTH_TOKEN
- TWILIO_MESSAGING_SERVICE_SID (recommended), or TWILIO_SMS_FROM

The Twilio account and sender must support the recipients' countries and the
message template. Complete any sender/template registration required by the
provider for Indian destinations. SMS charges depend on the provider account.
No SMS account, paid service or sender is created by this change.

If another gateway is used, replace accounts.sms.send_code while preserving its
signature and SMSDeliveryError contract. Do not merge until that transport is
configured and a real test text has been received.

Deployment runs the MobileNumber migration through the existing start.sh.
Customer SMS verification must be tested with a dedicated account; do not disable
the verification stage to work around a delivery problem. Owner-console login
continues using Django admin's own authentication.

The current single-instance service uses Django's default cache for allauth's
request limits. Configure a shared cache before adding processes or instances so
all workers enforce the same sending limits.
