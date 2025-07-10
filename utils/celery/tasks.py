from celery import shared_task
from utils.mail.email_connector import MSG91EmailConnector
from utils.push_notifications import send_push_notification
import datetime
from utils.elastic_search_reset.master import main as index_master_script

@shared_task
def send_booking_confirmation_task(recipient_name, recipient_email, booking_id, check_in_date, amount):
    """
    Celery task to send a booking confirmation email.
    """
    try:
        print('inside celery tasks')
        email_connector = MSG91EmailConnector()
        
        # Ensure date is in string format
        check_in_date = check_in_date.isoformat()
        
        # Convert Decimal to float if needed
        amount = float(amount)

        # Send email
        email_connector.send_booking_confirmation(
            recipient_name=recipient_name,
            recipient_email=recipient_email,
            booking_id=booking_id,
            check_in_date=check_in_date,
            amount=amount
        )
        return f"Email sent successfully to {recipient_email}"
    
    except Exception as e:
        return f"Email sending failed: {str(e)}"


@shared_task
def send_push_notification_task(token, title, message, **kwargs):
    
    try:
        response = send_push_notification(token, title, message, **kwargs)
        return response
    except Exception as e:
        print(f"Push notification error: {e}")
        return {"error": str(e)}


@shared_task
def set_elastic_search_index_task():
    # run the index_master_script
    try:
        index_master_script()
        return "Elastic search index set successfully"
    except Exception as e:
        print(f"Elastic search index error: {e}")
        return {"error": str(e)}