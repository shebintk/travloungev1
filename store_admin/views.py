from django.shortcuts import get_object_or_404, render
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from rest_framework.response import Response
from rest_framework import status
from admin_app.models import *
from customer.serializers import *
from .serializers import *
from django.contrib.auth.hashers import make_password
from django.contrib.auth import login
from rest_framework_simplejwt.tokens import RefreshToken
import logging
from datetime import datetime, timedelta
from django.contrib.auth import authenticate, login
from rest_framework.permissions import IsAuthenticated,AllowAny
from django.contrib.auth import authenticate
from rest_framework.parsers import JSONParser
from django.db.models import Sum
from django.http import QueryDict
import requests
from random import randint
from botocore.exceptions import ClientError
from utils.s3connector import upload_image_to_s3
from utils.light_connector import RoomUpdateView,RoomNumbers
from django.utils import timezone
from utils.push_notifications import send_push_notification


logger = logging.getLogger(__name__)

        
class EventsAPIView(APIView):
    # permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            events = Event.objects.filter(user=request.data.user, is_deleted=False)
            serializer = WalletSerializer(events, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error occurred in EventsAPIView GET: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request):
        try:
            chk_subscription = Subscription.objects.filter(user=request.data['user'],status='Active',is_deleted=False).last()
            chk_wallet = Wallet.objects.filter(user=request.data['user'],status='Active',is_deleted=False).last()
            total_amount = 0
            room_numbers = None
            x=0
            current_date = timezone.now().date()
            
            for value in request.data['service']:
                service = value['service']
                service_type = value['serviceType']
                number = value['number']
                if chk_subscription:
                    package_service = PackageServices.objects.filter(package=chk_subscription.package,service=service,serviceType__contains=service_type,is_deleted=False).first()
                    chk_events = Event.objects.filter(user=request.user.id,service=service,serviceType__in=[service_type],created_on__gte=chk_subscription.subscribed_date,created_on__lte=chk_subscription.expiry_date).aggregate(total_count=Sum('number'))
                   
                    if chk_events['total_count']:
                        if chk_events['total_count'] > package_service.number:
                            x=2
                            # return Response({"message": "usage of service is exceeded."}, status=status.HTTP_400_BAD_REQUEST)
                        else:
                            chk_balance = package_service.number - chk_events['total_count']
                            if number > chk_balance:
                                x=1
                                # return Response({"message": "You only have a balance of "+str(chk_balance)+" services remaining ."}, status=status.HTTP_400_BAD_REQUEST)
                if chk_wallet or x in (1,2):
                    package_amount = PackageServices.objects.filter(service=service,serviceType__contains=service_type,number=1,is_deleted=False,package__type=2).values_list('package__amount', flat=True)
                    amount_value = list(package_amount)[0] if package_amount else None
                    service_amount = amount_value
                    total_number = number
                    total_amount += service_amount*total_number
                    if total_amount > chk_wallet.balance:
                        return Response({"message": "You only have a balance of "+chk_wallet.balance+" services remaining ."}, status=status.HTTP_400_BAD_REQUEST)
                    balance = chk_wallet.balance-total_amount
                    Wallet.objects.filter(user=request.data['user'],status='Active',is_deleted=False).update(balance=balance)
                    transaction_data = {
                    'user': request.data['user'],
                    'amount': total_amount,
                    'balance': balance ,
                    'requested_by':request.data['user'],
                    'transaction_type':0
                    }
                    transactionSerializer = WalletTransactionSerializer(data=transaction_data)
                    if transactionSerializer.is_valid():
                        transactionSerializer.save()
                    else:
                        return Response(transactionSerializer.errors, status=status.HTTP_400_BAD_REQUEST)
                else:
                    return Response({'message': 'User dont have any active plan!'}, status=status.HTTP_400_BAD_REQUEST)
                if service == 2:
                    service_query = ServiceType.objects.filter(id=service_type).first()
                    if service_query.qrtype!=2:
                        getrooms = RoomNumbers()   
                        room_numbers = getrooms.post(service_type)
                        if room_numbers == 0:
                            return Response({"response": "No rooms available"}, status=status.HTTP_404_NOT_FOUND)


                   
                data = {
                    
                 'user': request.data['user'],
                 'service': service,
                 'serviceType': service_type,
                 'number': number,
                 'source':'m',
                 'date': current_date
                 
                }
                
                serializer = EventSerializer(data=data)
                if serializer.is_valid():
                    serializer.save()
                    if room_numbers:
                        room_update_data = room_numbers
                        room_update_view = RoomUpdateView()# Replace with actual data
                        room_update_response = room_update_view.post(room_update_data)
                else:
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            return Response({'message': 'Event created successfully!','room_numbers':room_numbers}, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Error occurred in EventsAPIView POST: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class UserIdView(APIView):
    def post(self, request):
        try:
            mobile_number = request.data.get('mobile_number')
            user = User.objects.filter(mobile_number=mobile_number).first()
            if user:
                response_data = {
                    'user_id': user.id
                }
                return Response(response_data, status=status.HTTP_200_OK)
            else:
                return Response({"error": "User not found for the given mobile number"}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class ServiceAPIView(APIView):
    # permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        try:
            services = Service.objects.all()
            serializer = ServiceSerializer(services, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class RedeemAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def push(self, **kwargs):
        if self.device_token:
            send_push_notification(
                token=self.device_token,
                date=datetime.now().strftime("%Y-%m-%d"),
                time=datetime.now().strftime("%H:%M:%S"),
                **kwargs
            )

    def get(self, request):
        try:
            service_types = ServiceType.objects.exclude(service__in=[1, 2], is_deleted=False)
            serializer = ServiceTypeSerializer(service_types, many=True)
            logger.info(f"Successfully retrieved service types for user {request.user.id}")
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error in RedeemAPIView GET: {str(e)}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        try:
            user = request.user.id
            listing = Listing.objects.filter(listing_user=user).first()

            current_date = timezone.now().date()
            user_id = request.data.get('user_id')
            selected_data = request.data.get('selected_data', [])


            self.device_token = User.objects.filter(id=user_id).values_list('device_token', flat=True).first()

            if not selected_data:
                logger.warning(f"No service data provided for user {user_id}")
                return Response({"message": "No service data provided."}, status=status.HTTP_400_BAD_REQUEST)

            active_subscriptions = Subscription.objects.filter(user=user_id, is_deleted=False, status='Active', expiry_date__gte=current_date).order_by('subscribed_date')

            if not active_subscriptions.exists():
                logger.warning(f"No active subscription found for user {user_id}")
                self.push(
                    status='failed',
                    title="QR Scan Failed",
                    message="No active subscription found.",
                    pop_message="Please subscribe to a Package to redeem this service.",
                    name=listing.display_name,
                    service_name="bean_wagon",
                    service_type_name="Capuccino",
                    location=listing.place
                )
                return Response({'message': 'No active subscription found!', 'status': 'failed'}, status=status.HTTP_400_BAD_REQUEST)

            for service_data in selected_data:
                servicetype_id = service_data.get('id')
                number = service_data.get('count')

                if number is None:
                    logger.warning(f"Count not provided for service {servicetype_id} by user {user_id}")
                    return Response({"message": "Count is required."}, status=status.HTTP_400_BAD_REQUEST)

                number = int(number)

                get_servicetype = ServiceType.objects.filter(id=servicetype_id, is_deleted=False).first()
                if not get_servicetype:
                    logger.warning(f"Invalid service type {servicetype_id} requested by user {user_id}")
                    return Response({"message": "Invalid service type."}, status=status.HTTP_400_BAD_REQUEST)

                # Step 1: Sum allowed and used from all subscriptions
                total_allowed = 0
                total_used = 0
                matched_subscriptions = []

                for sub in active_subscriptions:
                    package_service = PackageServices.objects.filter(
                        package=sub.package,
                        service=get_servicetype.service,
                        mode='number',
                        is_deleted=False
                    ).first()

                    if package_service and get_servicetype.id in package_service.serviceType:
                        allowed = package_service.number or 0
                        # Get used count from SubscriptionUsage instead of Event
                        used = SubscriptionUsage.objects.filter(
                            subscription=sub,
                            service_id=get_servicetype.service_id,
                            service_type_id=get_servicetype.id
                        ).values_list('used_count', flat=True).first() or 0

                        total_allowed += allowed
                        total_used += used
                        matched_subscriptions.append(sub)


                if not matched_subscriptions:
                    logger.warning(f"Service type {servicetype_id} not included in any package for user {user_id}")
                    self.push(
                        status='failed',
                        title="QR Scan Failed",
                        message="This service type is not included in your package.",
                        pop_message="This service type is not included in your current package.",
                        name=listing.display_name,
                        service_name="bean_wagon",
                        service_type_name=get_servicetype.serviceType_name,
                        location=listing.place
                    )
                    return Response({"message": "This service type is not included in your package.", 'status': 'failed'}, status=status.HTTP_400_BAD_REQUEST)

                balance = total_allowed - total_used
                if total_used >= total_allowed:
                    logger.warning(f"Service usage exceeded for service {servicetype_id} by user {user_id}")
                    self.push(
                        status='failed',
                        title="QR Scan Failed",
                        message="Service usage exceeded.",
                        pop_message="You have exceeded the usage limit for this service.",
                        name=listing.display_name,
                        service_name="bean_wagon",
                        service_type_name=get_servicetype.serviceType_name,
                        location=listing.place
                    )
                    return Response({"message": "Service usage exceeded.", 'status': 'failed'}, status=status.HTTP_400_BAD_REQUEST)

                if number > balance:
                    logger.warning(f"Insufficient balance for service {servicetype_id} by user {user_id}. Requested: {number}, Available: {balance}")
                    self.push(
                        status='failed',
                        title="QR Scan Failed",
                        message=f"You only have {balance} coupons remaining.",
                        pop_message=f"You only have {balance} coupons remaining.",
                        name=listing.display_name,
                        service_name="bean_wagon",
                        service_type_name=get_servicetype.serviceType_name,
                        location=listing.place
                    )
                    return Response({"message": f"You only have {balance} coupons remaining.", "balance_coupons": balance, 'status': 'failed'}, status=status.HTTP_400_BAD_REQUEST)

                # Step 2: Update subscription usage and save event
                remaining_to_use = number
                used_subscriptions = []

                for subscription in matched_subscriptions:
                    if remaining_to_use <= 0:
                        break

                    package_service = PackageServices.objects.filter(
                        package=subscription.package,
                        service=get_servicetype.service,
                        serviceType__contains=get_servicetype.id,
                        is_deleted=False
                    ).first()

                    if package_service:
                        # Get or create subscription usage record
                        subscription_usage, created = SubscriptionUsage.objects.get_or_create(
                            subscription=subscription,
                            service_id=get_servicetype.service_id,
                            service_type_id=get_servicetype.id,
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

                            # If this subscription is first_user_only and has remaining credits, don't check other subscriptions
                            if subscription.package.first_user_only and remaining > to_use:
                                break

                # Save event
                data = {
                    'user': user_id,
                    'service': get_servicetype.service_id,
                    'serviceType': get_servicetype.id,
                    'number': number,
                    'subscription': True,
                    'date': current_date,
                    'source': 'm',
                    'listing': listing.pk,
                }

                serializer = EventSerializer(data=data)
                if serializer.is_valid():
                    event = serializer.save()
                else:
                    logger.error(f"Failed to create event: {serializer.errors}")
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            self.push(
                status='success',
                title="QR Scan Success",
                message="Service redeemed successfully.",
                pop_message=f"{number} coupon(s) redeemed successfully.",
                name=listing.display_name,
                service_name="bean_wagon",
                service_type_name=get_servicetype.serviceType_name,
                location=listing.place,
            )

            return Response({'message': 'Redeemed successfully!', 'status': 'success'}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error in RedeemAPIView: {str(e)}, Request Data: {request.data}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)