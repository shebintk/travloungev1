from rest_framework import serializers
from .models import *
from customer.models import Banner, AssociationBanner
from listing.models import Listing, Listing_category


# class PackageServicesSerializer(serializers.ModelSerializer):
#     service_name = serializers.ReadOnlyField(source='service.service_name')
#     servicetype_name = serializers.ReadOnlyField(source='serviceType.serviceType_name', allow_null=True)

#     class Meta:
#         model = PackageServices
#         fields = ['service', 'service_name', 'serviceType','servicetype_name', 'number']

class PackageServicesSerializer(serializers.ModelSerializer):
    service_name = serializers.ReadOnlyField(source='service.service_name')
    servicetype_names = serializers.SerializerMethodField()

    def get_servicetype_names(self, obj):
        service_type_ids = obj.serviceType
        if service_type_ids:
            service_types = ServiceType.objects.filter(id__in=service_type_ids)
            return [stype.serviceType_name for stype in service_types]
        return None

    class Meta:
        model = PackageServices
        fields = ['service', 'service_name', 'serviceType', 'servicetype_names', 'mode', 'number', 'discount_value']

# for post only
class PackageCreateSerializer(serializers.ModelSerializer):
    package_services = PackageServicesSerializer(many=True)

    class Meta:
        model = Package
        fields = [
            'package_name', 'amount', 'days', 'months', 'valid_for', 'type',
            'description', 'display_description', 'start_date', 'end_date',
            'start_time', 'end_time', 'is_active', 'first_user_only', 'package_services'
        ]

    def create(self, validated_data):
        services_data = validated_data.pop('package_services')
        package = Package.objects.create(**validated_data)
        
        for service_data in services_data:
            PackageServices.objects.create(package=package, **service_data)
        
        return package

# for get only
class PackageSerializer(serializers.ModelSerializer):
    package_services = serializers.SerializerMethodField()

    def get_package_services(self, obj):
        services = obj.package_services.filter(is_deleted=False)
        return PackageServicesSerializer(services, many=True).data

    class Meta:
        model = Package
        fields = ['id', 'package_name', 'amount', 'days','months',  'valid_for', 'type', 'description', 'display_description', 'start_date', 'end_date','start_time', 'end_time', 'is_active', 'package_services', 'first_user_only']

    def create(self, validated_data):
        package_services_data = validated_data.pop('package_services')
        package = Package.objects.create(**validated_data)
        for service_data in package_services_data:
            PackageServices.objects.create(package=package, **service_data)
        return package
    
    def update(self, instance, validated_data):
        package_services_data = validated_data.pop('package_services', None)
        instance = super().update(instance, validated_data)
        
        if package_services_data is not None:
            PackageServices.objects.filter(package=instance).delete()  
            for service_data in package_services_data:
                PackageServices.objects.create(package=instance, **service_data)
        return instance
    
class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = '__all__'

class ServiceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceType
        fields = '__all__'
       
class BannerImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Banner
        fields = '__all__'

class ListingNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = Listing
        fields = ['display_name']

class ListingSerializer(serializers.ModelSerializer):
    category = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = ['id', 'name', 'category']
    def get_category(self, obj):
        try:
            category_obj = Listing_category.objects.get(id=obj.category)
            return {
                "id": category_obj.id,
                "category_name": category_obj.category_name
            }
        except Listing_category.DoesNotExist:
            return None

class AssocBannerPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssociationBanner
        fields = '__all__'

class AssocBannerSerializer(serializers.ModelSerializer):
    title = ListingNameSerializer(source='listing', read_only=True)
    listing = ListingSerializer()
    class Meta:
        model = AssociationBanner
        fields = ['title', 'image', 'listing']

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        # fields = '__all__'
        exclude = ['password', 'last_login', 'is_superuser', 'is_active', 'date_joined', 'groups', 'user_permissions']

class RefundSerializer(serializers.ModelSerializer):
    class Meta:
        model = Refund
        fields = '__all__'