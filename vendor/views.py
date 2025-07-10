from django.shortcuts import get_object_or_404, render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
import logging
from datetime import datetime, timedelta, date
from django.contrib.auth import authenticate, login
from rest_framework.permissions import IsAuthenticated,AllowAny
from rest_framework.parsers import JSONParser
from django.utils import timezone 
from collections import Counter,defaultdict
from django.db.models import Avg
from django.utils.dateparse import parse_date
from listing.serializers import RedemptionReportSerializer,Listing_redeem,Listing,Review_rating,ReviewRatingSerializer,ReviewReplyPostSerializer
from admin_app.models import PackageServices, UserProfile
from customer.models import Event
from utils.push_notifications import send_push_notification
from dateutil import parser
import pytz

import json
from datetime import date

from vendor.serializers import RedemptionSerializer, TolooSerializer
logger = logging.getLogger(__name__)


class SigninAPIView(APIView):
    # permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        device_token = request.data.get("device_token")
        # print(f"user--{username}--pass--{password}---")

        if not username or not password:
            return Response({"message": "Username and password are required"}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response({"message": "Incorrect username/email or password"}, status=status.HTTP_400_BAD_REQUEST)

        if getattr(user, 'role', None) != 5:
            return Response({"message": "Unauthorized role"}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            user_info = Listing.objects.filter(listing_user=user.id).first()
            if device_token:
                user.device_token = device_token
                user.save(update_fields=["device_token"])
                print("device token saved")

            refresh = RefreshToken.for_user(user)

            access_privileges = {
                1: {"service": "toloo"},
                2: {"service": "sleeping_pod"},
                6: {"service": "car_wash"},
                7: {"service": "rooms"},
            }.get(user_info.category, {"service": "listing_redeem"}) if user_info else None

            app_privileges = {
                3: {"service": "cafe"},
            }.get(user_info.category, {"service": "toloo"}) if user_info else None
            print("app access ", app_privileges, "for user:", user)
            print("access ", access_privileges, "for user:", user)

            response = {
                "access_token": str(refresh.access_token),
                "refresh_token": str(refresh),
                "status_code": status.HTTP_200_OK,
                "user": user.username,
                "role": user.role,
                "listing_id": user_info.id if user_info else None,
                "access_privileges": [access_privileges],
                "is_app_privilage": [app_privileges],
            }
            return Response(response, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error occurred in signin POST: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ResetPasswordAPIView(APIView):    
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            user = request.user  # Get user
            old_password = request.data.get('old_password')
            new_password = request.data.get('new_password')

            if not old_password or not new_password:
                return Response(
                    {"message": "Both old_password and new_password are required."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not user.check_password(old_password):
                return Response(
                    {"message": "The old password is incorrect."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            user.set_password(new_password)
            user.save()

            return Response({"message": "Password reset successfully!"}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error occurred in ResetPasswordAPIView POST: {e}")
            return Response({"error": "An error occurred while processing the request."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user

            listing_user = {}
            
            listing = get_object_or_404(Listing.objects.select_related('listing_user'), listing_user=user)
            redemptions = Listing_redeem.objects.filter(listing=listing, status='Verified')
            
            listing_user['username'] = listing.listing_user.name

            serializer_data = RedemptionReportSerializer(redemptions, many=True).data

            total_coupons_redeemed = len(serializer_data)

            amounts = [float(item["amount"]) for item in serializer_data]
            average_amount = sum(amounts) / len(amounts) if amounts else 0

            # reviews = Review_rating.objects.filter(listing=listing)
            # review_serializer = ReviewRatingSerializer(reviews, many=True).data

            return Response({"total_redeem": total_coupons_redeemed, "average_redeem_value": average_amount, "listing_user":listing_user}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error occurred in DashboardAPIView GET: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RedemptionChartAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            period = request.GET.get("period", "7")
            if period not in ["7", "1m", "3m"]:
                return Response({"error": "Invalid period. Use '7', '1m', or '3m'."}, status=status.HTTP_400_BAD_REQUEST)

            if period == "7":
                start_date = datetime.now() - timedelta(days=6)
                grouping = "day"
            elif period == "1m":
                start_date = datetime.now() - timedelta(days=30)
                grouping = "week"
            elif period == "3m":
                start_date = datetime.now() - timedelta(days=90)
                grouping = "week"

            end_date = datetime.now()

            user = request.user
            listing = get_object_or_404(Listing, listing_user=user)

            redemptions = Listing_redeem.objects.filter(
                listing=listing,
                status="Verified",
                created_on__gte=start_date,
                created_on__lte=end_date
            )

            serialized_data = RedemptionReportSerializer(redemptions, many=True).data

            if grouping == "day":
                dates = [datetime.fromisoformat(entry["updated_on"]).date() for entry in serialized_data]
                redeemed_per_day = Counter(dates)
                date_range = [
                    start_date.date() + timedelta(days=i) for i in range((end_date - start_date).days + 1)
                ]
                results = [
                    {"date": date.strftime("%d-%m-%Y"), "coupons_redeemed": redeemed_per_day.get(date, 0)}
                    for date in date_range
                ]

            elif grouping == "week":
                redeemed_per_week = defaultdict(int)
                for entry in serialized_data:
                    created_on = datetime.fromisoformat(entry["updated_on"]).date()
                    week_start = created_on - timedelta(days=created_on.weekday())
                    redeemed_per_week[week_start] += 1

                full_week_range_start = start_date.date() - timedelta(days=start_date.weekday())
                full_week_range_end = end_date.date() - timedelta(days=end_date.weekday())
                full_week_starts = [
                    full_week_range_start + timedelta(weeks=i)
                    for i in range((full_week_range_end - full_week_range_start).days // 7 + 1)
                ]

                results = [
                    {
                        "week_start": week_start.strftime("%d-%m-%Y"),
                        "week_end": (week_start + timedelta(days=6)).strftime("%d-%m-%Y"),
                        "coupons_redeemed": redeemed_per_week.get(week_start, 0)
                    }
                    for week_start in full_week_starts
                ]

            return Response({"chart": results}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error occurred in RedemptionChartAPIView GET: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CustomerReview(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            listing = get_object_or_404(Listing.objects.select_related('listing_user'), listing_user=user)

            reviews = Review_rating.objects.filter(listing=listing).select_related('user')
            user_ids = [review.user.id for review in reviews] #takes all related users with reviews
            user_profiles = UserProfile.objects.filter(user_id__in=user_ids, is_deleted=False)
            profile_images = {profile.user_id: profile.image if profile.image else None for profile in user_profiles}

            review_serializer = ReviewRatingSerializer(reviews, many=True).data

            for review in review_serializer:
                user_id = review['user_details']['id']
                review['user_details']['image'] = profile_images.get(user_id)

            return Response({"total_reviews": review_serializer}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error occurred in CustomerReview GET: {e}", exc_info=True)
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ReviewReplyAPIView(APIView):

    def post(self,request,pk):
        try:
            """
            get review id -> add reply for that
            """
            data = {
                "review":pk,
                "reply":request.data['reply']
            }
            serializer = ReviewReplyPostSerializer(data=data)
            if serializer.is_valid():
                reply = serializer.save()

            return Response({"message":"reply added", "data":serializer.data}, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Error occurred in ReviewReplyAPIView POST: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class ReviewSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            listing = get_object_or_404(Listing, listing_user=user)

            # Query all reviews for the user's listing
            reviews = Review_rating.objects.filter(listing=listing)

            # Calculate total number of reviews
            total_reviews = reviews.count()

            average_rating = reviews.aggregate(Avg('rating')).get('rating__avg', 0)

            star_counts = {
                "1_star": reviews.filter(rating=1).count(),
                "2_star": reviews.filter(rating=2).count(),
                "3_star": reviews.filter(rating=3).count(),
                "4_star": reviews.filter(rating=4).count(),
                "5_star": reviews.filter(rating=5).count(),
            }

            data = {
                "total_reviews": total_reviews,
                "average_rating": round(average_rating, 2) if average_rating else 0.0,
                "ratings_count": star_counts,
            }

            return Response(data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error occurred in ReviewSummaryAPIView GET: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CouponRedemptionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self,request,token):
        try:
            # if not token:
            #     return Response({"error":"Token is required"}, status=status.HTTP_400_BAD_REQUEST)

            try:
                Listing_redeem.objects.get(token=token, status="Unverified")
            except Listing_redeem.DoesNotExist:
                return Response({"message": "The given token is not valid"}, status=status.HTTP_404_NOT_FOUND)

            return Response({"message":"The given token is VALID"},status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error occurred in CouponRedemptionAPIView GET: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    def put(self,request,token):
        try:
            amount = request.data.get('amount')
            redeem = Listing_redeem.objects.get(token=token)
            if redeem:
                Listing_redeem.objects.filter(token=token).update(status='Verified', amount=amount, updated_on=datetime.now())
                
                user = redeem.user 
                device_token = getattr(user, 'device_token', None)
                print("@CouponRedemptionAPIView", device_token)
                #checking the device_token
                if device_token:
                    send_push_notification(
                        token=device_token,
                        title="Coupon Verified",
                        message="Your coupon is valid!",
                        status="valid",
                        listing_id=redeem.listing.id,
                        name=user.username,
                        date=str(date.today()),
                        time=str(datetime.now().strftime("%I:%M %p")),
                        service_name="Coupon Redemption",
                        service_type_name="Lounge Access"
                    )
                return Response({'message': 'redeem verified successfully!'}, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error occurred in CouponRedemptionAPIView PUT: {e}")
            return Response({"error": "An error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class OfferAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self,request):
        offer_data = [
            {
                "id": 1,
                "offer": f"10% discount",
                "description": "Valid for purchases above 500.",
            },
            {
                "id": 2,
                "offer": f"₹150/- off",
                "description": "Valid for purchases above 1000.",
            }
        ]

        return Response({"offers":offer_data}, status=status.HTTP_200_OK)

class RedemptionReport(APIView):
    permission_classes = [IsAuthenticated]

    def get(self,request):
        try:
            user = request.user
            listing = get_object_or_404(Listing, listing_user=user)

            redemptions = Listing_redeem.objects.filter(listing=listing, status='Verified')

            serializer = RedemptionReportSerializer(redemptions, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Listing_redeem.DoesNotExist:
            return Response({"error": "No redemptions found for the given Listing ID"}, status=status.HTTP_404_NOT_FOUND)
        
        except Exception as e:
            logger.error(f"Error fetching redemption report: {e}")
            return Response({"error": "An error occurred","data":str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class TolooReportAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            listing = Listing.objects.filter(listing_user=request.user).first()
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            service = request.query_params.get('service')
            
            if not listing:
                return Response({"error": "Listing not found"}, status=status.HTTP_404_NOT_FOUND)


            events = Event.objects.filter(listing=listing.pk, is_deleted=False).values_list(
                'id', 'user', 'user__name', 'user__mobile_number', 'service', 'serviceType__serviceType_name', 'serviceType__types', 'number', 'date', 'created_on', 'subscription', 'serviceType'
            )
            
            if start_date:
                start_date = parse_date(start_date)
                if not start_date:
                    return Response({'error': 'Invalid start_date format. Use YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)
                
                if end_date and end_date != "null":
                    end_date = parse_date(end_date)
                    if not end_date:
                        return Response({'error': 'Invalid end_date format. Use YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)
                    
                    if start_date > end_date:
                        return Response({'error': 'start_date cannot be greater than end_date.'}, status=status.HTTP_400_BAD_REQUEST)
                    
                    events = events.filter(date__range=[start_date, end_date])
                else:
                    events = events.filter(date__gte=start_date)
            
            # Filter by service
            if service:
                events = events.filter(service=service)

            package_services = PackageServices.objects.filter(number=1).select_related("package").values("serviceType", "package__amount")

            service_type_prices = {}
            for ps in package_services:
                if ps["serviceType"]:
                    for service_type_id in ps["serviceType"]:
                        service_type_prices[service_type_id] = ps["package__amount"]

            data = []
            for event in events:
                service_price = service_type_prices.get(event[11])
                dt = parser.isoparse(str(event[9]))  # Handles timezones like +05:30
                local_dt = dt.astimezone(pytz.timezone("Asia/Kolkata"))  
                e_data = {
                    'id': event[0],  
                    'user': event[1],  
                    'user_name': event[2],  
                    'user_mobile': event[3],  
                    'service': event[4],
                    'serviceType': ' '.join(event[5].split()[:2]),
                    'gender': 'Male' if event[6] == 'M' else 'Female' if event[6] == 'F' else '',
                    'count': event[7],
                    'date': event[8],
                    'time': local_dt.strftime("%H:%M:%S"),
                    'total_price': service_price * event[7] if service_price is not None else None,
                    'payment_type': 'Subscription' if event[10] else 'UPI',
                }
                data.append(e_data)
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error fetching TolooReportAPIView: {e}")
            return Response({"error": "An error occurred", "data": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class SubscriptionRedemptionAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            listing = Listing.objects.filter(listing_user=request.user).first()
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            
            if not listing:
                return Response({"error": "Listing not found"}, status=status.HTTP_404_NOT_FOUND)
            
            events = Event.objects.filter(listing=listing.id, subscription=True)
            
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
                    
                    events = events.filter(date__range=[start_date, end_date])
                else:
                    events = events.filter(date__gte=start_date)
                    
            serialize = RedemptionSerializer(events, many=True).data
            
            categorized_data = defaultdict(list)
            for event in serialize:
                service_name = event["service"]["service_name"]   # Assuming serializer returns service name
                event.pop("service")
                categorized_data[service_name].append(event)
            
            return Response(categorized_data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error fetching TolooReportAPIView: {e}")
            return Response({"error": "An error occurred", "data": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
                
                
                    


