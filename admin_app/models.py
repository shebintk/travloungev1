from django.conf import settings
from django.db import models
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser, PermissionsMixin
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError

# Create your models here.
class BaseModel(models.Model):
    """Model for subclassing."""
    created_on = models.DateTimeField(auto_now_add=True, null=True)
    updated_on = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        abstract = True
        ordering = ['-created_on']  
        
class UserManager(BaseUserManager):
            
    def create_user(self, is_active=True,mobile_number=None,username=None,name=None, email=None, password=None,role=None, uid=None, gender=None, device_token=None):
        
        if not username:
            raise ValueError('User must have an username')

        user = self.model(
            email=self.normalize_email(email),
            username=username,
            name=name,
            mobile_number=mobile_number,
            is_active=is_active, 
            role=role,
            uid=uid,
            gender=gender,
            device_token=device_token
            
             
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password, email=None, name=None,role=None, uid=None,gender=None,device_token=None):
        user = self.create_user(
            email=self.normalize_email(email),
            username=username,
            password=password,
            name=name,
            role=1,
            uid=uid,
            gender=gender,
            device_token=device_token
            )
        user.is_admin = True
        user.is_active = True
        user.is_staff = True
        
        user.save(using=self._db)
        return user
    
SELECTROLE = ((1, "admin"), (2, "biller"), (3, "customer"),  (4, "listing"), (5, "vendor"))

class User(AbstractBaseUser, PermissionsMixin):
    name = models.CharField(max_length=50, blank=True, null=True)
    username = models.CharField(max_length=50, unique=True, null=True)
    email = models.EmailField(max_length=100, null=True)
    mobile_number = models.CharField(max_length=50,unique=True, null=True)
    role = models.IntegerField(choices=SELECTROLE)
    uid = models.CharField(max_length=500, unique=True, null=True)
    gender = models.CharField(max_length=100,blank=True, null=True)
    device_token = models.TextField(blank=True,null=True)
    is_admin = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)
    is_registered = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = 'username'
    
    REQUIRED_FIELDS=[]

    objects = UserManager()

    def __str__(self):
        return self.username
    class Meta:
        db_table = "user"
        
        
class UserProfile(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100,blank=True, null=True)
    state = models.CharField(max_length=100,blank=True, null=True)
    pincode = models.CharField(max_length=100,blank=True, null=True)
    country = models.CharField(max_length=100,blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    image = models.TextField(blank=True, null=True)

    def clean(self):
        url_validator = URLValidator()
        try:
            url_validator(self.image)
        except ValidationError:
            raise ValidationError("Invalid URL format.")
    
class IdProof(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    id_proof = models.FileField(upload_to='idproof')
    
class Service(BaseModel):
    service_name = models.CharField(max_length=100)
    display_name = models.CharField(max_length=100,blank=True, null=True)
    image = models.CharField(max_length=500,blank=True, null=True)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True, null=True)
    
class ServiceType(BaseModel):
    serviceType_name = models.CharField(max_length=100)
    display_name = models.CharField(max_length=100,blank=True, null=True)
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    numbers = models.JSONField(blank=True, null=True)
    types = models.CharField(max_length=100,blank=True, null=True)
    qrtype = models.CharField(max_length=100,blank=True, null=True)
    image = models.FileField(upload_to='serviceType/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    tax = models.FloatField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"ServiceType {self.id} - {self.serviceType_name} - {self.service.service_name}"
    

class Package(BaseModel):
    package_name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=9, decimal_places=2)
    days = models.IntegerField()
    months = models.IntegerField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    valid_for = models.JSONField()
    description = models.TextField(blank=True, null=True)
    display_description = models.JSONField(blank=True, null=True)
    type = models.IntegerField(choices=((1, "subscription"), (2, "wallet")))
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    start_time = models.TimeField(blank=True, null=True)
    end_time = models.TimeField(blank=True, null=True)
    first_user_only = models.BooleanField(default=False)

    def __str__(self):
        return f"Package {self.id} - {self.package_name} - {self.amount} - {self.days} days - first_user_only: {self.first_user_only}"

SERVICE_MODE = (
    ('number', 'Number'),
    ('percentage', 'Percentage Discount'),
    ('fixed', 'Fixed Amount Discount'),
)

class PackageServices(BaseModel):
    package = models.ForeignKey(Package, related_name='package_services', on_delete=models.CASCADE)
    service = models.ForeignKey('Service', on_delete=models.CASCADE)
    serviceType = models.JSONField(null=True, blank=True)
    number = models.IntegerField(null=True, blank=True)
    sleepingpod_package_id = models.JSONField(blank=True, null=True)
    mode = models.CharField(max_length=20, choices=SERVICE_MODE, default='number')
    discount_value = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"PackageServices {self.id} - Package: {self.package.package_name} - Service: {self.service.service_name} - Mode: {self.mode} - Discount Value: {self.discount_value}"

class Refund(BaseModel):
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    booking_id = models.CharField(max_length=100)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    refund_id = models.CharField(max_length=255)
    payment_id = models.CharField(max_length=255)
    status = models.CharField(max_length=50)
    response_data = models.JSONField()
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Refund {self.id} | Service: {self.service.service_name} | Booking: {self.booking_id} | Status: {self.status}"

    