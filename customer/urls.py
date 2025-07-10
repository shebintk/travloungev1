from django.urls import path
from customer.views import *
from customer.payment_gateway import *
from rest_framework_simplejwt import views as jwt_views
from utils.light_connector import TolooConfirmation

urlpatterns = [
    path('update-profile/', UserProfileUpdateAPIView.as_view(), name='update-profile'),  
    path('subscribe/', SubscriptionAPIView.as_view(), name='subscribe'),
    path('wallet/', WalletAPIView.as_view(), name='wallet'),
    # path('wallet-update/<int:user>/', WalletAPIView.as_view(), name='wallet-update'),
    path('generateOtp/', generateOtp.as_view(), name='generateOtp'),
    path('signin/', signin.as_view(), name='signin'), 
    # path('events/', EventsAPIView.as_view(), name='events'), 
    path('create_order/', create_order, name='create_order'),
    path('travlounge_webhook/', travlounge_webhook, name='travlounge_webhook'), 
    path('service_type/',ServiceTypeView.as_view(),name='service_type'),  
    path('refresh-token-access/', jwt_views.TokenRefreshView.as_view(), name='refresh-token-access'),
    path('generateqr_checking/',QrGenerateEligibleView.as_view(),name='generateqr_checking'),  
    path('dashboard/',DashboardAPIView.as_view(),name='dashboard'),  
    path('customerprofile/',CustomerProfileApiView.as_view(),name='customer-profile-detail'),
    path('usage_history/',UsageHistoryApiView.as_view(),name='usage_history'),
    path('single-servicetype/<int:pk>/',SingleServiceView.as_view(),name='single_servicetype'),
    path('available-pods/',AvailablePodView.as_view(),name='available-pods'),
    path('remaining-coupons/',RemainingCoupons.as_view(),name='remaining-coupons'),
    path('service-type-detail/<int:pk>/',ServiceTypeDetailAPIView.as_view(),name='service-type-detail'),
    path('all-available-pods/', AllAvailablePodView.as_view(), name='all-available-pods'),
    path('sleepingpod-booking/', SleepingpodBookingAPIView.as_view(), name='sleepingpod-booking'),
    path('realtime-locations/', RealtimeLocationsAPIVIEW.as_view(), name='realtime-locations'),
    path('customer-locations/', CustomerLocationsAPIVIEW.as_view(), name='customer-locations'),
    path('packages-subscrition/', PackageSubscritionAPIView.as_view(), name='packages-subscrition'),
    path('subscriptions/active/', ActiveSubscriptionAPIView.as_view(), name='active-subscriptions'),
    path('home_listing/',HomeListingAPIView.as_view(),name="homepage_listings"),
    path('rating_create/',RatingCreateAPIView.as_view(),name="create_review"),
    path('rating_edit/<int:pk>/',RatingCreateAPIView.as_view(),name="edit_review"),
    path('fetch_listing/<int:pk>/',SingleListingFetchAPIView.as_view(),name="get_single_listing"),
    path('listing_category/',ListingCategoryAPIView.as_view(),name="get_categories"),
    path('coupon-redemption/',CouponRedemption.as_view(),name="coupon_redemption"),
    path('delete-account/',UserDeleteAPIView.as_view()),
    path('wallet-subs-usage/',WalletAndSubscriptionUsageAPIView.as_view()),
    path('user-bookings/',UserBoookingAPIView.as_view(),name='user-bookings'),
    path('toloo-usage-history/',ServiceUsageHistory.as_view()),
    
    # path('pay-for-service/',TolooPay.as_view()),
    path('toloo/razorpay/order/',TolooRazorpayOrderView.as_view()),
    path('toloo/razorpay/verify/',TolooRazorpayVerifyView.as_view()),

    path('confirm-toloo-event/',TolooConfirmation.as_view()),
    path('event-detail/<int:pk>/', TolooEventDetailAPIView.as_view(), name='event-detail'),
    path('verify-otp/', OtpVerifyView.as_view(), name='otp-verify'), 
]