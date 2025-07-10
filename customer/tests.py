from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient,APITestCase
from rest_framework import status
from .models import *  
from admin_app.models import *  
from django.contrib.auth import get_user_model
from datetime import timedelta, datetime
from copy import deepcopy
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from django.contrib.auth import authenticate

class WalletAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(mobile_number='9895623545', username='9895623545', password='9895623545', role=3)
        self.client.force_authenticate(user=self.user)
    
    def test_add_wallet(self):
        url = '/api/v1/customer/wallet/' 
        wallet_data = {
            'user': self.user.id,
            'amount': 100.00,
            'balance': 100.00,
            'status': 'Active'
        }
        response = self.client.post(url, wallet_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Wallet.objects.count(), 1)
        self.assertEqual(Wallet.objects.get().user, self.user)
    
    def test_list_wallets(self):
        Wallet.objects.create(user=self.user, amount=50.00, balance=50.00, status='Active')
        Wallet.objects.create(user=self.user, amount=75.00, balance=75.00, status='Active')
        url = '/api/v1/customer/wallet/' 
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2) 

class SubscriptionAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(mobile_number='9895623545', username='9895623545', password='9895623545', role=3)
        self.client.force_authenticate(user=self.user)
    
    def test_subscribe_package(self):
        service = Service.objects.create(service_name='Test Service', is_active=True)
        service_type = ServiceType.objects.create(serviceType_name='Test ServiceType', service=service, is_active=True)
        package = Package.objects.create(
            package_name='Test Package',
            amount=100.00,
            days=30,
            valid_for=[1],
            is_active=True,
            type=1
        )
        packageServices = PackageServices.objects.create(
            package=package,
            service=service,
            serviceType=service_type,
            number=2
           
        )
        today = datetime.today().date()
        expiry_date = today + timedelta(days=package.days)
        expiry_date_formatted = expiry_date.strftime('%Y-%m-%d')
        
        request_data = {
            'user': self.user.id,
            'expiry_date': expiry_date_formatted,
            'subscribed_date': today,
            'package': package.id
        }
        
        mutable_request_data = deepcopy(request_data)  # Create a mutable copy
        response = self.client.post('/api/v1/customer/subscribe/', mutable_request_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        subscription = Subscription.objects.filter(user=self.user.id).first()
        self.assertIsNotNone(subscription)

class GenerateOtpTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        
    def test_generate_otp(self):
        url = '/api/v1/customer/generateOtp/'
        data = {'mobile_number': '1234567898'}
        response = self.client.post(url,data=data)
        # print(response.data)
        if response.status_code == status.HTTP_400_BAD_REQUEST:
            self.assertEqual(response.data['message'], 'Incorrect Inputs')
        else:
            self.assertEqual(response.status_code, status.HTTP_200_OK)

# class EventsAPIViewTests(TestCase):
#     def setUp(self):
#         self.client = APIClient()
#         self.user = User.objects.create_user(mobile_number='9895623545', username='9895623545', password='9895623545', role=3)
#         self.client.force_authenticate(user=self.user)
        
#         self.service = Service.objects.create(service_name='Test Service', is_active=True)
#         self.service_type = ServiceType.objects.create(serviceType_name='Test ServiceType', service=self.service, is_active=True)
        
#         self.package = Package.objects.create(
#             package_name='Test Package',
#             amount=100.00,
#             days=30,
#             is_active=True,
#             valid_for=[1],
#             type=1  # Assuming 1 is for subscription type
#         )

#         self.package_service = PackageServices.objects.create(
#             package=self.package,
#             service=self.service,
#             serviceType=self.service_type,
#             number=5  # Specify the number for this service
#         )

#         self.event_data = [
#             {'service': self.service.id, 'serviceType': self.service_type.id, 'number': 5},
#             # Add more sample data for creating events
#         ]
        
#     def test_event_creation_success(self):
#         url = '/api/v1/customer/events/'
#         response = self.client.post(url, self.event_data, format='json')
#         self.assertEqual(response.status_code, status.HTTP_201_CREATED)
#         self.assertEqual(Event.objects.count(), len(self.event_data))
        
# class SignInAPITestCase(TestCase):
#     def setUp(self):
#         self.client = APIClient()
#         self.mobile_number = '1234567898'  # Adjust with a valid mobile number for testing

#     def test_signin_success(self):
#         # Access the stored OTP from GenerateOtpTestCase
#         generated_otp = tes
#         print(generated_otp)
#         url = '/api/v1/customer/signin/'
#         data = {'mobile_number': self.mobile_number, 'otp': generated_otp}
#         print(data)
#         response = self.client.post(url, data=data)

#         self.assertEqual(response.status_code, status.HTTP_200_OK)
#         self.assertIn('access_token', response.data)
#         self.assertIn('refresh_token', response.data)
        
class SigninAPITestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()
              
    def test_invalid_inputs(self):
        url = '/api/v1/customer/signin/'
        data = {
            'mobile_number': '1234567898',
            'otp': '4657',
        }
        response = self.client.post(url, data, format='json')
        print(response.data)
        if response.status_code == status.HTTP_400_BAD_REQUEST:
            self.assertEqual(response.data['message'], 'Incorrect Inputs')
        else:
            self.assertEqual(response.status_code, status.HTTP_200_OK)

