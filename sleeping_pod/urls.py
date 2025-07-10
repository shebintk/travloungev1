from django.urls import path
from .views import *
from .payments import *

urlpatterns = [
# path('sleepingpod-list/', SleepingpodAPIView.as_view(), name='sleepingpod-list'),
# path('sleepingpod-item/', SleepingpodItemAPIView.as_view(), name='sleepingpod-item'),
# path('sleepingpod-price/', SleepingpodPriceAPIView.as_view(), name='sleepingpod-price'),

path('sleepingpods/',SleepingpodAPIView.as_view(),name='sleepingpods'),
path('sleepingpod-status/<int:pod_id>/',SleepingpodStatusUpdateView.as_view(),name='sleepingpod-status'),
path('sleeping_pod_availability_price/', SleepingPodPriceAvailability.as_view(), name='sleepingpod-price-availablity'),
path('sleepingpods-bookings/',BookingAPIView.as_view(),name='sleepingpods-bookings'),
path('active-pods/', ActivePodsAPIView.as_view(), name='active_pods'),
path('sleepingpod-price/', SleepingpodPriceView.as_view(), name='add-sleepingpod-price'),
path('update-sleepingpod-price/<int:pk>/', SleepingpodPriceView.as_view()),
path('booking-details/<int:booking_id>/',BookingDetialsAPIView.as_view(),name='booking-details'),
path('booking-cancel/',BookingCancelAPIView.as_view(),name='booking-cancel'),
path('booking-report/',BookingReportAPIView.as_view(),name='booking-report'),


# fayas
path('sleeping-pods/search/', SleepingPodSearchAPIView.as_view(), name='sleeping_pod_search'),

path('instore-booking/', InstoreBookingAPI.as_view(), name='instore_booking'),

path('booking-payment/', BookingPaymentAPIView.as_view(), name='booking_payment'),
path('booking/<int:booking_id>/upload-id-proof/', UploadIDProofAPIView.as_view(), name='upload_id_proof'),
path('booking/<int:booking_id>/update-status/', UpdateBookingStatusAPIView.as_view(), name='update_booking_status'),
path('reservation-reassign/', ReassignPodAPIView.as_view(), name='reassign_pod'),
path('get-razorpay-id/<int:booking_id>/', GetRazorpayID.as_view(), name='retry_payment'),

# fayas
path('sleepingpods/<int:pk>/',SleepingpodAPIView.as_view(),name='sleepingpods'),

]