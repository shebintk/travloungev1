from django.urls import path
from contrib.existing_migtration import UserFromOtherDB
from utils.push_notifications import PushNotificationAPIView, get_csrf_token
from utils.light_connector import AllRoomOff, QrscanView, RoomUpdateView
from .views import *
from .cron import *
from .payments import BookingRefundAPIView

urlpatterns = [
    path('check-user/', CheckUser.as_view()),
    path('package-list/', PackageAPIView.as_view(), name='package-list'), 
    path('package-detail/<int:pk>/', PackageAPIView.as_view(), name='package-detail'), 
    path('services/', ServiceAPIView.as_view(), name='service-list'),
    path('service_type/',ServiceTypeAPIView.as_view(),name='service-type'),
    path('firebase-data/', RoomUpdateView.as_view(), name='firebase-data'),
    path('existing-user-migration/', UserFromOtherDB.as_view(), name='existing-user-migration'),
    path('update_toloo_rooms/', update_toloo_rooms, name='update_toloo_rooms'),
    path('qrscan/',QrscanView.as_view(),name='qrscan'),
    # path('urlcollection/',UrlcollectView.as_view(),name='urlcollection'),
    path('toloo-room-off/',AllRoomOff.as_view(),name='toloo-room-off'),
    path('push-notification/',PushNotificationAPIView.as_view(),name='push-notification'),
    path('get-csrf-token/',get_csrf_token,name='get-csrf-token'),
    path('add-banner/', BannerCreateAPIView.as_view()),
    path('assoc-banner/', AssocBannerAPIView.as_view()),
    path('booking-refund/', BookingRefundAPIView.as_view()),
]