from rest_framework import serializers
from admin_app.models import *
from customer.models import * 
from .models import * 

class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ['service_name']

class ServiceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceType
        fields = ['serviceType_name']

class EventReportSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    service = ServiceSerializer(read_only=True)
    serviceType = ServiceTypeSerializer(read_only=True)

    class Meta:
        model = Event
        fields = ['created_on', 'user', 'checkin_time', 'checkout_time', 'service', 'serviceType', 'number']
        
class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ['subscribed_date', 'expiry_date', 'status']

class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ['status', 'amount', 'balance', 'user','requested_by']
        
class WalletTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet_transactions
        fields = ['status', 'amount', 'balance', 'user','requested_by','transaction_type']        

class UserReportSerializer(serializers.ModelSerializer):
    subscription = serializers.SerializerMethodField()
    wallet = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'date_joined', 'name', 'mobile_number', 'subscription', 'wallet']

    def get_subscription(self, user):
        subscription = Subscription.objects.filter(user=user, is_deleted=False).first()
        return SubscriptionSerializer(subscription).data if subscription else None

    def get_wallet(self, user):
        wallet = Wallet.objects.filter(user=user, is_deleted=False).first()
        return WalletSerializer(wallet).data if wallet else None
    
class BillReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Billreport
        fields = '__all__'    
        

# class BillReportGetSerializer(serializers.Serializer):
#     bill_number = serializers.CharField()
#     total_count = serializers.IntegerField()

#     # Add other fields if needed

#     def to_representation(self, instance):
#         # Customize how the serializer represents the data
#         return {
#             'bill_number': instance['bill_number'],
#             'total_count': instance['total_count'],
#             # Add other fields if needed
#         }

class BillReportGetSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    mobile_number = serializers.SerializerMethodField()
    service_name = serializers.SerializerMethodField()
    service_type_name = serializers.SerializerMethodField()
    total_with_tax = serializers.SerializerMethodField()
    taxvalue = serializers.SerializerMethodField()
    tax = serializers.SerializerMethodField()

    def get_user_name(self, obj):
        return obj.user.name if obj.user else None

    def get_mobile_number(self, obj):
        return obj.user.mobile_number if obj.user else None

    def get_service_name(self, obj):
        return obj.service.service_name if obj.service else None

    def get_service_type_name(self, obj):
        return obj.serviceType.serviceType_name if obj.serviceType else None
    
    def get_tax(self, obj):
        return obj.serviceType.tax if obj.serviceType else None


    class Meta:
        model = Billreport
        fields = '__all__'

    def get_total_with_tax(self, obj):
        rate = float(obj.rate)
        tax_rate = obj.serviceType.tax if obj.serviceType and obj.serviceType.tax else 0  # Default to 0 if no tax rate
        rate_with_tax = rate + (rate * tax_rate / 100)
        return rate_with_tax
    
    def get_taxvalue(self, obj):
        rate = float(obj.rate)
        tax_rate = obj.serviceType.tax if obj.serviceType and obj.serviceType.tax else 0  # Default to 0 if no tax rate
        rate_with_tax = rate + (rate * tax_rate / 100)
        taxvalue = rate_with_tax - rate
        return taxvalue
class IdProofSerializer(serializers.ModelSerializer):

    class Meta:
        model = IdProof
        fields = ['id_proof']


class UserProfileSerializer(serializers.ModelSerializer):

    idproof = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id','name', 'mobile_number', 'gender', 'idproof']

    def get_idproof(self, user):
        try:
            idproof = IdProof.objects.filter(user=user, is_deleted=False)
            return IdProofSerializer(idproof, many=True).data if idproof else None
        except IdProof.DoesNotExist:
            return None

class DocumentSerializer(serializers.ModelSerializer):

    class Meta:
        model = IdProof
        fields = '__all__'