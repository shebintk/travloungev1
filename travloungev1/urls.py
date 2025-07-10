"""travloungev1 URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include
from django.conf.urls.static import static
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from utils.razorpay.razorpay_webhook_api import RazorpayWebhookAPIView  # Import from utils

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/admin_app/',include('admin_app.urls')),
    path('api/v1/customer/',include('customer.urls')),
    path('api/v1/billing/',include('billing.urls')),
    path('api/v1/store_admin/',include('store_admin.urls')),
    path('api/v1/sleeping_pod/',include('sleeping_pod.urls')),
    path('api/v1/listing/',include('listing.urls')),
    path('api/v1/vendor/',include('vendor.urls')),   
    path('api/v1/car_wash/',include('car_wash.urls')), 
    
    path("api/v1/razorpay-webhook/", csrf_exempt(RazorpayWebhookAPIView.as_view())),  # Directly call class-based view

    
    
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
