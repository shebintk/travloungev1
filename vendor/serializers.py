from rest_framework import serializers
from listing.serializers import * 
from customer.models import Event
from billing.serializers import ServiceSerializer, ServiceTypeSerializer

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id','name','mobile_number'] 
class TolooSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True) 
    service = ServiceSerializer(read_only=True)
    serviceType = ServiceTypeSerializer(read_only=True)
    class Meta:
        model = Event
        fields = ['id','created_on', 'user', 'service', 'serviceType','subscription']
        
class RedemptionSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True) 
    service = ServiceSerializer(read_only=True)
    serviceType = ServiceTypeSerializer(read_only=True)
    class Meta:
        model = Event
        fields = ['id','created_on', 'user', 'service', 'serviceType','subscription']
        