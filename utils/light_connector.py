import json
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from firebase_admin import db
import logging
from rest_framework.permissions import IsAuthenticated
from customer.serializers import EventSerializer, WalletTransactionSerializer, Listing
from customer.models import Event, Subscription, Wallet, SubscriptionUsage
from admin_app.models import PackageServices, ServiceType, User, Package
from django.db.models import Sum
from datetime import datetime, timezone
from django.conf import settings
from utils.celery.tasks import send_push_notification_task
from utils.push_notifications import send_push_notification

from firebase_admin import credentials, initialize_app, db, get_app

def get_firebase_db():
    """Initialize and return the Firebase DB instance."""
    try:
        # Try to get the named app if it already exists
        firebase_app = get_app('dbApp')
    except ValueError:  # If the app is not initialized yet
        cred = credentials.Certificate("utils/firebase-admin-sdk.json")
        firebase_app = initialize_app(cred, {
            'databaseURL': settings.OLD_FIREBASE_DB_URL
        }, name='dbApp')  # Unique name to avoid conflict
    
    return db.reference('/', app=firebase_app)


logger = logging.getLogger(__name__)
class RoomUpdateView(APIView):
    def post(self,request):
        room_numbers = request
        try:
           
            for room_number in room_numbers:
                # firebase_api_key = 'AIzaSyBV7b3vmVFJ7SBjQ1JMQcMPtUvxSNOs_Vk'
                # firebase_database_url = 'https://travlounge-c3bb6-default-rtdb.asia-southeast1.firebasedatabase.app/'
                # room_path = room_path = f"toloo/room{room_number}"

                # # Construct the endpoint for the room4 node
                # firebase_endpoint = f'{firebase_database_url}/{room_path}.json?auth={firebase_api_key}'

                # # Data to update
                # data_to_update = {
                #     "light": "on"
                # }
                # response = requests.patch(firebase_endpoint, json=data_to_update)
                room_path = f"toloo/room{room_number}"
                ref = get_firebase_db().child(room_path)
                ref.update({'light': 'on'})
            return Response({'message':'Rooms updated'},status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error':str(e)},status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
def getSubPackage(self, request):
    try:
        packages = Package.objects.filter(type=1, is_active=True, is_deleted=False, first_user_only=False)
        package_data = []

        for package in packages:
            services_qs = PackageServices.objects.filter(package=package, is_deleted=False)
            services = []
            for service in services_qs:
                services.append({
                    "name": service.service.service_name,
                    "number": f"{service.discount_value} %" if service.mode == 'percentage' else f"{service.number}",
                    # "description": service.serviceType.get("description") if isinstance(service.serviceType, dict) else None
                })

            package_data.append({
                "id": package.pk,
                "name": package.package_name,
                "amount": int(package.amount),
                "validity": package.days,
                "services": services,
                "description": package.display_description
            })

        return package_data    
    except Exception as e:
        logger.error(f"Error in getSubPackage: {e}")
        return {"error": "An error occurred"}
    
################################################################################EVENTS#################################################################################
# class QrscanView(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         try:
#             qrtype = request.data.get('qrtype')
#             types = request.data.get('types')
#             user_id = request.data.get('user_id')
#             source = request.data.get('source')

#             print("User ID:", user_id)

#             listing = Listing.objects.filter(listing_user=request.user).first()

#             device_token = User.objects.filter(id=user_id).values_list("device_token", flat=True).first()

#             # new count input
#             try:
#                 count = int(request.data.get('count', 1)) or 1
#             except (ValueError, TypeError):
#                 count = 1


#             service_query = ServiceType.objects.filter(qrtype=qrtype, types=types, is_deleted=False).first()

#             if not service_query:
#                 logger.error(f"ServiceType not found for qrtype: {qrtype}, types: {types}")
#                 return Response({"error": "No match found"}, status=status.HTTP_404_NOT_FOUND)

#             num = []
#             # delegate to EventsAPIView with count
#             events_api_instance = EventsAPIView()
#             events_data = {
#                 'user': user_id,
#                 'service': service_query.service_id,
#                 'service_name': service_query.service.service_name,
#                 'serviceType': service_query.id,
#                 'number': count,
#                 'room_numbers': num,
#                 'source': source,
#                 'listing': listing.pk,
#                 'gender': 'Male' if types=='M' else 'Female' if types=='F' else 'Unisex',
#                 'serviceType_name': service_query.serviceType_name,
#                 'original_request': request.data
#             }

#             events_response_data = events_api_instance.post(events_data)
#             response_data = events_response_data.data
#             status_code = events_response_data.status_code

#             if device_token and response_data.get('notification_sent', False) is False:
#                 print('herere')
#                 title = "QR Success" if status_code == 200 else "QR Failed"
#                 message = response_data.get('notification_message', "QR scan successful") if status_code == 200 else "QR scan failed"
#                 send_push_notification(token=device_token, 
#                                        title=title, message=message, 
#                                        status='success' if status_code == 200 else 'failed', 
#                                        room_no=num,
#                                        pop_message=message,
#                                        date=datetime.now().strftime("%Y-%m-%d"),
#                                        time=datetime.now().strftime("%H:%M:%S"),
#                                        name="Toloo",
#                                        location=listing.place,
#                                        required_amount=response_data.get('required_amount', 0),
#                                        wallet_balance=response_data.get('wallet_balance', 0),
#                                        service_name="toloo",
#                                        service_type_name=service_query.serviceType_name,
#                                        )

#             return Response({"data": response_data, "qrtype": qrtype, "status": 'success' if status_code==200 else 'failed'}, status=status_code)

#         except Exception as e:
#             logger.error(f"Error occurred in QrscanView POST: {e}")
#             return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# class EventsAPIView(APIView):
#     permission_classes = [IsAuthenticated]
    
#     def post(self, request):
#         try:
#             notification_message = ""
#             current_date = datetime.now().strftime("%Y-%m-%d")
#             user = request.get("user")

#             service_amount = 0
#             package_service = None

#             chk_subscription = Subscription.objects.filter(user=user, status='Active', expiry_date__gt=current_date, is_deleted=False).first()
#             chk_wallet = Wallet.objects.filter(user=user, status='Active', is_deleted=False).first()

#             service = request.get('service')
#             service_type = request.get('serviceType')
#             number = int(request.get('number', 1))
#             source = request.get('source')
#             listing = request.get('listing')
#             gender = request.get('gender')
#             service_name = request.get('service_name')
#             servicetype_name = request.get('serviceType_name')
#             device_token = User.objects.filter(id=user).values_list("device_token", flat=True).first()

#             listing_obj = Listing.objects.filter(pk=listing).first()
            
#             use_subscription = False
#             # print("chk sub and wallet=",chk_subscription,chk_wallet)
            
#             # 1. If a subscription exists, check if the requested number of services can be deducted.
#             if chk_subscription:
#                 package_service = PackageServices.objects.filter(package=chk_subscription.package,
#                                                                  service=service,
#                                                                  serviceType__contains=service_type,
#                                                                  is_deleted=False
#                                                                  ).first()
#                 if package_service:
#                     chk_events = Event.objects.filter(user=user,
#                                                       service=service,
#                                                       serviceType__in=package_service.serviceType,
#                                                       created_on__gte=chk_subscription.created_on,
#                                                       created_on__lte=chk_subscription.expiry_date,
#                                                       subscription=True,
#                                                       ).aggregate(total_count=Sum('number'))
                    
#                     used_count = chk_events['total_count'] or 0
#                     available_count = package_service.number - used_count
#                     # print("used and available count=",used_count,available_count)
                    
#                     if number <= available_count:
#                         use_subscription = True
            

#             request_data = request.get('original_request', {}).copy()
#             request_data["listing"] = listing

#             # 2. If using subscription is not possible, then attempt to use the wallet.
#             if not use_subscription:
#                 package_amount = PackageServices.objects.filter(service=service,
#                                                                 serviceType__contains=service_type,
#                                                                 number=1,
#                                                                 is_deleted=False,
#                                                                 package__type=2
#                                                                 ).values_list('package__amount', flat=True)
                
#                 amount_value = list(package_amount)[0] if package_amount else 0
#                 service_amount = amount_value
#                 total_amount = service_amount * number

#                 if not chk_wallet:
#                     notification_message = "Not enough credits left. Please pay by other methods."
#                     noti_data = {
#                         "is_paynow": True,
#                         "title": "No Package Found",
#                         "message": notification_message,
#                         "gender": gender,
#                         "service": servicetype_name,
#                         "count": number,
#                         "price": service_amount,
#                         "subscription": getSubPackage(self, request),
#                         "status": "failed",
#                         "pop_message": "Your wallet balance is low. Please pay using other methods.",
#                         "date": current_date,
#                         "time": datetime.now().strftime("%H:%M:%S"),
#                         "request_data": request_data,
#                         "location": listing_obj.place,
#                         "name": "Toloo",
#                         "service_name": "toloo",
#                         "service_type_name": servicetype_name,
#                     }
#                     noti_data["request_data"]["listing"] = listing

#                     if device_token:
#                         send_push_notification(token=device_token, **noti_data)
#                     return Response({"message": notification_message, "notification_data": noti_data, "required_amount": total_amount, "wallet_balance": 0, "notification_sent": True},  status=status.HTTP_400_BAD_REQUEST)



#                 if total_amount > chk_wallet.balance:
#                     notification_message = "Not enough credits left. Please pay by other methods."
#                     noti_data = {
#                             "is_paynow": True,
#                             "title": "Wallet Balance Low",
#                             "message": notification_message,
#                             "gender": gender,
#                             "service": service,
#                             "count": number,
#                             "price": service_amount,
#                             "subscription": getSubPackage(self, request),
#                             "status": "failed",
#                             "pop_message": "Your wallet balance is low. Please add funds.",
#                             "date": current_date,
#                             "time": datetime.now().strftime("%H:%M:%S"),
#                             "request_data": request_data,
#                             "location": listing_obj.place,
#                             "name": "Toloo",
#                             "service_name": "toloo",
#                             "service_type_name": servicetype_name,
#                         }
#                     noti_data["request_data"]["listing"] = listing
                    
#                     if device_token:
#                         send_push_notification(token=device_token, **noti_data) 
#                     return Response({"message": notification_message, "notification_data": noti_data, "wallet_balance": chk_wallet.balance, "required_amount": total_amount, "notification_sent": True}, status=status.HTTP_400_BAD_REQUEST)

#                 # Deduct the calculated total amount from the wallet.
#                 chk_wallet.balance -= total_amount
#                 chk_wallet.save()

#                 WalletTransactionSerializer(data={
#                     'user': user.id,
#                     'amount': total_amount,
#                     'balance': chk_wallet.balance,
#                     'requested_by': user.id,
#                     'transaction_type': 0
#                 }).save()

#             data = {
#                 'user': user,
#                 'service': service,
#                 'serviceType': service_type,
#                 'number': number,
#                 'source': source,
#                 'date': current_date,
#                 'room_numbers': request.get("room_numbers", []),
#                 'subscription': use_subscription,
#                 'listing': listing,
#             }

#             serializer = EventSerializer(data=data)
#             if serializer.is_valid():
#                 serializer.save()

#                 # notification_message = f"{number} Toloo booked successfully"
#                 notification_message = f"Booking Confirmed"
#                 return Response({"message": notification_message, "notification_message": notification_message, "service_amount": service_amount, "count": number}, status=status.HTTP_200_OK)

#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#         except Exception as e:
#             logger.error(f"Error occurred in EventsAPIView POST: {e}")
#             return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class QrscanView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            qrtype = request.data.get('qrtype')
            types = request.data.get('types')
            user_id = request.data.get('user_id')
            source = request.data.get('source')
            count = int(request.data.get('count', 1)) or 1

            listing = Listing.objects.filter(listing_user=request.user).first()
            device_token = User.objects.filter(id=user_id).values_list("device_token", flat=True).first()

            service_query = ServiceType.objects.filter(qrtype=qrtype, types=types, is_deleted=False).first()
            if not service_query:
                return Response({"error": "No matching service found"}, status=status.HTTP_404_NOT_FOUND)

            events_data = {
                'user': user_id,
                'service': service_query.service_id,
                'service_name': service_query.service.service_name,
                'serviceType': service_query.id,
                'number': count,
                'room_numbers': [],
                'source': source,
                'listing': listing.pk if listing else None,
                'gender': 'Male' if types == 'M' else 'Female' if types == 'F' else 'Unisex',
                'serviceType_name': service_query.serviceType_name,
                'original_request': request.data
            }

            events_api = EventsService()
            response_data, status_code = events_api.process_event(events_data)

            if device_token:
                title = "QR Success" if status_code == 200 else "QR Failed"
                send_push_notification(
                    pay_now=False if status_code == 200 else True,
                    token=device_token,
                    title=title,
                    message=response_data.get("notification_message", "QR scanned"),
                    status='success' if status_code == 200 else 'failed',
                    room_no=[],
                    pop_message=response_data.get("pop_message"),
                    date=datetime.now().strftime("%Y-%m-%d"),
                    time=datetime.now().strftime("%H:%M:%S"),
                    name="Toloo",
                    location=listing.place if listing else "",
                    required_amount=response_data.get("required_amount", 0),
                    wallet_balance=response_data.get("wallet_balance", 0),
                    service_name="toloo",
                    service_type_name=service_query.serviceType_name,
                    event_payload=response_data.get("event_payload")  # ✅ Include this
                )

            return Response({
                "data": response_data,
                "qrtype": qrtype,
                "status": 'success' if status_code == 200 else 'failed',
            }, status=status_code)

        except Exception as e:
            logger.exception("Error in QrscanView POST")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class EventsService:
    def process_event(self, data):
        try:
            user_id = data['user']
            service = data['service']
            service_type = data['serviceType']
            number = int(data.get('number', 1))
            device_token = User.objects.filter(id=user_id).values_list("device_token", flat=True).first()
            current_date = datetime.now().strftime("%Y-%m-%d")
            listing_obj = Listing.objects.filter(pk=data['listing']).first()

            # 1. Check subscription
            subscriptions = Subscription.objects.filter(
                user=user_id, 
                status='Active',
                expiry_date__gt=current_date, 
                is_deleted=False
            ).select_related('package').order_by('package__first_user_only', 'package__amount')

            remaining_to_use = number
            used_subscriptions = []
            mode_of_payment = 'direct_payment'  # Default mode

            for subscription in subscriptions:
                if remaining_to_use <= 0:
                    break

                package_service = PackageServices.objects.filter(
                    package=subscription.package,
                    service=service,
                    serviceType__contains=service_type,
                    is_deleted=False
                ).first()

                if package_service:
                    # Get or create subscription usage record
                    subscription_usage, created = SubscriptionUsage.objects.get_or_create(
                        subscription=subscription,
                        service_id=service,
                        service_type_id=service_type,
                        defaults={'used_count': 0}
                    )

                    # Calculate remaining usage
                    remaining = package_service.number - subscription_usage.used_count

                    if remaining > 0:
                        # Calculate how many to use from this subscription
                        to_use = min(remaining, remaining_to_use)
                        
                        # Update usage count
                        subscription_usage.used_count += to_use
                        subscription_usage.save()

                        # Update remaining count
                        remaining_to_use -= to_use
                        used_subscriptions.append({
                            'subscription': subscription,
                            'used': to_use
                        })
                        mode_of_payment = 'subscription'

                        # If this subscription is first_user_only and has remaining credits, don't check other subscriptions
                        if subscription.package.first_user_only and remaining > to_use:
                            break

            # 2. Check wallet for remaining services
            if remaining_to_use > 0:
                wallet = Wallet.objects.filter(user=user_id, status='Active', is_deleted=False).first()
                package_amount = PackageServices.objects.filter(
                    service=service,
                    serviceType__contains=service_type,
                    number=1,
                    is_deleted=False,
                    package__type=2
                ).values_list('package__amount', flat=True).first() or 0

                total_amount = remaining_to_use * package_amount

                if not wallet or wallet.balance < total_amount:
                    # Don't save event yet — return payload for frontend
                    event_payload = {
                        "user": user_id,
                        "service": service,
                        "service_name": data['service_name'],
                        "serviceType": service_type,
                        "number": remaining_to_use,
                        "source": data['source'],
                        "listing": data['listing'],
                        "gender": data.get('gender'),
                        "serviceType_name": data['serviceType_name'],
                        "original_request": data['original_request'],
                    }
                    return {
                        "notification_message": "Wallet balance is low. Please pay using other methods.",
                        "pop_message": "Wallet low or unavailable",
                        "required_amount": total_amount,
                        "wallet_balance": wallet.balance if wallet else 0,
                        "event_payload": event_payload,
                    }, status.HTTP_402_PAYMENT_REQUIRED

                # Deduct from wallet
                wallet.balance -= total_amount
                wallet.save()

                # Create wallet transaction
                wallet_txn_data = {
                    'user': user_id,
                    'amount': total_amount,
                    'balance': wallet.balance,
                    'requested_by': user_id,
                    'transaction_type': 0
                }
                wallet_txn_serializer = WalletTransactionSerializer(data=wallet_txn_data)
                if wallet_txn_serializer.is_valid():
                    wallet_txn_serializer.save()
                else:
                    logger.error(f"WalletTransactionSerializer validation failed: {wallet_txn_serializer.errors}")
                    return {"error": "Transaction could not be recorded", "details": wallet_txn_serializer.errors}, status.HTTP_400_BAD_REQUEST

                mode_of_payment = 'wallet'

            # 3. Create event
            event_data = {
                'user': user_id,
                'service': service,
                'serviceType': service_type,
                'number': number,
                'source': data['source'],
                'date': current_date,
                'room_numbers': data.get('room_numbers', []),
                'subscription': bool(used_subscriptions),  # True if any subscription was used
                'listing': data['listing'],
                'mode_of_payment': mode_of_payment
            }

            serializer = EventSerializer(data=event_data)
            if serializer.is_valid():
                event = serializer.save()
                return {
                    "message": "Event created successfully",
                    "notification_message": "Booking Confirmed",
                    "service_amount": total_amount if remaining_to_use > 0 else 0,
                    "count": number,
                    "subscription_used": bool(used_subscriptions),
                    "mode_of_payment": mode_of_payment
                }, status.HTTP_200_OK

            return serializer.errors, status.HTTP_400_BAD_REQUEST

        except Exception as e:
            logger.error(f"Error in EventsService.process_event: {e}")
            return {"error": str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR

    def _record_event(self, data, use_subscription=False, service_amount=0, mode='direct_payment'):
        """
        Record an event with specified payment mode and amount.
        Used for direct payments and other specific cases.
        """
        try:
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            # If using subscription, update subscription usage
            if use_subscription:
                subscriptions = Subscription.objects.filter(
                    user=data['user'],
                    status='Active',
                    expiry_date__gt=current_date,
                    is_deleted=False
                ).select_related('package').order_by('package__first_user_only', 'package__amount')

                remaining_to_use = data['number']
                used_subscriptions = []

                for subscription in subscriptions:
                    if remaining_to_use <= 0:
                        break

                    package_service = PackageServices.objects.filter(
                        package=subscription.package,
                        service=data['service'],
                        serviceType__contains=data['serviceType'],
                        is_deleted=False
                    ).first()

                    if package_service:
                        subscription_usage, created = SubscriptionUsage.objects.get_or_create(
                            subscription=subscription,
                            service_id=data['service'],
                            service_type_id=data['serviceType'],
                            defaults={'used_count': 0}
                        )

                        remaining = package_service.number - subscription_usage.used_count

                        if remaining > 0:
                            to_use = min(remaining, remaining_to_use)
                            subscription_usage.used_count += to_use
                            subscription_usage.save()

                            remaining_to_use -= to_use
                            used_subscriptions.append({
                                'subscription': subscription,
                                'used': to_use
                            })

                            if subscription.package.first_user_only and remaining > to_use:
                                break

            # Create event
            event_data = {
                'user': data['user'],
                'service': data['service'],
                'serviceType': data['serviceType'],
                'number': data['number'],
                'source': data['source'],
                'date': current_date,
                'room_numbers': data.get('room_numbers', []),
                'subscription': use_subscription,
                'listing': data['listing'],
                'mode_of_payment': mode
            }

            serializer = EventSerializer(data=event_data)
            if serializer.is_valid():
                event = serializer.save()
                return {
                    "message": "Event created successfully",
                    "notification_message": "Booking Confirmed",
                    "service_amount": service_amount,
                    "count": data['number'],
                    "subscription_used": use_subscription,
                    "mode_of_payment": mode
                }, status.HTTP_200_OK

            return serializer.errors, status.HTTP_400_BAD_REQUEST

        except Exception as e:
            logger.error(f"Error in EventsService._record_event: {e}")
            return {"error": str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR

#################################################################################################
class RoomNumbers(APIView):
    def post(self, request):
        print(request,'kkkk')

        room_list = []
        rooms_data = get_firebase_db().child("toloo").get()
        for i, j in rooms_data.items():
            if 'light' in j and j['light'] == 'off':
                room_list.append(int(''.join([char for char in i if char.isdigit()])))

        service_query = ServiceType.objects.filter(id=request).first()
        list1 = list(service_query.numbers)
        list2 = list(room_list)
        list3 = [x for x in list1 if x in list2]
        try:
            num = [list3[0]]
        except:
            num = 0
        return num
        

class AllRoomOff(APIView):
    def post(self, request):
        result = allRoomsOff()
        if result["status"] == "success":
            return Response(result["message"], status=status.HTTP_200_OK)
        else:
            return Response({"error": result["message"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def allRoomsOff():
    try:
        rooms_data = get_firebase_db().child("toloo").get()
        for room_number in rooms_data:
            room_ref = get_firebase_db().child(f"toloo/{room_number}/light")
            room_ref.set("off")
            rooms_data[room_number]["light"] = "off"
        return {"status": "success", "message": "All the room lights are off"}
    except Exception as e:
        logger.error(f"Error occurred in allRoomsOff: {e}")
        return {"status": "error", "message": str(e)}


class TolooConfirmation(APIView):
    permission_classes = [IsAuthenticated]

    '''This API is only used to confirm a toloo event in the case it is paid for by the user and not through the subscription'''

    def post(self, request):
        try:
            user = request.data.get('user_id')
            qrtype = request.data.get('qrtype')
            types = request.data.get('types')
            source = request.data.get('source')
            count = request.data.get('count')
            room_number = int(request.data.get('room_number'))
            listing = request.data.get("listing")
            
            service_query = ServiceType.objects.filter(qrtype=qrtype, types=types, is_deleted=False).first()

            # create an even to confirm the toloo
            data = {
                'user': user,
                'service': service_query.service_id,
                'serviceType': service_query.id,
                'number': count,
                'source': source,
                'date': datetime.now().strftime("%Y-%m-%d"),
                'room_numbers': [room_number],
                'subscription': False,
                'listing': listing,
            }
            event_serializer = EventSerializer(data=data)
            if event_serializer.is_valid():
                event_serializer.save()
                return Response({"message": "Event created successfully", "room_number": room_number},
                                status=status.HTTP_200_OK)
            return Response(event_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error occurred in TolooConfirmation POST: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)