from collections import defaultdict
import os
from django.shortcuts import get_object_or_404, render
import pandas as pd
# from pymongo import MongoClient
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from django.http import FileResponse, HttpResponse, JsonResponse
from rest_framework.response import Response
from rest_framework import status
# from admin_app.models import *
# from customer.serializers import *
from admin_app.serializers import *
# from rest_framework_simplejwt.tokens import RefreshToken
import logging
from datetime import datetime, timedelta
from rest_framework.permissions import IsAuthenticated,AllowAny, IsAdminUser
from django.contrib.auth import authenticate
from rest_framework.parsers import JSONParser
from django.db.models import Sum
from firebase_admin import db
from django.utils import timezone
# from customer.models import Banner
from customer.models import Subscription, Wallet
from utils.s3connector import s3_upload
from utils.authentication.customPermissions import IsAdminRole


logger = logging.getLogger(__name__)


class CheckUser(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        try:
            mobile = request.query_params.get('mobile')
            email = request.query_params.get('email')
            username = request.query_params.get('username')

            if not mobile and not email and not username:
                return Response({"error": "Please provide either mobile, email, or username."}, status=status.HTTP_400_BAD_REQUEST)

            user = None
            if mobile:
                user = User.objects.filter(mobile_number=mobile).first()
            elif email:
                user = User.objects.filter(email=email).first()
            elif username:
                user = User.objects.filter(username=username).first()

            if not user:
                return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

            serializer = UserSerializer(user)

            wallet = Wallet.objects.filter(user=user, is_deleted=False).first()
            wallet_balance = wallet.balance if wallet else 0

            current_date = timezone.now().date()
            subscriptions = Subscription.objects.filter(
                user=user,
                is_deleted=False,
                expiry_date__gte=current_date,
                status='Active'
            )

            subscription_packages = [
                {
                    "package_name": sub.package.package_name,
                    "expiry_date": sub.expiry_date,
                    "description": sub.package.description,
                }
                for sub in subscriptions
            ]

            response_data = {
                "user": serializer.data,
                "wallet_balance": wallet_balance,
                "packages": subscription_packages
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error occurred in CheckUser GET: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PackageAPIView(APIView):
    # permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            packages = Package.objects.filter(is_deleted=False)
            serializer = PackageSerializer(packages, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error occurred in PackageAPIView GET: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        try:
            serializer = PackageCreateSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response({'message': 'Package and PackageServices created successfully!'}, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error occurred in PackageAPIView POST: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request, pk):
        try:
            package = Package.objects.get(pk=pk,is_deleted=False)
            serializer = PackageSerializer(package, data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response({'message': 'Package and PackageServices updated successfully!'}, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error occurred in PackageAPIView PUT: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, pk):
        try:
            Package.objects.filter(pk=pk).update(is_deleted=True)
            PackageServices.objects.filter(package=pk).update(is_deleted=True)
            return Response({'message': 'Package deleted successfully!'}, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Error occurred in PackageAPIView DELETE: {e}")
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

    def post(self, request, format=None):
        try:
            # Check if a service with the same 'service_name' already exists
            existing_service = Service.objects.filter(service_name=request.data.get('service_name'))

            if existing_service.exists():
                return Response({'message': 'Service already exists!'}, status=status.HTTP_400_BAD_REQUEST)

            serializer = ServiceSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response({'message': 'Service posted successfully!', 'data': serializer.data}, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
       

# class ServiceTypeAPIView(APIView):
#     def get(self, request, format=None):
#         try:
#             ref = db.reference("toloo")
#             service_types = ServiceType.objects.all()
#             serializer = ServiceTypeSerializer(service_types, many=True)
#             service_types_data = serializer.data
#             all_rooms_data = ref.get()
#             rooms_with_light_off = []
#             for room_key, room_data in all_rooms_data.items():
#                 if 'light' in room_data and room_data['light'] == 'off':
#                     room_number = int(room_key[4:])
#                     rooms_with_light_off.append(room_number)

#             for service_type in service_types_data:
#                 service = Service.objects.get(pk=service_type['service'], is_deleted=False)
#                 package_service = PackageServices.objects.filter(serviceType=service_type['id'],is_deleted=False,number=1).first()
#                 if package_service:
#                     package = Package.objects.filter(pk=package_service.package_id,is_deleted=False,days=1,type=2).first()
#                     service_type['service_name'] = service.service_name
#                     service_type['amount'] = package.amount if package else None
#                 else:
#                     service_type['service_name'] = service.service_name
#                     service_type['amount'] = None

#             response_data = {
#                 "service_types": service_types_data,
#                 "rooms_with_light_off": rooms_with_light_off
#             }

#             return Response(response_data, status=status.HTTP_200_OK)

#         except Exception as e:
#             return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



# class ServiceTypeAPIView(APIView):
#     def get(self, request, format=None):
#         try:
#             # Assuming you have imported the necessary modules for Firebase
#             ref = db.reference("toloo")

#             # Add this line to get service types from Firebase
#             service_types = ServiceType.objects.all()
#             serializer = ServiceTypeSerializer(service_types, many=True)
#             service_types_data = serializer.data

#             # Add this line to get data from Firebase for all rooms
#             all_rooms_data = ref.get()

#             rooms_with_light_off = []

#             # Iterate through all rooms
#             for room_key, room_data in all_rooms_data.items():
#                 # Check if the 'light' key is present and its value is "off"
#                 if 'light' in room_data and room_data['light'] == 'off':
#                     # Extract the room number from the room key (assuming the room key is in the format 'roomX')
#                     room_number = int(room_key[4:])
#                     rooms_with_light_off.append(room_number)

#             # Create a dictionary with both service types and rooms with lights off
#             response_data = {
#                 "service_types": service_types_data,
#                 "rooms_with_light_off": rooms_with_light_off
#             }

#             return Response(response_data, status=status.HTTP_200_OK)

#         except Exception as e:
#             return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
class ServiceTypeAPIView(APIView):
    def get(self, request, format=None):
        try:
            current_date = timezone.now().date()
            current_time = timezone.now().time()

            ref = db.reference("toloo")
            service_types = ServiceType.objects.all()
            serializer = ServiceTypeSerializer(service_types, many=True)
            service_types_data = serializer.data
            all_rooms_data = ref.get()
            rooms_with_light_off = []

            for room_key, room_data in all_rooms_data.items():
                if 'light' in room_data and room_data['light'] == 'off':
                    room_number = int(room_key[4:])
                    rooms_with_light_off.append(room_number)

            for service_type in service_types_data:
                service = Service.objects.get(pk=service_type['service'], is_deleted=False)
                package_service = PackageServices.objects.filter(serviceType__contains=service_type['id'], is_deleted=False, number=1).first()

                if package_service:
                    #package = Package.objects.filter(pk=package_service.package_id, is_deleted=False, days=1, type=2, start_date__gte=current_date, end_date__lte=current_date, start_time__gte=current_time, end_time__lte=current_time).first()
                    package = Package.objects.filter(pk=package_service.package_id, is_deleted=False, days=1, type=2).first()

                    service_type['service_name'] = service.service_name
                    service_type['amount'] = package.amount if package else None
                else:
                    service_type['service_name'] = service.service_name
                    service_type['amount'] = None

            response_data = {
                "service_types": service_types_data,
                "rooms_with_light_off": rooms_with_light_off
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    def post(self, request, format=None):
        try:
            # Check if a ServiceType with the same 'serviceType_name' already exists
            existing_service_type = ServiceType.objects.filter(serviceType_name=request.data.get('serviceType_name'))

            if existing_service_type.exists():
                return Response({'message': 'ServiceType already exists!'}, status=status.HTTP_400_BAD_REQUEST)

            serializer = ServiceTypeSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response({'message': 'ServiceType posted successfully!'}, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BannerCreateAPIView(APIView):
    def post(self, request):
        try:
            title = request.data.get("title")
            service_id = request.data.get("service")
            images = request.FILES.getlist('image')

            if not title or not images:
                return Response({"error": "Title and at least one image are required fields."}, status=status.HTTP_400_BAD_REQUEST)

            service = None
            if service_id:
                service = get_object_or_404(Service, id=service_id)

            created_banners = []
            for image in images:
                s3_response = s3_upload(image, file_folder='banners', file_name_prefix=service.id if service else 0)
                if "s3_url" in s3_response:
                    banner_data = {
                        "title": title,
                        "image": s3_response['s3_url'],
                        "service": service.id if service else None
                    }

                    serializer = BannerImageSerializer(data=banner_data)
                    if serializer.is_valid():
                        serializer.save()
                        created_banners.append(serializer.data)
                    else:
                        logger.error(f"Invalid banner data: {serializer.errors}")
                        return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

            return Response({"message": "Banners created successfully.", "banners": created_banners}, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error occurred in BannerCreateAPIView POST: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AssocBannerAPIView(APIView):

    def post(self, request):
        try:
            title = request.data.get("title")
            images = request.FILES.getlist('image')
            listing = request.data.get("listing")

            if not title or not images:
                return Response({"error": "Title and at least one image are required."}, status=status.HTTP_400_BAD_REQUEST)

            created_banners = []
            for image in images:
                try:
                    s3_response = s3_upload(image, file_folder='assoc_banner', file_name_prefix=listing)
                    if "s3_url" in s3_response:
                        banner_data = {
                            "title": title,
                            "image": s3_response['s3_url'],
                            "listing": listing,
                        }
                        serializer = AssocBannerPostSerializer(data=banner_data)
                        if serializer.is_valid():
                            serializer.save()
                            created_banners.append(serializer.data)
                        else:
                            logger.error(f"Invalid data for {image.name}: {serializer.errors}")
                except Exception as ex:
                    logger.error(f"Failed to upload {image.name}: {ex}")

            if created_banners:
                return Response({"message": "Banners created successfully.", "banners": created_banners}, status=status.HTTP_201_CREATED)
            else:
                return Response({"error": "No banners were created."}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Unexpected error in AssocBannerAPIView: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# class UrlcollectView(APIView):
#     def get(self,request):
#         # DB connection
#         connection_string = f"mongodb+srv://travelounge_usr:dTCexnT3mzOaoWgY@travloungecluster.jvkpuzk.mongodb.net/?retryWrites=true&w=majority"
#         client = MongoClient(connection_string)
#         db = client['travloungev1_db']
#         collection = db['travloungev1_collection']
        
#         # Retrieve data from MongoDB collection
#         data = list(collection.find({}))
        
#         # Convert ObjectId to string for serialization
#         for item in data:
#             item['_id'] = str(item['_id'])
        
#         # Organize data by date and path
#         path_counts_by_date = defaultdict(lambda: defaultdict(int))
#         for item in data:
#             date = item['timestamp'].date()
#             path_counts_by_date[date][item['path']] += 1
        
#         # Create ExcelWriter object
#         excel_file_path = 'output.xlsx'
#         writer = pd.ExcelWriter(excel_file_path, engine='xlsxwriter')
        
#         # Write each date's data to a separate sheet
#         for date, path_counts in path_counts_by_date.items():
#             df = pd.DataFrame({'Path': list(path_counts.keys()), 'Count': list(path_counts.values())})
#             df['Date'] = date.strftime('%Y-%m-%d')
#             df = df[['Date', 'Path', 'Count']]
#             df.to_excel(writer, sheet_name=date.strftime('%Y-%m-%d'), index=False)
        
#         # Save the Excel file
#         writer.close()
        
#         # Return response indicating the Excel data is generated
#         return Response({"message": "Excel data is generated"},status=status.HTTP_200_OK)

# class UrlcollectView(APIView):
#     def get(self, request):
#         # DB connection
#         connection_string = f"mongodb+srv://travelounge_usr:dTCexnT3mzOaoWgY@travloungecluster.jvkpuzk.mongodb.net/?retryWrites=true&w=majority"
#         client = MongoClient(connection_string)
#         db = client['travloungev1_db']
#         collection = db['travloungev1_collection']
        
#         # Retrieve data from MongoDB collection
#         data = list(collection.find({}))
        
#         # Convert ObjectId to string for serialization
#         for item in data:
#             item['_id'] = str(item['_id'])
        
#         # Organize data by date and path
#         path_counts_by_date = defaultdict(lambda: defaultdict(int))
#         for item in data:
#             date = item['timestamp'].date()
#             path_counts_by_date[date][item['path']] += 1
        
#         # Create ExcelWriter object
#         download_folder = os.path.expanduser('~/Downloads')
#         print(download_folder,"iiiiii")
#         excel_file_path = os.path.join(download_folder, 'output.xlsx')
#         print(excel_file_path,"aaaaaaaa")
#         writer = pd.ExcelWriter(excel_file_path, engine='xlsxwriter')
        
#         # Write each date's data to a separate sheet
#         for date, path_counts in path_counts_by_date.items():
#             df = pd.DataFrame({'Path': list(path_counts.keys()), 'Count': list(path_counts.values())})
#             df['Date'] = date.strftime('%Y-%m-%d')
#             df = df[['Date', 'Path', 'Count']]
#             df.to_excel(writer, sheet_name=date.strftime('%Y-%m-%d'), index=False)
        
#         # Save the Excel file
#         print("work start")
#         writer.close()
#         print("work end")
#         # Return the Excel file as a response for download
#         response = FileResponse(open(excel_file_path, 'rb'), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
#         response['Content-Disposition'] = 'attachment; filename="output.xlsx"'
        
#         # Delete the Excel file from the server after download
#         # os.remove(excel_file_path)
        
#         # Return a message indicating the Excel file is generated
#         return Response({"message": "Excel file is generated"}, status=200)
