import logging
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from utils.s3connector import s3_upload
from .models import CarTimeSlot, CarWashService, User, Listing, Offer, CarCategory
from .serializers import OfferSerializer, OfferImageSerializer
from .models import Booking as CarWashBooking
from .serializers import CarTimeSlotSerializer, CarWashBookingSerializer, CarWashServiceSerializer, CarWashImageSerializer
from django.conf import settings
import razorpay
from rest_framework.permissions import IsAuthenticated
from datetime import datetime

logger = logging.getLogger(__name__)

class CarCategoryView(APIView):

    def get(self, request, category_id=None):
        """Retrieve a single category or all categories"""
        if category_id:
            try:
                category = CarCategory.objects.get(id=category_id)
                return Response({"id": category.id, "name": category.name}, status=status.HTTP_200_OK)
            except CarCategory.DoesNotExist:
                return Response({"error": "Category not found"}, status=status.HTTP_404_NOT_FOUND)
        else:
            categories = CarCategory.objects.all().values("id", "name")
            return Response(list(categories), status=status.HTTP_200_OK)

    def post(self, request):
        """Create a new category"""
        name = request.data.get("name")
        if not name:
            return Response({"error": "Name is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        category, created = CarCategory.objects.get_or_create(name=name)
        if created:
            return Response({"id": category.id, "name": category.name}, status=status.HTTP_201_CREATED)
        return Response({"message": "Category already exists", "id": category.id, "name": category.name}, status=status.HTTP_200_OK)
    

class CarWashServiceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, service_id=None):
        if service_id:
            try:
                service = CarWashService.objects.get(id=service_id, is_deleted=False)
                serializer = CarWashServiceSerializer(service)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except CarWashService.DoesNotExist:
                return Response({"error": "Service not found"}, status=status.HTTP_404_NOT_FOUND)
        else:
            services = CarWashService.objects.filter(is_deleted=False)
            serializer = CarWashServiceSerializer(services, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        listing_id = Listing.objects.filter(listing_user=request.user).first()
        if not listing_id:
            return Response({"error": "Listing not found for the user"}, status=status.HTTP_400_BAD_REQUEST)
        request.data['listing'] = listing_id.id
        serializer = CarWashServiceSerializer(data=request.data)
        if serializer.is_valid():
            service = serializer.save()
            message = []
            # images_data_for_es = []

            # Save images to S3
            images = request.FILES.getlist('image')
            try:
                print("Images:", images)
                for image in images:
                    s3_response = s3_upload(image, file_folder='carwash_images', file_name_prefix=service.id)
                    if "s3_url" in s3_response:
                        image_data = {'service': service.id, 'image': s3_response['s3_url']}
                        imageserializer = CarWashImageSerializer(data=image_data)
                        if imageserializer.is_valid():
                            saved_image = imageserializer.save()
                            # images_data_for_es.append({'id': saved_image.id, 'image': saved_image.image})
                        else:
                            message.append({"image_err": imageserializer.errors})
                    else:
                        message.append({"upload_err": s3_response.get("error", "Unknown error")})
            except Exception as e:
                message.append({"exception": str(e)})

            return Response({"service": serializer.data, "messages": message},
                            status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, service_id):
        try:
            service = CarWashService.objects.get(id=service_id, is_deleted=False)
        except CarWashService.DoesNotExist:
            return Response({"error": "Service not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = CarWashServiceSerializer(service, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            message = []
            images_data_for_es = []

            # Update images if provided
            images = request.FILES.getlist('image')
            if images:
                service.images.all().delete()  # Remove old images
                try:
                    for image in images:
                        s3_response = s3_upload(image, file_folder='carwash_service', file_name_prefix=service.id)
                        if "s3_url" in s3_response:
                            image_data = {'service': service.id, 'image': s3_response['s3_url']}
                            imageserializer = CarWashImageSerializer(data=image_data)
                            if imageserializer.is_valid():
                                saved_image = imageserializer.save()
                                images_data_for_es.append({'id': saved_image.id, 'image': saved_image.image})
                            else:
                                message.append({"image_err": imageserializer.errors})
                        else:
                            message.append({"upload_err": s3_response.get("error", "Unknown error")})
                except Exception as e:
                    message.append({"exception": str(e)})

            return Response({"service": serializer.data, "images": images_data_for_es, "messages": message},
                            status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, service_id):
        try:
            service = CarWashService.objects.get(id=service_id, is_deleted=False)
            service.is_deleted = True
            service.save()
            return Response({"message": "Service deleted successfully"}, status=status.HTTP_200_OK)
        except CarWashService.DoesNotExist:
            return Response({"error": "Service not found"}, status=status.HTTP_404_NOT_FOUND)

class CarWashBookingAPIView(APIView):
    def post(self, request):
        serializer = CarWashBookingSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            validated_data = serializer.validated_data

            user_id = validated_data['user_id']
            service_id = validated_data['service_id']
            listing_id = validated_data['listing_id']
            amount = int(validated_data['amount'] * 100)  # Convert to paise
            date = validated_data['date']
            slot_id = validated_data['slot_id']
            vehicle_number = validated_data['vehicle_number']
            vehicle_type = validated_data['vehicle_type']

            user = User.objects.filter(id=user_id).first()
            if not user:
                return Response({"error": "User ID not found"}, status=status.HTTP_400_BAD_REQUEST)

            booking = CarWashBooking.objects.create(
                user=user,
                service_id=service_id,
                listing_id=listing_id,
                amount=validated_data['amount'],
                payment_status='pending',
                booking_status='pending',
                date=date,
                slot_id=slot_id,
                vehicle_number=vehicle_number,
                vehicle_type=vehicle_type
            )

            client = razorpay.Client(auth=(settings.RAZORPAY_API_KEY, settings.RAZORPAY_API_SECRET))
            order_data = {'amount': amount, 'currency': 'INR', 'payment_capture': '1'}
            razorpay_order = client.order.create(data=order_data)
            
            booking.razorpay_order_id = razorpay_order['id']
            booking.save()

            return Response({
                'order_id': booking.razorpay_order_id,
                'booking_id': booking.id,
                'original_request': request.data
            }, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            logger.error(f"Error in creating car wash booking: {datetime.now()} : {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request):
        try:
            data = request.data
            razorpay_order_id = data.get('razorpay_order_id')
            razorpay_payment_id = data.get('razorpay_payment_id')
            razorpay_signature = data.get('razorpay_signature')

            client = razorpay.Client(auth=(settings.RAZORPAY_API_KEY, settings.RAZORPAY_API_SECRET))
            params_dict = {
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            }

            client.utility.verify_payment_signature(params_dict)

            booking = CarWashBooking.objects.get(razorpay_order_id=razorpay_order_id)
            booking.razorpay_payment_id = razorpay_payment_id
            booking.payment_status = 'confirmed'
            booking.save()

            return Response({'status': 'Payment confirmed successfully', 'booking_id': booking.pk}, status=status.HTTP_200_OK)
        
        except razorpay.errors.SignatureVerificationError:
            logger.error(f"Payment verification failed: {datetime.now()} : {razorpay_order_id}")
            return Response({'error': 'Payment verification failed'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error verifying car wash booking payment: {datetime.now()} : {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CarWashOffersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, offer_id=None):
        if offer_id:
            try:
                offer = Offer.objects.get(id=offer_id, status="active")
                serializer = OfferSerializer(offer)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except Offer.DoesNotExist:
                return Response({"error": "Offer not found"}, status=status.HTTP_404_NOT_FOUND)
        else:
            offers = Offer.objects.filter(status="active")
            serializer = OfferSerializer(offers, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        listing_id = Listing.objects.filter(listing_user=request.user).first()
        if not listing_id:
            return Response({"error": "Listing not found for the user"}, status=status.HTTP_400_BAD_REQUEST)
        mutable_data = request.data.copy()
        mutable_data['listing'] = listing_id.id

        serializer = OfferSerializer(data=mutable_data)
        if serializer.is_valid():
            offer = serializer.save()
            messages = []

            # Handle image uploads
            images = request.FILES.getlist('image')
            try:
                for image in images:
                    s3_response = s3_upload(image, file_folder='carwash_offers', file_name_prefix=offer.id)
                    if "s3_url" in s3_response:
                        image_data = {'offer': offer.id, 'image': s3_response['s3_url']}
                        image_serializer = OfferImageSerializer(data=image_data)
                        if image_serializer.is_valid():
                            image_serializer.save()
                        else:
                            messages.append({"image_err": image_serializer.errors})
                    else:
                        messages.append({"upload_err": s3_response.get("error", "Unknown error")})
            except Exception as e:
                messages.append({"exception": str(e)})

            return Response({"offer": serializer.data, "messages": messages}, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def put(self, request, offer_id):
        """Update an existing offer."""
        try:
            offer = Offer.objects.get(id=offer_id, status="active")
        except Offer.DoesNotExist:
            return Response({"error": "Offer not found"}, status=status.HTTP_404_NOT_FOUND)

        mutable_data = request.data.copy()
        listing_id = Listing.objects.filter(listing_user=request.user).first()
        if not listing_id:
            return Response({"error": "Listing not found for the user"}, status=status.HTTP_400_BAD_REQUEST)
        mutable_data['listing'] = listing_id.id

        serializer = OfferSerializer(offer, data=mutable_data, partial=True)
        if serializer.is_valid():
            updated_offer = serializer.save()
            messages = []

            # Handle image updates
            images = request.FILES.getlist('image')
            if images:
                offer.images.all().delete()  # Remove old images
                try:
                    for image in images:
                        s3_response = s3_upload(image, file_folder='carwash_offers', file_name_prefix=updated_offer.id)
                        if "s3_url" in s3_response:
                            image_data = {'offer': updated_offer.id, 'image': s3_response['s3_url']}
                            image_serializer = OfferImageSerializer(data=image_data)
                            if image_serializer.is_valid():
                                image_serializer.save()
                            else:
                                messages.append({"image_err": image_serializer.errors})
                        else:
                            messages.append({"upload_err": s3_response.get("error", "Unknown error")})
                except Exception as e:
                    messages.append({"exception": str(e)})

            return Response({"offer": serializer.data, "messages": messages}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, offer_id):
        """Delete an existing offer."""
        try:
            offer = Offer.objects.get(id=offer_id, status="active")
            offer.status = "inactive"  # Soft delete by marking the status as inactive
            offer.save()
            return Response({"message": "Offer deleted successfully"}, status=status.HTTP_200_OK)
        except Offer.DoesNotExist:
            return Response({"error": "Offer not found"}, status=status.HTTP_404_NOT_FOUND)



class CarTimeSlotAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        try:
            timeslot = CarTimeSlot.objects.filter(is_deleted=False)
            serializer = CarTimeSlotSerializer(timeslot, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # def post(self, request):
    #     try:
    #         listing = Listing.objects.filter(listing_user=request.user).first()
    #         if not listing:
    #             return Response({"error": "Listing not found for the user"}, status=status.HTTP_400_BAD_REQUEST)
    #         mutable_data = request.data.copy()
    #         mutable_data['listing'] = listing.id
    #         serializer = CarTimeSlotSerializer(data=mutable_data)
    #         if serializer.is_valid():
    #             print('work')
    #             serializer.save()
    #             return Response(serializer.data, status=status.HTTP_201_CREATED)
    #         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    #     except Exception as e:
    #         return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request):
        try:
            serializer = CarTimeSlotSerializer(data=request.data, context={'request': request})
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
    def put(self, request, pk):
        try:
            timeslot = CarTimeSlot.objects.get(pk=pk, is_deleted=False)
            serializer = CarTimeSlotSerializer(timeslot, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response({'message': 'CarTimeSlot updated successfully!'}, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    def delete(self, request, pk):
        try:
            service = CarTimeSlot.objects.get(pk=pk, is_deleted=False)
            service.is_deleted = True
            service.save()
            return Response({"message": "CarTimeSlot deleted successfully"}, status=status.HTTP_200_OK)
        except CarWashService.DoesNotExist:
            return Response({"error": "CarTimeSlot not found"}, status=status.HTTP_404_NOT_FOUND)
