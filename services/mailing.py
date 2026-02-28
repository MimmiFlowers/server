import asyncio
import smtplib
import ssl
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from config import settings

logger = logging.getLogger(__name__)

# Connection timeout in seconds
SMTP_TIMEOUT = 10


def _send_email_sync(to_email: str, order_id: str) -> None:
    """Blocking SMTP send — meant to be called via asyncio.to_thread()."""
    smtp_server = settings.ZOHO_SMTP_HOST
    smtp_port = int(settings.ZOHO_SMTP_PORT)
    smtp_user = settings.ZOHO_SMTP_USER
    smtp_password = settings.ZOHO_SMTP_PASSWORD
    smtp_sender_name = settings.ZOHO_SMTP_SENDER_NAME

    from_email = smtp_user

    subject = f"Order Confirmation - {order_id}"

    body = f"""
        Dear Customer,
        Thank you for your order! Your order ID is {order_id}.
        We will notify you once your order is processed.
        Best regards,
        Mimmi Flowers Team
    """
    msg = MIMEMultipart()
    msg['From'] = formataddr((smtp_sender_name, from_email))
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    context = ssl.create_default_context()

    with smtplib.SMTP(smtp_server, smtp_port, timeout=SMTP_TIMEOUT) as server:
        server.starttls(context=context)
        server.login(smtp_user, smtp_password)
        server.sendmail(from_email, to_email, msg.as_string())

    logger.info("Order confirmation email sent to %s for order %s", to_email, order_id)


async def send_order_confirmation(to_email: str, order_id: str) -> None:
    """Send order confirmation email without blocking the event loop.

    Runs the blocking SMTP call in a thread pool. Failures are logged
    but never propagated — email delivery must not crash the webhook.
    """
    logger.info("Preparing to send email to %s for order %s", to_email, order_id)
    try:
        await asyncio.to_thread(_send_email_sync, to_email, order_id)
    except Exception as e:
        logger.error("Failed to send email to %s: %s", to_email, e)
