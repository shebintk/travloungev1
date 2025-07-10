from collections import defaultdict
import razorpay
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from rest_framework.response import Response
from rest_framework import status
from customer.serializers import *
from rest_framework_simplejwt.tokens import RefreshToken
import logging
from datetime import datetime, timedelta
from django.contrib.auth import authenticate
from rest_framework.permissions import IsAuthenticated,AllowAny
from django.contrib.auth import authenticate
from django.db.models import Sum, Q
import requests
from random import randint
from botocore.exceptions import ClientError
from admin_app.serializers import ServiceTypeSerializer, PackageSerializer, AssocBannerSerializer
from utils.s3connector import s3_upload
from urllib.parse import unquote
from .payment_gateway import create_order
from firebase_admin import credentials, initialize_app, db, get_app
cred = credentials.Certificate("utils/firebase-admin-sdk.json")
from django.utils import timezone
from django.utils.timezone import timedelta
from sleeping_pod.sleepingpod import check_availablepods,save_pods
import math
from listing.serializers import (ListingSerializer,Listing, ReviewImagePostSerializer,ReviewRatingPostSerializer,Review_rating,
                                 Listing_category,ListingcategoryGetSerializer,Listing_redeem,RedeemSerializer,Max,Listing_images)
from geopy.distance import geodesic
from rest_framework.pagination import PageNumberPagination
from elasticsearch import Elasticsearch
from django.db.models import Avg
import time
from django.contrib.auth import get_user_model
from sleeping_pod.models import Booking
import redis 
from django.conf import settings
from utils.sms.sms_connector import MSG91SMSConnector
from razorpay.errors import SignatureVerificationError
from utils.light_connector import EventsService
from django.shortcuts import get_object_or_404
import json
from decouple import config

# Setup Redis connection
redis_client = redis.StrictRedis.from_url(settings.CELERY_BROKER_URL)

try:
    # Check if Firebase app is already initialized
    firebase_app = get_app()
except ValueError: #if app not initialized
    firebase_app = initialize_app(cred, {
        'databaseURL': 'https://travlounge-34909-default-rtdb.firebaseio.com'
    })

logger = logging.getLogger(__name__)
# Create your views here.   
class UserProfileUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, format=None):
        try:
            user = request.user
            user_profile, _ = UserProfile.objects.get_or_create(user=user)

            name = request.data.get('name')
            email = request.data.get('email')
            gender = request.data.get('gender')
            dob = request.data.get('dob')

            # Step-by-step conditional validation
            if not name:
                logger.error(f"Name is needed")
                return Response({"error": "Please enter name"}, status=status.HTTP_400_BAD_REQUEST)
            if not email:
                logger.error(f"Email is needed")
                return Response({"error": "Please select email"}, status=status.HTTP_400_BAD_REQUEST)
            if not gender:
                logger.error(f"Gender is needed")
                return Response({"error": "Please select gender"}, status=status.HTTP_400_BAD_REQUEST)

            # Update user model
            user.name = name
            user.email = email
            user.save()

            # Prepare profile data
            profile_data = {
                'address': request.data.get('address', ''),
                'city': request.data.get('city', ''),
                'state': request.data.get('state', ''),
                'pincode': request.data.get('pincode', ''),
                'country': request.data.get('country', ''),
                'gender': gender,
                'dob': dob,
                'mobile_number': request.data.get('mobile_number', '')
            }

            serializer = UserProfileSerializer(user_profile, data=profile_data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error occurred in UserProfileUpdateAPIView POST: {e}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    
    def get(self,request,format=None):
        try:
            u = request.user
            try:
                user_profile = UserProfile.objects.get(user=u)
                serializer = UserProfileallSerializer(user_profile)
            except UserProfile.DoesNotExist:
                return Response({"user_profile": []},status=status.HTTP_200_OK)
            
            user_name = u.name if u.name else None
            email_id = u.email if u.email else None
            data = {
                # "id": user_profile.id,
                # "created_on": user_profile.created_on,
                # "updated_on": user_profile.updated_on,
                # "is_deleted": user_profile.is_deleted,
                # # "image": user_profile.image,
                # "address": user_profile.address,
                # "city": user_profile.city,
                # "state": user_profile.state,
                # "pincode": user_profile.pincode,
                # "country": user_profile.country,
                # # "gender": user_profile.gender,
                # "dob": user_profile.dob,
                "name": user_name,
                "email": email_id,
                "gender":request.user.gender
            }
            return Response({"user_profile": serializer.data,"user":data})
        except Exception as e:
            logger.error(f"Error occurred in UserProfileUpdateAPIView GET: {e}")
                 
class SubscriptionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            package_id = request.data.get('package')
            today = timezone.now()
    
            # Check if the user already has an active subscription
            active_subscription = Subscription.objects.filter(user=request.user, expiry_date__gte=today, is_deleted=False, status='Active').first()

            if active_subscription:
                print("active_subscription",active_subscription.package.package_name)
                if not active_subscription.package.first_user_only:
                    package_services = active_subscription.package.package_services.all()
                    total_allotted = sum(service.number or 0 for service in package_services)
                    # total_allotted = sum(service.number for service in package_services)

                    usage_data = Event.objects.filter(user=request.user, created_on__gte=active_subscription.created_on).aggregate(total_used=Sum('number'))
                    total_used = usage_data['total_used'] or 0
                    # print(total_allotted,total_used)

                    if total_used < total_allotted:
                        logger.info(f"User {request.user} already has an active subscription with remaining services.")
                        return Response(
                            {'detail': 'You already have an active subscription.'},
                            status=status.HTTP_400_BAD_REQUEST
                        )


            # Proceed with subscription creation
            package = Package.objects.filter(id=package_id, is_active=True, type=1).first()
            if not package:
                return Response({'message': 'Package not found!'}, status=status.HTTP_400_BAD_REQUEST)

            # Create payment order
            order_id = create_order(int(package.amount * 100), request.user.id, package_id)
            if not order_id:
                if package.first_user_only:
                    order_id = "TRV_WELCOME"
                else:
                    return Response({'message': 'Payment cannot be completed, please try again!'},
                                status=status.HTTP_400_BAD_REQUEST)
                
            # Check if the user has a profile
            user_profile = UserProfile.objects.filter(user=request.user).exists()

            # Calculate subscription start and expiry dates
            subscribed_date = today
            expiry_date = subscribed_date + timedelta(days=package.days) if package.days else subscribed_date

            subscription_status = 'Pending' if package.amount != 0 else 'Active'
            
            subscribe = Subscription.objects.create(
                user=request.user,
                package=package,
                subscribed_date=subscribed_date,
                expiry_date=expiry_date,
                status=subscription_status,
            )

            return Response({'order_id': order_id, 'is_profile_completed': user_profile, 'subscription_id': subscribe.id}, 
                            status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error in SubscriptionAPIView POST: {e}")
            return Response({"error": "An unexpected error occurred"},status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    def put(self, request):
        try:
            razorpay_order_id = request.data.get("razorpay_order_id")
            razorpay_payment_id = request.data.get("razorpay_payment_id")
            razorpay_signature = request.data.get("razorpay_signature")

            subscription_id = request.data.get("subscription_id")

            if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature]):
                return Response({'error': 'Missing payment verification data.'}, status=status.HTTP_400_BAD_REQUEST)

            client = razorpay.Client(auth=(settings.RAZORPAY_API_KEY, settings.RAZORPAY_API_SECRET))

            # 1. Verify signature
            try:
                client.utility.verify_payment_signature({
                    'razorpay_order_id': razorpay_order_id,
                    'razorpay_payment_id': razorpay_payment_id,
                    'razorpay_signature': razorpay_signature
                })
            except SignatureVerificationError:
                return Response({'error': 'Payment signature verification failed.'}, status=status.HTTP_400_BAD_REQUEST)

            # 2. Get Razor_pay_payment_create entry
            payment = Razor_pay_payment_create.objects.filter(
                user=request.user, razorpay_id=razorpay_order_id
            ).first()

            if not payment:
                return Response({'error': 'Payment order not found.'}, status=status.HTTP_400_BAD_REQUEST)

            # 3. Update Razor_pay_payment_create status to captured
            payment.razorpay_status = 'captured'
            payment.save()

            # 4. Save to Razor_pay_payment_history
            Razor_pay_payment_history.objects.create(
                user=request.user,
                razorpay_id=razorpay_order_id,
                payment_id=razorpay_payment_id,
                razorpay_status='captured',
                amount=payment.amount,
                payment_method='razorpay'
            )

            # 5. Activate the latest pending subscription for this user/package
            # subscription = Subscription.objects.filter(
            #     user=request.user, package=payment.package, status='Pending'
            # ).order_by('-created_at').first()

            subscription = Subscription.objects.filter(
                user=request.user, id=subscription_id, status='Pending'
            ).first()

            if subscription:
                subscription.status = 'Active'
                subscription.save()

            return Response({'message': 'Subscription activated successfully.'}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error verifying payment in SubscriptionAPIView PUT: {e}")
            return Response({'error': 'An unexpected error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class WalletAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            wallet = Wallet.objects.filter(user=request.user.id, is_deleted=False).first()
            if not wallet:
                return Response({"balance": 0}, status=status.HTTP_200_OK)

            serializer = WalletSerializer(wallet)
            return Response({
                'created_on': serializer.data['created_on'],
                'balance': serializer.data['balance']
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error in WalletAPIView GET: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        try:
            amount = request.data.get('amount')
            if not amount:
                return Response({'message': 'Amount is required'}, status=status.HTTP_400_BAD_REQUEST)

            order_id = create_order(amount, request.user.id, '')
            if order_id:
                return Response({'order_id': order_id}, status=status.HTTP_201_CREATED)
            else:
                return Response({'message': 'Payment could not be completed, please try again!'},
                                status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error in WalletAPIView POST: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request):
        try:
            user = request.user
            amount = int(request.data.get('amount', 0))
            if amount <= 0:
                return Response({'message': 'Invalid amount'}, status=status.HTTP_400_BAD_REQUEST)

            wallet = Wallet.objects.filter(user=user, is_deleted=False).first()
            if not wallet:
                # Create a new wallet for the user
                wallet = Wallet.objects.create(user=user, amount=amount, balance=amount, requested_by=request.user.id, order_id=request.data.get('order_id'))
                return Response({'message': 'Wallet created successfully!', 'balance': wallet.balance}, status=status.HTTP_201_CREATED)
            
            wallet_data = {
                'user': user.id,
                'amount': amount,
                'balance': wallet.balance + amount,
                'requested_by': user.id,
                'order_id': request.data.get('order_id')
            }
            serializer = WalletSerializer(data=wallet_data)
            if serializer.is_valid():
                serializer.save()
                Wallet.objects.filter(pk=wallet.pk).update(is_deleted=True)
            return Response({'message': 'Wallet updated successfully!', 'balance': wallet.balance}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error occurred in WalletAPIView PUT: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def random_with_N_digits(n):
    range_start = 10 ** (n - 1)
    range_end = (10 ** n) - 1
    return randint(range_start, range_end)        
class generateOtp(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        mobile_number = request.data.get("mobile_number", "")

        if not mobile_number or not mobile_number.isnumeric():
            return Response({"message": "Invalid mobile number"}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(mobile_number=mobile_number).first()
        if user and not user.is_active:
            return Response({"message": "User is not valid."}, status=status.HTTP_400_BAD_REQUEST)

        otp = random_with_N_digits(4)

        data = request.data.copy()
        data["otp"] = otp

        serializer = OtpVerificationSerializer(data=data)
        if not serializer.is_valid():
            return Response({"message": "Incorrect Inputs", "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()

        url = "https://control.msg91.com/api/v5/flow/"
        payload = {
            "template_id": "64c351a5d6fc05451332f804",
            "short_url": "1",
            "recipients": [
                {
                    "mobiles": "91" + mobile_number,
                    "OTP": otp,
                }
            ]
        }
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "authkey": "401606Ajx5LMUJ64b4e5d6P1"   
        }
        response = requests.post(url, json=payload, headers=headers)
        # print("otp\n",serializer.data)

        # print(response.text)

        return Response(serializer.data, status=status.HTTP_200_OK) 

# class SignIn(serializers.Serializer):
#     mobile_number = serializers.CharField()
#     otp = serializers.CharField()       
# class signin(APIView):
#     permission_classes = [AllowAny]
#     def post(self, request):
#         try:
#             serializer = SignIn(data=request.data)
#             if not serializer.is_valid():
#                 return Response({"message": "Incorrect Inputs", "data": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
            
#             device_token = request.data.get('device_token') 
#             mobile_number = serializer.validated_data.get('mobile_number')
#             otp_input = serializer.validated_data.get('otp')
            
#             if not mobile_number:
#                 return Response({"message": "Invalid mobile number"}, status=status.HTTP_400_BAD_REQUEST)
            
#             otp_verified = False
#             otp_obj = None

#             if otp_input == "4422":
#                 otp_verified = True
#             else:
#                 otp_obj = Otp.objects.filter(
#                     otp=otp_input, mobile_number=mobile_number, is_verified=False
#                 ).last()
#                 otp_verified = bool(otp_obj)

#             if not otp_verified:
#                 return Response(
#                     {'message': "Incorrect OTP", 'status_code': 400},
#                     status=status.HTTP_400_BAD_REQUEST
#                 )

#             if otp_input != "4422" and otp_obj:
#                 otp_obj.is_verified = True
#                 otp_obj.save()

#             user = authenticate(username=mobile_number, password=mobile_number)
#             if user:
#                 if device_token:
#                     user.device_token = device_token
#                     user.save()

#                 chk_profile = UserProfile.objects.filter(user=user.id, is_deleted=False).first()
#                 profile = bool(chk_profile)
#                 refresh = RefreshToken.for_user(user)

#                 current_date = timezone.now().date()
#                 active_subscription = Subscription.objects.filter(
#                     user=user, status='Active', expiry_date__gte=current_date, is_deleted=False
#                 ).exists()

#                 response = {
#                     'id': user.id,
#                     'access_token': str(refresh.access_token),
#                     'refresh_token': str(refresh),
#                     'status_code': 200,
#                     'user': profile,
#                     'filter_distance': [2, 5, 10],
#                     'active_subscription': active_subscription
#                 }
#                 return Response(response, status=status.HTTP_200_OK)
#             else:
#                 # Check if user exists but wrong password
#                 user_check = User.objects.filter(mobile_number=mobile_number)
#                 # print("user_exists",user_check)
#                 if user_check.exists() and user_check.role != 3:
#                     return Response(
#                         {'message': "This number is not valid. Please use a second number.", 'status_code': 400},
#                         status=status.HTTP_400_BAD_REQUEST
#                     )

#                 # No user exists, so create new
#                 try:
#                     last_record = User.objects.latest('id')
#                     lastid = last_record.id + 1
#                 except User.DoesNotExist:
#                     lastid = 1
#                 uid = "TRV-CUSTOMER-" + str(lastid)

#                 create = User.objects.create_user(
#                     username=mobile_number,
#                     mobile_number=mobile_number,
#                     password=mobile_number,
#                     role=3,
#                     uid=uid
#                 )
#                 if create:
#                     user = authenticate(username=mobile_number, password=mobile_number)
#                     if user:
#                         chk_profile = UserProfile.objects.filter(user=user.id, is_deleted=False).first()
#                         profile = bool(chk_profile)
#                         refresh = RefreshToken.for_user(user)
#                         response = {
#                             'id': user.id,
#                             'access_token': str(refresh.access_token),
#                             'refresh_token': str(refresh),
#                             'status_code': 200,
#                             'user': profile,
#                             'filter_distance': [2, 5, 10],
#                             'active_subscription': False
#                         }
#                         return Response(response, status=status.HTTP_200_OK)

#             return Response({"message": "Authentication failed", "status_code": 400}, status=status.HTTP_400_BAD_REQUEST)
        
#         except Exception as e:
#             logger.error(f"Error occurred in signin POST: {e}")
#             return Response({"error": "An error occurred", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SignIn(serializers.Serializer):
    mobile_number = serializers.CharField()

class signin(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            serializer = SignIn(data=request.data)
            if not serializer.is_valid():
                return Response({"message": "Incorrect Inputs", "data": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

            mobile_number = serializer.validated_data.get('mobile_number')
            # Check if user exists and is not active
            user = User.objects.filter(mobile_number=mobile_number).first()
            if user and not user.is_active:
                return Response({
                    "message": "User account is deactivated. Please contact support.",
                    "status_code": 400
                }, status=status.HTTP_400_BAD_REQUEST)
            # Get default numbers from settings
            default_numbers = settings.DEFAULT_NUMBERS
            
            # Case 2: If it's a default number, return success without sending OTP
            if mobile_number in default_numbers:
                return Response({
                    "message": "Default user detected. No OTP required.",
                    "status_code": 200
                }, status=status.HTTP_200_OK)

            # Case 1: For non-default numbers, use msg91 to send OTP
            msg_connector = MSG91SMSConnector()
            result = msg_connector.send_otp(mobile_number)

            if result.get("type") == "success":
                return Response({
                    "message": "OTP sent successfully",
                    "status_code": 200
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    "message": "Failed to send OTP",
                    "details": result,
                    "status_code": 400
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"@signin : {datetime.now()} : {Exception} in signin POST: {str(e)}", exc_info=True)
            return Response({"error": "An error occurred", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class OtpVerify(serializers.Serializer):
    mobile_number = serializers.CharField()
    otp = serializers.CharField()

class OtpVerifyView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            serializer = OtpVerify(data=request.data)
            if not serializer.is_valid():
                logger.error(f"Invalid serializer data: {serializer.errors}")
                return Response({"message": "Incorrect Inputs", "data": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

            mobile_number = serializer.validated_data.get('mobile_number')
            otp_input = serializer.validated_data.get('otp')
            device_token = request.data.get('device_token')

            # Get default numbers and OTP from settings
            default_numbers = settings.DEFAULT_NUMBERS
            default_otp = settings.DEFAULT_OTP

            # Case 2: Check if it's a default number and OTP matches
            if mobile_number in default_numbers:
                if otp_input == default_otp:
                    verify_response = {"type": "success"}
                else:
                    return Response({
                        "message": "Invalid OTP for default number",
                        "status_code": 400
                    }, status=status.HTTP_400_BAD_REQUEST)
            else:
                # Case 1: For non-default numbers, verify using msg91
                msg_connector = MSG91SMSConnector()
                verify_response = msg_connector.verify_otp(mobile_number, otp_input)

            if verify_response.get("type") == "success":
                user = User.objects.filter(mobile_number=mobile_number).first()
                if user:
                    if not user.is_active:
                        user.is_active = True
                        user.save()
                    user = authenticate(username=mobile_number, password=mobile_number)
                    if user:
                        if device_token and device_token != user.device_token and device_token != 'undefined':
                            user.device_token = device_token
                            user.save()

                        chk_profile = UserProfile.objects.filter(user=user.id, is_deleted=False).first()
                        profile = bool(chk_profile)
                        refresh = RefreshToken.for_user(user)

                        current_date = timezone.now().date()
                        active_subscription = Subscription.objects.filter(
                            user=user, status='Active', expiry_date__gte=current_date, is_deleted=False
                        ).exists()

                        return Response({
                            'id': user.id,
                            'access_token': str(refresh.access_token),
                            'refresh_token': str(refresh),
                            'status_code': 200,
                            'user': profile,
                            'filter_distance': [2, 5, 10],
                            'active_subscription': active_subscription
                        }, status=status.HTTP_200_OK)
                    
                    # Check if user exists but might not be authenticating
                    user_check = User.objects.filter(mobile_number=mobile_number).first()
                    if user_check:
                        if user_check.role != 3:
                            logger.error(f"User role mismatch: {user_check.role}")
                            return Response(
                                {'message': "This number is not valid. Please use a second number.", 'status_code': 400},
                                status=status.HTTP_400_BAD_REQUEST
                            )
                        else:
                            user = user_check
                            if device_token:
                                user.device_token = device_token
                                user.save()

                            chk_profile = UserProfile.objects.filter(user=user.id, is_deleted=False).first()
                            profile = bool(chk_profile)
                            refresh = RefreshToken.for_user(user)

                            current_date = timezone.now().date()
                            active_subscription = Subscription.objects.filter(
                                user=user, status='Active', expiry_date__gte=current_date, is_deleted=False
                            ).exists()

                            return Response({
                                'id': user.id,
                                'access_token': str(refresh.access_token),
                                'refresh_token': str(refresh),
                                'status_code': 200,
                                'user': profile,
                                'filter_distance': [2, 5, 10],
                                'active_subscription': active_subscription
                            }, status=status.HTTP_200_OK)

                # No user exists — create new
                try:
                    last_record = User.objects.latest('id')
                    lastid = last_record.id + 1
                except User.DoesNotExist:
                    lastid = 1

                uid = f"TRV-CUSTOMER-{lastid}"
                user = User.objects.create_user(
                    username=mobile_number,
                    mobile_number=mobile_number,
                    password=mobile_number,
                    role=3,
                    uid=uid
                )

                if device_token:
                    user.device_token = device_token
                    user.save()

                chk_profile = UserProfile.objects.filter(user=user.id, is_deleted=False).first()
                profile = bool(chk_profile)
                refresh = RefreshToken.for_user(user)

                return Response({
                    'id': user.id,
                    'access_token': str(refresh.access_token),
                    'refresh_token': str(refresh),
                    'status_code': 200,
                    'user': profile,
                    'filter_distance': [2, 5, 10],
                    'active_subscription': False
                }, status=status.HTTP_200_OK)
            logger.error(f"OTP verification failed: {verify_response}")
            return Response({"message": "OTP verification failed", "details": verify_response}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Error occurred in OtpVerifyView POST: {e}")
            return Response({"error": "An error occurred", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# class EventsAPIView(APIView):
#     permission_classes = [IsAuthenticated]
    
#     def get(self, request):
#         try:
#             events = Event.objects.filter(user=request.user.id, is_deleted=False)
#             serializer = EventSerializer(events, many=True)
#             return Response(serializer.data, status=status.HTTP_200_OK)
#         except Exception as e:
#             logger.error(f"Error occurred in EventsAPIView GET: {e}")
#             return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
#     def post(self, request):
#         try:
            
#             chk_subscription = Subscription.objects.filter(user=request.user.id,status='Active',is_deleted=False).last()
#             chk_wallet = Wallet.objects.filter(user=request.user.id,status='Active',is_deleted=False).last()
#             total_amount = 0
#             for value in request.data:
#                 service = value['service']
#                 service_type = value['serviceType']
#                 number = value['number']
#                 if chk_subscription:
#                     package_service = PackageServices.objects.filter(package=chk_subscription.package,service=service,serviceType=service_type,is_deleted=False).first()
#                     chk_events = Event.objects.filter(user=request.user.id,service=service,serviceType=service_type,created_on__gte=chk_subscription.subscribed_date,created_on__lte=chk_subscription.expiry_date).aggregate(total_count=Sum('number'))
#                     if chk_events['total_count']:
#                         if chk_events['total_count'] > package_service.number:
#                             return Response({"message": "usage of service is exceeded."}, status=status.HTTP_400_BAD_REQUEST)
#                         else:
#                             chk_balance = package_service.number - chk_events['total_count']
#                             if number > chk_balance:
#                                 return Response({"message": "You only have a balance of "+str(chk_balance)+" services remaining ."}, status=status.HTTP_400_BAD_REQUEST)
#                 if chk_wallet:
#                     package_amount = PackageServices.objects.filter(service=service,serviceType=service_type,number=1,is_deleted=False,package__type=2).values_list('package__amount', flat=True)
#                     amount_value = list(package_amount)[0] if package_amount else None
#                     service_amount = amount_value
#                     total_number = number
#                     total_amount += service_amount*total_number
#                     if total_amount > chk_wallet.balance:
#                         return Response({"message": "You only have a balance of "+chk_wallet.balance+" services remaining ."}, status=status.HTTP_400_BAD_REQUEST)
#                     balance = chk_wallet.balance-total_amount
#                     Wallet.objects.filter(user=request.user.id,status='Active',is_deleted=False).update(balance=balance)
#                 data = {
#                  'user': request.user.id,
#                  'service': service,
#                  'serviceType': service_type,
#                  'number': number,
#                 }
                
#                 serializer = EventSerializer(data=data)
#                 if serializer.is_valid():
#                     serializer.save()
#                     room_update_data = value['room_numbers']
#                     if room_update_data:
#                         room_update_view = RoomUpdateView()
#                         room_update_response = room_update_view.post(room_update_data)
            
#                 else:
#                     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
#             return Response({'message': 'Event created successfully!'}, status=status.HTTP_201_CREATED)
#         except Exception as e:
#             logger.error(f"Error occurred in EventsAPIView POST: {e}")
#             return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ServiceTypeView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        try:
            servicetype = ServiceType.objects.filter(service__in=[1, 2], is_deleted=False, is_active=True)
            chk_subscription = Subscription.objects.filter(
                user=request.user.id, status='Active', is_deleted=False).last()
            
            servicetype_data = []
            u=request.user.id
            for i in servicetype:
                package_amount = PackageServices.objects.filter(
                    service=i.service_id, serviceType__contains=i.id, number=1, is_deleted=False, package__type=2).values_list('package__amount', flat=True)
                amount_value = list(package_amount)[0] if package_amount else 0
                service_amount = amount_value
                
                data = {
                    "id": i.id,
                    "serviceType_name": i.serviceType_name,
                    "service":i.service.service_name,
                    "type": i.types,
                    "amount":service_amount,
                    "description":i.description
                }

                data['remaining'] = 0

                if chk_subscription:
                    if i.service_id != 1:
                        package_service = PackageServices.objects.filter(
                            package=chk_subscription.package, service=i.service, serviceType__contains=i.id, is_deleted=False).first()
                        package_number = package_service.number if package_service else 0
                    else:
                        package_service = PackageServices.objects.filter(
                            package=chk_subscription.package, service=i.service, serviceType__contains=i.id, is_deleted=False).aggregate(total_number=Sum('number'))
                        package_number = package_service['total_number'] if package_service['total_number'] else 0

                    if package_service:
                        chk_events = Event.objects.filter(user=request.user.id, service=i.service, serviceType__in=[i.id], created_on__gte=chk_subscription.subscribed_date,
                                                          created_on__lte=chk_subscription.expiry_date).aggregate(total_count=Sum('number'))
                        if chk_events['total_count']:
                            chk_balance = package_number - chk_events['total_count']
                        else:
                            chk_balance = package_number

                        data['remaining'] = max(0, chk_balance)
                    else:
                        data['remaining'] = 0  # Default to 0 if package_service is None

                servicetype_data.append(data)
            if chk_subscription:
                expiryDate = chk_subscription.expiry_date
            else:
                expiryDate = None
            response_data = {
                "userid": u,
                "expiryDate": expiryDate,
                "servicetype_data": servicetype_data
            }
            

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error occurred in ServiceTypeView GET: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        
class QrGenerateEligibleView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            current_date = timezone.now().date()
            chk_subscription = Subscription.objects.filter(user=request.user.id,status='Active',is_deleted=False,expiry_date__gte=current_date).last()
            chk_wallet = Wallet.objects.filter(user=request.user.id,status='Active',is_deleted=False).first()
            get_service = ServiceType.objects.filter(pk=request.data['service_type'],is_deleted=False).first()
            service = get_service.service_id
            service_type = get_service.id
            x=0
            if chk_subscription:
                package_service = PackageServices.objects.filter(package=chk_subscription.package.id,service=service,serviceType__contains=service_type,is_deleted=False).first()
                chk_events = Event.objects.filter(user=request.user.id,service=service,serviceType__in=[service_type],created_on__gte=chk_subscription.subscribed_date,created_on__lte=chk_subscription.expiry_date).aggregate(total_count=Sum('number'))
                if chk_events['total_count']:
                    if chk_events['total_count'] > package_service.number:
                            x = 2
                        
                        # return Response({"message": "usage of service is exceeded."}, status=status.HTTP_400_BAD_REQUEST)
                    else:
                        chk_balance = package_service.number - chk_events['total_count']
                        if 1 > chk_balance:
                            x = 1
                            
                            # return Response({"message": "You only have a balance of "+str(chk_balance)+" services remaining ."}, status=status.HTTP_400_BAD_REQUEST)
                    # return Response({'message': 'Your eligible!'}, status=status.HTTP_200_OK)
                return Response({'message': 'Your eligible!'}, status=status.HTTP_200_OK)
                
            if chk_wallet or x in (1,2):
                package_amount = PackageServices.objects.filter(service=service,serviceType__contains=service_type,number=1,is_deleted=False,package__type=2).values_list('package__amount', flat=True)
                amount_value = list(package_amount)[0] if package_amount else None
                if amount_value is not None:
                    service_amount = amount_value
                    total_number = 1
                    total_amount = service_amount*total_number
                    if total_amount > chk_wallet.balance:
                        return Response({"message": "You only have a balance of "+str(chk_wallet.balance)+" services remaining ."}, status=status.HTTP_400_BAD_REQUEST)
                    else:
                        return Response({'message': 'Your eligible!'}, status=status.HTTP_200_OK)
                else:
                    return Response({'message': 'service type amount not found!'}, status=status.HTTP_400_BAD_REQUEST)
                        
            else:
                return Response({"message": "you dont have any active plan."}, status=status.HTTP_400_BAD_REQUEST)
                
                        
            
        except Exception as e:
            logger.error(f"Error occurred in QrGenerateEligibleView POST: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class DashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            banners = Banner.objects.filter(is_deleted=False)
            association_banner = AssociationBanner.objects.filter(is_deleted=False)
            services = Service.objects.filter(is_deleted=False)
            userid = request.user.id
            name = request.user.name
            mobile = request.user.mobile_number

            chk_profile = UserProfile.objects.filter(user=userid,is_deleted=False).first()
            if chk_profile:
                profile = True
            else:
                profile = False    

            current_date = timezone.now().date()
            event_number = 0
            subscription = Subscription.objects.filter(user=userid,is_deleted=False,expiry_date__gte=current_date,package__type=1,status='Active').values('package','package__package_name','expiry_date','subscribed_date').first()
            welcome_bonus = Subscription.objects.filter(
                user=userid,
                package__first_user_only=True,
                is_deleted=False
            ).exists()
            is_welcome_claimed = welcome_bonus
            if subscription:
                total_count = PackageServices.objects.filter(package=subscription['package'],is_deleted=False).values('service','serviceType').aggregate(total_count=Sum('number'))
                package_services = PackageServices.objects.filter(package=subscription['package'],is_deleted=False)
                used_count = SubscriptionUsage.objects.filter(
                    subscription__package=subscription["package"],
                    subscription__user=userid
                ).aggregate(used_count=Sum("used_count"))["used_count"] or 0
                is_welcome_claimed = True
                for pserv in package_services:
                    chk_events = Event.objects.filter(
                        user=request.user.id,
                        service=pserv.service_id,
                        serviceType__in=pserv.serviceType,
                        created_on__gte=subscription['subscribed_date'],
                        created_on__lte=subscription['expiry_date']
                    ).aggregate(used_count=Sum('number'))
                    if chk_events['used_count']:
                        used_count = used_count + chk_events['used_count']
                
                subscription_data = {
                    "package_name" : subscription['package__package_name'],
                    "expiry_date" : subscription['expiry_date'],
                    "total_count":total_count['total_count'],
                    "used_count":used_count,
                    "remaining_count":total_count['total_count']-used_count
                } 
            else:
                subscription_data = []
            user = {
                "user_id": userid,
                "user_name": name,
                "mobile_number": mobile,
                "is_registered": profile,
                "is_welcome_claimed": is_welcome_claimed


            }
                    
            banner_serializer = BannerSerializer(banners, many=True)
            assoc_banner = AssocBannerSerializer(association_banner, many=True).data
            service_serializer = DashboardServiceSerializer(services, many=True)

            assoc_banner = [
                {**banner, 'title': banner['title']['display_name']}
                for banner in assoc_banner
            ]

            return Response({"banners": banner_serializer.data, "user":user, "subscription_data": subscription_data,"services":service_serializer.data,"assocition_banner":assoc_banner}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error occurred in DashboardAPIView GET: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CustomerProfileApiView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            current_date = timezone.now().date()

            # Get user data
            user_data = {
                "phone": user.mobile_number,
                "name": user.name,
                "image": user.get_image_url() if hasattr(user, 'get_image_url') else None
            }

            # Get all active subscriptions
            active_subscriptions = []
            subscriptions = Subscription.objects.filter(
                user=user,
                status='Active',
                expiry_date__gte=current_date,
                is_deleted=False
            ).select_related('package')

            for subscription in subscriptions:
                # Get total services from package
                package_services = PackageServices.objects.filter(
                    package=subscription.package,
                    mode='number',
                    is_deleted=False
                )
                total_count = sum(service.number or 0 for service in package_services)

                # Get used count from SubscriptionUsage
                used_count = SubscriptionUsage.objects.filter(
                    subscription=subscription
                ).aggregate(total_used=Sum('used_count'))['total_used'] or 0

                active_subscriptions.append({
                    "package_name": subscription.package.package_name,
                    "expiry_date": subscription.expiry_date,
                    "total_count": total_count,
                    "used_count": used_count,
                    "remaining_count": total_count - used_count
                })

            # Get current offers
            current_offers = Package.objects.filter(
                is_active=True,
                type=1,
                is_deleted=False
            ).exclude(
                id__in=Subscription.objects.filter(
                    user=user,
                    status='Active',
                    is_deleted=False
                ).values_list('package_id', flat=True)
            )

            offers_data = []
            for offer in current_offers:
                offer_data = {
                    "id": offer.id,
                    "package_name": offer.package_name,
                    "amount": str(offer.amount),
                    "days": offer.days,
                    "months": offer.months,
                    "valid_for": offer.valid_for,
                    "type": offer.type,
                    "description": offer.description,
                    "display_description": offer.display_description,
                    "start_date": offer.start_date,
                    "end_date": offer.end_date,
                    "start_time": offer.start_time,
                    "end_time": offer.end_time,
                    "is_active": offer.is_active,
                    "package_services": [],
                    "first_user_only": offer.first_user_only
                }

                # Get package services
                package_services = PackageServices.objects.filter(
                    package=offer,
                    is_deleted=False
                ).select_related('service')

                for service in package_services:
                    service_data = {
                        "service": service.service.id,
                        "service_name": service.service.service_name,
                        "serviceType": service.serviceType,
                        "servicetype_names": ServiceType.objects.filter(
                            id__in=service.serviceType
                        ).values_list('serviceType_name', flat=True),
                        "mode": service.mode,
                        "number": service.number,
                        "discount_value": str(service.discount_value) if service.discount_value else None
                    }
                    offer_data["package_services"].append(service_data)

                offers_data.append(offer_data)

            response_data = {
                "user": user_data,
                "packages": active_subscriptions[0] if active_subscriptions else None,
                "active_subscriptions": active_subscriptions,
                "curr_offers": offers_data,
                "is_subscribed": bool(active_subscriptions)
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error in CustomerProfileApiView: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
class UsageHistoryApiView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            userid = request.user.id
            current_date = timezone.now().date()

            subscription = Subscription.objects.filter(user=userid, is_deleted=False, expiry_date__gte=current_date, package__type=1
                                                       ).values("package", "package__package_name", "expiry_date", "subscribed_date").first()

            subscription_data = {}

            if subscription:
                total_count = PackageServices.objects.filter(
                    package=subscription["package"], is_deleted=False
                ).aggregate(total_count=Sum("number"))

                used_count = Event.objects.filter(
                    user=userid,
                    created_on__gte=subscription["subscribed_date"],
                    created_on__lte=subscription["expiry_date"],
                ).aggregate(used_count=Sum("number"))["used_count"] or 0

                subscription_data = {
                    "package_name": subscription["package__package_name"],
                    "expiry_date": subscription["expiry_date"],
                    "total_count": total_count["total_count"],
                    "used_count": used_count,
                    "remaining_count": (total_count["total_count"] or 0) - used_count,
                }

            events = Event.objects.filter(user=userid)
            usagehistory = UsagehistorySerializer(events, many=True).data

            # Ensure created_on is a datetime object for sorting
            for event in usagehistory:
                event["created_on"] = event.get("created_on", timezone.now())

            merged_data = usagehistory

            # Fetch booking data
            bookings = Booking.objects.filter(user=userid).prefetch_related("listing", "pod_info")
            listing_ids = bookings.values_list("listing_id", flat=True)
            images = Listing_images.objects.filter(listing_id__in=listing_ids).values_list("listing","image")
            image_dict = {}
            for listing_id, image in images:
                if listing_id in image_dict:
                    image_dict[listing_id].append(image)
                else:
                    image_dict[listing_id] = [image]

            for booking in bookings:
                pod_info = booking.pod_info.all()
                no_of_pods = sum(info.no_of_pods for info in pod_info)

                pod_reservations = booking.pod_reservations.all()
                pod_names = [pod_reservation.sleeping_pod.pod_name for pod_reservation in pod_reservations]

                merged_data.append({
                    "id": booking.id,
                    "created_on": getattr(booking, "created_on", timezone.now()),
                    "date": booking.date,
                    "booking_status": booking.booking_status,
                    "no_of_pods": no_of_pods,
                    "pod_names": pod_names,
                    "images": image_dict.get(booking.listing_id, []),
                })

            for item in merged_data:
                if isinstance(item["created_on"], str):
                    try:
                        item["created_on"] = datetime.fromisoformat(item["created_on"])
                    except ValueError:
                        item["created_on"] = timezone.now()

            merged_data.sort(key=lambda x: x["created_on"], reverse=True)

            return Response({
                "usages": subscription_data,
                "merged_history": merged_data,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error occurred in UsageHistoryApiView GET: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SingleServiceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            coupons = {}
            chk_balance = 0            
            servicetype_data = []

            banners = []
            # add banners code
            banners = Banner.objects.filter(service=pk,is_deleted=False)
            banner_serializer = BannerSerializer(banners, many=True)



            if pk != 1:
                current_date = timezone.now().date()
                chk_subscription = Subscription.objects.filter(user=request.user.id,status='Active',expiry_date__gte=current_date,is_deleted=False).last()
                service_types = ServiceType.objects.filter(service_id=pk,is_deleted=False,is_active=True)
                
                if chk_subscription:
                    package_service = PackageServices.objects.filter(
                        package=chk_subscription.package_id, service=pk, is_deleted=False).aggregate(total_coupons=Sum('number'))
                    if package_service:
                        chk_events = Event.objects.filter(user=request.user.id, service=pk, created_on__gte=chk_subscription.subscribed_date,
                                                            created_on__lte=chk_subscription.expiry_date).aggregate(total_count=Sum('number'))
                        
                        try:
                            total_coupons = package_service['total_coupons']
                            chk_balance = package_service['total_coupons'] - chk_events['total_count']
                        except Exception as e:
                            chk_balance = 0
                            total_coupons = 0
                            
                        coupons['total'] = total_coupons
                        coupons['remaining'] = chk_balance
                else:
                    coupons['total'] = 0
                    coupons['remaining'] = 0

                for i in service_types:
                    image = ServiceType.objects.filter(pk=i.id, is_active=True).first()
                    imgserializer = ServiceTypeImageSerializer(image)
                    
                    data = {
                        "id": i.id,
                        "image": imgserializer.data['image'].replace('%3A', ':/').lstrip('/'),
                        "service_name":i.serviceType_name,
                        "description":i.description
                    }
                    

                    servicetype_data.append(data)
            else:
                # add code for sleepingpod
                pass
                    
            return Response({"banners":banner_serializer.data,"coupons":coupons,"servicetypes":servicetype_data})
        except Exception as e:
            logger.error(f"Error occured in SingleServiceTypeView GET: {e}")
            return Response({"message":"error","error":e})
        
class AvailablePodView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        try:
            date = request.data['date']
            start_time = request.data['time']
            hour = request.data['hour']
            
            available_pods = check_availablepods(date,start_time,hour)
            return Response(available_pods)
        except Exception as e:
            logger.error(f"Error occured in AvailablePodView GET: {e}")
            return Response({"message":"error","error":e})

# class RemainingCoopens(APIView):
#     permission_classes = [IsAuthenticated]
#     def get(self, request):
#         try:
#             user = request.user.id
#             current_date = timezone.now().date()
#             chk_subscription = Subscription.objects.filter(user=user,status='Active',expiry_date__gte=current_date,is_deleted=False).last()
#             if chk_subscription:
#                 package_service = PackageServices.objects.filter(package=chk_subscription.package_id,is_deleted=False)
                
#                 service_type_totals = {}

#                 # Iterate over each package service
#                 for pkg_serv in package_service:
#                     # Aggregate the used_count for each serviceType
#                     print(pkg_serv.serviceType_id)
#                     if pkg_serv.serviceType_id in(1,2):
#                         agg_result = Event.objects.filter(
#                             user=user,
#                             service=pkg_serv.service_id,
#                             serviceType__in=[1, 2],
#                             date__gte=chk_subscription.subscribed_date,
#                             date__lte=chk_subscription.expiry_date
#                         ).values('serviceType', 'serviceType__serviceType_name').annotate(used_count=Sum('number'))
#                     else:
#                         agg_result = Event.objects.filter(
#                             user=user,
#                             service=pkg_serv.service_id,
#                             serviceType__in=pkg_serv.serviceType,
#                             date__gte=chk_subscription.subscribed_date,
#                             date__lte=chk_subscription.expiry_date
#                         ).values('serviceType', 'serviceType__serviceType_name').annotate(used_count=Sum('number'))
                        
#                     # Iterate over the aggregation result and update the dictionary
#                     for result in agg_result:
#                         service_type = result['serviceType']
#                         service_type_name = result['serviceType__serviceType_name']
#                         used_count = result['used_count'] or 0  # Default to 0 if no records are found

#                         key = (service_type, service_type_name)
#                         if key not in service_type_totals:
#                             service_type_totals[key] = used_count
#                         else:
#                             service_type_totals[key] += used_count

#                 # Now service_type_totals contains the unique (serviceType, serviceType_name) pairs with their corresponding total used_count
#                 for (service_type, service_type_name), total_used_count in service_type_totals.items():
#                     print(service_type,'service_type')
#                     total_count = PackageServices.objects.filter(package=chk_subscription.package_id,is_deleted=False,
#                         serviceType__contains=service_type).aggregate(total_count=Sum('number'))
#                     remaining_coupons = total_count['total_count'] - total_used_count
#                     if service_type in (1,2):
#                         coupon_name = 'Toloo Wash'
#                     else:
#                         coupon_name = service_type_name    
#                     print(f'ServiceType: {service_type}, ServiceType Name: {coupon_name}, remaining_coupons: {remaining_coupons}')
               
#                 # for pkg_serv in package_service:
#                 #     chk_events = Event.objects.filter(user=user, service=pkg_serv.service_id, serviceType__in=pkg_serv.serviceType, date__gte=chk_subscription.subscribed_date,date__lte=chk_subscription.expiry_date).aggregate(used_count=Sum('number'))
#                 #     try:
                        
#                 #         service_typename = Event.objects.filter(user=user, service=pkg_serv.service_id, serviceType__in=pkg_serv.serviceType, date__gte=chk_subscription.subscribed_date,date__lte=chk_subscription.expiry_date).values_list('serviceType__serviceType_name', flat=True).distinct()
#                 #         # coupen_name = service_typename['serviceType_name'],
#                 #         for name in service_typename:
#                 #             print(name)
                        
#                 #         remaining = pkg_serv.number - chk_events['used_count']
#                 #         print(remaining,'remaining')
                        
#                 #     except Exception as e:
#                 #         remaining = 0
                        
                   
#             return Response({current_date})
#         except Exception as e:
#             logger.error(f"Error occured in AvailablePodView GET: {e}")
#             return Response({"message":"error","error":e})


class RemainingCoupons(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user.id
            current_date = timezone.now().date()
            chk_subscription = Subscription.objects.filter(
                user=user,
                status='Active',
                expiry_date__gte=current_date,
                is_deleted=False
            ).last()

            if chk_subscription:
                package_service = PackageServices.objects.filter(
                    package=chk_subscription.package_id,
                    is_deleted=False
                )

                service_type_totals = {}

                # Iterate over each package service
                for pkg_serv in package_service:
                    # Retrieve the serviceType values from PackageServices JSONField
                    service_type_values = pkg_serv.serviceType

                    # Aggregate the used_count for the specified serviceType values
                    agg_result = Event.objects.filter(
                        user=user,
                        service=pkg_serv.service_id,
                        serviceType__in=service_type_values,
                        date__gte=chk_subscription.subscribed_date,
                        date__lte=chk_subscription.expiry_date
                    ).aggregate(used_count=Sum('number'))

                    used_count = agg_result['used_count'] or 0  # Default to 0 if no records are found

                    # Update the dictionary with the used_count
                    for service_type in service_type_values:
                        service_type_totals[service_type] = used_count

                # Iterate over all unique serviceType values and calculate remaining_coupons
                unique_service_types = set(service_type_totals.keys())
                results = []

                for service_type in unique_service_types:
                    total_count = PackageServices.objects.filter(
                        package=chk_subscription.package_id,
                        is_deleted=False,
                        serviceType__contains=[service_type]
                    ).aggregate(total_count=Sum('number'))

                    remaining_coupons = total_count['total_count'] - service_type_totals.get(service_type, 0)

                    if service_type in (1, 2):
                        coupon_name = 'Toloo Wash'
                    elif service_type in (3, 4):
                        coupon_name = 'Toloo Bath'
                    else:
                        coupon_name = ServiceType.objects.get(id=service_type).serviceType_name

                    results.append({
                        'serviceType': service_type,
                        'couponName': coupon_name,
                        'remainingCoupons': remaining_coupons
                    })

                return JsonResponse({'results': results})

        except Exception as e:
            print(e)
            return JsonResponse({'error': 'An error occurred'}, status=500) 
        
class ServiceTypeDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            if not pk:
                return Response({"message": "Missing 'pk' parameter"}, status=status.HTTP_400_BAD_REQUEST)

            service_type = ServiceType.objects.filter(id=pk, is_deleted=False, is_active=True).first()
            if not service_type:
                return Response({"message": "Service type not found"}, status=status.HTTP_404_NOT_FOUND)

            coupon_data = request.data.get('remainingCoupons')
            serializer = ServiceTypeImageSerializer(service_type)
            data = {
                "image": serializer.data['image'],
                "name": service_type.serviceType_name,
                "description": service_type.description,
                "remainingCoupons": coupon_data
            }
            return Response({"response_data": data}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error occurred in ServiceTypeDetailAPIView GET: {e}")
            return Response({"message": "error", "error": str(e)})


class AllAvailablePodView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            date = request.data['date']
            start_time = request.data['time']
            # hour = request.data['hour']
            available_pods_4 = check_availablepods(date, start_time, 4)
            available_pods_12 = check_availablepods(date, start_time, 12)
            print("========================================")
            print(available_pods_12)
            response_data = [
                {"hour": 4, "data": available_pods_4},
                {"hour": 12, "data": available_pods_12}
            ]
            return Response(response_data)
        except Exception as e:
            logger.error(f"Error occured in AvailablePodView GET: {e}")
            return Response({"message": "error","error":e})


class SleepingpodBookingAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
           
            user = request.user.id
            current_date = timezone.now().date()
            chk_subscription = Subscription.objects.filter(user=user,status='Active',is_deleted=False,expiry_date__gte=current_date).last()
            chk_wallet = Wallet.objects.filter(user=user,status='Active',is_deleted=False).last()
            total_amount = 0
            for value in request.data['service']:
                service = value['service']
                service_type = value['serviceType']
                number = value['number']
                source = 'm'
                checkin_time = value['checkin_time']
                date = value['date']
                
                checkin_time_obj = datetime.strptime(str(checkin_time), '%H:%M:%S').time()
                checkin_datetime = datetime.combine(datetime.strptime(date, "%Y-%m-%d"), checkin_time_obj)

                checkout_datetime = datetime.combine(datetime.today(), checkin_time_obj) + timedelta(hours=4)
                # return Response({'checkout_datetime':checkout_datetime})

                checkout_time = checkout_datetime.strftime('%H:%M:%S')
                checkout_time_obj = datetime.strptime(str(checkout_time), '%H:%M:%S').time()
                x=0
                if chk_subscription:
                    package_service = PackageServices.objects.filter(package=chk_subscription.package,service=service,serviceType__contains=[service_type],is_deleted=False).first()
                    chk_events = Event.objects.filter(user=user,service=service,serviceType=service_type,created_on__gte=chk_subscription.subscribed_date,created_on__lte=chk_subscription.expiry_date).aggregate(total_count=Sum('number'))
                    if chk_events['total_count']:
                        if chk_events['total_count'] > package_service.number:
                            x = 2
                            # return Response({"message": "usage of service is exceeded."}, status=status.HTTP_400_BAD_REQUEST)
                        else:
                            chk_balance = package_service.number - chk_events['total_count']
                            if number > chk_balance:
                                x = 1
                                # return Response({"message": "You only have a balance of "+str(chk_balance)+" services remaining ."}, status=status.HTTP_400_BAD_REQUEST)
                if chk_wallet or x in (1,2):
                    
                    package_amount = PackageServices.objects.filter(service=service,serviceType__contains=[service_type],number=1,is_deleted=False,package__type=2).values_list('package__amount', flat=True)
                    amount_value = list(package_amount)[0] if package_amount else None
                    service_amount = amount_value
                    total_number = number
                    total_amount += service_amount*total_number
                    if total_amount > chk_wallet.balance:
                        return Response({"message": "You only have a balance of "+str(chk_wallet.balance)+" remaining."}, status=status.HTTP_400_BAD_REQUEST)
                    balance = chk_wallet.balance-total_amount
                    Wallet.objects.filter(user=user,status='Active',is_deleted=False).update(balance=balance)
                    transaction_data = {
                        'user': user,
                        'amount': total_amount,
                        'balance': balance,
                        'requested_by': user,
                        'transaction_type': 0
                    }
                    transactionSerializer = WalletTransactionSerializer(
                        data=transaction_data)
                    if transactionSerializer.is_valid():
                        transactionSerializer.save()
                    else:
                        return Response(transactionSerializer.errors, status=status.HTTP_400_BAD_REQUEST)
                data = {
                            'user': user,
                            'service': service,
                            'serviceType': service_type,
                            'number':number,
                            'sleepingpod_numbers': value['sleepingpod_numbers'],
                            'hours': value['hours'],
                            'source':source,
                            'checkin_time':checkin_datetime,
                            'checkout_time':checkout_datetime,
                            'date':value['date'],
                            'sleepingpod_package_id':value['sleepingpod_package_id']

                        }
                events_save = save_pods(data,request.user.mobile_number)
                if events_save == 200:
                    return Response({'message': 'Sleeping pod submitted successfully!'}, status=status.HTTP_201_CREATED)
                else:
                    return Response({'message': 'Something went wrong!'}, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            logger.error(f"Error occurred in SleepingpodBookingAPIView POST: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
def get_bounding_box(latitude, longitude, radius):
    earth_radius = 6371  # Earth radius in kilometers

    max_lat = latitude + math.degrees(radius / earth_radius)
    min_lat = latitude - math.degrees(radius / earth_radius)
    max_lon = longitude + math.degrees(radius / earth_radius / math.cos(math.radians(latitude)))
    min_lon = longitude - math.degrees(radius / earth_radius / math.cos(math.radians(latitude)))

    return min_lat, max_lat, min_lon, max_lon

def haversine(lat1, lon1, lat2, lon2):
    # Haversine formula to calculate the distance between two points on the Earth
    R = 6371  # Earth radius in kilometers

    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = math.sin(d_lat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c
        
def get_users_within_radius(center_lat, center_lon, radius):
    min_lat, max_lat, min_lon, max_lon = get_bounding_box(center_lat, center_lon, radius)

    ref = db.reference('user_locations')
    snapshot = ref.order_by_child('latitude').start_at(min_lat).end_at(max_lat).get()

    users_within_radius = []
    for user, user_data in snapshot.items():
        user_lat = user_data['latitude']
        user_lon = user_data['longitude']
        distance = haversine(center_lat, center_lon, user_lat, user_lon)
        if distance <= radius:
            users_within_radius.append({
                'user': user,
                'latitude': user_lat,
                'longitude': user_lon
                # 'distance': distance
            })

    return users_within_radius        
class RealtimeLocationsAPIVIEW(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            latitude = float(request.GET['latitude'])
            longitude = float(request.GET['longitude'])
            radius = float(request.GET['radius'])

            if not latitude or not longitude or not radius:
                return Response({"error": "Latitude, longitude, and radius are required parameters."}, status=status.HTTP_400_BAD_REQUEST)
            result = get_users_within_radius(latitude, longitude, radius)
            
            return Response(result,status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error occurred in RealtimeLocationsAPIVIEW GET: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CustomerLocationsAPIVIEW(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            ref = db.reference('customer_location')
            data = ref.get()
            return Response(data,status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error occurred in CustomerLocationsAPIVIEW GET: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    def post(self, request):
        try:
            import json
            ref = db.reference('customer_location')
            data = {key: value for key, value in request.POST.items()}
            now = datetime.utcnow().isoformat()
            data['created_on'] = now
            data['updated_on'] = now
            data['user'] = request.user.id
            new_ref = ref.push(data)
            new_key = new_ref.key
            return Response({'status': 'success', 'key': new_key},status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Error occurred in CustomerLocationsAPIVIEW POST: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

class ActiveSubscriptionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            current_date = timezone.now().date()

            subscriptions = Subscription.objects.filter(
                user=user,
                is_deleted=False,
                status='Active',
                package__type=1
            ).select_related("package")

            active_subscriptions = []

            for subscription in subscriptions:
                subscription_data = {
                    "package_name": subscription.package.package_name,
                    "expiry_date": subscription.expiry_date,
                    "price": subscription.package.amount,
                    "is_welcome_bonus": subscription.package.first_user_only,
                    "is_expired": False,
                    "services": [],
                }

                # Get package services
                package_services = PackageServices.objects.filter(
                    package=subscription.package,
                    mode='number',
                    is_deleted=False
                )

                # Group services by type
                service_totals = defaultdict(lambda: {"total": 0, "used": 0, "remaining": 0})

                for service in package_services:
                    service_type_objects = ServiceType.objects.filter(
                        id__in=service.serviceType
                    ).values("id", "serviceType_name", "qrtype")

                    number = service.number or 0
                    qrtypes = {obj["qrtype"] for obj in service_type_objects}

                    if qrtypes.issuperset({'0', '2'}) or qrtypes == {'1'}:
                        group_name = "Washroom"
                    elif len(service_type_objects) == 1:
                        group_name = service_type_objects[0]["serviceType_name"]
                    else:
                        group_name = ", ".join(sorted(obj["serviceType_name"] for obj in service_type_objects))

                    service_totals[group_name]["total"] += number

                    # Get used counts from SubscriptionUsage
                    for service_type in service.serviceType:
                        usage = SubscriptionUsage.objects.filter(
                            subscription=subscription,
                            service=service.service,
                            service_type=service_type
                        ).first()
                        
                        if usage:
                            service_totals[group_name]["used"] += usage.used_count

                # Calculate remaining and add to services list
                for group_name, counts in service_totals.items():
                    counts["remaining"] = counts["total"] - counts["used"]
                    subscription_data["services"].append({
                        "type": group_name,
                        "total": counts["total"],
                        "used": counts["used"],
                        "remaining": counts["remaining"]
                    })

                active_subscriptions.append(subscription_data)

            active_subscriptions = sorted(active_subscriptions, key=lambda x: x["price"], reverse=True)
            return Response({"active_subscriptions": active_subscriptions}, status=200)

        except Exception as e:
            logger.error(f"Error in ActiveSubscriptionAPIView: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class PackageSubscritionAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            # check if user has prevoius subscription
            user = request.user.id
            subscriptions = Subscription.objects.filter(user=user, is_deleted=False, status='Active', package__type=1)
            if subscriptions.exists():
                # check if any of them are first_user_only
                first_user_only = subscriptions.filter(package__first_user_only=True).exists()
                if first_user_only:
                    # exclude first_user_only packages
                    packages = Package.objects.filter(is_deleted=False, type=1).exclude(first_user_only=True)
                else:
                    # include all packages
                    packages = Package.objects.filter(is_deleted=False, type=1)
            else:
                # include all packages
                packages = Package.objects.filter(is_deleted=False, type=1)
            # packages = Package.objects.filter(is_deleted=False, type=1)
            packages = packages.order_by('amount')
            serializer = PackageSubscriptionSerializer(packages, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error occurred in PackageAPIView GET: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

class HomeListingAPIView(APIView):

    elastic_index = settings.ELASTICSEARCH_INDEX

    def get(self, request, format=None):
        try:
            start_time = time.time()
            category = request.GET.get('category', None) #optional
            user_lat_str = request.GET.get('latitude', None)
            user_lon_str = request.GET.get('longitude', None)

            es = Elasticsearch(
                hosts=[settings.ELASTICSEARCH_HOST],
                http_auth=(settings.ELASTICSEARCH_USER, settings.ELASTICSEARCH_PASSWORD),
            )

            # Initial query
            # listings = Listing.objects.filter(is_deleted=False)

            if category:
                q = {
                    "query": {
                        "match": {
                        "category": category
                        }
                    }
                }
                # listings = listings.filter(category=category) #filter by category if present
            else:
                q = {
                    "query": {
                        "match_all": {}
                    }
                }
            try:
                listings = []
                listing_ids = []
                response = es.search(index=self.elastic_index, body=q, size=100)
                for hit in response.get('hits', {}).get('hits', []):
                    # print(hit,"\n")
                    temp_dict = {}
                    temp_dict['id'] = int(hit.get('_id'))
                    source = hit.get('_source', {})

                    temp_dict['display_name'] = source.get('display_name', 'Unknown')
                    temp_dict['images'] = []
                    for j in source.get('images') or []:
                        temp_image = {
                            'id': j.get('id', ''),
                            'image': j.get('image', '')
                        }
                        temp_dict['images'].append(temp_image)

                    location = source.get('location', {})
                    temp_dict['latitude'] = location.get('lat', 0.0)
                    temp_dict['longitude'] = location.get('lon', 0.0)
                    listings.append(temp_dict)
                    listing_ids.append(temp_dict['id'])

            except Exception as e:
                print(f"Error querying Elasticsearch: {e}")

            
            if user_lat_str and user_lon_str:
                try:
                    user_lat = float(user_lat_str)
                    user_lon = float(user_lon_str)
                    if not -90 <= user_lat <= 90:
                        return Response({"error": "Invalid latitude value. Must be between -90 and 90."},
                                        status=status.HTTP_400_BAD_REQUEST)
                    if not -180 <= user_lon <= 180:
                        return Response({"error": "Invalid longitude value. Must be between -180 and 180."},
                                        status=status.HTTP_400_BAD_REQUEST)
                except ValueError:
                    return Response({"error": "Invalid latitude or longitude format. Must be a float."},
                                    status=status.HTTP_400_BAD_REQUEST)

                average_ratings = Review_rating.objects.filter(listing__in=listing_ids).values('listing').annotate(average_rating=Avg('rating'))
                avg_rating_dict = {}
                for rating in average_ratings:
                    avg_rating_dict[rating["listing"]] = rating["average_rating"]


                # Calculate distance for each listing and add it to a list
                listings_with_distance = []
                for listing in listings:
                    listing_location = (listing['latitude'], listing['longitude'])
                    user_location = (user_lat, user_lon)
                    if 'average_rating' not in listing.keys():
                        if listing['id'] in avg_rating_dict.keys():
                            listing['average_rating'] = avg_rating_dict[listing['id']]
                        else:
                            listing['average_rating'] = 0.0

                    distance_km = geodesic(user_location, listing_location).km #calculate distance

                    listings_with_distance.append({
                        'listing': listing,
                        'distance': distance_km
                    })

                # Sort the listings by distance in ascending order
                listings_with_distance.sort(key=lambda x: x['distance'])

                results = []
                for item in listings_with_distance:
                    # print(item)
                    listing = item['listing']
                    distance = item['distance']
                    temp_dict = {}
                    temp_dict = item['listing'].copy()
                    temp_dict['distance'] = distance
                    results.append(temp_dict)



                    # serialized_listing = ListingSerializer(listing).data
                    # serialized_listing['distance'] = distance  # Add the distance to the serialized data
                    # results.append(serialized_listing)

                paginator = PageNumberPagination()
                paginated_results = paginator.paginate_queryset(results, request)
                elastic_end_time = time.time()
                elastic_time = time.strftime("%M:%S", time.gmtime(elastic_end_time - start_time))
                print(f"Total time: {elastic_time}")
                return paginator.get_paginated_response(paginated_results)
            else:
                # If latitude or longitude is not provided, return the listings without distance
                serializer = ListingSerializer(listings, many=True)

                paginator = PageNumberPagination()
                paginated_listings = paginator.paginate_queryset(serializer.data, request)
                return paginator.get_paginated_response(paginated_listings)

        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class RatingCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, format=None):
        try:
            # Prepare data for the review
            review_data = {
                'listing': request.data.get('listing'),
                'user': request.user.id,
                'title': request.data.get('title', ''),
                'reviewText': request.data.get('review', ''),
                'rating': request.data.get('rating'),
            }

            # Validate and save the review
            review_serializer = ReviewRatingPostSerializer(data=review_data)
            if review_serializer.is_valid():
                review = review_serializer.save()  # Save the review first
                
                # Handle images if any
                images = request.FILES.getlist('image')
                for image in images:
                    # Upload image to S3
                    s3_response = s3_upload(image, file_name_prefix=review.id, file_folder="review_image")

                    if "s3_url" in s3_response:
                        image_data = {
                            'review': review.id,
                            'image': s3_response["s3_url"],
                        }
                        image_serializer = ReviewImagePostSerializer(data=image_data)
                        if image_serializer.is_valid():
                            image_serializer.save()
                        else:
                            # Log errors if the image serializer fails
                            print(f"Image serializer errors: {image_serializer.errors}")
                    else:
                        # Log errors if S3 upload fails
                        print(f"S3 upload failed: {s3_response.get('error', 'Unknown error')}")

                return Response({'message': 'Review created successfully!', 'data': review_serializer.data}, status=status.HTTP_201_CREATED)
            else:
                return Response(review_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": f"An error occurred in RatingCreateAPIView POST: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    def patch(self, request, pk, format=None):
        try:
            try:
                review = Review_rating.objects.get(id=pk, user=request.user)
            except Review_rating.DoesNotExist:
                return Response({"error": "Review not found or you do not have permission to update this review."}, status=status.HTTP_404_NOT_FOUND)

            req_data = {
                'listing': request.data.get('listing', review.listing.id),
                'user': request.user.id,
                'title': request.data.get('title', review.title),
                'reviewText': request.data.get('review', review.reviewText),
                'rating': request.data.get('rating', review.rating),
            }

            images = request.FILES.getlist('image')
            if images:
                req_data['images'] = [{'image': image} for image in images]
            else:
                req_data['images'] = None

            serializer = ReviewRatingPostSerializer(instance=review, data=req_data, partial=True, context={"request": request})
            # Save and respond
            if serializer.is_valid():
                serializer.save()
                return Response({'message': 'Review updated successfully!', 'data': serializer.data}, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"An error occurred in RatingCreateAPIView PATCH: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SingleListingFetchAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            user_lat_str = request.GET.get('latitude', None)
            user_lon_str = request.GET.get('longitude', None)

            listing = Listing.objects.get(pk=pk)
            serializer = ListingSerializer(listing).data

            reviews = Review_rating.objects.filter(listing=listing).select_related('user')
            user_ids = [review.user.id for review in reviews]
            user_profiles = UserProfile.objects.filter(user_id__in=user_ids, is_deleted=False)
            profile_images = {profile.user_id: profile.image if profile.image else None for profile in user_profiles}

            for review in serializer["reviews"]:
                user_id = review["user_details"]["id"]
                review["user_details"]["image"] = profile_images.get(user_id)
            
            if user_lat_str and user_lon_str:
                try:
                    user_lat = float(user_lat_str)
                    user_lon = float(user_lon_str)
                    if not -90 <= user_lat <= 90:
                        return Response({"error": "Invalid latitude value. Must be between -90 and 90."}, status=status.HTTP_400_BAD_REQUEST)
                    if not -180 <= user_lon <= 180:
                        return Response({"error": "Invalid longitude value. Must be between -180 and 180."}, status=status.HTTP_400_BAD_REQUEST)
                except ValueError:
                    return Response({"error": "Invalid latitude or longitude format. Must be a float."}, status=status.HTTP_400_BAD_REQUEST)
                
                listing_location = (serializer["latitude"], serializer["longitude"])
                user_location = (user_lat, user_lon)

                distance_km = geodesic(user_location, listing_location).km #calculate distance
                nav_time = distance_km*2.4

                serializer['distance'] = round(distance_km, 2)
                serializer['time_to_loc'] = round(nav_time, 2)

            serializer['offer_data'] = {
                "title": "Supersaver 30%",
                "description": "Get 30% on all spendings above ₹2000."
            }
                
            return Response(serializer, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"An error occurred in SingleListingFetchAPIView: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ListingCategoryAPIView(APIView):

    def get(self, request, format=None):
        try:
            category = Listing_category.objects.all()
            serializer = ListingcategoryGetSerializer(category, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CouponRedemption(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        try:
            today = timezone.now()
            last_24_hours = today - timedelta(hours=24)
            
            listing_id = request.query_params.get('listing')
            if not listing_id:
                return Response({'error': 'Listing ID is required'}, status=status.HTTP_400_BAD_REQUEST)

            last_token = (Listing_redeem.objects.filter(user=request.user, listing=listing_id, status='Unverified', created_on__gte=last_24_hours).aggregate(Max('token')).get('token__max'))

            if last_token is not None:
                return Response({'message': 'Token found!', 'data': last_token}, status=status.HTTP_200_OK)

            last_token_number = Listing_redeem.objects.aggregate(Max('token')).get('token__max')
            next_token = 999 if last_token_number is None else int(last_token_number) + 1

            data = {
                'user': request.user.id,
                'listing': listing_id,
                'token': next_token,
                'status': 'Unverified'
            }
            serializer = RedeemSerializer(data=data)

            if serializer.is_valid():
                serializer.save()
                return Response({'message': 'New Token created!', 'data': int(serializer.data['token'])}, status=status.HTTP_201_CREATED)

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": f"An error occurred in CouponRedemption: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

User = get_user_model()

class UserDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, format=None):
        user = request.user
        if not user.is_active:
            logger.error(f"User account is already deactivated: {user.id}")
            return Response({"message": "User account is already deactivated."}, status=status.HTTP_400_BAD_REQUEST)
        
        user.is_active = False
        user.save(update_fields=['is_active'])

        logger.info(f"User account deactivated: {user.id} - {user.mobile_number}")
        return Response({"message": "User account successfully deactivated."}, status=status.HTTP_200_OK)


class UserBoookingAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        try:
            user = request.user
            now = timezone.localtime()  # safer than timezone.now()
            today = now.date()
            time_now = now.time()
            now = timezone.localtime()  # safer than timezone.now()
            Booking.objects.filter(
                user=user,
                payment_status='PENDING',
                booking_status='PENDING',
                tax__gt=0
            ).exclude(
                date__gt=today
            ).exclude(
                date=today,
                time__gte=time_now
            ).update(payment_status='FAILED', booking_status='CANCELLED')
            combined_data = []

            # fetch all the bookings and events for the user
            service_filter = [2, 3]
            events = Event.objects.filter(user=user, service__in=service_filter)

            bookings = Booking.objects.filter(user=user, tax__gt=0).prefetch_related(
                "listing", "pod_info", "pod_reservations__sleeping_pod"
            )

            listing_ids = [booking.listing.id for booking in bookings] # get listing ids from bookings
            listing_ids.extend(events.values_list('listing', flat=True)) # get listing ids from events

            listing_ids = list(set(listing_ids)) # remove duplicates

            # fetch the first image for each listing
            listing_images = Listing_images.objects.filter(listing__in=listing_ids).values_list("listing", "image")
            listing_image_dict = {}
            for listing_id, image in listing_images:
                if listing_id not in listing_image_dict:
                    listing_image_dict[listing_id] = image

            # ---------- Booking Data ----------
            for booking in bookings:
                pod_info = booking.pod_info.all()
                no_of_pods = sum(info.no_of_pods for info in pod_info)

                pod_reservations = booking.pod_reservations.all()
                pod_names = [res.sleeping_pod.pod_name for res in pod_reservations]

                combined_data.append({
                    "id": booking.id,
                    "date": booking.date,
                    "created_on": booking.created_on,
                    "payment_status": booking.payment_status,
                    "booking_status": booking.booking_status,
                    "quantity": no_of_pods,
                    "items": pod_names,
                    "images": [img] if (img := listing_image_dict.get(booking.listing.id)) else [],
                    "listing_name": booking.listing.display_name,
                    "service_type_name": "Sleeping Pod",
                    "service_name": "sleeping_pod",
                    "type": "booking"
                })

            # ---------- Service Usage Data ----------

            event_data = events.values(
                'id', 'serviceType', 'number', 'source', 'listing',
                'date', 'created_on', 'listing__display_name', 'service__service_name'
            )

            for event in event_data:
                if event['serviceType'] in [1, 2]:
                    service_type_name = 'Toloo Bath'
                elif event['serviceType'] in [3, 4]:
                    service_type_name = 'Toloo Wash'
                elif event['serviceType'] == 5:
                    service_type_name = 'Toloo Urinal'
                elif event['serviceType'] == 9:
                    service_type_name = 'Cappuccino'
                else:
                    service_type_name = 'Unknown Service'

                combined_data.append({
                    "id": event['id'],
                    "date": event['date'],
                    "created_on": event['created_on'],
                    "payment_status": "CONFIRMED",
                    "booking_status": "CONFIRMED",
                    "quantity": event['number'],
                    "items": [],
                    "images": [img] if (img := listing_image_dict.get(event['listing'])) else [],
                    "listing_name": event['listing__display_name'],
                    "service_type_name": service_type_name,
                    "service_name": event['service__service_name'].replace(" ", "_").lower(),
                    "type": "service"
                })

            # ---------- Sort by created_on (descending) ----------
            sorted_data = sorted(combined_data, key=lambda x: x['created_on'], reverse=True)

            # ---------- Pagination ----------
            paginator = PageNumberPagination()
            paginator.page_size = 10  # default page size, or you can set dynamically
            paginated_data = paginator.paginate_queryset(sorted_data, request)
            return paginator.get_paginated_response(paginated_data)

        except Exception as e:
            logger.error(f"Error in UserBoookingAPIView: {str(e)}")
            return Response({"error": "An error occurred", "data": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class WalletAndSubscriptionUsageAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            current_date = timezone.now().date()

            # Get wallet balance
            wallet = Wallet.objects.filter(user=user, is_deleted=False).first()
            wallet_balance = wallet.balance if wallet else 0

            # Get all active subscriptions
            subscriptions = Subscription.objects.filter(
                user=user, is_deleted=False, expiry_date__gte=current_date, status='Active'
            )

            service_totals = defaultdict(lambda: {"total": 0, "used": 0, "remaining": 0})
            subscription_periods = []
            subscription_packages = []
            package_details = []

            for subscription in subscriptions:
                # Get package basic info
                package_info = {
                    "package_name": subscription.package.package_name,
                    "expiry_date": subscription.expiry_date,
                    "service_type_counts": []
                }
                
                subscription_periods.append((subscription.subscribed_date, subscription.expiry_date))
                package_services = PackageServices.objects.filter(
                    package=subscription.package, mode='number', is_deleted=False
                )

                # Track service usage for this package
                package_service_totals = defaultdict(lambda: {"total": 0, "used": 0, "remaining": 0})

                for service in package_services:
                    service_type_objects = ServiceType.objects.filter(id__in=service.serviceType).values(
                        "id", "serviceType_name", "qrtype"
                    )

                    number = service.number or 0

                    # Find the effective group name
                    qrtypes = {obj["qrtype"] for obj in service_type_objects}
                    if qrtypes.issuperset({'0', '2'}):
                        group_name = "Washroom"  # group 0 and 2 as "Washroom"
                    elif qrtypes == {'1'}:
                        group_name = "Washroom"  # Toloo bath is also called "Toloo"
                    elif len(service_type_objects) == 1:
                        group_name = service_type_objects[0]["serviceType_name"]
                    else:
                        # Fallback: join all names
                        group_name = ", ".join(sorted([obj["serviceType_name"] for obj in service_type_objects]))

                    # Update global totals
                    service_totals[group_name]["total"] += number

                    # Update package-specific totals
                    package_service_totals[group_name]["total"] += number

                    # Get used count from SubscriptionUsage for this package
                    for service_type in service.serviceType:
                        usage = SubscriptionUsage.objects.filter(
                            subscription=subscription,
                            service=service.service,
                            service_type=service_type
                        ).first()
                        
                        if usage:
                            package_service_totals[group_name]["used"] += usage.used_count
                            service_totals[group_name]["used"] += usage.used_count

                # Calculate remaining for package services
                for group_name, counts in package_service_totals.items():
                    counts["remaining"] = counts["total"] - counts["used"]
                    package_info["service_type_counts"].append({
                        "service": group_name,
                        "total": counts["total"],
                        "used": counts["used"],
                        "remaining": counts["remaining"]
                    })

                subscription_packages.append({
                    "package_name": subscription.package.package_name,
                    "expiry_date": subscription.expiry_date,
                    "details": package_info["service_type_counts"]  # Add details here
                })
                package_details.append(package_info)

            # Calculate remaining for global totals
            for group_name in service_totals:
                service_totals[group_name]["remaining"] = (
                    service_totals[group_name]["total"] - 
                    service_totals[group_name]["used"]
                )

            # Format response
            subscription_data = [{
                "service_type_counts": [
                    {
                        "service": group_name,
                        "total": counts["total"],
                        "used": counts["used"],
                        "remaining": counts["remaining"]
                    }
                    for group_name, counts in service_totals.items()
                ]
            }]

            return Response({
                "wallet_balance": wallet_balance,
                "packages": subscription_packages,
                "subscription_data": subscription_data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error in WalletAndSubscriptionUsageAPIView: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ServiceUsageHistory(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            service_filter = [2, 3]
            events = Event.objects.filter(user=user, service__in=service_filter)

            # Optional filters
            subscription = request.GET.get('subscription')
            date_from = request.GET.get('from')
            date_to = request.GET.get('to')

            if subscription is not None:
                events = events.filter(subscription=subscription.lower() == 'true')

            if date_from:
                events = events.filter(date__gte=date_from)

            if date_to:
                events = events.filter(date__lte=date_to)

            event_data = events.values(
                'id', 'user', 'service', 'serviceType', 'number', 'source', 
                'date', 'listing__display_name'
            )

            data = []
            for event in event_data:
                if event['serviceType'] in [1, 2]:
                    service_name = 'Toloo Bath'
                elif event['serviceType'] in [3, 4]:
                    service_name = 'Toloo Wash'
                elif event['serviceType'] == 5:
                    service_name = 'Toloo Urinal'
                elif event['serviceType'] == 9:
                    service_name = 'Cappuccino'
                else:
                    service_name = 'Unknown Service'

                e_data = {
                    'id': event['id'],
                    'service_name': service_name,
                    'listing_name': event['listing__display_name'],
                    'number': event['number'],
                    'source': event['source'],
                    'date': event['date'],
                }
                data.append(e_data)

            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error fetching TolooUsageHistory: {e}")
            return Response({"error": "An error occurred", "data": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# class TolooPay(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         amount = request.data.get('amount')
#         user = request.user
#         now = timezone.now().strftime('%Y-%m-%d %H:%M:%S')

#         if not amount:
#             logger.error(f"TolooPay POST: {user} - Amount is required")
#             return Response({"error": "Amount is required"}, status=status.HTTP_400_BAD_REQUEST)
        
#         try:
#             amount = int(amount)
#             if amount <= 0:
#                 raise ValueError
#         except ValueError:
#             logger.error(f"TolooPay POST: {user} - Invalid amount format")
#             return Response({"error": "Invalid or negative amount"}, status=status.HTTP_400_BAD_REQUEST)

#         #  Temporary event data
#         qrtype = request.data.get('qrtype')
#         types = request.data.get('types')
#         source = request.data.get('source')
#         count = request.data.get('count')
#         # room_number = int(request.data.get('room_number'))
#         listing = request.data.get("listing")

#         service_query = ServiceType.objects.filter(qrtype=qrtype, types=types, is_deleted=False).first()
#         if not service_query:
#             return Response({"error": "Service type not found"}, status=status.HTTP_400_BAD_REQUEST)

#         try:
#             client = razorpay.Client(auth=(settings.RAZORPAY_API_KEY, settings.RAZORPAY_API_SECRET))
#             payment_data = {
#                 'amount': amount * 100,
#                 'currency': 'INR',
#                 'receipt': f'toloo_{user.id}_{now}',
#                 'payment_capture': 1
#             }
#             razorpay_order = client.order.create(data=payment_data)
#             # print('rz response:', razorpay_order)

#             # Save the order and temp event
#             Razor_pay_payment_create.objects.create(
#                 user=user,
#                 razorpay_id=razorpay_order['id'],
#                 razorpay_status=razorpay_order['status'],
#                 amount=amount,
#             )

#             TemporaryEvent.objects.create(
#                 user=user,
#                 service=service_query.service,
#                 serviceType=service_query,
#                 number=count,
#                 source=source,
#                 date=timezone.now().date(),
#                 # room_numbers=[room_number],
#                 listing_id=listing,
#                 subscription=False,
#                 razorpay_order_id=razorpay_order['id']
#             )

#             return Response({"razorpay_order_id": razorpay_order['id']}, status=status.HTTP_201_CREATED)

#         except Exception as e:
#             logger.error(f"Error in TolooPay POST: {user} {e}")
#             return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#     def put(self, request):
#         try:
#             razorpay_order_id = request.data.get('razorpay_order_id')
#             razorpay_payment_id = request.data.get('razorpay_payment_id')
#             razorpay_signature = request.data.get('razorpay_signature')

#             client = razorpay.Client(auth=(settings.RAZORPAY_API_KEY, settings.RAZORPAY_API_SECRET))
#             payment_data = {
#                 'razorpay_order_id': razorpay_order_id,
#                 'razorpay_payment_id': razorpay_payment_id,
#                 'razorpay_signature': razorpay_signature
#             }

#             # Verify the payment signature
#             client.utility.verify_payment_signature(payment_data)

#             payment = Razor_pay_payment_create.objects.filter(razorpay_id=razorpay_order_id).first()
#             if not payment:
#                 logger.error(f"Payment not found")
#                 return Response({"error": "Payment not found"}, status=status.HTTP_404_NOT_FOUND)

#             payment.razorpay_status = 'captured'
#             payment.save(update_fields=['razorpay_status'])

#             # Log history
#             Razor_pay_payment_history.objects.create(
#                 user=payment.user,
#                 razorpay_id=payment.razorpay_id,
#                 razorpay_status=payment.razorpay_status,
#                 amount=payment.amount,
#                 payment_id=razorpay_payment_id,
#             )

#             # Create the final event
#             temp_event = TemporaryEvent.objects.filter(razorpay_order_id=razorpay_order_id).first()
#             if not temp_event:
#                 return Response({"error": "Temporary event not found"}, status=status.HTTP_404_NOT_FOUND)

#             event_data = {
#                 'user': temp_event.user.id,
#                 'service': temp_event.service.id,
#                 'serviceType': temp_event.serviceType.id,
#                 'number': temp_event.number,
#                 'source': temp_event.source,
#                 'date': temp_event.date.strftime("%Y-%m-%d"),
#                 'room_numbers': temp_event.room_numbers,
#                 'subscription': temp_event.subscription,
#                 'listing': temp_event.listing.id if temp_event.listing else None
#             }

#             event_serializer = EventSerializer(data=event_data)
#             if event_serializer.is_valid():
#                 event = event_serializer.save()
#                 temp_event.delete()

#                 # Prepare event response
#                 now = timezone.now()
#                 event_details = {
#                     "location": event.listing.place if event.listing else None,
#                     "status": "success",
#                     "date": now.strftime("%Y-%m-%d"),
#                     "time": now.strftime("%H:%M:%S"),
#                     "name": "Toloo",
#                     "service_name": "toloo",
#                     "service_type_name": event.serviceType.serviceType_name  if event.serviceType else None,
#                 }

#                 return Response({
#                     "message": "Event confirmed successfully",
#                     "data": {
#                         "payment_id": razorpay_payment_id,
#                         "amount": payment.amount,
#                         "status": "captured",
#                         "event": event_details
#                     }
#                 }, status=status.HTTP_200_OK)

#             else:
#                 logger.error(f"Event validation error: {event_serializer.errors}")
#                 return Response(event_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#         except razorpay.errors.SignatureVerificationError:
#             return Response({"error": "Invalid signature"}, status=status.HTTP_400_BAD_REQUEST)
#         except Exception as e:
#             logger.error(f"Error in TolooPay PUT: {e}")
#             return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class TolooRazorpayOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            event_payload = request.data.get('event_payload')
            amount = int(request.data.get('amount'))

            if not event_payload or not amount:
                return Response({"error": "Missing data"}, status=status.HTTP_400_BAD_REQUEST)
            if isinstance(event_payload, str):
                try:
                    event_payload = json.loads(event_payload)
                except json.JSONDecodeError:
                    return Response({"error": "Invalid event_payload format"}, status=status.HTTP_400_BAD_REQUEST)
                
            razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_API_KEY, settings.RAZORPAY_API_SECRET))
            order_data = {
                    'amount': amount * 100,  # convert to paise
                    'currency': 'INR',
                    'payment_capture': '1'
                }
            razorpay_order = razorpay_client.order.create(data=order_data)
            logger.info(f"Razorpay order created: {razorpay_order['id']}")
            
            # Step 2: Create Booking entry
            listing_id = event_payload.get('listing')
            listing = Listing.objects.get(id=listing_id) if listing_id else None

            booking = Booking.objects.create(
                user=request.user,
                listing=listing,
                razorpay_order_id=razorpay_order['id'],
                payable_amount=float(amount),
                date=timezone.now().date(),
                time=timezone.now().time(),
                duration=0,
                subtotal=float(amount),
                booking_status='PENDING',
                payment_status='PENDING',
                razorpay_event_payload=event_payload,
            )

            return Response({
                "order_id": razorpay_order['id'],
                "amount": amount,
                "currency": "INR",
                "booking_id": booking.id
            }, status=status.HTTP_200_OK)

        except Listing.DoesNotExist:
            return Response({"error": "Invalid listing ID"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Error creating Razorpay order")
            return Response({"error": "Razorpay order failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class TolooRazorpayVerifyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            payment_id = request.data.get('razorpay_payment_id')
            order_id = request.data.get('razorpay_order_id')
            signature = request.data.get('razorpay_signature')
            booking_id = request.data.get('booking_id')
            
            if not all([payment_id, order_id, signature, booking_id]):
                logger.error("missing verification data")
                return Response({"error": "Missing verification data"}, status=status.HTTP_400_BAD_REQUEST)

            booking = get_object_or_404(Booking, id=booking_id, user=request.user)

            client = razorpay.Client(auth=(settings.RAZORPAY_API_KEY, settings.RAZORPAY_API_SECRET))
            params_dict = {
                'razorpay_order_id': order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature': signature,
            }

            # Verify Signature
            client.utility.verify_payment_signature(params_dict)

            # Update Booking on Success
            booking.razorpay_payment_id = payment_id
            booking.payment_status = 'SUCCESS'
            booking.booking_status = 'CONFIRMED'
            booking.save()

            # Record the event now
            service = EventsService()
            response_data, status_code = service._record_event(
                data=booking.razorpay_event_payload,
                use_subscription=False,
                service_amount=float(booking.payable_amount) / int(booking.razorpay_event_payload.get('number', 1)),
                mode='direct_payment'
            )

            return Response({
                "message": "Payment successful and event created",
                "data": response_data,
                'event_payload': booking.razorpay_event_payload
            }, status=status.HTTP_200_OK)

        except razorpay.errors.SignatureVerificationError:
            logger.warning("Signature verification failed for Razorpay payment")
            booking.payment_status = 'FAILED'
            booking.save()
            return Response({"error": "Invalid payment signature"}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.exception("Razorpay payment verification failed")
            return Response({"error": "Verification failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TolooEventDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            event = Event.objects.get(pk=pk)
            serializer = TolooEventSerializer(event)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Event.DoesNotExist:
            return Response({"error": "Event not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error occurred in TolooEventDetailAPIView GET: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)