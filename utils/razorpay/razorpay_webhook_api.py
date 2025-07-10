from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
import razorpay
import hmac
import hashlib
import json
import logging
from datetime import datetime
from sleeping_pod.models import Booking
from customer.models import Subscription, Wallet_transactions
from firebase_admin import messaging

logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class RazorpayWebhookAPIView(APIView):

    def post(self, request, *args, **kwargs):
        print("@RazorpayWebhook Utils----")
        try:
            payload = request.body
            signature = request.headers.get("X-Razorpay-Signature")

            # Verify Webhook Signature
            secret = settings.RAZORPAY_WEBHOOK_SECRET
            expected_signature = hmac.new(
                bytes(secret, 'utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(expected_signature, signature):
                logger.error(f"Invalid webhook signature: {datetime.now()}")
                return Response({'error': 'Invalid signature'}, status=status.HTTP_400_BAD_REQUEST)

            event_data = json.loads(payload)
            event_type = event_data.get("event")

            # Razorpay only sends `payment.captured`, so differentiate internally
            if event_type == "payment.captured":
                return self.process_payment(event_data)

            logger.info(f"Unhandled Razorpay event: {event_type}")
            return Response({'status': 'Event ignored'}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Razorpay Webhook Processing Error: {datetime.now()} : {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def process_payment(self, event_data):
        """ Handles all `payment.captured` events and differentiates between Booking, Subscription, and Wallet """
        try:
            razorpay_payment_id = event_data["payload"]["payment"]["entity"]["id"]
            razorpay_order_id = event_data["payload"]["payment"]["entity"]["order_id"]
            amount = event_data["payload"]["payment"]["entity"]["amount"] / 100  # Convert from paisa to INR
            print('order_id=', razorpay_order_id)
            # Check if it's a booking payment
            if Booking.objects.filter(razorpay_order_id=razorpay_order_id).exists():
                return self.handle_booking_payment(razorpay_order_id, razorpay_payment_id)

            # Check if it's a subscription payment
            # if Subscription.objects.filter(razorpay_order_id=razorpay_order_id).exists():
            #     return self.handle_subscription_payment(razorpay_order_id, razorpay_payment_id)

            # # Check if it's a wallet recharge payment
            # if Wallet_transactions.objects.filter(razorpay_order_id=razorpay_order_id).exists():
            #     return self.handle_wallet_recharge(razorpay_order_id, razorpay_payment_id, amount)
            
            # fayas
            return Response({'status': 'Booking payment processed successfully'}, status=status.HTTP_200_OK)
            # fayas

            logger.error(f"Unknown payment received: {razorpay_order_id}")
            return Response({'error': 'Order ID not found'}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            logger.error(f"Payment Processing Error: {datetime.now()} : {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def handle_booking_payment(self, razorpay_order_id, razorpay_payment_id):
        """ Handles confirmed booking payments """
        try:
            booking = Booking.objects.get(razorpay_order_id=razorpay_order_id)
            booking.razorpay_payment_id = razorpay_payment_id
            booking.payment_status = "CONFIRMED"
            # booking.booking_status = "BOOKED"
            booking.save()

            return Response({'status': 'Booking payment processed successfully'}, status=status.HTTP_200_OK)

        except Booking.DoesNotExist:
            logger.error(f"Booking not found for Razorpay order ID: {razorpay_order_id}")
            return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)

    def handle_subscription_payment(self, razorpay_order_id, razorpay_payment_id):
        """ Handles confirmed subscription payments """
        try:
            subscription = Subscription.objects.get(razorpay_order_id=razorpay_order_id)
            subscription.razorpay_payment_id = razorpay_payment_id
            subscription.status = "ACTIVE"  # Change this based on logic
            subscription.save()

            return Response({'status': 'Subscription payment processed successfully'}, status=status.HTTP_200_OK)

        except Subscription.DoesNotExist:
            logger.error(f"Subscription not found for Razorpay order ID: {razorpay_order_id}")
            return Response({'error': 'Subscription not found'}, status=status.HTTP_404_NOT_FOUND)

    def handle_wallet_recharge(self, razorpay_order_id, razorpay_payment_id, amount):
        """ Handles wallet recharges """
        try:
            wallet_transaction = Wallet_transactions.objects.get(razorpay_order_id=razorpay_order_id)
            wallet_transaction.razorpay_payment_id = razorpay_payment_id
            wallet_transaction.status = "SUCCESS"
            wallet_transaction.save()

            # Update user's wallet balance
            user = wallet_transaction.user
            user.wallet_balance += amount
            user.save()

            return Response({'status': 'Wallet recharge processed successfully'}, status=status.HTTP_200_OK)

        except Wallet_transactions.DoesNotExist:
            logger.error(f"Wallet transaction not found for Razorpay order ID: {razorpay_order_id}")
            return Response({'error': 'Wallet transaction not found'}, status=status.HTTP_404_NOT_FOUND)
