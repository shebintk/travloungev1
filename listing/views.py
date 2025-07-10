from django.shortcuts import get_object_or_404, render
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from rest_framework.response import Response
from rest_framework import status
from listing.serializers import *
from django.contrib.auth.hashers import make_password
from django.contrib.auth import login
from rest_framework_simplejwt.tokens import RefreshToken
import logging
from datetime import datetime, timedelta
from django.contrib.auth import authenticate, login
from rest_framework.permissions import IsAuthenticated,AllowAny
from django.contrib.auth import authenticate
from rest_framework.parsers import JSONParser
import requests
from geopy.distance import geodesic
from .documents import ListingDocument
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError
from elasticsearch_dsl import Q
from django.utils import timezone 
from utils.s3connector import s3_upload
from django.conf import settings
from decimal import Decimal

import json
from datetime import date
logger = logging.getLogger(__name__)
# print(settings.ELASTICSEARCH_DSL,'llll')

# Initialize Elasticsearch client
# es = Elasticsearch(
#     hosts='http://localhost:9200',
#     http_auth='listingelastic'
# )

class Signin(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()
class SigninAPIView(APIView):
    permission_classes = [AllowAny]
    def post(self,request): 
        try:
            username = request.data.get('username')
            password = request.data.get('password')
            user = authenticate(request,username=username,password=password)
            if user is not None:
                refresh = RefreshToken.for_user(user)
                response ={
                    "access_token":str(refresh.access_token),
                    "refresh_token":str(refresh),
                    "status_code":status.HTTP_200_OK,
                    "user":user.username,
                    "role":4
                }
                return Response(response,status=status.HTTP_200_OK)
            else:
                return Response({"message":"Incorrect inputs"},status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error occured in signin POST:{e}")
            return Response({"error":"An error occured"},status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        


class ListingAPIView(APIView):
    permission_classes = [IsAuthenticated]

    elastic_index = settings.ELASTICSEARCH_INDEX

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.es = Elasticsearch(
            hosts=[settings.ELASTICSEARCH_HOST],  # Update with your Elasticsearch IP and port
            http_auth=(settings.ELASTICSEARCH_USER, settings.ELASTICSEARCH_PASSWORD),
        )
    def clean_number(self, value):
        # Implement this method to clean up the latitude and longitude values if needed
        return value

   
    def get(self, request, format=None):
        start_time = time.time()
        try:
            listings = Listing.objects.filter(is_deleted=False)
            serializer = ListingSerializer(listings, many=True).data
            end_time = time.time()
            total_time = time.strftime("%M:%S", time.gmtime(end_time - start_time))
            print(f"Total time: {total_time}")
            return Response(serializer, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    def post(self, request, format=None):
        message = []
        try:
            # Extract and validate latitude and longitude
            latitude_str = request.data['latitude']
            longitude_str = request.data['longitude']

            try:
                latitude = float(self.clean_number(latitude_str))
                longitude = float(self.clean_number(longitude_str))
                if not -90 <= latitude <= 90:
                    raise ValueError(f"Latitude must be between -90 and 90. Got {latitude}.")
                if not -180 <= longitude <= 180:
                    raise ValueError(f"Longitude must be between -180 and 180. Got {longitude}.")
            except ValueError as ve:
                return Response({"error": str(ve)}, status=status.HTTP_400_BAD_REQUEST)

            media_link = request.data.get('media_link')
            if isinstance(media_link, str):
                try:
                    media_link = json.loads(media_link)
                except json.JSONDecodeError:
                    return Response({"error": "Invalid format for media_link. It must be a valid JSON object."},
                                    status=status.HTTP_400_BAD_REQUEST)

            # Validate and process facilities
            facilities = request.data.get("facilities")
            valid_facilities_data = []

            if facilities:
                try:
                    facility_ids = json.loads(facilities) if isinstance(facilities, str) else facilities
                    if not isinstance(facility_ids, list):
                        raise ValueError
                except (ValueError, TypeError):
                    return Response({"error": "Facilities must be a valid list of IDs."}, status=status.HTTP_400_BAD_REQUEST)

                # Fetch valid facilities (both IDs and names)
                valid_facilities = Listing_faclities.objects.filter(id__in=facility_ids).values("id", "facility_name", "description", "image")
                valid_facility_ids = [f["id"] for f in valid_facilities]
                valid_facilities_data = [
                    {
                    "name": f['facility_name'],
                    "description": f["description"],
                    "image": f["image"]
                } 
                for f in valid_facilities
                ]

                # Check for invalid facility IDs
                invalid_facilities = set(facility_ids) - set(valid_facility_ids)
                if invalid_facilities:
                    return Response({"error": f"Invalid facility IDs: {list(invalid_facilities)}"}, status=status.HTTP_400_BAD_REQUEST)

            else:
                facility_ids = []
                
            #########new line
            existing_user = User.objects.filter(mobile_number=request.data['contact_number']).first()
            if existing_user:
                return Response({"error": "This contact number already exists."}, status=status.HTTP_400_BAD_REQUEST)

            # Prepare data for Django model
            request_data = {
                'name': request.data['name'],
                'category': request.data['category'],
                'latitude': latitude,
                'longitude': longitude,
                'display_name': request.data['display_name'],
                'description': request.data['description'],
                'media_link': media_link,
                'contact_name': request.data['contact_name'],
                'contact_number': request.data['contact_number'],
                'place': request.data['place'],
                'toloo_assured': request.data['toloo_assured'],
                'email': request.data['email'],
                'facilities': facility_ids,  # Store facility IDs as a list in JSONField
            }

            # Save the data to the Django model
            serializer = ListingSerializer(data=request_data)
            if serializer.is_valid():

                # updated mobile number to start with 0 since we can have similar customer with same number
                username = request.data['name'].lower().replace(" ", "")
                user_data = {
                    'name': request.data['contact_name'] or "Default Name",
                    'username': username,
                    'role': 5,
                    'password': username,
                    'mobile_number': f"0{request.data['contact_number']}",
                    'email': request.data['email'],
                    'is_active': True,
                }

                # Create and save the User
                try:
                    user = User.objects.create_user(**user_data)
                except Exception as e:
                    return Response({"message": f"{e}"}, status=status.HTTP_400_BAD_REQUEST)

                user.uid = f"TRV-VENDOR-{user.id}"
                user.save()

                listing = serializer.save() # Listing created after succesful creation of user, previous issue > sometimes username was not unique, 
                                            # causing listing to be created without a corresponding user

                listing.listing_user = user
                listing.save()

                try:
                    if listing.category == 2:
                        ListingConstant.objects.create(
                            listing=listing,
                            price_per_bath=Decimal('150.00')
                        )
                except Exception as e:
                    logger.error(f"Failed to create ListingConstant for listing {listing.id}: {e}")
                    # Optionally pass or raise depending on your use case
                    pass  # Don't interrupt the flow

                cat_title = Listing_category.objects.get(id=listing.category).category_name

                # Save images
                images = request.FILES.getlist('image')
                print('FAYAS', images)
                images_data_for_es = []
                try:
                    for image in images:
                        s3_response = s3_upload(image, file_folder='listing_image', file_name_prefix=listing.id)
                        if "s3_url" in s3_response:
                            image_data = {
                                'listing': listing.id,
                                'image': s3_response['s3_url']
                            }

                            imageserializer = ListingImagePostSerializer(data=image_data)
                            if imageserializer.is_valid():
                                saved_image = imageserializer.save()
                                # Collect image data for Elasticsearch
                                images_data_for_es.append({
                                    'id': saved_image.id,
                                    'image': saved_image.image
                                })
                            else:
                                message.append({"image_err": imageserializer.errors})
                        else:
                            logger.error(f"s3Error {listing.id}: {s3_response.get('error', 'Unknown error')}")
                            message.append({"upload_err": s3_response.get("error", "Unknown error")})
                except Exception as e:
                    logger.error(f"Failed to add image {listing.id}: {e}")
                    message.append({"exception": str(e)})

                self.es.indices.refresh(index=self.elastic_index)

                # Prepare data for Elasticsearch indexing
                es_data = {
                    'name': listing.name,
                    'category': listing.category,
                    'location': {
                        'lat': listing.latitude,
                        'lon': listing.longitude
                    },
                    'display_name': listing.display_name,
                    'description': listing.description,
                    'media_link': listing.media_link,
                    'contact_name': listing.contact_name,
                    'contact_number': listing.contact_number,
                    'status': listing.status,
                    'place': listing.place,
                    'toloo_assured': listing.toloo_assured,
                    'images': images_data_for_es,
                    'cat_title': cat_title,
                    'facilities': valid_facilities_data,
                }

                # Index the data into Elasticsearch
                self.es.index(index=self.elastic_index, id=listing.id, body=es_data)

                # Save offer images
                offer_images = request.FILES.getlist('offer_image')
                try:
                    for image in offer_images:
                        s3_response = s3_upload(image, file_folder='listing_offer_image', file_name_prefix=listing.id)
                        if "s3_url" in s3_response:
                            image_data = {
                                'listing': listing.id,
                                'image': s3_response['s3_url']
                            }
                            offerimageserializer = ListingOfferImagePostSerializer(data=image_data)
                            if offerimageserializer.is_valid():
                                offerimageserializer.save()
                            else:
                                message.append({"offer_image_err": offerimageserializer.errors})
                except:
                    pass

                #Save listing videos
                videos = request.FILES.getlist('videos')
                try:
                    for video in videos:
                        s3_response = s3_upload(video, file_folder='listing_video', file_name_prefix=listing.id)
                        if "s3_url" in s3_response:
                            video_data = {
                                'listing': listing.id,
                                'video': s3_response['s3_url']
                            }
                            videoserializer = ListingVideoPostSerializer(data=video_data)
                            if videoserializer.is_valid():
                                videoserializer.save()
                            else:
                                message.append({"video_err": videoserializer.errors})
                except Exception as e:
                    logger.error(f"Video upload error for listing {listing.id}: {e}")
                    message.append({"video_upload_error": str(e)})

                # Fetch all videos for the listing and update Elasticsearch
                current_videos = []
                try:
                    existing_videos = Listing_videos.objects.filter(listing=listing.id).values("id", "video")
                    current_videos = [{"id": vid["id"], "video": vid["video"]} for vid in existing_videos]
                except Exception as db_error:
                    message.append({"db_query_error_videos": str(db_error)})

                try:
                    self.es.update(index=self.elastic_index, id=listing.id, body={"doc": {"videos": current_videos}})
                except Exception as es_error:
                    logger.error(f"Elasticsearch video update error for listing {listing.id}: {es_error}")
                    message.append({"elasticsearch_video_update_error": str(es_error)})

                return Response({'message': 'Listing posted successfully!', 'data': serializer.data, **({'errors': message} if message else {})}, status=status.HTTP_201_CREATED)

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

    def clean_number(self, value):
        # Remove any non-numeric characters except for decimal points and hyphens (for negative numbers)
        cleaned_value = ''.join([char for char in value if char.isdigit() or char in ['.', '-']])
        if cleaned_value.count('.') > 1:
            raise ValueError(f"Invalid number format: {value}")
        return cleaned_value

    def get_or_default(self, request, key, default):
        value = request.data.get(key, default)
        return value if value not in [None, ""] else default
    
    def put(self, request, pk, format=None):
        message = []
        try:
            # Retrieve the existing listing from the Django model
            try:
                listing = Listing.objects.get(pk=pk)
            except Listing.DoesNotExist:
                return Response({"error": "Listing not found."}, status=status.HTTP_404_NOT_FOUND)

            # Extract and validate latitude and longitude
            latitude_str = self.get_or_default(request, 'latitude', listing.latitude)
            longitude_str = self.get_or_default(request, 'longitude', listing.longitude)

            try:
                latitude = latitude_str if isinstance(latitude_str, float) else float(self.clean_number(latitude_str))
                longitude = longitude_str if isinstance(longitude_str, float) else float(self.clean_number(longitude_str))
                if not -90 <= latitude <= 90:
                    raise ValueError(f"Latitude must be between -90 and 90. Got {latitude}.")
                if not -180 <= longitude <= 180:
                    raise ValueError(f"Longitude must be between -180 and 180. Got {longitude}.")
            except ValueError as ve:
                return Response({"error": str(ve)}, status=status.HTTP_400_BAD_REQUEST)

            # Parse media_link
            media_link = self.get_or_default(request, 'media_link', listing.media_link)
            if isinstance(media_link, str):
                try:
                    media_link = json.loads(media_link)
                except json.JSONDecodeError:
                    return Response({"error": "Invalid format for media_link. It must be a valid JSON object."},
                                    status=status.HTTP_400_BAD_REQUEST)

            # Validate and fetch facilities
            facilities = request.data.get("facilities", None)
            valid_facilities_data = []
            if facilities:
                try:
                    facility_ids = json.loads(facilities)
                    if not isinstance(facility_ids, list):
                        raise ValueError("Facilities must be a list of IDs.")
                except (ValueError, TypeError):
                    return Response({"error": "Facilities must be a valid list of IDs."}, status=status.HTTP_400_BAD_REQUEST)

                # Fetch valid facilities (both IDs and names)
                valid_facilities = Listing_faclities.objects.filter(id__in=facility_ids).values("id", "facility_name", "description", "image")
                valid_facilities_data = [
                    {
                        "name": f["facility_name"],
                        "description": f["description"],
                        "image": f["image"]
                    }
                    for f in valid_facilities
                ]

            # Prepare data for updating the Django model
            request_data = {
                'name': self.get_or_default(request, 'name', listing.name),
                'category': self.get_or_default(request, 'category', listing.category),
                'latitude': latitude,
                'longitude': longitude,
                'display_name': self.get_or_default(request, 'display_name', listing.display_name),
                'description': self.get_or_default(request, 'description', listing.description),
                'media_link': media_link,
                'contact_name': self.get_or_default(request, 'contact_name', listing.contact_name),
                'contact_number': self.get_or_default(request, 'contact_number', listing.contact_number),
                'place': self.get_or_default(request, 'place', listing.place),
                'toloo_assured': self.get_or_default(request, 'toloo_assured', listing.toloo_assured),
                'email': self.get_or_default(request, 'email', listing.email),
                'facilities': valid_facilities_data
            }

            serializer = ListingSerializer(listing, data=request_data, partial=True)
            if serializer.is_valid():
                listing = serializer.save()

                # Update Elasticsearch
                es_data = {
                    'name': listing.name,
                    'category': listing.category if listing.category else None,
                    'location': {
                        'lat': listing.latitude,
                        'lon': listing.longitude
                    },
                    'display_name': listing.display_name,
                    'description': listing.description,
                    'media_link': listing.media_link,
                    'contact_name': listing.contact_name,
                    'contact_number': listing.contact_number,
                    'status': listing.status,
                    'place': listing.place,
                    'toloo_assured': listing.toloo_assured,
                    'facilities': valid_facilities_data  # Store facilities in ES
                }
                self.es.index(index=self.elastic_index, id=listing.id, body=es_data)

                # Handle image deletions
                images_to_delete = request.data.get("images_to_delete", "")
                if isinstance(images_to_delete, str):
                    images_to_delete = [int(id.strip()) for id in images_to_delete.split(",") if id.strip().isdigit()]

                if isinstance(images_to_delete, list):
                    # try:
                    #     # Retrieve the document from Elasticsearch
                    #     document = self.es.get(index=self.elastic_index, id=listing.id)
                    #     if document['found']:
                    #         current_images = document['_source'].get('images', [])
                    #         updated_images = [img for img in current_images if img['id'] not in images_to_delete]

                    #         # Update the document in Elasticsearch
                    #         self.es.update(index=self.elastic_index, id=listing.id, body={"doc": {"images": updated_images}})
                    #     else:
                    #         message.append({"elasticsearch_error": "Document not found in Elasticsearch."})

                    # except Exception as es_error:
                    #     message.append({"elasticsearch_error": str(es_error)})
                    try:
                        # Ensure the images are deleted from the database
                        deleted_count, _ = Listing_images.objects.filter(id__in=images_to_delete, listing=listing).delete()

                        if deleted_count == 0:
                            message.append({"database_error": "No images were deleted from the database. Verify image IDs."})
                    except Exception as db_error:
                        message.append({"database_error": str(db_error)})

                print(f"Images deleted from Elasticsearch and DB: {images_to_delete}")

                current_images = []

                try:
                    existing_images = Listing_images.objects.filter(listing=listing.id).values("id", "image")
                    current_images = [{"id": img["id"], "image": img["image"]} for img in existing_images]
                except Exception as db_error:
                    logger.error(f"Error fetching images from DB for listing {listing.id}: {db_error}")
                    message.append({"db_query_error": str(db_error)})

                # Add new images
                images = request.FILES.getlist('image')
                if images:
                    for image in images:
                        s3_response = s3_upload(image, file_folder='listing_image', file_name_prefix=listing.id)
                        if "s3_url" in s3_response:
                            image_data = {
                                'listing': listing.id,
                                'image': s3_response['s3_url']
                            }
                            imageserializer = ListingImagePostSerializer(data=image_data)
                            if imageserializer.is_valid():
                                image_instance = imageserializer.save()

                                # Append new image with its ID and S3 URL to current_images
                                new_image = {
                                    "id": image_instance.id,
                                    "image": s3_response["s3_url"]
                                }
                                current_images.append(new_image)

                            else:
                                logger.error(f"Image serializer error for listing {listing.id}: {imageserializer.errors}")
                                message.append({"image_err": imageserializer.errors})
                        else:
                            logger.error(f"S3 upload error for image in listing {listing.id}: {s3_response.get('error', 'Unknown error during S3 upload')}")
                            message.append({"s3_upload_error": s3_response.get("error", "Unknown error during S3 upload")})

                try:
                    self.es.update(index=self.elastic_index, id=listing.id, body={"doc": {"images": current_images}})
                except Exception as es_error:
                    logger.error(f"Elasticsearch image update error for listing {listing.id}: {es_error}")
                    message.append({"elasticsearch_image_update_error": str(es_error)})
                
                #Save listing videos
                videos = request.FILES.getlist('videos')
                try:
                    for video in videos:
                        s3_response = s3_upload(video, file_folder='listing_video', file_name_prefix=listing.id)
                        if "s3_url" in s3_response:
                            video_data = {
                                'listing': listing.id,
                                'video': s3_response['s3_url']
                            }
                            videoserializer = ListingVideoPostSerializer(data=video_data)
                            if videoserializer.is_valid():
                                videoserializer.save()
                            else:
                                logger.error(f"Video upload error for listing {listing.id}: {videoserializer.errors}")
                                message.append({"video_err": videoserializer.errors})
                except Exception as e:
                    logger.error(f"Video upload error for listing {listing.id}: {e}")
                    message.append({"video_upload_error": str(e)})

                # Fetch all videos for the listing and update Elasticsearch
                current_videos = []
                try:
                    existing_videos = Listing_videos.objects.filter(listing=listing.id).values("id", "video")
                    current_videos = [{"id": vid["id"], "video": vid["video"]} for vid in existing_videos]
                except Exception as db_error:
                    logger.error(f"Error fetching videos from DB for listing {listing.id}: {db_error}")
                    message.append({"db_query_error_videos": str(db_error)})

                try:
                    self.es.update(index=self.elastic_index, id=listing.id, body={"doc": {"videos": current_videos}})
                except Exception as es_error:
                    logger.error(f"Elasticsearch video update error for listing {listing.id}: {es_error}")
                    message.append({"elasticsearch_video_update_error": str(es_error)})

                return Response({'message': 'Listing updated successfully!', 'data': serializer.data, **({'errors': message} if message else {})}, status=status.HTTP_200_OK)

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



    def delete(self, request, pk):
        try:
            user_role = request.user.role
            print(user_role)
            if user_role != 4:
                return Response({'message':'You are not authorized to use this function.'},status= status.HTTP_401_UNAUTHORIZED)

            listing = Listing.objects.filter(pk=pk).first()
            if not listing:
                return Response({'error': 'Listing not found.'}, status=status.HTTP_404_NOT_FOUND)

            listing_user_id = listing.listing_user_id

            listing.delete()

            self.es.delete(index=self.elastic_index, id=pk, ignore=[404])

            User.objects.filter(id=listing_user_id).delete()

            return Response({'message': 'Listing deleted successfully!'}, status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.error(f"Error occurred in ListingAPIView DELETE: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ListingSingleFetchAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, pk):
        try:
            listings = Listing.objects.get(pk=pk)
            serializer = ListingSerializer(listings)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        
class ListingFilterAPIView(APIView):
    # permission_classes = [IsAuthenticated]thesnthesn

    def get(self, request, format=None):
        try:
            latitude = request.GET.get('latitude')
            longitude = request.GET.get('longitude')
            radius = request.GET.get('radius')
            category = request.GET.get('category')
            
            if not latitude or not longitude or not radius or not category:
                return Response({"error": "Latitude, longitude, radius and category are required parameters."}, status=400)

            latitude = float(latitude)
            longitude = float(longitude)
            radius = float(radius)
            if category == "0":
               
                listings = Listing.objects.filter(is_deleted=False)
            else:
                listings = Listing.objects.filter(is_deleted=False, category=category)

            filtered_listings = []

            for listing in listings:
                
                listing_location = (listing.latitude, listing.longitude)
                user_location = (latitude, longitude)
                distance = geodesic(listing_location, user_location).km
                travlounge_location = ("10.78479180904762", "76.65545109723469")
                travlounge_distance = geodesic(travlounge_location, user_location).km

                
                if distance <= radius:
                    # Fetch valid offers for the listing
                    valid_offers = Listing_offer.objects.filter(
                        listing=listing,
                        valid_start__lte=date.today(),
                        valid_end__gte=date.today(),
                        status='Active',
                        is_deleted='False'

                    )
                    # Serialize listing and related valid offers
                    if valid_offers.exists():
                        filtered_listings.append({
                            'listing': ListingFilterSerializer(listing).data,
                            'offers': ListingOfferFilterSerializer(valid_offers, many=True).data,
                            'distance': travlounge_distance
                        })
                    else:
                        filtered_listings.append({
                            'listing': ListingFilterSerializer(listing).data,
                            'offers': [],
                            'distance': travlounge_distance
                        })

            return Response(filtered_listings, status=200)
        except Exception as e:
            return Response({"error": str(e)}, status=500)

    

class ListingOfferAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            offer = Listing_offer.objects.filter(listing=pk)
            serializer = ListingOfferSerializer(offer, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request, format=None):
        try:
            serializer = ListingOfferSerializer(data=request.data)
            if serializer.is_valid():
                offer = serializer.save()

                # save images
                images = request.FILES.getlist('offer_image')

                for image in images:
                    image_data = {
                        'listing_offer': offer.id,  # Pass the ID of the related listing
                        'image': image
                    }
                    
                    imageserializer = ListingOfferImagePostSerializer(data=image_data)
                    
                    if imageserializer.is_valid():
                        imageserializer.save()
                    else:
                        return Response({"message":"offer added","error":imageserializer.errors}, status=status.HTTP_400_BAD_REQUEST)
                    
                return Response({'message': 'Listing offer posted successfully!', 'data': serializer.data}, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request,pk):
        try:
            offer = Listing_offer.objects.get(pk=pk)
            serializer = ListingOfferSerializer(offer, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response({'message': 'listing offer updated successfully!'}, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error occurred in ListingOfferAPIView PUT: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)   
    
    def delete(self, request, pk):
        try:
            offer = Listing_offer.objects.filter(pk=pk).update(is_deleted=True)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.error(f"Error occurred in ListingOfferAPIView DELETE: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class ListingOfferimageAPIView(APIView):
    def delete(self,request,pk):
        try:
            offer_image = Listing_offer_images.objects.filter(pk=pk).delete()
            return Response({'message': 'Offer image deleted successfully!'}, status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.error(f"Error occured in ListingOfferimageAPIView DELETE: {e}")
            return Response({"error":"An error occured","message":f"{e}"})
        
class ListingVideoAPIView(APIView):
    def delete(self,request,pk):
        try:
            vid = Listing_videos.objects.filter(pk=pk).delete()
            return Response({'message': 'Video deleted successfully!'}, status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.error(f"Error occured in ListingVideoAPIView DELETE: {e}")
            return Response({"error":"An error occured","message":f"{e}"})

class ListingSearchAPIView(APIView):
    def get(self, request, format=None):
        try:
            search = ListingDocument.search()
            response = search.execute()
            results = response.to_dict()['hits']['hits']
            data = []
            for hit in results:
                source = hit['_source']
                source['id'] = str(hit['_id'])
                # Split location into latitude and longitude
                if 'location' in source:
                    source['latitude'] = source['location']['lat']
                    source['longitude'] = source['location']['lon']
                data.append(source)

            serializer = ListingElasticSerializer(data, many=True)
            # print(len(serializer.data))
            return Response(serializer.data, status=status.HTTP_200_OK)

        except NotFoundError as e:
            logger.error(f"Error (NotFound) in ListingSearchAPIView GET: {e}")
            return Response({"error": "Elasticsearch index 'listings' not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error occured in ListingSearchAPIView GET: {e}")
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

import time
class ElasticSearchFilterAPIView(APIView):
    
    elastic_index = settings.ELASTICSEARCH_INDEX

    def get(self, request, format=None):
        try:
            start_time = time.time()
            # Get query parameters
            curr_lat = request.GET.get('curr_lat')
            curr_lon = request.GET.get('curr_lon')
            radius = request.GET.get('radius', 5)

            lat_from = request.GET.get('lat_from')
            lon_from = request.GET.get('lon_from')
            lat_to = request.GET.get('lat_to')
            lon_to = request.GET.get('lon_to')

            queries = []
            if curr_lat and curr_lon:  # Case 1
                curr_lat = float(curr_lat)
                curr_lon = float(curr_lon)
                radius = float(radius)

                radius_meters = (radius * 1000) / 2

                query = {
                    "geo_distance": {
                        "distance": f"{radius_meters}m",
                        "location": {
                            "lat": curr_lat,
                            "lon": curr_lon
                        }
                    }
                }
                queries.append(query)

            elif lat_from and lon_from and lat_to and lon_to:  # Case 2
                lat_from = float(lat_from)
                lon_from = float(lon_from)
                lat_to = float(lat_to)
                lon_to = float(lon_to)

                distance_km = geodesic((lat_from, lon_from), (lat_to, lon_to)).km
                radius_meters = (distance_km * 1000) / 2  # Convert km to meters and get half of it

                query1 = {
                    "geo_distance": {
                        "distance": f"{radius_meters}m",
                        "location": {
                            "lat": lat_from,
                            "lon": lon_from
                        }
                    }
                }
                queries.append(query1)

                query2 = {
                    "geo_distance": {
                        "distance": f"{radius_meters}m",
                        "location": {
                            "lat": lat_to,
                            "lon": lon_to
                        }
                    }
                }
                queries.append(query2)

            else:
                # If neither set of parameters is provided
                raise ValidationError("Missing or incomplete query parameters.")

            es = Elasticsearch(
                hosts=['http://95.217.186.74:9200'],
                http_auth=(settings.ELASTICSEARCH_USER, settings.ELASTICSEARCH_PASSWORD),
            )

            # Construct the 'Bool' query with the 'should' clause
            query_body = {
                "query": {
                    "bool": {
                        "should": queries,
                        "minimum_should_match": 1
                    }
                },
                "size": 50  # Limit the number of results
            }

            # Execute the combined search query
            response = es.search(index=self.elastic_index, body=query_body)

            elastic_end_time = time.time()
            elastic_time = time.strftime("%M:%S", time.gmtime(elastic_end_time - start_time))

            results = []
            cat_ids = []
            listing_ids = []
            # print("Elasticsearch response:", response)

            for hit in response['hits']['hits']:
                hit_id = hit['_id']
                hit_dict = hit['_source']
                hit_dict['id'] = int(hit_id)

                if 'location' in hit_dict and hit_dict['location']:
                    hit_dict['latitude'] = hit_dict['location']['lat']
                    hit_dict['longitude'] = hit_dict['location']['lon']
                
                results.append(hit_dict)

                cat_id = hit_dict['category']
                # cat_ids.append(cat_id)
                if cat_id == 2:
                    hit_dict['is_sleeping_pod'] = True
                else:
                    hit_dict['is_sleeping_pod'] = False

                listing_ids.append(hit_dict['id'])

            # cat_ids = list(set(cat_ids))
            # categories = Listing_category.objects.filter(id__in=cat_ids)
            # cat_dict = {}
            # for cat in categories:
            #     cat_dict[cat.id] = cat.category_name
            

            # listing_ids = list(set(listing_ids))
            # images = Listing_images.objects.filter(listing_id__in=listing_ids)
            # listing_image_dict = {}
            # for img in images:
            #     if img.listing.id not in listing_image_dict.keys():
            #         listing_image_dict[img.listing.id] = []
            #         listing_image_dict[img.listing.id].append(img.image)
            #     else:
            #         listing_image_dict[img.listing.id].append(img.image)


            average_ratings = Review_rating.objects.filter(listing__in=listing_ids).values('listing').annotate(average_rating=Avg('rating'))
            avg_rating_dict = {}
            for rating in average_ratings:
                avg_rating_dict[rating["listing"]] = rating["average_rating"]

            final_out = []
            
            for listing in results:
                images = []
                if 'images' in listing:
                    images += [img['image'] for img in listing['images']]
                listing['images'] = images
                # listing['cat_title'] = cat_dict[listing['category']]
                # if listing['id'] in listing_image_dict.keys():
                #     listing['images'] = listing_image_dict[listing['id']]
                # else:
                #     listing['images'] = []
                if listing['id'] in avg_rating_dict.keys():
                    listing['avg_rating'] = avg_rating_dict[listing['id']]
                else:
                    listing['avg_rating'] = 0.0
                final_out.append(listing)
            # print("final\n",final_out)

            # print("Serialized input:", len(results))

            # serializer = ListingElasticFilterSerializer(data=results, many=True)
            # serializer.is_valid(raise_exception=True)

            # serialized_data = serializer.data

            end_time = time.time()
            elapsed_time = time.strftime("%M:%S", time.gmtime(end_time - start_time))
            print(f"Elastic time: {elastic_time}")
            print(f"Total time: {elapsed_time}")
            return Response(final_out, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error occurred in ElasticSearchFilterAPIView GET: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class RedeemAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, format=None):
        try:
            today = timezone.now()
            query = Listing_redeem.objects.filter(status='Unverified', created_on__lt=today)
            for hit in query:
                last_token = Listing_redeem.objects.aggregate(Max('token')).get('token__max')
                token = int(last_token)+1
                Listing_redeem.objects.filter(id=hit.id).update(token=token)
            return Response({'message': 'Token  updated successfully!'}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request, format=None):
        try:
            last_token = Listing_redeem.objects.aggregate(Max('token')).get('token__max')
            mutable = request.POST._mutable
            request.POST._mutable = True
            if last_token is None:
                request.data['token'] = '999'
            else:
                request.data['token'] = int(last_token)+1
            request.POST._mutable = mutable
            serializer = RedeemSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response({'message': 'Redeem posted successfully!', 'data': serializer.data}, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request,redeem_token):
        try:
            redeem = Listing_redeem.objects.get(token=redeem_token)
            if redeem:
                Listing_redeem.objects.filter(token=redeem_token).update(status='Verified')
                return Response({'message': 'redeem verified successfully!'}, status=status.HTTP_201_CREATED)
             
            return Response({'message': 'invalid token!'}, status=status.HTTP_400_BAD_REQUEST)
               
        except Exception as e:
            logger.error(f"Error occurred in RedeemAPIView PUT: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)   

class ListingTravloungeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        try:
            listings = Listing.objects.filter(is_deleted=False,category=4)
            serializer = ListingSerializer(listings, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ListingCategoryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        try:
            category = Listing_category.objects.all()
            serializer = ListingcategoryGetSerializer(category, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request, format=None):
        try:
            serializer = ListingcategorySerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response({'message': 'Listing category posted successfully!', 'data': serializer.data}, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ListingIDAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, format=None):
        try:
            listings = Listing.objects.filter(is_deleted=False)
            serializer = ListingIdSerializer(listings, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ListingSingleAPIView(APIView):
    # permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            listings = Listing.objects.filter(pk=pk)
            distance = ""
            # serializer = ListingFilterSerializer(listings, many=True)
            # return Response(serializer.data, status=status.HTTP_200_OK)
            user_location = (request.GET['latitude'], request.GET['longitude'])
            travlounge_location = ("10.78479180904762", "76.65545109723469")
            travlounge_distance = geodesic(travlounge_location, user_location).km


            filtered_listings = []

            for listing in listings:
                
                
                    # Fetch valid offers for the listing
                valid_offers = Listing_offer.objects.filter(
                        listing=listing,
                        valid_start__lte=date.today(),
                        valid_end__gte=date.today(),
                        status='Active',
                        is_deleted='False'

                    )
                    # Serialize listing and related valid offers
                if valid_offers.exists():
                        filtered_listings.append({
                            'listing': ListingFilterSerializer(listing).data,
                            'offers': ListingOfferFilterSerializer(valid_offers, many=True).data,
                            'distance':travlounge_distance
                        })
                else:
                        filtered_listings.append({
                            'listing': ListingFilterSerializer(listing).data,
                            'offers': [],
                            'distance':travlounge_distance

                        })

            return Response(filtered_listings, status=200)

        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class OfferRedemptionReportAPIView(APIView):
    def get(self,request,pk):
        """pk -> ID of the category to get the redemption report of."""
        try:
            redemptions = Listing_redeem.objects.filter(listing=pk,status='Verified')

            serializer = RedemptionReportSerializer(redemptions, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Listing_redeem.DoesNotExist:
            return Response({"error": "No redemptions found for the given Listing ID"}, status=status.HTTP_404_NOT_FOUND)
        
        except Exception as e:
            logger.error(f"Error fetching redemption report: {e}")
            return Response({"error": "An error occurred","data":str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class OfferImageAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            listing_id = request.GET.get('listing_id')
            
            if not listing_id:
                return Response({"error": "Listing ID is required"}, status=400)
            
            try:
                listing = Listing.objects.get(id=listing_id)
            except Listing.DoesNotExist:
                return Response({"error": "Listing not found"}, status=404)
            
            offer_images = Listing_offer_images.objects.filter(listing=listing)
            # offerimageserializer = ListingOfferImagePostSerializer(offer_images, many=True)
            offer_image_data = offer_images.values('id', 'image', 'listing')

            
            return Response({"offer_images": list(offer_image_data)}, status=200)        
        except Exception as e:
            return Response({"error": str(e)}, status=500)
        
        
    def put(self, request,pk):
        try:
            offer_images = request.FILES.getlist('image')
            
            if not pk:
                return Response({"error": "Listing ID is required"}, status=400)
            
            if not offer_images:
                return Response({"error": "No images provided for update"}, status=400)
            
            try:
                listing = Listing.objects.get(id=pk)
            except Listing.DoesNotExist:
                return Response({"error": "Listing not found"}, status=404)
            
            message = []
            for image in offer_images:
                s3_response = s3_upload(image, file_folder='listing_offer_image', file_name_prefix=listing.id)
                
                if "s3_url" in s3_response:
                    image_data = {
                        'listing': listing.id,
                        'image': s3_response['s3_url']
                    }
                    
                    offerimageserializer = ListingOfferImagePostSerializer(data=image_data)
                    
                    if offerimageserializer.is_valid():
                        offerimageserializer.save()
                        message.append({"image": image.name, "status": "updated successfully"})
                    else:
                        message.append({"image": image.name, "error": offerimageserializer.errors})
                else:
                    message.append({"image": image.name, "error": "S3 upload failed"})
            
            return Response({"message": message}, status=200)
        
        except Exception as e:
            return Response({"error": str(e)}, status=500)
        
class VideoAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            listing_id = request.GET.get('listing_id')

            if not listing_id:
                return Response({"error": "Listing ID is required"}, status=400)
            
            try:
                listing = Listing.objects.get(id=listing_id)
            except Listing.DoesNotExist:
                return Response({"error": "Listing not found"}, status=404)
                 
            videos = Listing_videos.objects.filter(listing=listing)
            video_data = videos.values('id', 'image', 'listing')

            return Response({"videos": list(video_data)}, status=200)        
        except Exception as e:
            return Response({"error": str(e)}, status=500)
        
    def put(self, request,pk):
        try:
            videos = request.FILES.getlist('video')
            
            if not pk:
                return Response({"error": "Listing ID is required"}, status=400)
            
            if not videos:
                return Response({"error": "No data provided for update"}, status=400)
            
            try:
                listing = Listing.objects.get(id=pk)
            except Listing.DoesNotExist:
                return Response({"error": "Listing not found"}, status=404)
            
            message = []
            for video in videos:
                s3_response = s3_upload(video, file_folder='listing_video', file_name_prefix=listing.id)
                
                if "s3_url" in s3_response:
                    image_data = {
                        'listing': listing.id,
                        'video': s3_response['s3_url']
                    }
                    
                    videoserializer = ListingVideoPostSerializer(data=image_data)
                    
                    if videoserializer.is_valid():
                        videoserializer.save()
                        message.append({"video": video.name, "status": "updated successfully"})
                    else:
                        message.append({"video": video.name, "error": videoserializer.errors})
                else:
                    message.append({"video": video.name, "error": "S3 upload failed"})
            
            return Response({"message": message}, status=200)
        
        except Exception as e:
            return Response({"error": str(e)}, status=500)



class FacilityUploadAPIView(APIView):

    def get(self, request, format=None):
        try:
            category = Listing_faclities.objects.all()
            serializer = ListingFacilitiesSerializer(category, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request, *args, **kwargs):
        try:
            facility_name = request.data.get('facility_name')
            description = request.data.get('description', '')

            if not facility_name:
                return Response({"error": "Facility name is required."}, status=status.HTTP_400_BAD_REQUEST)

            image = request.FILES.get('image')
            if not image:
                return Response({"error": "Facility image is required."}, status=status.HTTP_400_BAD_REQUEST)

            file_folder = 'facility_images'
            file_name_prefix = facility_name.replace(" ", "_").lower()
            s3_response = s3_upload(image, file_name_prefix=file_name_prefix, file_folder=file_folder)

            if "error" in s3_response:
                return Response({"error": s3_response["error"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            facility_data = {
                'facility_name': facility_name,
                'description': description,
                'image': s3_response['s3_url']
            }
            serializer = ListingFacilitiesSerializer(data=facility_data)
            if serializer.is_valid():
                serializer.save()
                return Response({"message": "Facility created successfully!", "data": serializer.data},
                                status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)