import ast
from collections import Counter
import json
from django.shortcuts import get_object_or_404, render
from rest_framework.views import APIView
# from django.contrib.auth import get_user_model
# from django.http import JsonResponse
from rest_framework.response import Response
from rest_framework import status, generics
from admin_app.models import *
from utils.s3connector import s3_upload
from .models import *
from customer.serializers import *
from admin_app.serializers import *
from rest_framework_simplejwt.tokens import RefreshToken
import logging
from datetime import datetime, timedelta
from datetime import date as dt
from rest_framework.permissions import IsAuthenticated,AllowAny
from django.contrib.auth import authenticate
from rest_framework.parsers import JSONParser
from django.db.models import Sum, F, Q
# from firebase_admin import db
# from sleeping_pod.sleepingpod import * 
from .serializers import (SleepingpodSerializer, SleepingpodPriceSerializer, PodSearchSerializer, SleepingpodStatusSerializer, 
                          GetSleepingpodStatusSerializer, ListingReviewSerializer, SleepingPodPriceAvailabilitySerializer)
# from django.db.models.functions import ACos, Cos, Radians, Sin
from listing.models import Listing_images, Review_rating, ListingConstant
from elasticsearch import Elasticsearch, NotFoundError
from rest_framework.pagination import PageNumberPagination
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
from django.utils.dateparse import parse_date
from django.utils.timezone import now
from utils.celery.tasks import set_elastic_search_index_task
from django.conf import settings

logger = logging.getLogger(__name__)

# class SleepingpodAPIView(APIView):
#     # permission_classes = [IsAuthenticated]
    
#     def get(self, request):
#         try:
#             current_date = timezone.now().date()
#             sleepingpods = get_allpods()
#             # availablepods = get_availablepods(current_date)
#             response={
#                 "sleepingpods":sleepingpods
#                 # "availablepods":availablepods
#             }
#             return Response(response, status=status.HTTP_200_OK)
#         except Exception as e:
#             logger.error(f"Error occurred in SleepingpodAPIView GET: {e}")
#             return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# class SleepingpodItemAPIView(APIView):
    
#     def get(self, request, format=None):
#         try:
#             item = Sleepingpod_item.objects.filter(is_deleted=False)
#             serializer = ItemSerializer(item, many=True)
#             return Response(serializer.data, status=status.HTTP_200_OK)
#         except Exception as e:
#             return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#     def post(self, request, format=None):
#         try:
#             serializer = ItemSerializer(data=request.data)
#             if serializer.is_valid():
#                 serializer.save()
#                 return Response({'message': 'Sleepingpod item posted successfully!', 'data': serializer.data}, status=status.HTTP_201_CREATED)
            
#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
#         except Exception as e:
#             return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# class SleepingpodPriceAPIView(APIView):
    
#     def get(self, request, format=None):
#         try:
#             price = Sleepingpod_price.objects.filter(is_deleted=False)
#             serializer = PriceSerializer(price, many=True)
#             return Response(serializer.data, status=status.HTTP_200_OK)
#         except Exception as e:
#             return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#     def post(self, request, format=None):
#         try:
#             serializer = PriceSerializer(data=request.data)
#             if serializer.is_valid():
#                 serializer.save()
#                 return Response({'message': 'Sleepingpod price posted successfully!', 'data': serializer.data}, status=status.HTTP_201_CREATED)
            
#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
#         except Exception as e:
#             return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
import re

class SleepingpodAPIView(APIView):
    def post(self, request, format=None):
        try:
            images = request.FILES.getlist('images')

            facilities_data = request.data.get('facilities', '[]')
            if isinstance(facilities_data, str):
                facilities_data = json.loads(facilities_data)

            # Extracting facility images based on the dynamic keys
            facility_images = {}
            pattern = re.compile(r'facilityImages_(\d+)_(\d+)')
            
            for key in request.FILES:
                match = pattern.match(key)
                if match:
                    facility_index = int(match.group(1))
                    if facility_index not in facility_images:
                        facility_images[facility_index] = []
                    facility_images[facility_index].append(request.FILES[key])

            # Copy and clean data
            data = request.data.copy()
            data.pop('facilities', None)

            serializer = SleepingpodSerializer(data=data)

            if serializer.is_valid():
                sleepingpod_serialize = serializer.save()
                
                if facilities_data:
                    for idx, facility_data in enumerate(facilities_data):
                        if facility_data:  # Ensure facility_data is not empty
                            facility = Sleepingpod_facilities.objects.create(
                                sleepingpod=sleepingpod_serialize,
                                name=facility_data.get('name'),
                                description=facility_data.get('description')
                            )

                            # Attach facility images based on index
                            for facility_image in facility_images.get(idx, []):
                                s3_url = s3_upload(facility_image, file_folder='sleepingpod_facility_image')
                                Sleepingpodfacility_images.objects.create(
                                    sleepingpod=facility,
                                    image=s3_url
                                )

                # Upload sleeping pod images
                for image_file in images:
                    s3_url = s3_upload(image_file, file_folder='sleepingpod_image')
                    Sleepingpod_images.objects.create(
                        sleepingpod=sleepingpod_serialize,
                        image=s3_url
                    )

                response = SleepingpodSerializer(sleepingpod_serialize)
                return Response({'message': 'Sleepingpod posted successfully!', 'data': response.data}, status=status.HTTP_201_CREATED)

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        
    import ast

    def get(self, request, format=None):
        try:
            listing_id = request.query_params.get('listing_id')
            sleepingpods = Sleepingpod.objects.filter(is_deleted=False,listing=listing_id)
            sleepingpods_response = []

            reservations = PodReservation.objects.filter(booking__listing=listing_id, check_out__gte=datetime.now(), is_deleted=False
                                                         ).values_list('id', 'sleeping_pod', 'check_in', 'check_out', 'booking__user__name', 'booking')
            
            reservations_data = {}
            for res in reservations:
                if res[1] in reservations_data:
                    reservations_data[res[1]].append({
                        'id': res[0],
                        'sleeping_pod': res[1],
                        'check_in': res[2],
                        'check_out': res[3],
                        'user_name': res[4],
                        'booking_id': res[5],
                    })
                else:
                    reservations_data[res[1]] = [{
                        'id': res[0],
                        'sleeping_pod': res[1],
                        'check_in': res[2],
                        'check_out': res[3],
                        'user_name': res[4],
                        'booking_id': res[5],
                    }]
            # print('reservation\n', json.dumps(reservations_data, indent=4, default=str))
            for pod in sleepingpods:
                # Fetch related images
                images = Sleepingpod_images.objects.filter(sleepingpod=pod)
                images_data = []
                for image in images:
                    try:
                        image_dict = ast.literal_eval(image.image)
                        s3_url = image_dict.get('s3_url', '')
                    except (ValueError, SyntaxError):
                        s3_url = ''
                
                    images_data.append({'id': image.id, 'image': s3_url})
            
                # Fetch related facilities and their images
                facilities = Sleepingpod_facilities.objects.filter(sleepingpod=pod)
                facilities_data = []
            
                for facility in facilities:
                    facility_images = Sleepingpodfacility_images.objects.filter(sleepingpod=facility)
                    facility_images_data = []
                    for facility_image in facility_images:
                        try:
                            facility_image_dict = ast.literal_eval(facility_image.image)
                            facility_s3_url = facility_image_dict.get('s3_url', '')
                        except (ValueError, SyntaxError):
                            facility_s3_url = ''
                    
                        facility_images_data.append({'id': facility_image.id, 'image': facility_s3_url})

                    facilities_data.append({
                        'id': facility.id,
                        'name': facility.name,
                        'description': facility.description,
                        'facility_images': facility_images_data
                    })

                pod_stat = Sleepingpod_status.objects.filter(sleepingpod=pod).first()

                # Construct final pod data with related data
                pod_data = {
                    'id': pod.id,
                    'listing': pod.listing.id,
                    'pod_name': pod.pod_name,
                    'pod_number': pod.pod_number,
                    'pod_type': pod.pod_type,
                    'pod_position': pod.pod_position,
                    # 'price': str(pod.price),
                    # 'description': pod.description,
                    'images': images_data,
                    'facilities': facilities_data,
                    'pod_status': pod_stat.status if pod_stat else None,
                    'upcoming_reservation': reservations_data.get(pod.id, [])
                }

                sleepingpods_response.append(pod_data)

            return Response(sleepingpods_response, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    
    def put(self, request, pk, format=None):
        try:
            sleepingpod = Sleepingpod.objects.get(pk=pk, is_deleted=False)
            images = request.FILES.getlist('images')
            facilities_data = request.data.get('facilities', '[]')
            if isinstance(facilities_data, str):
                facilities_data = json.loads(facilities_data)
            facility_images = {}
            pattern = re.compile(r'facilityImages_(\d+)_(\d+)')

            for key in request.FILES:
                match = pattern.match(key)
                if match:
                    facility_index = int(match.group(1))
                    if facility_index not in facility_images:
                        facility_images[facility_index] = []
                    facility_images[facility_index].append(request.FILES[key])

            data = request.data.copy()
            data.pop('facilities', None)
            data.pop('facility_images', None)

            serializer = SleepingpodSerializer(sleepingpod, data=data, partial=True)

            if serializer.is_valid():
                sleepingpod_serialize = serializer.save()

                # Update or create facilities
                # for idx, facility_data in enumerate(facilities_data):
                for facility_data in facilities_data:#new line
                    facility_id = facility_data.get('id')

                    if facility_id:
                        # If facility ID exists, update the facility
                        try:
                            facility = Sleepingpod_facilities.objects.get(id=facility_id, sleepingpod=sleepingpod)
                            facility.name = facility_data.get('name', facility.name)
                            facility.description = facility_data.get('description', facility.description)
                            facility.save()
                        except Sleepingpod_facilities.DoesNotExist:
                            return Response({"error": f"Facility with ID {facility_id} not found."}, status=status.HTTP_404_NOT_FOUND)
                    else:
                        # If no ID, create a new facility
                        facility = Sleepingpod_facilities.objects.create(
                            sleepingpod=sleepingpod_serialize,
                            name=facility_data.get('name'),
                            description=facility_data.get('description')
                        )

                        # Handle facility images
                        # if facility_images:
                        # for facility_image in facility_images.get(idx, []):
                        facility_images_list = facility_images.get(facility_id, [])  # new line Fetch using `facility_id`
                        for facility_image in facility_images_list:
                            s3_url = s3_upload(facility_image, file_folder='sleepingpod_facility_image')
                            Sleepingpodfacility_images.objects.create(
                                sleepingpod=facility,
                                image=s3_url
                            )

                # Update images (if provided)
                if images:
                    Sleepingpod_images.objects.filter(sleepingpod=sleepingpod).delete()  # Clear existing images
                    for image_file in images:
                        s3_url = s3_upload(image_file, file_folder='sleepingpod_image')
                        Sleepingpod_images.objects.create(
                            sleepingpod=sleepingpod_serialize,
                            image=s3_url
                        )

                response = SleepingpodSerializer(sleepingpod_serialize)
                return Response({'message': 'Sleepingpod updated successfully!', 'data': response.data}, status=status.HTTP_200_OK)

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Sleepingpod.DoesNotExist:
            return Response({"error": "Sleepingpod not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    
    def delete(self, request, pk, format=None):
        try:
            # Fetch the sleeping pod by primary key
            sleepingpod = Sleepingpod.objects.get(pk=pk, is_deleted=False)

            # Soft delete the sleeping pod
            sleepingpod.is_deleted = True
            sleepingpod.save()

            # Soft delete associated images
            Sleepingpod_images.objects.filter(sleepingpod=sleepingpod).update(is_deleted=True)

            # Soft delete associated facilities
            Sleepingpod_facilities.objects.filter(sleepingpod=sleepingpod).update(is_deleted=True)

            # Soft delete associated facility images
            Sleepingpodfacility_images.objects.filter(sleepingpod__sleepingpod=sleepingpod).update(is_deleted=True)

            return Response({'message': 'Sleepingpod and associated data deleted successfully!'}, status=status.HTTP_200_OK)

        except Sleepingpod.DoesNotExist:
            return Response({"error": "Sleepingpod not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



            

# fayas
class SleepingPodSearchAPIView(generics.GenericAPIView):
    serializer_class = PodSearchSerializer
    elastic_index = settings.ELASTICSEARCH_INDEX

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.es = Elasticsearch(
            hosts=[settings.ELASTICSEARCH_HOST],
            http_auth=(settings.ELASTICSEARCH_USER, settings.ELASTICSEARCH_PASSWORD),
        )

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        latitude = serializer.validated_data.get("latitude")
        longitude = serializer.validated_data.get("longitude")

        query = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"category": 2}}  # Filter for sleeping pods
                    ],
                    "filter": {
                        "geo_distance": {
                            "distance": "1500km",
                            "location": {
                                "lat": latitude,
                                "lon": longitude
                            }
                        }
                    }
                }
            }
        }

        try:
            response = self.es.search(index=self.elastic_index, body=query,size=1000)
            
            listings = list()
            for hit in response["hits"]["hits"]:
                if hit["_source"]["category"] in  [2]:
                    tmp_dict = { "id":hit["_id"],"price":200,"display_name":hit["_source"]["display_name"],"average_rating":5,"listing_id": hit["_id"],"place": hit["_source"].get("name", ""), "media_link": hit["_source"].get("media_link", ""),"images": hit["_source"].get("images", "")}
                    tmp_dict["images"] = []
                    if hit["_source"]["images"]:
                        count =0
                        for i in hit["_source"]["images"]:
                            t_dict = dict()
                            t_dict["id"] = count
                            if isinstance(i,dict):
                                tmp_dict["images"].append(i)
                            else:
                                t_dict["image"] = i
                                tmp_dict["images"].append(t_dict)
                            # print("=======================",tmp_dict)
                    listings.append(tmp_dict)


            return Response(
                {
                    "available_places": listings,
                    "search_criteria": serializer.validated_data
                },
                status=status.HTTP_200_OK
            )
        
        except NotFoundError as e:
            logger.error(f"Elasticsearch index not found in SleepingPodSearchAPIView POST: {e}")
            set_elastic_search_index_task.delay()
            return Response(
                {"error": f"Index '{self.elastic_index}' not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        except Exception as e:
            logger.error(f"Error (NotFound) in SleepingPodSearchAPIView POST: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    def get(self, request, *args, **kwargs):
        try:
            listing_id = request.query_params.get('listing_id')

            if not listing_id:
                return Response({"error": "listing_id is required."}, status=status.HTTP_400_BAD_REQUEST)

            listing_query = {
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"_id": listing_id}},         # Filter by listing_id
                            {"term": {"category": 2}}              # Filter for sleeping pods (assuming category 2)
                        ]
                    }
                }
            }

            listing_response = self.es.search(index=self.elastic_index, body=listing_query)
            hits = listing_response.get('hits', {}).get('hits', [])

            listing_source = hits[0].get('_source', {}) if hits else []

            reviews = Review_rating.objects.filter(
            listing_id=listing_id,
            listing__category=2               # Filter reviews for sleeping pods only
        )
            paginator = PageNumberPagination()
            paginator.page_size = 5  # Or dynamically get from query params
            paginated_reviews = paginator.paginate_queryset(reviews, request)

            review_data = ListingReviewSerializer(paginated_reviews, many=True).data

            return paginator.get_paginated_response({
                "listing_details": listing_source,
                "reviews": review_data
            })

        except Exception as e:
            logger.error(f"{datetime.now()} : {listing_id} : {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# fayas    


class SleepingpodStatusUpdateView(APIView):
    def put(self, request, pod_id):
        try:
            sleepingpod = Sleepingpod.objects.get(id=pod_id)
            sleepingpod_status, created = Sleepingpod_status.objects.get_or_create(
                sleepingpod=sleepingpod,
                defaults={"listing_id": sleepingpod.listing_id}  # Set listing_id properly
            )

            serializer = SleepingpodStatusSerializer(sleepingpod_status, data=request.data, partial=True)
            
            if serializer.is_valid():
                serializer.save()
                return Response(
                    {"message": "Sleepingpod status updated successfully", "data": serializer.data}, 
                    status=status.HTTP_200_OK
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SleepingPodPriceAvailability(APIView):
    def post(self, request):
        try:
            serializer = SleepingPodPriceAvailabilitySerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            validated_data = serializer.validated_data
            listing_id = validated_data['listing_id']
            date = validated_data['date']
            time = validated_data['time']
            pod_info = validated_data['pod_info']
            add_ons = validated_data.get('add_ons', {})
            
            app_user = request.user

            has_sleeping_pod_discount = False
            discount_info = None

            if app_user.is_authenticated:
                today = dt.today()
                active_subs = Subscription.objects.filter(
                    user=app_user,
                    status='Active',
                    expiry_date__gte=today,
                    subscribed_date__lte=today
                ).select_related('package')

                for sub in active_subs:
                    sleeping_pod_service = PackageServices.objects.filter(
                        package=sub.package, service__id=1
                    ).first()
                    if sleeping_pod_service and sleeping_pod_service.mode:
                        has_sleeping_pod_discount = True
                        discount_info = {
                            "mode": sleeping_pod_service.mode,
                            "discount_value": sleeping_pod_service.discount_value,
                            "number": sleeping_pod_service.number,
                            "package_name": sub.package.package_name,
                            "subscription_id": sub.id
                        }
                        break  # Only considering one matching subscription

            checkin_datetime = datetime.combine(date, datetime.strptime(time, '%H:%M:%S').time())

            duration = pod_info[0].get('duration')
            checkout_datetime = checkin_datetime + timedelta(hours=duration)

            # Step 1: Get all confirmed bookings for that listing that overlap
            overlapping_bookings = Booking.objects.filter(
                listing_id=listing_id,
                payment_status='CONFIRMED',
                date=date,
                time__lt=checkout_datetime.time()
            ).exclude(
                booking_status="CANCELLED"
            )

            # Step 2: Collect already booked pod counts from overlapping bookings
            booked_pod_counts = Counter()
            for booking in overlapping_bookings:
                booking_checkin = datetime.combine(booking.date, booking.time)
                booking_checkout = booking_checkin + timedelta(hours=booking.duration)
                
                if booking_checkout > checkin_datetime and booking_checkin < checkout_datetime:
                    customer_pods = CustomerPodInfo.objects.filter(booking=booking)
                    for cp in customer_pods:
                        booked_pod_counts[cp.pod_type] += cp.no_of_pods

            # Step 3: Check for disabled pods
            disabled_pod_ids = Sleepingpod_status.objects.filter(
                listing_id=listing_id, status='disabled'
            ).values_list('sleepingpod_id', flat=True)

            # Step 3.1: Get total available pod counts excluding disabled pods
            total_available_counts = Counter(
                Sleepingpod.objects.filter(
                    listing_id=listing_id,
                    is_deleted=False
                ).exclude(
                    id__in=disabled_pod_ids
                ).values_list('pod_type', flat=True)
            )

            available_pods = []
            unavailable_pods = []
            payable_amount = 0
            total_base_price = 0
            total_tax = 0
            total_add_ons_price = 0
            is_unavailable = False
            tax_rate = settings.SLEEPING_POD_TAX_RATE
            total_discount_price = 0  # New: accumulate per-pod discount

            for pod in pod_info:
                pod_type = pod.get('pod_type')
                if pod_type:
                    pod_type = pod_type.lower()
                count = int(pod.get('number_of_pods', 1))
                duration = int(pod.get('duration', 3))
                is_bath = pod.get('is_bath', False)
                is_restroom = pod.get('is_restroom', False)

                if not pod_type or count <= 0 or duration <= 0:
                    return Response({"error": f"Invalid pod details: {pod}"}, status=status.HTTP_400_BAD_REQUEST)

                already_booked = booked_pod_counts.get(pod_type, 0)
                total_available = total_available_counts.get(pod_type, 0)
                remaining = total_available - already_booked
                print('remaining_pod=', remaining)

                if remaining >= count:
                    prices = SleepingpodPrice.objects.filter(
                        listing_id=listing_id,
                        pod_type=pod_type,
                        duration=duration,
                        is_active=True,
                        is_bath=is_bath,
                        is_restroom=is_restroom,
                        is_deleted=False
                    )

                    if not prices.exists():
                        is_unavailable = True
                        features = []
                        if is_bath: features.append("bath")
                        if is_restroom: features.append("restroom")
                        feature_text = f' with {" & ".join(features)}' if features else ""
                        pod['error'] = f'{pod_type.capitalize()} pod - {duration}h{feature_text} not available. Please adjust your selection.'
                        unavailable_pods.append(pod)
                        continue

                    price_obj = prices.first()
                    base_price = float(price_obj.price)
                    discount_price = float(price_obj.discount_price)  # Now: percentage discount
                    # Calculate per-pod discount as a percentage
                    pod_discount_per_pod = base_price * discount_price / 100
                    pod_discount_total = round(pod_discount_per_pod * count)

                    pod_total = round(base_price * count)

                    total_base_price += pod_total
                    total_discount_price += pod_discount_total

                    pod['price'] = round(base_price)
                    pod['total_pod_price'] = pod_total
                    pod['discount_price'] = discount_price  # percentage value
                    pod['total_discount_price'] = pod_discount_total
                    pod['discount_per_pod'] = round(pod_discount_per_pod)  # new: per-pod discount value
                    available_pods.append(pod)

                else:
                    is_unavailable = True
                    pod['error'] = (
                        f"Sorry, only {max(0, remaining)} {pod_type} pod"
                        f"{'s are' if remaining != 1 else ' is'} available. Please adjust your selection."
                    )
                    unavailable_pods.append(pod)

            # step 4: Apply discounts if applicable and calculate total pod price
            discount_amount = 0
            if has_sleeping_pod_discount:
                if discount_info["mode"] == "percentage":
                    discount_amount = (total_base_price - total_discount_price) * discount_info["discount_value"] / 100
                elif discount_info["mode"] == "fixed":
                    discount_amount = discount_info["discount_value"]

            # Calculate tax (on base price minus per-pod discount and subscription discount)
            total_tax = round(float(total_base_price - total_discount_price - discount_amount) * tax_rate)

            has_six_hr_bath_pod = any(
                int(p.get('duration', 0)) >= 6 and p.get('is_bath', False) is True
                for p in available_pods
            )
            # step 5: Calculate add-ons 
            add_ons_output = []
            no_of_bath = int(add_ons.get("no_of_bath", 0))
            # If has_six_hr_bath_pod is True and no_of_bath > 0, reduce no_of_bath by 1
            if has_six_hr_bath_pod and no_of_bath > 0:
                no_of_bath -= 1
            if no_of_bath > 0:
                price_per_bath = 0
                listing_constant = ListingConstant.objects.filter(listing_id=listing_id).first()
                if listing_constant:
                    price_per_bath = float(listing_constant.price_per_bath)
                total_price_bath = round(price_per_bath * no_of_bath)

                add_ons_output.append({
                    "type": "bath",
                    "quantity": no_of_bath,
                    "price_per_unit": price_per_bath,
                    "total_price": total_price_bath
                })
                total_add_ons_price += total_price_bath


            # subtotal before tax including all discounts
            subtotal = round(total_base_price - total_discount_price - discount_amount + total_add_ons_price)
            payable_amount = subtotal + total_tax

            # Calculate average discount percentage (across all available pods)
            pod_discounts = [float(p.get('discount_price', 0)) for p in available_pods]
            discount_percentage = sum(pod_discounts) / len(pod_discounts) if pod_discounts else 0
            # Sum of all discounts
            total_discount_amount = round(total_discount_price + discount_amount)
            logger.info(f"{datetime.now()} : available_pods - {available_pods}")
            return Response(
                {
                    "status": "success",
                    "total_base_price": round(total_base_price),
                    "discount_percentage": discount_percentage,
                    "discount_amount": total_discount_amount,
                    "subtotal": subtotal,
                    "tax": total_tax,
                    "tax_rate": tax_rate,
                    "total_add_ons_price": total_add_ons_price,
                    "payable_amount": payable_amount,
                    "add_ons": add_ons_output,
                    "is_unavailable": is_unavailable,
                    "available_pods": available_pods,
                    "unavailable_pods": unavailable_pods,
                },
                status=status.HTTP_200_OK
            )

        except ValueError as ve:
            logger.error(f"{datetime.now()} : ValueError in sleeping_pod_availability_price: {str(ve)}", exc_info=True)
            return Response({"error": f"Invalid input: {str(ve)}"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"{datetime.now()} : {Exception} in sleeping_pod_availability_price: {str(e)}", exc_info=True)
            return Response({"error": f"An unexpected error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        
def get_unavailable_pods(checkin_time, checkout_time):
    # print('checkin', checkin_time)
    # print('checkout', checkout_time)
    reserved_pods = PodReservation.objects.filter(
        Q(check_in__lt=checkout_time) &
        Q(check_out__gt=checkin_time),
        is_deleted=False
    ).values_list('sleeping_pod', flat=True)
    return reserved_pods

class ActivePodsAPIView(APIView):
    def get(self, request):
        try:
            booking_id = request.query_params.get('booking_id')
            if not booking_id:
                return Response({"error": "Booking ID is required"}, status=status.HTTP_400_BAD_REQUEST)
            booking = Booking.objects.get(id=booking_id)

            checkin_date = booking.date
            checkin_time = booking.time
            duration = booking.duration
            checkin = datetime.combine(checkin_date, checkin_time)
            checkout = checkin + timedelta(hours=duration)

            unavailable_pods = get_unavailable_pods(checkin, checkout)
            # print('listing', booking.listing.id, 'unavailable', unavailable_pods)

            # Get IDs of disabled pods for this listing
            disabled_pod_ids = Sleepingpod_status.objects.filter(
                listing_id=booking.listing.id, status='disabled'
            ).values_list('sleepingpod_id', flat=True)

            available_pods = Sleepingpod.objects.filter(is_deleted=False,listing=booking.listing.id)\
                .exclude(id__in=unavailable_pods)\
                .exclude(id__in=disabled_pod_ids)
            logger.info(f"@ActivePodsAPIView : {datetime.now()} : available_pods - {available_pods.count()}")
            serializer = GetSleepingpodStatusSerializer(available_pods, many=True).data
            return Response({"status":"success","available_pods": serializer},status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"@ActivePodsAPIView : {datetime.now()} : {Exception} in ActivePodsAPIView: {str(e)}", exc_info=True)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SleepingpodPriceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_id = request.user.id
        listing_id = Listing.objects.filter(listing_user=user_id).first().id
        sleepingpod_prices = SleepingpodPrice.objects.filter(listing=listing_id, is_deleted=False)
        serializer = SleepingpodPriceSerializer(sleepingpod_prices, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = SleepingpodPriceSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def put(self, request, pk):
        """Update an existing SleepingpodPrice instance"""
        sleepingpod_price = get_object_or_404(SleepingpodPrice, pk=pk)
        serializer = SleepingpodPriceSerializer(sleepingpod_price, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        """Soft delete a SleepingpodPrice instance"""
        sleepingpod_price = get_object_or_404(SleepingpodPrice, pk=pk)
        sleepingpod_price.is_deleted = True
        sleepingpod_price.save()
        return Response({"message": "Sleepingpod price soft deleted."}, status=status.HTTP_204_NO_CONTENT)


class BookingAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # Extract listing_id from listing_user
            user_id = request.user.id
            listing_id = Listing.objects.filter(listing_user=user_id).first().id

            # Extract date filter params
            filter_type = request.query_params.get('filter', 'today')  # "today", "tomorrow", "range"
            from_date = request.query_params.get('from_date')
            to_date = request.query_params.get('to_date')

            # Prepare Q object for date filtering
            date_filter = Q()
            if filter_type == "today":
                date_filter = Q(date=dt.today())

            elif filter_type == "tomorrow":
                date_filter = Q(date=dt.today() + timedelta(days=1))

            elif filter_type == "range" and from_date and to_date:
                from_date_parsed = parse_date(from_date)
                to_date_parsed = parse_date(to_date)
                if from_date_parsed and to_date_parsed:
                    date_filter = Q(date__range=(from_date_parsed, to_date_parsed))
                else:
                    return Response({"error": "Invalid from_date or to_date format."}, status=status.HTTP_400_BAD_REQUEST)

            # Final query with filter
            customer_bookings = Booking.objects.filter(Q(listing=listing_id), Q(user__role=3), date_filter).exclude(
                Q(booking_status="PENDING") & Q(payment_status="PENDING")).values(
                "id", "user_id", "user__name", "razorpay_payment_id", "user__mobile_number",
                "date", "duration", "time", "pod_info__no_of_pods", "pod_info__pod_type","pod_info__is_bath","pod_info__is_restroom", "user__gender"
            )

            bookings_dict = {}
            for booking in customer_bookings:
                booking_id = booking["id"]
                if booking_id not in bookings_dict:
                    pod_reservation_info = []
                    pod_reservations = PodReservation.objects.filter(booking=booking_id)
                    if pod_reservations:
                        for pod in pod_reservations:
                            pod_info = Sleepingpod.objects.filter(id=pod.sleeping_pod.pk).values().first()
                            # print("\n\n\n\n============",pod_info,pod_info.keys(),"\n\n\n\n=========")
                            pod_type = pod_info["pod_type"]
                            pod_name =  pod_info["pod_name"]
                            pod_number =  pod_info["pod_number"]
                            pod_reservation_info.append({
                                "id": pod.id,
                                "no_of_pods": 1,
                                "pod_type": pod_type,
                                "pod_name": pod_name,
                                "pod_number":pod_number
                                })
                    if len(pod_reservation_info):
                        is_assign_button = False
                    else:
                        is_assign_button = True

                    bookings_dict[booking_id] = {
                        "id": booking["id"],
                        "user_id": booking["user_id"],
                        "name": booking["user__name"],
                        "razorpay_payment_id": booking["razorpay_payment_id"],
                        "mobile_number": booking["user__mobile_number"],
                        "gender": booking["user__gender"],
                        "expected_check_out_date": (
                            datetime.combine(booking["date"], booking["time"]) + timedelta(hours=booking["duration"])
                            if booking["date"] else None
                        ).date() if booking["date"] else None,  # Adjusted to reflect actual check-out date
                        "check_out": (
                            datetime.combine(booking["date"], booking["time"]) + timedelta(hours=booking["duration"])
                            if booking["date"] else None
                        ).time().strftime("%H:%M") if booking["date"] else None,  # Adjusted check-out time
                        "check_in_date": booking["date"], 
                        "check_in": (
                            datetime.combine(booking["date"], booking["time"])
                            if booking["date"] else None
                        ).time().strftime("%H:%M") if booking["date"] else None,
                        "pod_info": [],
                        "pod_reservation_info": pod_reservation_info,
                        "is_assign_button": is_assign_button,
                    }
                bookings_dict[booking_id]["pod_info"].append({
                "pod_type": booking["pod_info__pod_type"],
                "no_of_pods": booking["pod_info__no_of_pods"],
                "duration": booking["duration"],
                "is_bath": booking["pod_info__is_bath"],
                "is_restroom": booking["pod_info__is_restroom"]
                })
            return Response({"bookings": list(bookings_dict.values())},status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error in BookingAPIView GET: {str(e)}", exc_info=True)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class BookingDetialsAPIView(APIView):
    def get(self, request, booking_id):
        try:
            booking = Booking.objects.get(id=booking_id)
            listing = booking.listing
            customer_pod_info = CustomerPodInfo.objects.filter(booking=booking).values()

            pod_reservations = PodReservation.objects.filter(booking=booking)

            # Fetch CustomerInfo if it exists
            customer_info = CustomerInfo.objects.filter(booking=booking).values()
            # print(customer_info)

            # Prepare pod_info to be a list of dicts, one for each pod reservation
            pod_info = []
            id_proof_data = []

            # Check if id_proof_image_url exists and is iterable (e.g., a list of dictionaries)
            if customer_info:
                for id_proof in customer_info:
                    id_proof_data.append({
                        "id_proof_type": id_proof['id_proof_type'].strip('"'),
                        "customer_name":id_proof["customer_name"],
                        "id_proof_image_url": id_proof['id_proof_image_url'],
                    })

            # Prepare pod information
            pod_reservation_info = []
            if pod_reservations:
                for pod in pod_reservations:
                    pod_info = Sleepingpod.objects.filter(id=pod.sleeping_pod.pk).values().first()
                    pod_type = pod_info["pod_type"]
                    pod_name =  pod_info["pod_name"]
                    pod_number =  pod_info["pod_number"]
                    pod_reservation_info.append({
                        "no_of_pods": 1,
                        "pod_type": pod_type,
                        "pod_name": pod_name,
                        "pod_number":pod_number
                    })

            addons = booking.add_ons.all()
            addons_info = [
                {
                    "type": addon.get_type_display(),  # shows human-readable name like "Bath"
                    "rate": float(addon.price_per_unit),
                    "quantity": addon.quantity,
                    "total": float(addon.total_price),
                }
                for addon in addons
            ]   

            billing_details = {
                "items":[
                    {
                    "type":pod["pod_type"],
                    "rate":pod["pod_price"],
                    "quantity":pod["no_of_pods"],
                    "is_bath":pod["is_bath"],
                    "is_restroom":pod["is_restroom"],
                    }
                    for pod in customer_pod_info
                ],
                "addons": addons_info,
                "subtotal": round(booking.subtotal, 2),
                "tax": booking.tax,
                "tax_rate": settings.SLEEPING_POD_TAX_RATE,
                "discount": booking.discount_amount,
                "payable_amount": round(booking.payable_amount, 2),
            }

                
            listing_images = Listing_images.objects.filter(listing=booking.listing)
            image_urls = [image.image for image in listing_images if image.image]
            
            latitude = listing.latitude
            longitude = listing.longitude
            
            if latitude and longitude:
                try:
                    geolocator = Nominatim(user_agent="booking_app")
                    location = geolocator.reverse((latitude, longitude), exactly_one=True)
                    if location:
                        address = location.raw.get('address', {})
                        location_name = address.get('city', address.get('town', address.get('village', 'Unknown')))
                except GeocoderTimedOut:
                    location_name = "Location lookup timed out"
            # Construct the response data
            booking_data = {
                "user": {
                    "user_id": booking.user.id,
                    "name": booking.user.name,
                    "mobile_number": booking.user.mobile_number,
                },
                "booking_id": booking_id,
                "payment_status": booking.payment_status,
                "check_in_date": booking.date,
                "amount": booking.payable_amount,
                "pod_reservations": "Booked",
                "id_proof_data": id_proof_data,
                "pod_info": pod_info,
                "pod_name" : listing.display_name,
                "image":image_urls,
                "cancellable": True,
                'listing': listing.pk,
                "billing_details":billing_details,
                "location": location_name,
                "pod_reservation_info":pod_reservation_info,
                # "location":"Kozhikode",
                "duration": booking.duration,
                "arrival_time": booking.time,
                "status":booking.booking_status,
                "canceled_at" :(booking.updated_on).strftime("%d-%m-%Y") if booking.booking_status=="CANCELLED" else None
            }

            return Response(booking_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class BookingCancelAPIView(APIView):
    def post(self, request):
        try:
            booking_id = request.data.get("booking_id")
            
            if not booking_id:
                return Response({"error": "Booking ID is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            booking = get_object_or_404(Booking, id=booking_id)
            
            if booking.booking_status == "CANCELLED":
                return Response({"message": "Booking is already cancelled"}, status=status.HTTP_400_BAD_REQUEST)
            
            booking.booking_status = "CANCELLED"
            booking.updated_on = now()
            booking.save()
            
            return Response({"message": "Booking cancelled successfully","canceled_on": booking.updated_on}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class BookingReportAPIView(APIView):
    def get(self, request, *args, **kwargs):
        try:
            listing_id = request.query_params.get('listing_id')
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            gender = request.query_params.get('gender')

            if not listing_id:
                return Response({"error": "Listing ID is required"}, status=status.HTTP_400_BAD_REQUEST)

            bookings = Booking.objects.filter(listing_id=listing_id).exclude(payment_status="PENDING")

            if start_date:
                start_date = parse_date(start_date)
                if not start_date:
                    return Response({'error': 'Invalid start_date format. Use YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)

                if end_date and end_date !="null":
                    end_date = parse_date(end_date)
                    if not end_date:
                        return Response({'error': 'Invalid end_date format. Use YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)

                    if start_date > end_date:
                        return Response({'error': 'start_date cannot be greater than end_date.'}, status=status.HTTP_400_BAD_REQUEST)

                    bookings = bookings.filter(date__range=[start_date, end_date])
                else:
                    bookings = bookings.filter(date__gte=start_date)

            if gender:
                bookings = bookings.filter(user__gender__iexact=gender)

            if not bookings.exists():
                return Response({'error': 'No bookings found for the given criteria'}, status=status.HTTP_404_NOT_FOUND)

            booking_data = []
            for booking in bookings:
                check_in = booking.time
                duration = booking.duration

                check_out = None
                if check_in:
                    check_out = (datetime.combine(datetime.today(), check_in) + timedelta(hours=duration)).time()

                pod_info = booking.pod_info.all().values("pod_type", "no_of_pods")

                booking_data.append({
                    'id': booking.id,
                    "user": {
                        "user_id": booking.user.id,
                        "name": booking.user.name,
                        "mobile_number": booking.user.mobile_number,
                        "gender": booking.user.gender if booking.user.gender else "Not specified"
                    },
                    'razorpay_payment_id': booking.razorpay_payment_id,
                    'amount': str(booking.payable_amount),
                    'checkout_date': booking.date,
                    'check_in': check_in,  
                    'check_out': check_out,
                    'booking_status': booking.booking_status,
                    'payment_status': booking.payment_status,
                    'pod_info': list(pod_info)
                })

            return Response(booking_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReassignPodAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            booking_id = request.data.get("booking_id")
            pod_to_cancel = request.data.get("pod_to_cancel") # reservation_id
            pod_to_assign = request.data.get("pod_to_assign") # new pod_id
            pod_status = request.data.get("pod_status")

            if not booking_id or not pod_to_cancel or not pod_to_assign or not pod_status:
                return Response({"error": "booking_id, pod_to_cancel, pod_to_assign, and pod_status are required"}, status=status.HTTP_400_BAD_REQUEST)
            
            booking = Booking.objects.get(id=booking_id)
            pod_reservation = PodReservation.objects.get(id=pod_to_cancel)
            sleeping_pod = Sleepingpod.objects.get(id=pod_to_assign)

            if booking.booking_status == "CANCELLED":
                return Response({"error": "Booking is already cancelled"}, status=status.HTTP_400_BAD_REQUEST)
            
            if pod_reservation.booking != booking:
                return Response({"error": "Pod reservation does not belong to the given booking"}, status=status.HTTP_400_BAD_REQUEST)
            
            if pod_reservation.sleeping_pod == sleeping_pod:
                return Response({"error": "Pod is already assigned to the booking"}, status=status.HTTP_400_BAD_REQUEST)
            
            # Reassign the pod
            pod_reservation.sleeping_pod = sleeping_pod
            pod_reservation.status = pod_status
            pod_reservation.save()
            
            status_mapping = {
                'BOOKED': 'active',
                'CHECKED_IN': 'check_in',
                'CHECKED_OUT': 'check_out',
                'CANCELLED': 'active',
                'MAINTENANCE': 'disabled',
            }

            # Update Sleepingpod_status
            Sleepingpod_status.objects.update_or_create(
                listing=sleeping_pod.listing,
                sleepingpod=sleeping_pod,
                defaults={"status": status_mapping.get(pod_status, "inactive")}
            )

            return Response({"message": "Pod reassigned successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
