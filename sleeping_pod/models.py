from django.db import models
from django.db.models import Max
# Create your models here.
from admin_app.models import BaseModel,User,Service,UserProfile
from listing.models import Listing
from django.contrib.auth import get_user_model
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError


# class Sleepingpod_item(BaseModel):
#     service = models.ForeignKey(Service, on_delete=models.CASCADE)
#     item = models.CharField(max_length=50)
#     branch = models.IntegerField() 
#     sequence_number = models.CharField(max_length=50, blank=True, null=True)
#     remarks = models.TextField(blank=True, null=True)
#     room_numbers = models.JSONField(blank=True, null=True)
#     berth = models.IntegerField(blank=True, null=True),
#     description = models.TextField(blank=True, null=True)
    
POD_TYPES = (
    ('single','single'),
    ('double','double'),
    ('triple','triple')
)

POD_POSITION = (
    ('up','up'),
    ('down','down')
)
    
class Sleepingpod(BaseModel):
    listing = models.ForeignKey(Listing,on_delete=models.CASCADE)
    pod_name = models.CharField(max_length=50,blank=True,null=True)
    pod_number = models.CharField(max_length=50)
    pod_type = models.CharField(max_length=50,choices=POD_TYPES)
    pod_position = models.CharField(max_length=50,choices=POD_POSITION)
    policy = models.JSONField(blank=True, null=True)
    # price = models.DecimalField(max_digits=9, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    Is_active = models.CharField(max_length=50, default=True)
    
class Sleepingpod_images(BaseModel):
    sleepingpod = models.ForeignKey(Sleepingpod, on_delete=models.CASCADE)
    image = models.TextField(blank=True, null=True)
    
    def clean(self):
        if self.image:
            url_validator = URLValidator()
            try:
                url_validator(self.image)
            except ValidationError:
                raise ValidationError({"image": "Invalid URL format."})
    
class Sleepingpod_facilities(BaseModel):
    sleepingpod = models.ForeignKey(Sleepingpod,on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True,null=True)
    
class Sleepingpodfacility_images(BaseModel):
    sleepingpod = models.ForeignKey(Sleepingpod_facilities, on_delete=models.CASCADE)
    image = models.TextField(blank=True, null=True)
    
    def clean(self):
        if self.image:
            url_validator = URLValidator()
            try:
                url_validator(self.image)
            except ValidationError:
                raise ValidationError({"image": "Invalid URL format."})

class SleepingpodPrice(BaseModel):
    id = models.AutoField(primary_key=True)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='sleepingpod_prices')
    pod_type = models.CharField(max_length=50)
    duration = models.IntegerField()
    price = models.DecimalField(max_digits=9, decimal_places=2)
    discount_price = models.DecimalField(max_digits=9, decimal_places=2,default=0.00)
    is_bath = models.BooleanField(default=False)
    is_restroom = models.BooleanField(default=False)
    # addon_bath = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    is_active = models.CharField(max_length=50, default='True')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)

    def __str__(self):
        features = []
        if self.is_restroom:
            features.append("restroom")
        if self.is_bath:
            features.append("bath")
        
        feature_text = f' with {" & ".join(features)}' if features else ""
        
        return f"{self.pod_type.capitalize()} pod {self.id} - {self.duration}h{feature_text} - ₹{self.price}"

STATUS_CHANGE = (
    ('active','active'),
    ('inactive','inactive'),
    ('disabled','disabled'),
    ('check_in','check_in'),
    ('check_out','check_out')
)
class Sleepingpod_status(BaseModel):
    listing = models.ForeignKey(Listing,on_delete=models.CASCADE)
    sleepingpod = models.ForeignKey(Sleepingpod,on_delete=models.CASCADE)
    status = models.CharField(max_length=50, choices=STATUS_CHANGE)

User = get_user_model()

class Booking(BaseModel):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('CANCELLED', 'Cancelled'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='bookings')

    razorpay_order_id = models.CharField(max_length=255, null=True, blank=True)  # Store payment ID on success
    razorpay_payment_id = models.CharField(max_length=255, null=True, blank=True)  # Store payment ID on success
    # razorpay_payment_link = models.URLField(max_length=500, null=True, blank=True)  # Payment link storage
    razorpay_event_payload = models.JSONField(null=True, blank=True)


    payable_amount = models.DecimalField(max_digits=10, decimal_places=2)
    duration = models.IntegerField(help_text="Duration in hours")
    date = models.DateField(null=True, blank=True)
    time = models.TimeField(null=True, blank=True)

    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    booking_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='PENDING')

    def __str__(self):
        return f"Booking {self.id} - {self.user.email} ({self.booking_status})"

class BookingAddOn(models.Model):
    ADD_ON_TYPE_CHOICES = [
        ('bath', 'Bath'),
        # Future options:
        # ('restroom', 'Restroom'),
        # ('wifi', 'WiFi'),
        # ('meals', 'Meals'),
    ]

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='add_ons')
    type = models.CharField(max_length=50, choices=ADD_ON_TYPE_CHOICES)
    quantity = models.PositiveIntegerField()
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.get_type_display()} x{self.quantity} for Booking {self.booking.id}"


class CustomerPodInfo(BaseModel):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='pod_info')
    pod_type = models.CharField(max_length=50)
    no_of_pods = models.IntegerField()
    duration = models.IntegerField()
    pod_price = models.DecimalField(max_digits=9, decimal_places=2)
    is_restroom = models.BooleanField(default=False)
    is_bath = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.pod_type} - {self.no_of_pods} pods - {self.duration} hrs"
    
class CustomerInfo(BaseModel):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="customer_info")
    id_proof_type = models.CharField(max_length=100,null=True, blank=True)  # e.g., Aadhar, Passport, etc.
    id_proof_image_url = models.URLField(max_length=500)
    customer_name = models.CharField(max_length=100,null=True,blank=True)

    def __str__(self):
        return f"ID Proof for Booking {self.booking.id}"


class PodReservation(BaseModel):
    STATUS_CHOICES = [
        ('BOOKED', 'Booked'),
        ('CHECKED_IN', 'Checked In'),
        ('CHECKED_OUT', 'Checked Out'),
        ('CANCELLED', 'Cancelled'),
        ('MAINTENANCE', 'MAINTENANCE'),
    ]

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="pod_reservations")
    sleeping_pod = models.ForeignKey(Sleepingpod, on_delete=models.CASCADE)
    check_in = models.DateTimeField()
    check_out = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='BOOKED')

    def __str__(self):
        return f"Pod Reservation - {self.sleeping_pod.name} ({self.status})"


# fayas

