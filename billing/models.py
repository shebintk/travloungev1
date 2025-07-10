from django.db import models
from admin_app.models import *

class Billreport(BaseModel):
    user =  models.ForeignKey(User, on_delete=models.CASCADE)
    bill_number = models.TextField()
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    serviceType = models.ForeignKey(ServiceType, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    rate = models.DecimalField(max_digits=9, decimal_places=2)
    total = models.DecimalField(max_digits=9, decimal_places=2)
    payment_mode = models.CharField(max_length=50) 
    split = models.TextField(blank=True, null=True) 
    room_numbers = models.JSONField(blank=True, null=True) 
    sleepingpod_numbers = models.JSONField(blank=True, null=True) 
    hours = models.IntegerField(blank=True, null=True) 
    status = models.CharField(max_length=50, default='Active')
    date = models.DateField(blank=True, null=True)
    