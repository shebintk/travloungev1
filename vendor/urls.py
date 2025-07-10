from django.urls import path
from .views import *
from rest_framework_simplejwt import views as jwt_views


urlpatterns = [
    path('signin/', SigninAPIView.as_view(), name='vendor-signin'),
    path('reset-password/', ResetPasswordAPIView.as_view(), name='password-reset'),
    path('dashboard/', DashboardAPIView.as_view(), name='vendor-dashboard'),
    path('redemption-history-chart/',RedemptionChartAPIView.as_view(), name='redemption_history_chart'),
    path('customer_reviews/', CustomerReview.as_view(), name="customer_reviews"),
    path('review_summary/', ReviewSummaryAPIView.as_view(), name='review_summary'),
    path('coupon_redemption/<int:token>/', CouponRedemptionAPIView.as_view(), name='coupon_redemption'),
    path('offer_fetch/', OfferAPIView.as_view()),
    path('redemption_report/', RedemptionReport.as_view()),
    path('refresh-token-access/', jwt_views.TokenRefreshView.as_view(), name='refresh-token-access'),
    path('addreply/<int:pk>/',ReviewReplyAPIView.as_view()),
    
    path('toloo-report/',TolooReportAPIView.as_view(),name='toloo-report/'),
    path('subscription-redemption-history/',SubscriptionRedemptionAPIView.as_view(),name='subscription-redemption-history')
]