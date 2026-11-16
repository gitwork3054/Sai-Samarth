"""SMS transport. Log only allowlisted status codes, never message bodies or recipients."""
import logging
import re

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class SMSDeliveryError(Exception):
    def __init__(self, message="Text verification is unavailable right now. Please contact our team for help.", *, reason="provider"):
        super().__init__(message)
        self.reason = reason


def configuration_problems():
    values = {key: str(getattr(settings, key, "")).strip() for key in (
        "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_MESSAGING_SERVICE_SID", "TWILIO_SMS_FROM")}
    problems = []
    if not re.fullmatch(r"AC[0-9a-fA-F]{32}", values["TWILIO_ACCOUNT_SID"]):
        problems.append("TWILIO_ACCOUNT_SID")
    if not values["TWILIO_AUTH_TOKEN"]:
        problems.append("TWILIO_AUTH_TOKEN")
    if values["TWILIO_MESSAGING_SERVICE_SID"]:
        if not re.fullmatch(r"MG[0-9a-fA-F]{32}", values["TWILIO_MESSAGING_SERVICE_SID"]):
            problems.append("TWILIO_MESSAGING_SERVICE_SID")
    elif not values["TWILIO_SMS_FROM"]:
        problems.append("TWILIO_MESSAGING_SERVICE_SID_OR_TWILIO_SMS_FROM")
    return values, problems


def provider_code(response):
    try:
        value = response.json().get("code")
        return int(value) if re.fullmatch(r"[0-9]{4,6}", str(value)) else None
    except (ValueError, AttributeError, TypeError):
        return None


def check_provider():
    """Read-only credential check. Does not send messages or return account data."""
    values, problems = configuration_problems()
    if problems:
        return "configuration_invalid", problems
    account = values["TWILIO_ACCOUNT_SID"]
    try:
        response = requests.get(
            f"https://api.twilio.com/2010-04-01/Accounts/{account}.json",
            auth=(account, values["TWILIO_AUTH_TOKEN"]), timeout=(3, 8),
        )
        if response.status_code != 200:
            return "provider_rejected", [str(response.status_code), str(provider_code(response))]
        if response.json().get("status") != "active":
            return "account_not_active", []
    except (requests.RequestException, ValueError, AttributeError):
        return "provider_unreachable", []
    return "credentials_accepted", []


def send_code(phone, code):
    values, problems = configuration_problems()
    if problems:
        logger.error("SMS delivery configuration invalid: keys=%s", ",".join(problems))
        raise SMSDeliveryError(reason="configuration")
    account = values["TWILIO_ACCOUNT_SID"]
    data = {
        "To": phone,
        "Body": f"Your Sai Samarth Holidays verification code is {code}. Valid for 5 minutes. Do not share this code.",
    }
    if values["TWILIO_MESSAGING_SERVICE_SID"]:
        data["MessagingServiceSid"] = values["TWILIO_MESSAGING_SERVICE_SID"]
    else:
        data["From"] = values["TWILIO_SMS_FROM"]
    try:
        response = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{account}/Messages.json",
            data=data, auth=(account, values["TWILIO_AUTH_TOKEN"]), timeout=(3, 10),
        )
        if response.status_code not in (200, 201, 202):
            error = provider_code(response)
            logger.error("SMS send rejected: http_status=%s provider_code=%s", response.status_code, error)
            if error == 21608:
                raise SMSDeliveryError("A text could not be sent to this number. Please contact our team for help.", reason="recipient")
            if response.status_code == 429:
                raise SMSDeliveryError("Too many text requests. Please wait a minute before trying again.", reason="rate_limit")
            raise SMSDeliveryError()
        if response.json().get("status") not in {"queued", "accepted", "sending", "sent", "delivered"}:
            logger.error("SMS send rejected: reason=unexpected_delivery_status")
            raise SMSDeliveryError()
    except (requests.RequestException, ValueError, AttributeError):
        logger.error("SMS send failed: reason=network_or_invalid_response")
        raise SMSDeliveryError("We couldn’t reach the text-message service. Please try again shortly.", reason="network") from None
