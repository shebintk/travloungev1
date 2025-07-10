from django.db import models
from django.db.models import Max
# Create your models here.
from admin_app.models import BaseModel,User
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError

class Listing_category(BaseModel):
    category_name = models.CharField(max_length=100)
    icon = models.FileField(upload_to='listing_category_icon',blank=True,null=True)
    
class Listing_faclities(BaseModel):
    facility_name = models.CharField(max_length=100)
    description = models.TextField(blank=True,null=True)
    image = models.TextField(blank=True,null=True)

    def clean(self):
        if self.image:
            url_validator = URLValidator()
            try:
                url_validator(self.image)
            except ValidationError:
                raise ValidationError({"image": "Invalid URL format."})


class Listing(BaseModel):
    listing_user = models.ForeignKey(User,on_delete=models.CASCADE,null=True,blank=True)
    name = models.CharField(max_length=100)
    category =  models.IntegerField()
    email = models.CharField(max_length=100,blank=True,null=True)
    # image = models.FileField(upload_to='image', blank=True, null=True)
    latitude = models.FloatField(max_length=50)
    longitude = models.FloatField(max_length=50) 
    status = models.CharField(max_length=50, default='Active')
    remarks = models.TextField(blank=True, null=True)
    display_name = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    media_link = models.JSONField(blank=True, null=True)
    contact_name = models.CharField(max_length=100, blank=True, null=True)
    contact_number = models.CharField(max_length=100, blank=True, null=True)
    place = models.CharField(max_length=100, blank=True, null=True)
    toloo_assured = models.BooleanField(default=False)
    facilities = models.JSONField(blank=True, null=True, default=list)  

class Listing_images(BaseModel):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE)
    image = models.TextField(blank=True, null=True)

    def clean(self):
        if self.image:
            url_validator = URLValidator()
            try:
                url_validator(self.image)
            except ValidationError:
                raise ValidationError({"image": "Invalid URL format."})
            
class Listing_videos(BaseModel):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE)
    video = models.TextField(blank=True, null=True)
    
    def clean(self):
        if self.image:
            url_validator = URLValidator()
            try:
                url_validator(self.video)
            except ValidationError:
                raise ValidationError({"video": "Invalid URL format."})

class Listing_offer(BaseModel):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE)
    valid_start =  models.DateField(blank=True, null=True)
    valid_end = models.DateField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=50, default='Active')

class Listing_offer_images(BaseModel):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE) #listing_offer changed to listing for now
    image = models.TextField(blank=True, null=True)

    def clean(self):
        if self.image:
            url_validator = URLValidator()
            try:
                url_validator(self.image)
            except ValidationError:
                raise ValidationError({"image": "Invalid URL format."})
   
class Listing_redeem(BaseModel):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE)
    # offer = models.ForeignKey(Listing_offer, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.IntegerField(unique=True)
    amount =  models.DecimalField(max_digits=9, decimal_places=2, default=0.00)
    status = models.CharField(max_length=50, default='Unverified')

class Review_rating(BaseModel):
    listing = models.ForeignKey(Listing,on_delete=models.CASCADE)
    user = models.ForeignKey(User,on_delete=models.CASCADE)
    title = models.CharField(max_length=100,blank=True)
    reviewText = models.TextField(max_length=500,blank=True)
    rating = models.FloatField()

class Review_Image(BaseModel): #review_image
    review = models.ForeignKey(Review_rating,on_delete=models.CASCADE)
    image = models.TextField(blank=True, null=True)

    def clean(self):
        if self.image:
            url_validator = URLValidator()
            try:
                url_validator(self.image)
            except ValidationError:
                raise ValidationError({"image": "Invalid URL format."})
    
class ReviewReply(BaseModel):
    review = models.ForeignKey(Review_rating,on_delete=models.CASCADE)
    reply = models.TextField(max_length=500)

# bath constant
class ListingConstant(BaseModel):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE)
    price_per_bath =  models.DecimalField(max_digits=9, decimal_places=2, default=0.00)
