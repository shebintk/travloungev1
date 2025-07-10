from rest_framework import serializers
from listing.models import * 
from django.db.models import Avg
from collections import OrderedDict



class ListingImagePostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Listing_images
        fields = '__all__'

class ListingVideoPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Listing_videos
        fields = '__all__'

class ReviewReplyPostSerializer(serializers.ModelSerializer):

    class Meta:
        model = ReviewReply
        fields = '__all__'

class ReviewImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review_Image
        fields = ['id', 'image']


class UserSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = User
        fields = ['id', 'name']


class ReviewReplySerializer(serializers.ModelSerializer):

    class Meta:
        model = ReviewReply
        fields = ['id', 'review', 'reply', 'created_on']


class ReviewRatingSerializer(serializers.ModelSerializer):
    images = ReviewImageSerializer(source='review_image_set', many=True, read_only=True)
    user_details = UserSerializer(source='user', read_only=True)
    review_reply = ReviewReplySerializer(source='reviewreply_set.order_by',many=True, read_only=True)

    class Meta:
        model = Review_rating
        exclude = ['updated_on', 'is_deleted']

class ListingImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Listing_images
        fields = ['id', 'image']

class ListingVideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Listing_videos
        fields = ['id', 'video']

class ListingOfferImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Listing_offer_images
        fields = ['id', 'image', 'listing']

class ListingSerializer(serializers.ModelSerializer):
    images = ListingImageSerializer(source='listing_images_set', many=True, read_only=True)
    offer_images = ListingOfferImageSerializer(source='listing_offer_images_set', many=True, read_only=True)
    videos = ListingVideoSerializer(source='listing_videos_set',many=True,read_only=True)
    reviews = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        exclude = ['updated_on', 'is_deleted']

    def get_reviews(self, obj):
        reviews = obj.review_rating_set.filter(is_deleted=False)
        return ReviewRatingSerializer(reviews, many=True).data

    def get_average_rating(self, obj):
        reviews = obj.review_rating_set.filter(is_deleted=False)
        if reviews.exists():
            return reviews.aggregate(Avg('rating'))['rating__avg']
        return None

class ListingElasticFilterSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField()
    cat_title = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    avg_rating = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        exclude = ['updated_on', 'is_deleted', 'created_on']

    def get_cat_title(self, obj):
        category_id = obj.get('category') if isinstance(obj, dict) else getattr(obj, 'category', None)
        
        if category_id:
            try:
                category = Listing_category.objects.get(id=category_id)
                return category.category_name
            except Listing_category.DoesNotExist:
                return None
        return None
    
    def get_images(self, obj):
        listing_id = obj.get('id') if isinstance(obj, (dict, OrderedDict)) else getattr(obj, 'id', None)

        if listing_id:
            images = Listing_images.objects.filter(listing_id=listing_id)
            if images.exists():
                return [image.image for image in images]
        return []

    def get_avg_rating(self, obj):
        listing_id = obj.get('id') if isinstance(obj, (dict, OrderedDict)) else getattr(obj, 'id', None)
        
        if listing_id:
            reviews = Review_rating.objects.filter(listing_id=listing_id,is_deleted=False)
            if reviews.exists():
                return reviews.aggregate(Avg('rating'))['rating__avg']
            return None


class ListingElasticSerializer(serializers.ModelSerializer):
    id = serializers.CharField()

    class Meta:
        model = Listing
        exclude = ['updated_on', 'is_deleted', 'listing_user']


class ListingSerializerElastic(serializers.ModelSerializer):
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = '__all__'

    def get_latitude(self, obj):
        return obj['location']['lat'] if 'location' in obj else None

    def get_longitude(self, obj):
        return obj['location']['lon'] if 'location' in obj else None


class ListingFilterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Listing
        fields = ('id','contact_name','latitude','longitude','category', 'image', 'place')

class ListingIdSerializer(serializers.ModelSerializer):
    class Meta:
        model = Listing
        fields = ('id','category','latitude','longitude')

                
class ListingOfferSerializer(serializers.ModelSerializer):
    offer_images = ListingOfferImageSerializer(source='listing_offer_images_set',many=True,read_only=True)

    class Meta:
        model = Listing_offer
        fields = '__all__'

class ListingOfferImagePostSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Listing_offer_images
        fields = '__all__'

class ListingOfferFilterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Listing_offer
        fields = ('id','valid_start','valid_end','description')

class RedeemSerializer(serializers.ModelSerializer):
    token = serializers.CharField(required=False, allow_blank=True)
    class Meta:
        model = Listing_redeem
        fields = '__all__'

    
class ListingcategorySerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Listing_category
        fields = '__all__'

class ListingcategoryGetSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Listing_category
        fields = fields = ('id', 'category_name','icon')


class RedemptionReportSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.name', read_only=True)
    mobile = serializers.CharField(source='user.mobile_number', read_only=True)

    class Meta:
        model = Listing_redeem
        fields = ['id', 'user', 'token', 'mobile', 'user_name', 'listing', 'amount', 'updated_on']


class ReviewImagePostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review_Image
        fields = ['review', 'image']

class ReviewRatingPostSerializer(serializers.ModelSerializer):
    title = serializers.CharField(required=False, allow_blank=True)
    reviewText = serializers.CharField(required=False, allow_blank=True)
    images = serializers.SerializerMethodField()

    class Meta:
        model = Review_rating
        fields = ['listing', 'user', 'title', 'reviewText', 'rating', 'images']

    def get_images(self, obj):
        # Fetch associated images for the review
        images = Review_Image.objects.filter(review=obj)
        return ReviewImageSerializer(images, many=True).data

class ListingFacilitiesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Listing_faclities
        fields = ['id', 'facility_name', 'description', 'image']
