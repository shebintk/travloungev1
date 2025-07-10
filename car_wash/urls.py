from django.urls import path
from .views import CarTimeSlotAPIView, CarWashServiceView, CarWashBookingAPIView, CarWashOffersView,CarCategoryView

urlpatterns = [
    path('services/', CarWashServiceView.as_view(), name='carwash-service-list'),
    path('services/<int:service_id>/', CarWashServiceView.as_view(), name='carwash-service-detail'),
    path('bookings/', CarWashBookingAPIView.as_view(), name='carwash-booking'),
    path('offers/', CarWashOffersView.as_view(), name='offer-list'),
    path('offers/<int:offer_id>/', CarWashOffersView.as_view(), name='offer-detail'),
    path('car-categories/', CarCategoryView.as_view(), name='car-category-list'),
    path('car-categories/<int:category_id>/', CarCategoryView.as_view(), name='car-category-detail'),
    path('timeslot-bookings/', CarTimeSlotAPIView.as_view(), name='car-timeslot-list'),
    path('timeslot-bookings/<int:pk/', CarTimeSlotAPIView.as_view(), name='car-timeslot-list'),
]
