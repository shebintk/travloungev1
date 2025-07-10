from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime, timedelta
import logging
from sleeping_pod.models import Booking as SleepingPodBooking
from utils.razorpay.core import process_razorpay_refund
from admin_app.models import Service, Refund, User
from utils.authentication.customPermissions import IsAdminRole
from .serializers import RefundSerializer
from rest_framework.permissions import IsAuthenticated

logger = logging.getLogger(__name__)

def get_booking_model(service_type):
    """
    Returns the Booking model for the given service_type.
    Extend this function to support more services.
    """
    if service_type == 'sleeping_pod':
        return SleepingPodBooking
    # Example for future:
    # elif service_type == 'car_wash':
    #     from car_wash.models import Booking as CarWashBooking
    #     return CarWashBooking
    # Add more services here
    return None

def refund_booking(booking, service_type):
    """
    Service-specific refund logic. Extend for more services.
    """
    if service_type == 'sleeping_pod':
        payment_id = booking.razorpay_payment_id
        amount = booking.payable_amount
        if not payment_id:
            return {"success": False, "error": "No payment_id found for this booking."}
        return process_razorpay_refund(payment_id=payment_id, amount=amount)
    # Add more service-specific logic here
    return {"success": False, "error": f"Refund not implemented for service_type: {service_type}"}

class BookingRefundAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        try:
            booking_id = request.data.get('booking_id')
            service_id = request.data.get('service_id')
            notes = request.data.get('notes')

            if not booking_id or not service_id:
                logger.error("@RefundAPIView: booking_id or service_id not provided in request.")
                return Response({"error": "booking_id and service_id are required."}, status=status.HTTP_400_BAD_REQUEST)

            # Fetch Service
            service = Service.objects.filter(id=service_id).first()
            if not service:
                logger.error(f"@RefundAPIView: Service not found for service_id: {service_id}")
                return Response({"error": "Service not found for given service_id."}, status=status.HTTP_404_NOT_FOUND)

            # Derive service_type from service (for future expansion)
            service_type = service.service_name.lower().replace(' ', '_')

            BookingModel = get_booking_model(service_type)
            if not BookingModel:
                logger.error(f"@RefundAPIView: Unknown or unsupported service for refund: {service.service_name}")
                return Response({"error": f"Unknown or unsupported service for refund: {service.service_name}"}, status=status.HTTP_400_BAD_REQUEST)

            booking = BookingModel.objects.filter(id=booking_id).first()
            if not booking:
                logger.error(f"@RefundAPIView: Booking not found for booking_id: {booking_id}")
                return Response({"error": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)

            # Validate status
            if getattr(booking, 'booking_status', '').upper() != 'CANCELLED':
                logger.error(f"@RefundAPIView: Booking is not cancelled for booking_id: {booking_id}")
                return Response({"error": "Refund not eligible: Booking is not cancelled."}, status=status.HTTP_400_BAD_REQUEST)
            if getattr(booking, 'payment_status', '').upper() not in ['CONFIRMED', 'SUCCESS']:
                logger.error(f"@RefundAPIView: Payment not confirmed for booking_id: {booking_id}")
                return Response({"error": "Refund not eligible: Payment not confirmed."}, status=status.HTTP_400_BAD_REQUEST)

            # Validate within 24 hours using created_on (booking creation time)
            created_on = getattr(booking, 'created_on', None)
            if not created_on:
                logger.error(f"@RefundAPIView: Booking created_on not found for booking_id: {booking_id}")
                return Response({"error": "Booking creation time not found."}, status=status.HTTP_400_BAD_REQUEST)
            now = datetime.now(created_on.tzinfo) if hasattr(created_on, 'tzinfo') and created_on.tzinfo else datetime.now()
            if (now - created_on) > timedelta(hours=24):
                logger.error(f"@RefundAPIView: More than 24 hours since booking creation for booking_id: {booking_id}")
                return Response({"error": "Refund not eligible: More than 24 hours since booking creation."}, status=status.HTTP_400_BAD_REQUEST)

            # Service-specific refund logic
            refund_result = refund_booking(booking, service_type)
            if refund_result.get('success'):
                refund_data = refund_result['refund']
                # Save Refund record
                data = Refund.objects.create(
                    service=service,
                    booking_id=str(booking_id),
                    user=getattr(booking, 'user', None),
                    amount=getattr(booking, 'payable_amount', 0),
                    refund_id=refund_data.get('id', ''),
                    payment_id=refund_data.get('payment_id', ''),
                    status=refund_data.get('status', 'success'),
                    response_data=refund_data,
                    notes=notes
                )
                serialized_refund = RefundSerializer(data).data
                return Response({"message": "Refund processed successfully.", "refund": serialized_refund}, status=status.HTTP_200_OK)
            else:
                logger.error(f"@RefundAPIView: Refund failed for booking_id: {booking_id}, error: {refund_result.get('error', 'Unknown error')}")
                return Response({"error": refund_result.get('error', 'Refund failed')}, status=status.HTTP_502_BAD_GATEWAY)

        except Exception as e:
            logger.error(f"Error in BookingRefundAPIView: {e}")
            return Response({"error": "An error occurred while processing the refund."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR) 