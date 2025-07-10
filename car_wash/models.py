from admin_app.models import BaseModel
from django.db import models
from listing.models import Listing
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from customer.models import User

class CarCategory(BaseModel):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class CarWashService(BaseModel):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]

    name = models.CharField(max_length=255)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="car_wash_services")
    category = models.CharField(max_length=255)
    car_category_ids = models.JSONField(default=list)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration = models.PositiveIntegerField(help_text="Duration in minutes")
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')

    def __str__(self):
        return self.name

    def get_car_categories(self):
        """Retrieve CarCategory objects based on stored IDs."""
        return CarCategory.objects.filter(id__in=self.car_category_ids)


class CarWashImage(BaseModel):
    service = models.ForeignKey(CarWashService, on_delete=models.CASCADE, related_name="images")
    image = models.TextField(blank=True, null=True)

    def clean(self):
        """Ensure the image field contains a valid URL."""
        if self.image:
            url_validator = URLValidator()
            try:
                url_validator(self.image)
            except ValidationError:
                raise ValidationError({"image": "Invalid URL format."})

class CarTimeSlot(BaseModel):
    SLOT_CHOICES = [
        ('1', '1'),
        ('2', '2'),
    ]
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE)
    start_time = models.TimeField(blank=True, null=True)
    end_time = models.TimeField(blank=True, null=True)
    slot_capacity  = models.CharField(max_length=10, choices=SLOT_CHOICES, default='1')

class Booking(BaseModel):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="car_wash_bookings")
    service = models.ForeignKey(CarWashService, on_delete=models.CASCADE)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE)
    vehicle_number = models.CharField(max_length=20)
    vehicle_type = models.CharField(max_length=50)
    date = models.DateField()
    slot = models.ForeignKey(CarTimeSlot, on_delete=models.CASCADE)
    razorpay_order_id = models.CharField(max_length=255, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=255, blank=True, null=True)
    booking_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=50, default='pending')
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Booking {self.id} - {self.user.username} - {self.service.name}"


class Offer(BaseModel):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]

    OFFER_TYPE_CHOICES = [
        ('percentage', 'Percentage'),
        ('fixed_amount', 'Fixed Amount'),
    ]

    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="listing_offers")
    name = models.CharField(max_length=255)
    offer_type = models.CharField(max_length=20, choices=OFFER_TYPE_CHOICES)
    coupon_code = models.CharField(max_length=50, unique=True)
    discount_value = models.CharField(max_length=20)
    validity_start = models.DateField()
    validity_end = models.DateField()
    applicable_services = models.JSONField(default=list)
    car_category_ids = models.JSONField(default=list)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')

    def __str__(self):
        return self.name


class OfferImage(BaseModel):
    offer = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name="images")
    image = models.TextField(blank=True, null=True)

    def clean(self):
        """Ensure the image field contains a valid URL."""
        if self.image:
            url_validator = URLValidator()
            try:
                url_validator(self.image)
            except ValidationError:
                raise ValidationError({"image": "Invalid URL format."})