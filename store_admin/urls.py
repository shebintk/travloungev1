from django.urls import path
from .views import *


urlpatterns = [
     path('event-list/', EventsAPIView.as_view(), name='event-list'),
     path('UserIdCheck/',UserIdView.as_view(),name='UserIdCheck'), 
     path('service-list/', ServiceAPIView.as_view(), name='service-list'),
     path('service-redeem/', RedeemAPIView.as_view(), name='redeem-list'),

   
]