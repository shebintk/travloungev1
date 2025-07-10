from firebase_admin import messaging
from rest_framework.views import APIView
from rest_framework.response import Response
from firebase_admin.exceptions import FirebaseError
from django.middleware.csrf import get_token
from django.http import JsonResponse
import requests
import json
from django.conf import settings
import datetime


# def send_fcm_notification(registration_token, room_number):
#     try:
#         message = messaging.Message(
#             notification=messaging.Notification(
#                 title="QR Code Scanned",
#                 body=f"Room number: {room_number}"
#             ),
#             token=registration_token

#         response = messaging.send(message) 
#         print('Message sent:', response)
#     except Exception as e:
#         print('Error sending message:', e)

def get_csrf_token(request):
    csrf_token = get_token(request)
    return JsonResponse({'csrf_token': csrf_token}) 

class PushNotificationAPIView(APIView):
    def post(self, request):
        try:
            device_token = request.data.get('device_token')
            message = messaging.Message(
                notification=messaging.Notification(
                    title='Dummy Title',
                    body='This is a dummy notification message'
                    ),
                token=device_token
            )   
            response = messaging.send(message)
            return Response({'success': True, 'message': 'Notification sent successfully.'})
        except FirebaseError as e:
            return Response({'success': False, 'message': f'Failed to send notification: {e}'})
        

def send_push_notification(token, title, message, **kwargs):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    # print("token", token)
    extra_data = {
                "status": kwargs.get("status"),
                "pay_now": kwargs.get("pay_now"),
                "is_popup": True,
                "id": kwargs.get("listing_id"),
                "duration": kwargs.get("duration", 0),
                "time": kwargs.get("time"),
                "date": kwargs.get("date"),
                "location": kwargs.get("location", ""),
                "name": kwargs.get("name","Dummy name"),
                "image": kwargs.get("image", "https://stage-travlounge-bucket.s3.amazonaws.com/listing_image/86_screenshot2(1)_20250209200821.png"),
                "message": kwargs.get("pop_message", None),
                "service_name": kwargs.get('service_name'),
                "service_type_name": kwargs.get('service_type_name'),
            }
    
    if kwargs.get("room_no") is not None:
        extra_data['room_no'] = kwargs.get("room_no")
    if kwargs.get("wallet_balance"):
        extra_data['wallet_balance'] = int(kwargs.get("wallet_balance", 0))
    if kwargs.get("required_amount"):
        extra_data['required_amount'] = int(kwargs.get("required_amount", 0))
    if kwargs.get("event_payload") is not None:
        extra_data['event_payload'] = kwargs.get("event_payload")

    data = {
        "to": token,
        "title": title,
        "body": message,
        "sound": "default",
        "is_priority": True,
        "data": extra_data
    }

    # print("data=====\n", data)
    # for d in data["data"]:
    #     print(f"{d}: {data['data'][d]}")
    # print("Current time:", datetime.datetime.now().strftime("%I:%M:%S %p"))
    try:
        response = requests.post(settings.EXPO_PUSH_URL, headers=headers, data=json.dumps(data))
        print("Notification response=", response.json()['data'])
    except Exception as e:
        print(f"Push notification error: {e}")

