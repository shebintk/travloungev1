from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from .models import *  
from customer.models import *  
from django.contrib.auth import get_user_model
from datetime import timedelta, datetime
from copy import deepcopy
from django.urls import reverse

class PackageAPIViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(mobile_number='9895623545', username='9895623545', password='9895623545',role=3)
        self.client.force_authenticate(user=self.user)
        
        self.service = Service.objects.create(service_name='Test Service', is_active=True)
        self.service_type = ServiceType.objects.create(serviceType_name='Test ServiceType', service=self.service, is_active=True)
        
        self.package_data = {
            'package_name': 'Test Package',
            'amount': 100.00,
            'days': 30,
            'is_active': True,
            'valid_for': [1],
            'description': 'Test description',
            'type': 1,
            "package_services": [
                {
                    "service": self.service.id,  
                    "serviceType": self.service_type.id,  
                    "number": 5
                },
                {
                    "service": self.service.id,  
                    "serviceType": self.service_type.id, 
                    "number": 10
                }
            ]
        }

    def test_create_package(self):
        url = '/api/v1/admin_app/package-list/'
        response = self.client.post(url, self.package_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_get_packages(self):
        url = reverse('package-list') 
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
      
   
    def test_update_package(self):
        service = Service.objects.create(service_name='Test Service', is_active=True)
        service_type = ServiceType.objects.create(serviceType_name='Test ServiceType', service=service, is_active=True)
        package_data = {
            'package_name': 'Test Package',
            'amount': 100.00,
            'days': 30,
            'is_active': True,
            'valid_for': [1],
            'description': 'Test description',
            'type': 1,
            "package_services": [
                {
                    "service": service.id,
                    "serviceType": service_type.id,
                    "number": 5
                },
                {
                    "service": service.id,
                    "serviceType": service_type.id,
                    "number": 10
                }
            ]
        }
        
        package = Package.objects.create(
            package_name=package_data['package_name'],
            amount=package_data['amount'],
            days=package_data['days'],
            is_active=package_data['is_active'],
            valid_for=package_data['valid_for'],
            description=package_data['description'],
            type=package_data['type']
        )

        
        for service_data in package_data['package_services']:
            PackageServices.objects.create(
                package=package,
                service_id=service_data['service'],
                serviceType_id=service_data['serviceType'],
                number=service_data['number']
            )

        
        url = reverse('package-detail', args=[package.id])
        updated_package_data = {
            'package_name': 'Updated Package',
            'amount': 100.00,
            'days': 30,
            'valid_for': [1],
            'type': 1,
            'package_services': [
                {
                    "service": service.id,
                    "serviceType": service_type.id,
                    "number": 15
                }
            ]
        }

        response = self.client.put(url, updated_package_data, format='json')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
        updated_package = Package.objects.get(pk=package.id)
        self.assertEqual(updated_package.package_name, 'Updated Package')
        updated_services = PackageServices.objects.filter(package=updated_package)
        self.assertEqual(len(updated_services), 1)
        self.assertEqual(updated_services[0].number, 15)
        package.delete()


class ServiceAPIViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(mobile_number='9895623545', username='9895623545', password='9895623545',role=3)
        self.client.force_authenticate(user=self.user)
    

        self.service_data = {
            'service_name': 'Test Package',
            'is_active': True,
            'description': 'Test description',}
           
def test_create_service(self):
        url = '/api/v1/admin_app/services/'
        response = self.client.post(url, self.service_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

def test_get_packages(self):
        url = reverse('services') 
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)



class ServiceTypeAPIViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(mobile_number='9895623545', username='9895623545', password='9895623545',role=3)
        self.client.force_authenticate(user=self.user)

        self.service = Service.objects.create(service_name='Test Service', is_active=True)


        self.serviceType_data = {
            'serviceType_name': 'Test Package',
            'service':1,
            'number':[1,2,3,4],
            'is_active': True,
            'description': 'Test description',}
           
def test_create_service(self):
        url = '/api/v1/admin_app/service_Type/'
        response = self.client.post(url, self.serviceType_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

def test_get_packages(self):
        url = reverse('services_type') 
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
