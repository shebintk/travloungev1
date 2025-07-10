from rest_framework import serializers
from .models import * 
from listing.models import Review_Image, Review_rating, ReviewReply
from datetime import datetime

# class ItemSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Sleepingpod_item
#         fields = '__all__'

# class CheckItemSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Sleepingpod_item
#         fields = ['id','service','item', 'room_numbers']
# class PriceSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Sleepingpod_price
#         fields = '__all__'

class SleepingpodPriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = SleepingpodPrice
        fields = '__all__'

class SleepingpodimagesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sleepingpod_images
        fields = ['id','image']

class SleepingpodFacilityImagesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sleepingpodfacility_images
        fields = ['id', 'image']

class SleepingpodFacilitiesSerializer(serializers.ModelSerializer):
    facility_images = SleepingpodFacilityImagesSerializer(source='sleepingpodfacility_images_set', many=True, read_only=True)
    class Meta:
        model = Sleepingpod_facilities
        fields = ['id', 'name', 'description']    
        
class SleepingpodSerializer(serializers.ModelSerializer):
    images = SleepingpodimagesSerializer(source='Sleepingpod_images_set',many=True,read_only=True)
    facilities = SleepingpodFacilitiesSerializer(source='Sleepingpod_facilities_set', many=True, read_only=True)
    class Meta:
        model = Sleepingpod
        fields = ['id','listing','pod_name','pod_number','pod_type','pod_position','description','images','facilities']

class SleepingpodStatusSerializer(serializers.ModelSerializer):

    class Meta:
        model = Sleepingpod_status
        fields = ['listing','sleepingpod','status'] 
        
class GetSleepingpodStatusSerializer(serializers.ModelSerializer):
    sleepingpod_id = serializers.IntegerField(source='id', read_only=True)

    class Meta:
        model = Sleepingpod
        fields = ['sleepingpod_id', 'pod_name', 'pod_type', 'pod_number']

# fayas
class PodSerializer(serializers.Serializer):
    is_bath = serializers.BooleanField()
    is_restroom = serializers.BooleanField()
    type = serializers.CharField()
    number_of_pods = serializers.IntegerField()

class PodSearchSerializer(serializers.Serializer):
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    date = serializers.DateField()
    time = serializers.TimeField()
    duration = serializers.IntegerField()
    list_of_pods = PodSerializer(many=True)

# for single listing review
class UserSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = User
        fields = ['id', 'name']

class ReviewImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review_Image
        fields = ['id', 'image']

class ReviewReplySerializer(serializers.ModelSerializer):

    class Meta:
        model = ReviewReply
        fields = ['id', 'review', 'reply', 'created_on']

class ListingReviewSerializer(serializers.ModelSerializer):
    images = ReviewImageSerializer(source='review_image_set', many=True, read_only=True)
    user_details = UserSerializer(source='user', read_only=True)
    review_reply = ReviewReplySerializer(source='reviewreply_set.order_by',many=True, read_only=True)

    class Meta:
        model = Review_rating
        exclude = ['updated_on', 'is_deleted']

class AddOnSerializer(serializers.Serializer):
    type = serializers.CharField()
    quantity = serializers.IntegerField()
    price_per_unit = serializers.DecimalField(max_digits=9, decimal_places=2)
    total_price = serializers.DecimalField(max_digits=9, decimal_places=2)
    
class CustomerPodInfoSerializer(serializers.ModelSerializer):
    number_of_pods = serializers.IntegerField(source='no_of_pods')
    price = serializers.DecimalField(source='pod_price', max_digits=9, decimal_places=2)

    class Meta:
        model = CustomerPodInfo
        fields = ['pod_type', 'number_of_pods', 'duration', 'price', 'is_restroom', 'is_bath']

class BookingSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField()
    listing_id = serializers.IntegerField()
    duration = serializers.IntegerField()
    pod_info = CustomerPodInfoSerializer(many=True)
    
    add_ons = AddOnSerializer(many=True, required=False)

    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    tax = serializers.DecimalField(max_digits=10, decimal_places=2, coerce_to_string=False)
    payable_amount = serializers.DecimalField(max_digits=10, decimal_places=2, coerce_to_string=False)

    class Meta:
        model = Booking
        fields = ['user_id', 'listing_id', 'date', 'time', 'pod_info', 'duration', 'subtotal', 'discount_amount', 'tax', 'payable_amount', 'add_ons']

    def create(self, validated_data):
        pod_info_data = validated_data.pop('pod_info')  # Extract pod info
        add_ons_data = validated_data.pop('add_ons', [])
        duration = validated_data.get('duration')  # Get the duration separately

        # Create the booking instance
        booking = Booking.objects.create(**validated_data)

        # Save each pod_info with the same duration as booking
        for pod_data in pod_info_data:
            CustomerPodInfo.objects.create(
                booking=booking, 
                duration=duration,  # Use booking's duration
                **pod_data
            )
        
        # Save add-ons (requires BookingAddOn model)
        for addon in add_ons_data:
            BookingAddOn.objects.create(
                booking=booking,
                type=addon['type'],
                quantity=addon['quantity'],
                price_per_unit=addon['price_per_unit'],
                total_price=addon['total_price']
            )

        return booking

class InstoreBookingSerializer(serializers.ModelSerializer):
    user_info = serializers.JSONField()
    listing_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, coerce_to_string=False)
    duration = serializers.IntegerField()
    pod_info = CustomerPodInfoSerializer(many=True, write_only=True)

    class Meta:
        model = Booking
        fields = ['user_info', 'listing_id', 'amount', 'date', 'time', 'pod_info', 'duration']

    def validate_user_info(self, value):
        """Ensure user_info contains mobile_number, name, and gender."""
        required_fields = ['mobile_number', 'name', 'gender']
        missing_fields = [field for field in required_fields if field not in value]

        if missing_fields:
            raise serializers.ValidationError(f"Missing required fields in user_info: {', '.join(missing_fields)}")

        return value

class CustomerInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerInfo
        fields = ["booking", "id_proof_type", "id_proof_image_url","customer_name"]

    def create(self, validated_data):
        return CustomerInfo.objects.create(**validated_data)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
# fayas

class PodInfoSerializer(serializers.Serializer):
    pod_type = serializers.CharField()
    number_of_pods = serializers.IntegerField(min_value=1)
    duration = serializers.IntegerField(min_value=1)
    is_bath = serializers.BooleanField(default=False)
    is_restroom = serializers.BooleanField(default=False)

class SleepingPodPriceAvailabilitySerializer(serializers.Serializer):
    listing_id = serializers.IntegerField()
    date = serializers.DateField()
    time = serializers.CharField()
    pod_info = PodInfoSerializer(many=True)
    add_ons = serializers.DictField(required=False)

    def validate_time(self, value):
        try:
            # Try parsing HH:MM:SS
            datetime.strptime(value, '%H:%M:%S')
        except ValueError:
            try:
                # Try parsing HH:MM
                value = datetime.strptime(value, '%H:%M').strftime('%H:%M:%S')
            except ValueError:
                raise serializers.ValidationError("Invalid time format. Use HH:MM or HH:MM:SS")
        return value
    def validate_pod_info(self, value):
        if not value:
            raise serializers.ValidationError("pod_info must contain at least one item.")
        return value