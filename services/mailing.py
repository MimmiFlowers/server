import asyncio
import re
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

# Basic email format validation
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _build_html_body(order_id: str) -> str:
    """Build an HTML email body for order confirmation."""
    return f"""\
<!DOCTYPE html>
<html lang="sv">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Order Confirmation</title>
</head>
<body style="margin:0;padding:0;background-color:#f7f7f7;font-family:Arial,Helvetica,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f7f7f7;padding:32px 0;">
    <tr>
      <td align="center">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:8px;overflow:hidden;max-width:600px;width:100%;">
          <!-- Header -->
          <tr>
            <td style="background-color:#edc7f5;padding:24px;text-align:center;">
              <h1 style="margin:0;color:#333;font-size:24px;">Mimmi Flowers</h1>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding:32px 24px;">
              <h2 style="margin:0 0 16px;color:#333;font-size:20px;">Thank you for your order!</h2>
              <p style="margin:0 0 12px;color:#555;font-size:16px;line-height:1.5;">
                Your order has been received and is being processed.
              </p>
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:24px 0;background-color:#f9f5fb;border-radius:6px;">
                <tr>
                  <td style="padding:16px 20px;">
                    <p style="margin:0;color:#777;font-size:14px;">Order ID</p>
                    <p style="margin:4px 0 0;color:#333;font-size:18px;font-weight:bold;">{order_id}</p>
                  </td>
                </tr>
              </table>
              <p style="margin:0 0 12px;color:#555;font-size:16px;line-height:1.5;">
                We will notify you once your order is on its way.
              </p>
              <p style="margin:0;color:#555;font-size:16px;line-height:1.5;">
                If you have any questions, please contact us at
                <a href="mailto:info@mimmiflowers.se" style="color:#9b59b6;">info@mimmiflowers.se</a>.
              </p>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="padding:20px 24px;border-top:1px solid #eee;text-align:center;">
              <p style="margin:0;color:#999;font-size:13px;">
                &copy; Mimmi Flowers &middot; Stockholm, Sweden
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _send_email_sync(to_email: str, order_id: str) -> None:
    """Blocking SMTP send — meant to be called via asyncio.to_thread()."""
    smtp_server = settings.ZOHO_SMTP_HOST
    smtp_port = int(settings.ZOHO_SMTP_PORT)
    smtp_user = settings.ZOHO_SMTP_USER
    smtp_password = settings.ZOHO_SMTP_PASSWORD
    smtp_sender_name = settings.ZOHO_SMTP_SENDER_NAME

    from_email = smtp_user

    subject = f"Order Confirmation - {order_id}"

    msg = MIMEMultipart("alternative")
    msg['From'] = formataddr((smtp_sender_name, from_email))
    msg['To'] = to_email
    msg['Subject'] = subject

    # Plain-text fallback for clients that don't render HTML
    text_body = (
        f"Dear Customer,\n\n"
        f"Thank you for your order! Your order ID is {order_id}.\n"
        f"We will notify you once your order is processed.\n\n"
        f"Best regards,\n"
        f"Mimmi Flowers Team"
    )
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(_build_html_body(order_id), "html"))

    context = ssl.create_default_context()

    with smtplib.SMTP(smtp_server, smtp_port, timeout=SMTP_TIMEOUT) as server:
        server.starttls(context=context)
        server.login(smtp_user, smtp_password)
        server.sendmail(from_email, to_email, msg.as_string())

    logger.info("Order confirmation email sent to %s for order %s", to_email, order_id)


async def send_order_confirmation(to_email: str, order_id: str) -> None:
    """Send order confirmation email without blocking the event loop.

    Validates the email format before attempting to send. Runs the
    blocking SMTP call in a thread pool. Failures are logged but never
    propagated — email delivery must not crash the webhook.
    """
    if not _EMAIL_RE.match(to_email):
        logger.warning("Invalid email format '%s' for order %s, skipping send", to_email, order_id)
        return

    logger.info("Preparing to send email to %s for order %s", to_email, order_id)
    try:
        await asyncio.to_thread(_send_email_sync, to_email, order_id)
    except Exception as e:
        logger.error("Failed to send email to %s: %s", to_email, e)
