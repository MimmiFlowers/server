import smtplib, ssl, os
from dotenv import load_dotenv
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
# from email import encoders

ENV = os.environ.get("ENV", "dev")

if ENV == "dev":
    load_dotenv(".env.dev")
else:
    load_dotenv(".env.stg")

def send_order_confirmation(to_email: str, order_id: str):
    smtp_server = os.getenv("ZOHO_SMPT_HOST")
    smtp_port = int(os.getenv("ZOHO_SMPT_PORT"))
    smtp_user = os.getenv("ZOHO_SMPT_USER")
    smtp_password = os.getenv("ZOHO_SMPT_PASSWORD")

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
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    context = ssl.create_default_context()

    print("Preparing to send email...", to_email, order_id, smtp_server, smtp_port, smtp_user)

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls(context=context)
            server.login(smtp_user, smtp_password)
            server.sendmail(from_email, to_email, msg.as_string())
        print(f"Order confirmation email sent to {to_email} for order {order_id}.")
    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")

