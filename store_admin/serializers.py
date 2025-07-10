from rest_framework import serializers
from admin_app.models import *
from .models import * 

class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ('logo',)

class ServiceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceType
        fields = '__all__'
