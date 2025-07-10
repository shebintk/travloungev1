from django.urls import path
from .views import *


urlpatterns = [
     path('bill-submit/', BillSubmitAPIView.as_view(), name='bill-submit'),
     path('event-report/', EventReportAPIView.as_view(), name='event-report'),
     path('event-report-export/', EventReportExportAPIView.as_view(), name='event-report-export'),
     path('user-report/', UserReportAPIView.as_view(), name='user-report'),
     path('add-wallet/', WalletAPIView.as_view(), name='add-wallet'),
     path('signup/', SignupAPIView.as_view(), name='signup'),
     path('forgot-password/', ForgotpasswordAPIView.as_view(), name='forget-password'),
     path('signin/', SigninAPIView.as_view(), name='signin'),
     path('bill-report/', BillReportAPIView.as_view(), name='bill-report'),
     path('bill-report-export/', BillReportExportAPIView.as_view(), name='bill-report-export'),
     path('refund/', RefundAPIView.as_view(), name='refund'),
     path('bill-details/<str:bill_number>/', BillSubmitAPIView.as_view(), name='bill-details'),
     path('bill-update/', BillUpdateAPIView.as_view(), name='bill-update'),
     path('user-check/',UserCheckApiView.as_view(), name='user-check'),
     path('idproof-update/<int:pk>/', UserCheckApiView.as_view(), name='idproof-update'),    
]