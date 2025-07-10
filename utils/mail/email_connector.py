import requests
import json
from django.conf import settings
from datetime import datetime, date
from decimal import Decimal

class MSG91EmailConnector:
    BASE_URL = "https://control.msg91.com/api/v5/email/send"

    def __init__(self):
        self.auth_key = settings.MSG91_AUTH_KEY
        self.from_email = settings.MSG91_FROM_EMAIL
        self.domain = settings.MSG91_DOMAIN
        self.booking_template_id = settings.MSG91_BOOKING_TEMPLATE_ID

    def send_booking_confirmation(self, recipient_name, recipient_email, booking_id, check_in_date, amount):
        """
        Sends a booking confirmation email via MSG91 Email API.

        :param recipient_name: Name of the recipient
        :param recipient_email: Email address of the recipient
        :param booking_id: Unique booking ID
        :param check_in_date: Check-in date
        :param amount: Total amount
        :return: API response as a dictionary
        """
        headers = {
            "accept": "application/json",
            "authkey": self.auth_key,
            "content-type": "application/json"
        }

        payload = {
            "recipients": [
                {
                    "to": [
                        {
                            "name": recipient_name,
                            "email": recipient_email
                        }
                    ],
                    "variables": {
                        "name": recipient_name,
                        "booking_id": booking_id,
                        "check_in_date": check_in_date,
                        "amount": amount
                    }
                }
            ],
            "from": {
                "email": self.from_email
            },
            "domain": self.domain,
            "template_id": self.booking_template_id
        }

        try:
            response = requests.post(self.BASE_URL, headers=headers, data=json.dumps(payload))
            print('response from send_booking_confirmation=', response)
            return response.json()  # Return the API response
        except requests.RequestException as e:
            return {"error": str(e)}
