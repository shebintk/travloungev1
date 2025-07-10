from django.urls import path
from listing.views import *
from rest_framework_simplejwt import views as jwt_views

urlpatterns = [
    path('listings/', ListingAPIView.as_view(), name='listings'), 
    path('listings-view/<int:pk>/', ListingAPIView.as_view(), name='listings-view'),  
    path('listings-single/<int:pk>/', ListingSingleFetchAPIView.as_view(), name='listings-single'),  
    path('listing-filter/', ListingFilterAPIView.as_view(), name='listing-filter'),  
    path('listing-offer/', ListingOfferAPIView.as_view(), name='listing-offer'), 
    path('listing-offer-view/<int:pk>/', ListingOfferAPIView.as_view(), name='listing-offer-view'),  
    path('listing-offer-image/<int:pk>/', ListingOfferimageAPIView.as_view(), name='listing-offer-image-delete'),
    path('elastic-search/', ListingSearchAPIView.as_view(), name='elastic-search'),
    path('elastic-search-filter/', ElasticSearchFilterAPIView.as_view(), name='elastic-search-filter'),
    path('listing-signin/', SigninAPIView.as_view(), name='listing-signin'),
    path('listing-redeem/', RedeemAPIView.as_view(), name='listing-redeem'),
    path('listing-verify-redeem/<int:redeem_token>/', RedeemAPIView.as_view(), name='listing-verify-redeem'),  
    path('listings-travlounge/', ListingTravloungeAPIView.as_view(), name='listings-travlounge'), 
    path('listings-category/', ListingCategoryAPIView.as_view(), name='listings-category'), 
    path('listings-id/', ListingIDAPIView.as_view(), name='listings-id'), 
    path('listing-single-filter/<int:pk>/', ListingSingleAPIView.as_view(), name='listing-single-filter'),
    path('listing-redemption-report/<int:pk>/',OfferRedemptionReportAPIView.as_view(), name='listing-redemption-report'),
    path('offer_image/', OfferImageAPIView.as_view(), name='offer_image'),
    path('offer_image_update/<int:pk>/', OfferImageAPIView.as_view(), name='offer_image_update'),
    path('upload-facility/', FacilityUploadAPIView.as_view(), name='upload-facility'),
    path('refresh-token-access/', jwt_views.TokenRefreshView.as_view(), name='refresh-token-access'),
    path('listing-video/<int:pk>/', ListingVideoAPIView.as_view(), name='listing-video'),
    
]