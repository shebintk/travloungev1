from rest_framework import serializers
from admin_app.models import *
from .models import * 


class UserProfileSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='user.name', read_only=True)
    email = serializers.CharField(source='user.email',read_only=True)

    address = serializers.CharField(required=False, allow_blank=True)
    city = serializers.CharField(required=False, allow_blank=True)
    state = serializers.CharField(required=False, allow_blank=True)
    pincode = serializers.CharField(required=False, allow_blank=True)
    dob = serializers.DateField(required=False, allow_null=True)
    class Meta:
        model = UserProfile
        exclude = ['user']
        
class SubscriptionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = '__all__'
        
class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = '__all__'    
        
class WalletTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet_transactions
        fields = '__all__'    
        
        
class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = '__all__'    
          
        
class OtpVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model=Otp
        fields = ('mobile_number','otp')
        
        
class UserSerializer(serializers.ModelSerializer):
    def __init__(self, *args, **kwargs):
        fields = kwargs.pop('fields', None)
        super(UserSerializer, self).__init__(*args, **kwargs)
        if fields is not None:
            allowed = set(fields)
            existing = set(self.fields.keys())
            for field_name in existing - allowed:
                self.fields.pop(field_name)
    class Meta:
        model=User
        fields = ('id','mobile_number','name')
        
class RazorpaySerializer(serializers.ModelSerializer):
    class Meta:
        model=Razor_pay_payment_create
        fields = "__all__"
        
class BannerServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ('id', 'service_name')
        
class BannerSerializer(serializers.ModelSerializer):
    service = BannerServiceSerializer()
    class Meta:
        model=Banner
        fields = ('image', 'service')

        
class DashboardServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model=Service
        fields = ('id','service_name','description','is_active','image')

class PackageViewSerializer(serializers.ModelSerializer):

    class Meta:
        model = Package
        fields = ('id', 'package_name', 'amount', 'description')


class PackageSubscriptionSerializer(serializers.ModelSerializer):

    class Meta:
        model = Package
        fields = ('id', 'package_name', 'amount', 'months', 'description', 'display_description')
        

class UsagehistorySerializer(serializers.ModelSerializer):
    servicetype_name = serializers.ReadOnlyField(source='serviceType.serviceType_name')
    class Meta:
        model = Event
        fields = ('created_on', 'servicetype_name')     
        
class UserImageSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = UserProfile
        fields = ('image', )     
   
class ServiceTypeImageSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.image:
            representation['image'] = instance.image.url.replace('%3A', ':/').lstrip('/')
        return representation
        
    class Meta:
        model = ServiceType
        fields = ['image']

class UserProfileallSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = UserProfile
        fields = '__all__'   

class EventServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ['id', 'service_name', 'display_name']

class EventServiceTypeSerializer(serializers.ModelSerializer):
    # service = EventServiceSerializer()

    class Meta:
        model = ServiceType
        fields = ['id', 'serviceType_name']

class EventListingImageSerializer(serializers.ModelSerializer):

    class Meta:
        model = Listing_images
        fields = ['image']

class EventListingSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = ['id', 'display_name', 'name', 'place', 'image']

    def get_image(self, obj):
        first_image = obj.listing_images_set.first()
        if first_image:
            return first_image.image
        return None


class TolooEventSerializer(serializers.ModelSerializer):
    service = EventServiceSerializer()
    serviceType = EventServiceTypeSerializer()
    listing = EventListingSerializer()

    class Meta:
        model = Event
        fields = [
            'id','service','serviceType','listing','number',
            'room_numbers','date','subscription','created_on',
        ]