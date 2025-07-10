from firebase_admin import messaging
from rest_framework.views import APIView
from rest_framework.response import Response
from django.middleware.csrf import get_token
from django.http import JsonResponse



class SendSMSAPIView(APIView):
    def post(self, request):
        
        import requests
        url = "https://control.msg91.com/api/v5/flow/"
        payload = {
            "template_id": "64c351a5d6fc05451332f804",
            "short_url": "1",
            "recipients": [
            {
                "mobiles": "91"+request,
                "OTP": 'sleeping pod booked successfully',
            }
        ]
    }
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "authkey": "401606Ajx5LMUJ64b4e5d6P1"   
        }
        response = requests.post(url, json=payload, headers=headers)
        print(response.text)
        return response.text

