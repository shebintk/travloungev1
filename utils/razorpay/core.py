import razorpay
import logging
from django.conf import settings
from decimal import Decimal

logger = logging.getLogger(__name__)

def _convert_decimal(obj):
    """Recursively convert Decimal to float or int in dicts/lists for JSON serialization."""
    if isinstance(obj, Decimal):
        # Razorpay expects amount in paise as int
        if obj == obj.to_integral():
            return int(obj)
        return float(obj)
    elif isinstance(obj, dict):
        return {k: _convert_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_decimal(i) for i in obj]
    return obj

def process_razorpay_refund(payment_id, amount=None, notes=None):
    """
    Process a refund via Razorpay API (general purpose).
    Args:
        payment_id (str): Razorpay payment ID to refund.
        amount (Decimal/int/float, optional): Amount in rupees to refund. If None, full refund is processed.
        notes (dict, optional): Additional notes for the refund.
    Returns:
        dict: Razorpay refund response or error dict.
    """
    client = razorpay.Client(auth=(settings.RAZORPAY_API_KEY, settings.RAZORPAY_API_SECRET))
    try:
        refund_data = {"payment_id": payment_id}
        if amount is not None:
            # Convert rupees to paise as int
            if isinstance(amount, Decimal):
                amount_paise = int(amount * 100)
            else:
                amount_paise = int(float(amount) * 100)
            refund_data["amount"] = amount_paise
        if notes:
            refund_data["notes"] = _convert_decimal(notes)

        refund = client.payment.refund(payment_id, refund_data)
        logger.info(f"Razorpay refund processed: {refund}")
        return {"success": True, "refund": refund}
    except razorpay.errors.BadRequestError as e:
        logger.error(f"Razorpay BadRequestError during refund: {e}")
        return {"success": False, "error": str(e)}
    except razorpay.errors.ServerError as e:
        logger.error(f"Razorpay ServerError during refund: {e}")
        return {"success": False, "error": str(e)}
    except razorpay.errors.GatewayError as e:
        logger.error(f"Razorpay GatewayError during refund: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error during Razorpay refund: {e}")
        return {"success": False, "error": str(e)}

def create_razorpay_order(amount, currency='INR', payment_capture='1', notes=None):
    """
    Create a Razorpay order.
    Args:
        amount (int): Amount in paise.
        currency (str): Currency code, default 'INR'.
        payment_capture (str): '1' for auto-capture, '0' for manual.
        notes (dict, optional): Additional notes.
    Returns:
        dict: Razorpay order response or error dict.
    """
    client = razorpay.Client(auth=(settings.RAZORPAY_API_KEY, settings.RAZORPAY_API_SECRET))
    try:
        order_data = {
            'amount': amount,
            'currency': currency,
            'payment_capture': payment_capture
        }
        if notes:
            order_data['notes'] = notes
        order = client.order.create(data=order_data)
        logger.info(f"Razorpay order created: {order['id']}")
        return {"success": True, "order": order}
    except Exception as e:
        logger.error(f"Error creating Razorpay order: {e}")
        return {"success": False, "error": str(e)}

def verify_razorpay_payment_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
    """
    Verify Razorpay payment signature.
    Args:
        razorpay_order_id (str)
        razorpay_payment_id (str)
        razorpay_signature (str)
    Returns:
        dict: {'success': True} if valid, else {'success': False, 'error': ...}
    """
    client = razorpay.Client(auth=(settings.RAZORPAY_API_KEY, settings.RAZORPAY_API_SECRET))
    params_dict = {
        'razorpay_order_id': razorpay_order_id,
        'razorpay_payment_id': razorpay_payment_id,
        'razorpay_signature': razorpay_signature
    }
    try:
        client.utility.verify_payment_signature(params_dict)
        logger.info(f"Razorpay payment signature verified for order {razorpay_order_id}")
        return {"success": True}
    except razorpay.errors.SignatureVerificationError as e:
        logger.error(f"Razorpay signature verification failed: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error during Razorpay signature verification: {e}")
        return {"success": False, "error": str(e)} 