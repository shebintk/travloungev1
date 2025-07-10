from django.db import models

# Create your models here.
from admin_app.models import *
from listing.models import Listing, Listing_images
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError


class Subscription(BaseModel):
    package = models.ForeignKey(Package, on_delete=models.CASCADE)
    user =  models.ForeignKey(User, on_delete=models.CASCADE)
    subscribed_date = models.DateField(blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=50, default='Active')

    def __str__(self):
        # return user - package name - package price
        return f"{self.user} - {self.package.package_name} - {self.package.amount}"

class SubscriptionUsage(BaseModel):
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='usages')
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    service_type = models.ForeignKey(ServiceType, on_delete=models.CASCADE)
    used_count = models.IntegerField(default=0)

    class Meta:
        unique_together = ('subscription', 'service', 'service_type')

    def __str__(self):
        return f"{self.subscription} - {self.service.service_name} - {self.service_type.serviceType_name} - Used: {self.used_count}"
    
   
class Wallet(BaseModel):
    user =  models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=50, default='Active') 
    order_id = models.CharField(max_length=100, null=True, blank=True)
    amount = models.DecimalField(max_digits=9, decimal_places=2)
    balance = models.DecimalField(max_digits=9, decimal_places=2)
    requested_by = models.IntegerField(blank=True, null=True)
    
TRANSACTIONTYPE = ((0, "debit"), (1, "credit"))

class Wallet_transactions(BaseModel):
    user =  models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=50, default='Active') 
    amount = models.DecimalField(max_digits=9, decimal_places=2)
    balance = models.DecimalField(max_digits=9, decimal_places=2)
    transaction_type = models.IntegerField(choices=TRANSACTIONTYPE)
    requested_by = models.IntegerField(blank=True, null=True)   
    
class Otp(models.Model):
    otp = models.CharField(max_length=266)
    mobile_number = models.CharField(max_length=266)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, related_name='user_otp')
    is_verified = models.BooleanField(default=False, help_text="0=not verified, 1=verified")
    
class Event(BaseModel):
    user =  models.ForeignKey(User, on_delete=models.CASCADE)
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    serviceType = models.ForeignKey(ServiceType, on_delete=models.CASCADE)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, blank=True, null=True)
    number = models.IntegerField()
    source = models.CharField(max_length=50,blank=True, null=True)
    checkin_time = models.DateTimeField(blank=True, null=True)
    checkout_time = models.DateTimeField(blank=True, null=True)
    room_numbers = models.JSONField(blank=True, null=True)
    sleepingpod_numbers = models.JSONField(blank=True, null=True)
    hours = models.IntegerField(blank=True, null=True)
    date = models.DateField(blank=True, null=True)
    sleepingpod_package_id = models.IntegerField(blank=True, null=True)
    subscription = models.BooleanField(default=False)
    mode_of_payment = models.CharField(max_length=100,blank=True, null=True)

    

class TemporaryEvent(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    serviceType = models.ForeignKey(ServiceType, on_delete=models.CASCADE)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, blank=True, null=True)
    number = models.IntegerField()
    source = models.CharField(max_length=50, blank=True, null=True)
    date = models.DateField(blank=True, null=True)
    room_numbers = models.JSONField(blank=True, null=True)
    subscription = models.BooleanField(default=False)
    razorpay_order_id = models.CharField(max_length=255, blank=True, null=True)
    
    
RAZORPAY_STATUS = (
    ('created', 'created'),
    ('authorized', 'authorized'),
    ('captured', 'captured'),
    ('pending', 'pending'),
    ('failed', 'failed'),
)    
class Razor_pay_payment_create(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='razor_payment')
    razorpay_id = models.CharField(max_length=100, null=False, blank=False)
    razorpay_status = models.CharField(max_length=100, null=False, blank=False, choices=RAZORPAY_STATUS)
    amount = models.IntegerField(null=False, blank=False)
    package = models.ForeignKey(Package, on_delete=models.CASCADE,blank=True, null=True)
    
        
class Razor_pay_payment_history(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_payment')
    razorpay_id = models.CharField(max_length=100, null=False, blank=False)
    payment_id = models.CharField(max_length=100, null=False, blank=False)
    payment_method = models.CharField(max_length=100, null=False, blank=False)
    razorpay_status = models.CharField(max_length=100, null=False, blank=False, choices=RAZORPAY_STATUS)
    amount = models.IntegerField(null=False, blank=False)
    acc_holder_name = models.CharField(max_length=266, null=True, blank=True)
    acc_no = models.CharField(max_length=266, null=True, blank=True)
    ifsc_code = models.CharField(max_length=266, null=True, blank=True)
    upi_id = models.CharField(max_length=266, null=True, blank=True)
    
class Banner(BaseModel):
    title = models.CharField(max_length=100, null=False, blank=False)
    service = models.ForeignKey(Service, on_delete=models.CASCADE, null=True, blank=True)
    image = models.TextField(blank=True, null=True)

    def clean(self):
        url_validator = URLValidator()
        try:
            url_validator(self.image_url)
        except ValidationError:
            raise ValidationError("Invalid URL format.")
        
class AssociationBanner(BaseModel):
    title = models.CharField(max_length=100, null=False, blank=False)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, null=True, blank=True)
    image = models.TextField(blank=True, null=True)

    def clean(self):
        url_validator = URLValidator()
        try:
            url_validator(self.image_url)
        except ValidationError:
            raise ValidationError("Invalid URL format.")
      