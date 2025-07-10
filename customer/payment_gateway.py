from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework import status
import razorpay
from customer.serializers import *
import json
from datetime import datetime, timedelta
from django.shortcuts import render, redirect,get_object_or_404
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

# @api_view(['POST'])
def create_order(amount, user, package):
    if amount:
        client = razorpay.Client(auth=(settings.RAZORPAY_API_KEY, settings.RAZORPAY_API_SECRET))
        order_amount = amount
        order_currency = 'INR'
        order_receipt = 'purchase'

        try:
            order = client.order.create({
                'amount': order_amount,
                'currency': order_currency,
                'receipt': order_receipt,
                'payment_capture': '1',
            })

            if order.get('id'):
                data = {
                    'user': user,
                    'razorpay_id': order['id'],
                    'razorpay_status': order['status'],
                    'amount': int(order['amount'] * 0.01),
                    'package': package
                }

                serializer = RazorpaySerializer(data=data)
                if serializer.is_valid():
                    serializer.save()
                else:
                    print(serializer.errors)

                return order['id']
        except Exception as e:
            logger.error(f"Error creating Razorpay order: {e}")
            return None  # clearly indicates failure

    return None  # instead of Response

@api_view(['POST'])
def travlounge_webhook(request):
    rz_key = 'rzp_test_ixUwPZfQzBt2Zy'
    rz_secret = '3YYkKV8zv8aXnglAuucnSIRs'
    
    # print(request.body, 'request.body')
    received_json_data = json.loads(request.body)
    
    razorpay_order_id = received_json_data['payload']['payment']['entity']['order_id']
    payment_id = received_json_data['payload']['payment']['entity']['id']
    status = received_json_data['payload']['payment']['entity']['status']
    payload_amount = received_json_data['payload']['payment']['entity']['amount']
    method = received_json_data['payload']['payment']['entity']['method']
    amount = int(payload_amount*0.01)
    # print(type(amount),'mmmmmm')
    print(status, '------------status-----------------')
    
    create = Razor_pay_payment_create.objects.filter(razorpay_id=razorpay_order_id).first()
    if create and create.razorpay_id:
        # chk = Razor_pay_payment_history.objects.filter(razorpay_id=razorpay_order_id, razorpay_status='captured').first()
        # print(chk,'chk')
        # if not chk :
        #     existing_captured_payment = Razor_pay_payment_history.objects.filter(razorpay_id=razorpay_order_id, razorpay_status='captured').first()
        #     if not existing_captured_payment:
        payment = Razor_pay_payment_history()
        payment.user_id = create.user_id
        payment.razorpay_id = razorpay_order_id
        payment.payment_id = payment_id
        payment.payment_method = method
        payment.razorpay_status = status
        payment.amount = amount
        payment.save()
        if hasattr(payment, 'razorpay_status') and payment.razorpay_status == 'captured':
            if create.package_id is not None:
                package_id = create.package_id
                package = Package.objects.filter(id=package_id).first()
                
                if not package:
                    return Response({"status": 400,"error": "Invalid package ID"})
                
                days = package.days
                today = datetime.today().date()
                expiry_date = today + timedelta(days=days)
                expiry_date_formatted = expiry_date.strftime('%Y-%m-%d')
                
                data = {
                    'user': create.user_id,
                    'expiry_date': expiry_date_formatted,
                    'subscribed_date': today,
                    'package': package_id,
                }
                
                serializer = SubscriptionsSerializer(data=data)
                if serializer.is_valid():
                    serializer.save()
                    return Response({"status": 200,"message": "Package subscribed successfully!"})
                
                return Response({"status": 400},serializer.errors)
            else:
                chk_wallet = Wallet.objects.filter(user=create.user_id,is_deleted=False).first()
                if chk_wallet:
                    balance = amount+chk_wallet.balance
                    Wallet.objects.filter(pk=chk_wallet.id).update(amount=amount,balance=balance)
                    transaction_data = {
                        'user': create.user_id,
                        'amount': amount,
                        'balance': balance ,
                        'requested_by':create.user_id,
                        'transaction_type':1
                        }
                    transactionSerializer = WalletTransactionSerializer(data=transaction_data)
                    if transactionSerializer.is_valid():
                        transactionSerializer.save()
                        return Response({"status": 200, "message": "Wallet added successfully"})
                    else:
                        return Response({"status": 400,},transactionSerializer.errors)
                        
                else:
                    wallet_data = {
                        'user': create.user_id,
                        'amount': amount,
                        'balance': amount ,
                        'requested_by':create.user_id
                    }
                    serializer = WalletSerializer(data=wallet_data)
                    if serializer.is_valid():
                        serializer.save()
                        transaction_data = {
                        'user': create.user_id,
                        'amount': amount,
                        'balance': amount ,
                        'requested_by':create.user_id,
                        'transaction_type':1
                        }
                        transactionSerializer = WalletTransactionSerializer(data=transaction_data)
                        if transactionSerializer.is_valid():
                            transactionSerializer.save()
                            return Response({"status": 200, "message": "Wallet added successfully"})
                        else:
                            return Response({"status": 400,},transactionSerializer.errors)

                    return Response({"status": 400,},serializer.errors,)
                # return Response({'message': 'Wallet added successfully!'}, status=status.HTTP_201_CREATED)
        elif hasattr(payment, 'razorpay_status') and payment.razorpay_status == 'authorized':
            return Response({"status": 200, "message": "payment authorized"})
        elif hasattr(payment, 'razorpay_status') and payment.razorpay_status == 'failed':
            return Response({"status": 400, "message": "payment failed"})
        else:
            return Response({"status": 400, "message": "payment failed"})
    else:
        return Response({"status": 400, "message": "Invalid Razorpay order ID"})

