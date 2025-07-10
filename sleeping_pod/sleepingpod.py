from datetime import datetime, timedelta
from django.utils import timezone
import json
from admin_app.models import *
from customer.models import *
from billing.models import *
from .models import *
from .serializers import *
from customer.serializers import EventSerializer
from django.http import JsonResponse
from utils.smsgateway import SendSMSAPIView

json_file_path = 'utils/sleepingpod.json'

def get_allpods():
    with open(json_file_path, 'r') as file:
        data = json.load(file)
        for item in data['number']:
            service_type_id = item.get('serviceType')
        
        
            # Fetch the ServiceType object from the database
            service_type_obj = ServiceType.objects.filter(id=service_type_id,is_deleted=False).first()

            # Set the 'serviceTypeName' key with the service type name
            item['serviceType_name'] = service_type_obj.serviceType_name if service_type_obj else ''
        for item in data['sleepingpod']:
            service_type_id = item.get('serviceType')
        
        
            # Fetch the ServiceType object from the database
            service_type_obj = ServiceType.objects.filter(id=service_type_id,is_deleted=False).first()

            # Set the 'serviceTypeName' key with the service type name
            item['serviceType_name'] = service_type_obj.serviceType_name if service_type_obj else ''


    return data
    # return data
def get_availablepods(current_date):
    today = current_date
    fromdate = str(today) + ' 00:00:00.000000'
    todate = str(today) + ' 23:59:59.999999'
    current_time = datetime.now().time()
    formatted_time = current_time.strftime('%H:%M:%S')
    total_pods = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23]
    active_pods = []
    inactive_pods = [] 
    events = Event.objects.filter(is_deleted=False, created_on__gte=fromdate, created_on__lte=todate).exclude(sleepingpod_numbers__isnull=True)
    if events:
        for event in events:
            if event.checkout_time is not None:
                checkout_time_obj = datetime.strptime(str(event.checkout_time), '%H:%M:%S').time()
                after2_datetime = datetime.combine(datetime.today(), checkout_time_obj) + timedelta(hours=2)
                after2_time_str = after2_datetime.strftime('%H:%M:%S')
                if formatted_time >= after2_time_str:
                    active_pods = event.sleepingpod_numbers
                else:
                    inactive_pods.extend(event.sleepingpod_numbers)
            else:
                checkin_time_obj = datetime.strptime(str(event.checkin_time), '%H:%M:%S').time()
                checkout_datetime = datetime.combine(datetime.today(), checkin_time_obj) + timedelta(hours=event.hours)
                checkout_time = checkout_datetime.strftime('%H:%M:%S')
                checkout_time_obj = datetime.strptime(str(checkout_time), '%H:%M:%S').time()
                after2_datetime = datetime.combine(datetime.today(), checkout_time_obj) + timedelta(hours=2)
                after2_time_str = after2_datetime.strftime('%H:%M:%S')
                if formatted_time <= after2_time_str:
                   active_pods = event.sleepingpod_numbers
                else:
                   inactive_pods.extend(event.sleepingpod_numbers)
    else:
        active_pods = total_pods
    total_pods = list(set(total_pods) - set(inactive_pods))

    return total_pods

# def get_availablepods(current_date):
#     today = current_date
#     fromdate = str(today) + ' 00:00:00.000000'
#     todate = str(today) + ' 23:59:59.999999'
#     current_time = datetime.now().time()
#     formatted_time = current_time.strftime('%H:%M:%S')
#     total_pods = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23]
#     active_pods = []
#     inactive_pods = [] 
#     events = Event.objects.filter(is_deleted=False, created_on__gte=fromdate, created_on__lte=todate).exclude(sleepingpod_numbers__isnull=True)
#     if events:
#         for event in events:
#             if event.checkout_time is not None:
#                 checkout_time_obj = datetime.strptime(str(event.checkout_time), '%H:%M:%S').time()
#                 after2_datetime = datetime.combine(datetime.today(), checkout_time_obj) + timedelta(hours=2)
#                 after2_time_str = after2_datetime.strftime('%H:%M:%S')
#                 if formatted_time >= after2_time_str:
#                     active_pods = event.sleepingpod_numbers
#                 else:
#                     inactive_pods.extend(event.sleepingpod_numbers)
#             else:
#                 checkin_time_obj = datetime.strptime(str(event.checkin_time), '%H:%M:%S').time()
#                 checkout_datetime = datetime.combine(datetime.today(), checkin_time_obj) + timedelta(hours=event.hours)
#                 checkout_time = checkout_datetime.strftime('%H:%M:%S')
#                 checkout_time_obj = datetime.strptime(str(checkout_time), '%H:%M:%S').time()
#                 after2_datetime = datetime.combine(datetime.today(), checkout_time_obj) + timedelta(hours=2)
#                 after2_time_str = after2_datetime.strftime('%H:%M:%S')
#                 if formatted_time <= after2_time_str:
#                    active_pods = event.sleepingpod_numbers
#                 else:
#                    inactive_pods.extend(event.sleepingpod_numbers)
#     else:
#         active_pods = total_pods
#     total_pods = list(set(total_pods) - set(inactive_pods))

#     return total_pods

def check_availablepods(date,start_time,hour):
    date = date
    start_time = start_time
    hour = int(hour)
    placeholder_date = datetime.strptime(date, '%Y-%m-%d')
    start_datetime = datetime.combine(placeholder_date, datetime.strptime(start_time, '%H:%M:%S').time())
    end_datetime = start_datetime + timedelta(hours=hour)
    end_time = end_datetime.strftime('%H:%M:%S')
    total_pods = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23]
    events = Event.objects.filter(is_deleted=False, date=date).exclude(sleepingpod_numbers__isnull=True)
    available_pods = total_pods.copy() 
    for event in events:
        checkout_datetime = datetime.combine(event.date, event.checkout_time)
        checkin_datetime = datetime.combine(event.date, event.checkin_time)
        cleaning_start_time = checkout_datetime + timedelta(hours=2)
        if start_datetime < cleaning_start_time and end_datetime > checkin_datetime:
            available_pods = [pod for pod in available_pods if pod not in event.sleepingpod_numbers]
    # with open(json_file_path, 'r') as file:
    #     existing_data = json.load(file)
    sleepingpod_item = Sleepingpod_item.objects.filter(is_deleted = False)
    
    for entry in sleepingpod_item:
        
        if entry.id == 1:
            entry.room_numbers = [pod for pod in available_pods if pod in [2, 3, 4, 5, 8, 9, 10, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22]]
        elif entry.id == 2:
            entry.room_numbers = [pod for pod in available_pods if pod in [1, 6, 7, 11]]
        elif entry.id == 3:
            entry.room_numbers = [pod for pod in available_pods if pod in [23]]

    # with open(json_file_path, 'w') as json_file:
    #     json.dump(existing_data, json_file)
    serializer = CheckItemSerializer(sleepingpod_item, many=True)
    return serializer.data

def save_pods(data,mobile):
    serializer = EventSerializer(data=data)
    if serializer.is_valid():
        serializer.save()
        sendsms = SendSMSAPIView()
        sendsms.post(mobile)
        return 200
    else:
        return 400


# def send_sms(mobile):
#     import requests
#     url = "https://control.msg91.com/api/v5/flow/"
#     payload = {
#         "template_id": "64c351a5d6fc05451332f804",
#         "short_url": "1",
#         "recipients": [
#         {
#              "mobiles": "91"+mobile,
#              "OTP": 'sleeping pod booked successfully',
#         }
#     ]
#  }
#     headers = {
#          "accept": "application/json",
#          "content-type": "application/json",
#         "authkey": "401606Ajx5LMUJ64b4e5d6P1"   
#      }
#     response = requests.post(url, json=payload, headers=headers)
#     print(response.text)
#     return response.text




