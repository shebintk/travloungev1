import razorpay
from razorpay.errors import BadRequestError, ServerError, GatewayError
import logging
from datetime import datetime, timedelta
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import *
from django.shortcuts import get_object_or_404
from utils.s3connector import s3_upload
from firebase_admin import messaging
from .serializers import *
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import hmac
import hashlib
import json
from utils.mail.email_connector import MSG91EmailConnector
from utils.celery.tasks import send_booking_confirmation_task
from listing.models import Listing_images, ListingConstant
import traceback
from decimal import Decimal
from utils.razorpay.core import create_razorpay_order, verify_razorpay_payment_signature

logger = logging.getLogger(__name__)


# for customer side
class BookingPaymentAPIView(APIView):
    def post(self, request):
        try:
            serializer = BookingSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            validated_data = serializer.validated_data
            user_id = validated_data['user_id']
            listing_id = validated_data['listing_id']
            amount = int(validated_data['payable_amount'])  # Convert to paise for Razorpay
            date = validated_data.get('date')
            time = validated_data.get('time')
            duration = validated_data['duration']
            pod_info = validated_data['pod_info']
            add_ons = validated_data.get('add_ons', [])

            subtotal = validated_data['subtotal']
            discount_amount = validated_data['discount_amount']
            tax = validated_data['tax']
            print("validated_data", amount)

            # Check if user exists
            user = User.objects.filter(id=user_id).first()
            if not user:
                return Response({"error": "User ID not found"}, status=status.HTTP_400_BAD_REQUEST)
            
            user_profile = UserProfile.objects.filter(user=user).exists()
            ## print("USER PROFILE", user_profile)

            # user_name = request.data.get('user_name')
            # gender = request.data.get('gender')

            # if user_name:
            #     user.name = user_name
            # if gender:
            #     user.gender = gender
            # user.save()

            # user_profile, _ = UserProfile.objects.get_or_create(user=user)

            booking = Booking.objects.create(
                user_id=user_id,
                listing_id=listing_id,
                payable_amount=amount,
                subtotal=subtotal,
                discount_amount=discount_amount,
                tax=tax,
                payment_status='PENDING',
                booking_status='PENDING',
                date=date,
                time=time,
                duration=duration
            )

            # Razorpay order creation
            try:
                order_result = create_razorpay_order(amount * 100, currency='INR', payment_capture='1')
                if not order_result.get('success'):
                    logger.error(f"Razorpay order creation failed: {order_result.get('error')}")
                    return Response({'error': 'Payment gateway error. Please try again later.'}, status=status.HTTP_502_BAD_GATEWAY)
                razorpay_order = order_result['order']
                logger.info(f"Razorpay order created: {razorpay_order['id']}")

                booking.razorpay_order_id = razorpay_order['id']
                booking.save()

                # Preprocess pod_info to ensure pod_type is lowercased
                for pod in pod_info:
                    if 'pod_type' in pod and isinstance(pod['pod_type'], str):
                        pod['pod_type'] = pod['pod_type'].lower()

                # Save Pod Info
                pod_instances = [
                    CustomerPodInfo(booking=booking, **pod) for pod in pod_info
                ]
                CustomerPodInfo.objects.bulk_create(pod_instances)

                # Save Add-ons
                addon_instances = [
                    BookingAddOn(
                        booking=booking,
                        type=addon['type'],
                        quantity=addon['quantity'],
                        price_per_unit=addon['price_per_unit'],
                        total_price=addon['total_price']
                    ) for addon in add_ons
                ]
                BookingAddOn.objects.bulk_create(addon_instances)

                return Response({
                    'order_id': booking.razorpay_order_id,
                    'booking_id': booking.id,
                    'is_profile_completed': user_profile,
                    'original_request': request.data
                }, status=status.HTTP_201_CREATED)

            except Exception as e:
                logger.error(f"Unexpected Razorpay error at {datetime.now()} [Listing ID: {listing_id}]: {str(e)}")
                logger.debug(traceback.format_exc())
                return Response({'error': 'The server encountered an unexpected error. Please try again later.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.error(f"Unhandled exception in BookingPaymentAPIView at {datetime.now()} [User ID: {request.data.get('user_id')}] : {str(e)}")
            logger.debug(traceback.format_exc())
            return Response({'error': 'A server error occurred. Please try again later.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # PUT: Verify Razorpay Payment and Update Booking
    def put(self, request):
        try:
            data = request.data
            razorpay_order_id = data.get('razorpay_order_id')
            razorpay_payment_id = data.get('razorpay_payment_id')
            razorpay_signature = data.get('razorpay_signature')

            verify_result = verify_razorpay_payment_signature(
                razorpay_order_id, razorpay_payment_id, razorpay_signature
            )
            if not verify_result.get('success'):
                logger.error(f"Razorpay signature verification failed: {verify_result.get('error')}")
                return Response({'error': 'Payment verification failed'}, status=status.HTTP_400_BAD_REQUEST)

            # Update only the payment_status in Booking
            booking = Booking.objects.get(razorpay_order_id=razorpay_order_id)

            booking.razorpay_payment_id = razorpay_payment_id
            booking.payment_status = 'CONFIRMED'
            listing_id = booking.listing_id

            listing_image = Listing_images.objects.filter(listing_id=listing_id).last()
            listing_image_url = listing_image.image if listing_image else ''
             
            # mailing user
            user = booking.user  # Assuming there's a ForeignKey to User in Booking
            email_connector = MSG91EmailConnector()

            if(booking.user.email):
                send_booking_confirmation_task.delay(
                    recipient_name=user.name,  
                    recipient_email=user.email,
                    booking_id=booking.id,
                    check_in_date=booking.date,
                    amount=booking.payable_amount
                )
            else:
                print('User email not found')

            # Firebase Notification
            try:
                listing = Listing.objects.get(id=listing_id)
                listing_user = listing.listing_user
                if listing_user and listing_user.device_token:
                    customer_pod_info = CustomerPodInfo.objects.filter(booking=booking.id).values()
                    pod_details = "\n".join([f"• {item['pod_type'].capitalize()} - Quantity: {item['no_of_pods']}" for item in customer_pod_info])

                    # Create the message with improved body text
                    message = messaging.Message(
                        notification=messaging.Notification(
                            title="You have a new booking.",
                            # body="You have a new booking."
                        ),
                        data={
                            'date': str(booking.date),
                            'time': str(booking.time),
                            'duration': str(booking.duration),
                            'pod_info': pod_details,
                        },
                        token=listing_user.device_token
                    )
                    response = messaging.send(message)
                    logger.info(f"FCM Notification sent successfully: {response}")
            except Exception as e:
                logger.error(f"Firebase Notification error: {datetime.now()} : {listing_id} : {e}")

            booking.save()

            data = {
                'booking_id': booking.pk,
                'image_url': listing_image_url,
                'name': booking.listing.display_name,
                'location': booking.listing.place,
                'date': booking.date,
                'time': booking.time,
                'duration': booking.duration,
                'amount': booking.payable_amount,
                'status': 'success',
                'message': f'You have successfully booked Sleeping Pod(s) at {booking.listing.display_name}.'
            }

            return Response({'status': 'Payment confirmed successfully', 'data': data}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Razorpay payment verification section: {datetime.now()} : {locals().get('razorpay_order_id', 'N/A')} : {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetRazorpayID(APIView):
    def get(self, request, booking_id):
        try:
            booking = Booking.objects.get(id=booking_id)
            if booking.payment_status == 'PENDING':
                return Response({
                    'razorpay_order_id': booking.razorpay_order_id,
                    'booking_id': booking.id,
                    'amount': booking.payable_amount,
                    'status': 'pending'
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'message': 'Booking payment is already confirmed or failed',
                    'status': booking.payment_status
                }, status=status.HTTP_400_BAD_REQUEST)
        except Booking.DoesNotExist:
            return Response({'error': 'Booking does not exist.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error in RetryPaymentAPIView GET: {datetime.now()} : {booking_id} : {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# for Admin side
class UploadIDProofAPIView(APIView):
    """
    API for Admin to upload ID proof image and ID proof type for a customer.
    """
    # permission_classes = [IsAdminUser]

    # def post(self, request, booking_id):
    #     try:
    #         booking = get_object_or_404(Booking, id=booking_id)
    #         # id_proof_type = request.data.get("id_proof_type")
    #         # id_proof_image = request.FILES.get('id_proof_image') 
    #         print("Request Data:", request.data)
    #         id_proofs = request.data.get("id_proofs", [])
    #         if isinstance(id_proofs, dict):
    #             id_proofs = [id_proofs]
    #         print(id_proofs,"id_proofs")
    #         created_entries = []
    #         for proof in id_proofs:
    #             id_proof_type = proof.get("id_proof_type")
    #             customer_name = proof.get("customer_name")
    #             id_proof_image = proof.get('id_proof_image')
    #             print('id_proof_image', id_proof_image)
    #             s3_response = s3_upload(id_proof_image, file_folder='sleeping_pod_booking_id_proof_images', file_name_prefix=f"{booking.id}_{id_proof_type}")
    #             print("s3_response", s3_response)
    #             if "s3_url" not in s3_response:
    #                 return Response(
    #                     {"error": "Failed to upload ID proof. Please try again."},
    #                     status=status.HTTP_400_BAD_REQUEST
    #                 )

    #             data = {
    #                 "booking": booking.id,
    #                 "id_proof_type": id_proof_type,
    #                 "customer_name":customer_name,
    #                 "id_proof_image_url": s3_response["s3_url"]
    #             }
    #             print(data,"datatatat")

    #             serializer = CustomerInfoSerializer(data=data)
    #             if serializer.is_valid():
    #                 created_entry = serializer.save()
    #                 created_entries.append(CustomerInfoSerializer(created_entry).data)
    #             else:
    #                 return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    #         return Response(
    #             {"message": "ID Proof updated successfully"},
    #             status=status.HTTP_200_OK
    #         )
            

    #     except Exception as e:
    #         logger.error(f"Image Upload error at UploadIDProofAPIView: {datetime.now()} : {booking_id} : {e}")
    #         return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request, booking_id):
        try:
            booking = get_object_or_404(Booking, id=booking_id)

            # Extracting single values from the form-data request
            id_proof_type = request.data.get("id_proof_type")
            customer_name = request.data.get("customer_name")
            id_proof_image = request.FILES.get("id_proof_image")  # Use request.FILES for file uploads

            print("Extracted Data:", id_proof_type, customer_name, id_proof_image)  # Debugging

            # Upload to S3
            s3_response = s3_upload(
                id_proof_image,
                file_folder="sleeping_pod_booking_id_proof_images",
                file_name_prefix=f"{booking.id}_{id_proof_type}"
            )

            print("S3 Response:", s3_response)  # Debugging

            if "s3_url" not in s3_response:
                return Response(
                    {"error": "Failed to upload ID proof. Please try again."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Saving data
            data = {
                "booking": booking.id,
                "id_proof_type": id_proof_type,
                "customer_name": customer_name,
                "id_proof_image_url": s3_response["s3_url"]
            }
            print("Data to Save:", data)

            serializer = CustomerInfoSerializer(data=data)
            if serializer.is_valid():
                created_entry = serializer.save()
                return Response(
                    {"message": "ID Proof uploaded successfully"},
                    status=status.HTTP_200_OK
                )
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Image Upload error at UploadIDProofAPIView: {datetime.now()} : {booking_id} : {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class UpdateBookingStatusAPIView(APIView):
    """
    API for Admin to update the booking status and associated pod reservations.
    """
    # permission_classes = [IsAdminUser]

    def put(self, request, booking_id):
        try:
            booking = get_object_or_404(Booking, id=booking_id)
            booking.booking_status = request.data.get('booking_status')
            check_in = datetime.combine(booking.date, booking.time)
            check_out = check_in + timedelta(hours=booking.duration)
            booking.save()

            status_mapping = {
                'BOOKED': 'active',
                'CHECKED_IN': 'check_in',
                'CHECKED_OUT': 'check_out',
                'CANCELLED': 'active',
                'MAINTENANCE': 'disabled',
            }

            for pod_data in request.data.get('assigned_pods', []):
                sleeping_pod = get_object_or_404(Sleepingpod, id=pod_data['sleeping_pod_id'])
                pod_status = pod_data['status']

                # Update or create PodReservation
                PodReservation.objects.update_or_create(
                    booking=booking,
                    sleeping_pod=sleeping_pod,
                    defaults={
                        "check_in": check_in,
                        "check_out":check_out,
                        "status": pod_status
                    }
                )

                # Update Sleepingpod_status
                Sleepingpod_status.objects.update_or_create(
                    listing=sleeping_pod.listing,
                    sleepingpod=sleeping_pod,
                    defaults={"status": status_mapping.get(pod_status, "inactive")}
                )

            return Response({"message": "Booking and Pod status updated successfully"}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error@UpdateBookingStatusAPIView: {datetime.now()} : {booking_id} : {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

# for Admin side

#for admin side booking
class InstoreBookingAPI(APIView):
    def post(self, request):
        serializer = InstoreBookingSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            validated_data = serializer.validated_data
            listing_id = validated_data['listing_id']
            user_info = validated_data['user_info']
            mobile_number = user_info['mobile_number']
            name = user_info.get('name', '')
            gender = user_info.get('gender', '')
            
            # Check if user exists, otherwise create a new one
            user = User.objects.filter(mobile_number=mobile_number).first()
            if not user:
                try:
                    last_record = User.objects.latest('id')
                    lastid = last_record.id + 1
                except User.DoesNotExist:
                    lastid = 1
                uid = "TRV-CUSTOMER-" + str(lastid)
                user = User.objects.create_user(
                    name=name,
                    username=mobile_number,
                    mobile_number=mobile_number,
                    password=mobile_number,
                    gender=gender,
                    role=3,
                    uid=uid
                )
            user_id = user.id
            amount = int(validated_data['amount'])
            date = validated_data.get('date')
            time = validated_data.get('time')
            pod_info = validated_data['pod_info']
            duration = validated_data['duration']
            
            # Create in-store booking
            booking = Booking.objects.create(
                user_id=user_id,
                listing_id=listing_id,
                payable_amount=amount,
                payment_status='CONFIRMED',
                booking_status='CONFIRMED',
                date=date,
                time=time,
                duration=duration
            )
            booking.razorpay_order_id = "in_store"
            booking.razorpay_payment_id = "In_store"
            booking.save()
            
            # Save Pod Info
            pod_instances = [
                CustomerPodInfo(booking=booking, **pod) for pod in pod_info
            ]
            CustomerPodInfo.objects.bulk_create(pod_instances)

            return Response({
                'order_id': booking.razorpay_order_id,
                'booking_id': booking.id,
                'original_request': request.data
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Instore booking error: {datetime.now()} : {listing_id} : {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)