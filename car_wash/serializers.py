from rest_framework import serializers

from listing.models import Listing
from .models import CarTimeSlot, CarWashService, CarWashImage, Booking, Offer, OfferImage


class CarWashImageSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = CarWashImage
        fields = ['service', 'image']


class CarWashServiceSerializer(serializers.ModelSerializer):
    images = CarWashImageSerializer(many=True, read_only=True)

    class Meta:
        model = CarWashService
        fields = ['id', 'listing', 'name', 'category', 'car_category_ids', 'price', 
                  'duration', 'description', 'status', 'images']
        
# class CarTimeSlotSerializer(serializers.ModelSerializer): 
#     class Meta:
#         model = CarTimeSlot
#         fields = ['id', 'start_time', 'end_time', 'listing', 'slot_capacity']

class CarTimeSlotSerializer(serializers.ModelSerializer): 
    class Meta:
        model = CarTimeSlot
        fields = ['id', 'start_time', 'end_time', 'listing', 'slot_capacity']
        read_only_fields = ['listing']

    def create(self, validated_data):
        request = self.context.get('request')
        listing = Listing.objects.filter(listing_user=request.user).first()
        if not listing:
            raise serializers.ValidationError({"listing": "Listing not found for this user."})

        validated_data['listing'] = listing
        return super().create(validated_data)

class CarWashBookingSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField()
    service_id = serializers.IntegerField()
    listing_id = serializers.IntegerField()
    slot_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    date = serializers.DateField()
    vehicle_number = serializers.CharField(max_length=20)
    vehicle_type = serializers.CharField(max_length=50)

    class Meta:
        model = Booking
        fields = [
            'user_id', 'service_id', 'listing_id', 'slot_id', 'amount', 'date', 'vehicle_number', 'vehicle_type'
        ]


class OfferImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfferImage
        fields = '__all__'

class GetOfferImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfferImage
        fields = ['id', 'image', 'offer']

class OfferSerializer(serializers.ModelSerializer):
    images = GetOfferImageSerializer(many=True, read_only=True)

    class Meta:
        model = Offer
        fields = '__all__'
