"""SMS transport. Never print codes, credentials, or provider response bodies."""
import re

import requests
from django.conf import settings


class SMSDeliveryError(Exception):
    pass


def send_code(phone, code):
    account = settings.TWILIO_ACCOUNT_SID
    token = settings.TWILIO_AUTH_TOKEN
    service = settings.TWILIO_MESSAGING_SERVICE_SID
    sender = settings.TWILIO_SMS_FROM
    if not (re.fullmatch(r"AC[0-9a-fA-F]{32}", account) and token and (service or sender)):
        raise SMSDeliveryError("SMS delivery is not configured.")
    data = {
        "To": phone,
        "Body": f"Your Sai Samarth Holidays verification code is {code}. Valid for 5 minutes. Do not share this code.",
    }
    if service:
        data["MessagingServiceSid"] = service
    else:
        data["From"] = sender
    try:
        response = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{account}/Messages.json",
            data=data, auth=(account, token), timeout=(3, 10),
        )
        response.raise_for_status()
        if response.json().get("status") in {"failed", "undelivered"}:
            raise SMSDeliveryError("The SMS provider could not send the code.")
    except (requests.RequestException, ValueError):
        raise SMSDeliveryError("The SMS provider could not send the code.") from None
