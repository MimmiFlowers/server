import asyncio
import json
import re
import smtplib
import ssl
import logging
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from config import settings

logger = logging.getLogger(__name__)

# Connection timeout in seconds
SMTP_TIMEOUT = 10

# Basic email format validation
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

# Derive base site URL from SUCCESS_URL (strip trailing /Success/)
_SITE_URL = settings.SUCCESS_URL.rsplit("/Success/", 1)[0] or "https://mimmiflowers.se"

# Store pickup address
_PICKUP_ADDRESS = "Rågsved torg, Bandhagen"

# ── Design tokens (matching website) ──────────────────────────────
_BG = "#FFF0F5"           # lavender blush — page background
_ACCENT = "#edc7f5"       # lilac — brand accent
_ACCENT_LIGHT = "#f9f2fc" # very light lilac — section backgrounds
_CARD_BG = "#ffffff"      # white — card/content background
_TEXT_DARK = "#1a1a1a"     # near-black — headings
_TEXT = "#374151"          # gray-700 — body text
_TEXT_LIGHT = "#6b7280"    # gray-500 — secondary text
_TEXT_MUTED = "#9ca3af"    # gray-400 — muted/captions
_BORDER = "#e5e7eb"        # gray-200 — dividers


# ── Bilingual text ────────────────────────────────────────────────
_I18N: dict[str, dict[str, str]] = {
    "en": {
        "subject":          "Order Confirmation",
        "title":            "Order Confirmation",
        "thank_you":        "Thank you for your order!",
        "greeting":         "Hi {name}, your order has been confirmed.",
        "order_id":         "Order ID",
        "order_summary":    "Order Summary",
        "qty":              "Qty",
        "subtotal":         "Subtotal",
        "delivery":         "Delivery",
        "vat":              "VAT (included)",
        "total":            "Total",
        "pickup":           "Pickup",
        "delivery_label":   "Delivery",
        "date":             "Date",
        "time":             "Time",
        "address":          "Address",
        "recipient":        "Recipient",
        "name":             "Name",
        "email":            "Email",
        "phone":            "Phone",
        "your_details":     "Your Details",
        "visit_shop":       "Visit Our Shop",
        "questions":        "Questions about your order? Contact us at",
    },
    "sv": {
        "subject":          "Orderbekräftelse",
        "title":            "Orderbekräftelse",
        "thank_you":        "Tack för din beställning!",
        "greeting":         "Hej {name}, din beställning har bekräftats.",
        "order_id":         "Order-ID",
        "order_summary":    "Ordersammanfattning",
        "qty":              "Antal",
        "subtotal":         "Delsumma",
        "delivery":         "Leverans",
        "vat":              "Moms (ingår)",
        "total":            "Totalt",
        "pickup":           "Upphämtning",
        "delivery_label":   "Leverans",
        "date":             "Datum",
        "time":             "Tid",
        "address":          "Adress",
        "recipient":        "Mottagare",
        "name":             "Namn",
        "email":            "E-post",
        "phone":            "Telefon",
        "your_details":     "Dina uppgifter",
        "visit_shop":       "Besök vår butik",
        "questions":        "Frågor om din beställning? Kontakta oss på",
    },
}


def _t(locale: str, key: str, **kwargs: str) -> str:
    """Look up a translated string. Falls back to English."""
    lang = "sv" if locale.startswith("sv") else "en"
    text = _I18N.get(lang, _I18N["en"]).get(key, _I18N["en"].get(key, key))
    if kwargs:
        text = text.format(**kwargs)
    return text


def _fmt_sek(ore: int) -> str:
    """Format öre (int) as SEK with 2 decimals."""
    return f"{ore / 100:,.2f} kr"


# ── Shared helpers to parse order fields ──────────────────────────
def _parse_order(order: dict) -> dict:
    """Normalise JSON-string fields into dicts/lists."""
    customer = order.get("customer", {})
    if isinstance(customer, str):
        customer = json.loads(customer)
    recipient = order.get("recipient")
    if isinstance(recipient, str):
        recipient = json.loads(recipient)
    items = order.get("items", [])
    if isinstance(items, str):
        items = json.loads(items)
    return {
        "order_id": order["orderID"],
        "locale": order.get("locale", "en"),
        "customer": customer,
        "recipient": recipient,
        "items": items,
        "pickup": order.get("pickup", False),
        "order_for_myself": order.get("orderForMyself", False),
        "subtotal": order.get("subtotal", 0),
        "delivery_fee": order.get("deliveryFee", 0),
        "total": order.get("total", 0),
        "moms": order.get("moms", 0),
        "created_at": order.get("createdAt"),
    }


def _customer_name(customer: dict) -> str:
    return f"{customer.get('firstName', '')} {customer.get('lastName', '')}".strip()


# ── HTML builder ──────────────────────────────────────────────────

def _build_item_row(item: dict, locale: str) -> str:
    """Build a single product row for the items table."""
    name = item.get("name", "Product")
    qty = item.get("quantity", 1)
    price = item.get("price", 0)
    picture = item.get("picture", "")
    line_total = price * qty

    img_html = ""
    if picture:
        img_html = (
            f'<img src="{picture}" alt="{name}" '
            f'width="56" height="56" '
            f'style="display:block;border-radius:8px;object-fit:cover;" />'
        )

    return f"""\
    <tr>
      <td style="padding:12px 0;border-bottom:1px solid {_BORDER};vertical-align:middle;" width="64">
        {img_html}
      </td>
      <td style="padding:12px 8px;border-bottom:1px solid {_BORDER};vertical-align:middle;">
        <p style="margin:0;font-size:14px;font-weight:600;color:{_TEXT_DARK};text-transform:uppercase;letter-spacing:0.5px;">
          {name}
        </p>
        <p style="margin:2px 0 0;font-size:12px;color:{_TEXT_MUTED};">
          {_t(locale, "qty")}: {qty}
        </p>
      </td>
      <td style="padding:12px 0;border-bottom:1px solid {_BORDER};vertical-align:middle;text-align:right;">
        <p style="margin:0;font-size:14px;font-weight:600;color:{_TEXT_DARK};">
          {line_total:,} kr
        </p>
      </td>
    </tr>"""


def _build_info_row(label: str, value: str) -> str:
    """Build a label: value row for order/delivery details."""
    return f"""\
    <tr>
      <td style="padding:4px 0;font-size:13px;color:{_TEXT_MUTED};text-transform:uppercase;letter-spacing:0.5px;width:120px;vertical-align:top;">
        {label}
      </td>
      <td style="padding:4px 0;font-size:14px;color:{_TEXT};">
        {value}
      </td>
    </tr>"""


def _build_html_body(order: dict) -> str:
    """Build a designed HTML email body for order confirmation."""
    o = _parse_order(order)
    loc = o["locale"]
    lang_attr = "sv" if loc.startswith("sv") else "en"
    customer = o["customer"]
    recipient = o["recipient"]
    items = o["items"]
    pickup = o["pickup"]
    order_for_myself = o["order_for_myself"]
    subtotal = o["subtotal"]
    delivery_fee = o["delivery_fee"]
    total = o["total"]
    moms = o["moms"]
    created_at = o["created_at"]
    order_id = o["order_id"]
    name = _customer_name(customer)

    # Format date
    if isinstance(created_at, datetime):
        order_date = created_at.strftime("%d %B %Y" if lang_attr == "sv" else "%B %d, %Y")
    else:
        order_date = str(created_at)[:10] if created_at else ""

    # Build items table rows
    items_html = "\n".join(_build_item_row(item, loc) for item in items)

    # ── Delivery / Pickup info section ──
    delivery_info_rows = ""

    if recipient:
        r_date = recipient.get("date", "")
        r_time = recipient.get("time", "")
        if r_date:
            delivery_info_rows += _build_info_row(_t(loc, "date"), r_date)
        if r_time:
            delivery_info_rows += _build_info_row(_t(loc, "time"), r_time)

    if pickup:
        delivery_method_label = _t(loc, "pickup").upper()
        delivery_info_rows += _build_info_row(_t(loc, "address"), _PICKUP_ADDRESS)
    else:
        delivery_method_label = _t(loc, "delivery_label").upper()
        if recipient:
            addr = recipient.get("address", "")
            if addr:
                delivery_info_rows += _build_info_row(_t(loc, "address"), addr)

    # Recipient section (only when ordering for someone else)
    recipient_section = ""
    if not order_for_myself and recipient:
        r_name = f"{recipient.get('firstName', '')} {recipient.get('lastName', '')}".strip()
        r_phone = recipient.get("phone", "")
        if r_name or r_phone:
            recipient_rows = ""
            if r_name:
                recipient_rows += _build_info_row(_t(loc, "name"), r_name)
            if r_phone:
                recipient_rows += _build_info_row(_t(loc, "phone"), r_phone)
            recipient_section = f"""\
  <!-- Recipient -->
  <tr>
    <td style="padding:0 32px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:8px;">
        <tr>
          <td style="padding:20px 0 8px;font-size:10px;font-weight:600;color:{_TEXT_MUTED};text-transform:uppercase;letter-spacing:2px;">
            {_t(loc, "recipient")}
          </td>
        </tr>
      </table>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
        {recipient_rows}
      </table>
    </td>
  </tr>"""

    # Delivery fee row (only show if there is one)
    delivery_fee_row = ""
    if delivery_fee > 0:
        delivery_fee_row = f"""\
        <tr>
          <td style="padding:4px 0;font-size:13px;color:{_TEXT_LIGHT};">{_t(loc, "delivery")}</td>
          <td style="padding:4px 0;font-size:13px;color:{_TEXT_LIGHT};text-align:right;">{_fmt_sek(delivery_fee)}</td>
        </tr>"""

    return f"""\
<!DOCTYPE html>
<html lang="{lang_attr}">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{_t(loc, "title")} — {order_id}</title>
</head>
<body style="margin:0;padding:0;background-color:{_BG};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;-webkit-font-smoothing:antialiased;">

  <!-- Outer wrapper -->
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:{_BG};padding:40px 16px;">
    <tr>
      <td align="center">

        <!-- Card -->
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="background-color:{_CARD_BG};border-radius:16px;overflow:hidden;max-width:600px;width:100%;box-shadow:0 1px 3px rgba(0,0,0,0.04);">

          <!-- Header -->
          <tr>
            <td style="background-color:{_ACCENT};padding:32px 32px 28px;text-align:center;">
              <h1 style="margin:0;color:{_TEXT_DARK};font-size:18px;font-weight:300;letter-spacing:4px;text-transform:uppercase;">
                Mimmi Flowers
              </h1>
            </td>
          </tr>

          <!-- Success badge -->
          <tr>
            <td style="padding:32px 32px 0;text-align:center;">
              <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 auto;">
                <tr>
                  <td style="width:48px;height:48px;border-radius:50%;background-color:#f0fdf4;text-align:center;vertical-align:middle;font-size:24px;">
                    &#10003;
                  </td>
                </tr>
              </table>
              <h2 style="margin:16px 0 4px;font-size:22px;font-weight:600;color:{_TEXT_DARK};">
                {_t(loc, "thank_you")}
              </h2>
              <p style="margin:0;font-size:14px;color:{_TEXT_LIGHT};">
                {_t(loc, "greeting", name=name)}
              </p>
            </td>
          </tr>

          <!-- Order ID badge -->
          <tr>
            <td style="padding:20px 32px 0;text-align:center;">
              <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 auto;background-color:{_ACCENT_LIGHT};border-radius:24px;">
                <tr>
                  <td style="padding:10px 24px;">
                    <p style="margin:0;font-size:10px;color:{_TEXT_MUTED};text-transform:uppercase;letter-spacing:1.5px;">{_t(loc, "order_id")}</p>
                    <p style="margin:3px 0 0;font-size:16px;font-weight:700;color:{_TEXT_DARK};letter-spacing:1px;font-family:'Courier New',Courier,monospace;">
                      {order_id}
                    </p>
                  </td>
                </tr>
              </table>
              <p style="margin:8px 0 0;font-size:12px;color:{_TEXT_MUTED};">{order_date}</p>
            </td>
          </tr>

          <!-- Hairline divider -->
          <tr>
            <td style="padding:24px 32px 0;">
              <div style="height:1px;background-color:{_BORDER};"></div>
            </td>
          </tr>

          <!-- Items header -->
          <tr>
            <td style="padding:20px 32px 0;">
              <p style="margin:0;font-size:10px;font-weight:600;color:{_TEXT_MUTED};text-transform:uppercase;letter-spacing:2px;">
                {_t(loc, "order_summary")}
              </p>
            </td>
          </tr>

          <!-- Items table -->
          <tr>
            <td style="padding:12px 32px 0;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                {items_html}
              </table>
            </td>
          </tr>

          <!-- Totals -->
          <tr>
            <td style="padding:16px 32px 0;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td style="padding:4px 0;font-size:13px;color:{_TEXT_LIGHT};">{_t(loc, "subtotal")}</td>
                  <td style="padding:4px 0;font-size:13px;color:{_TEXT_LIGHT};text-align:right;">{_fmt_sek(subtotal)}</td>
                </tr>
                {delivery_fee_row}
                <tr>
                  <td style="padding:4px 0;font-size:12px;color:{_TEXT_MUTED};">{_t(loc, "vat")}</td>
                  <td style="padding:4px 0;font-size:12px;color:{_TEXT_MUTED};text-align:right;">{_fmt_sek(moms)}</td>
                </tr>
                <tr>
                  <td colspan="2" style="padding:8px 0 0;">
                    <div style="height:1px;background-color:{_BORDER};"></div>
                  </td>
                </tr>
                <tr>
                  <td style="padding:10px 0 4px;font-size:16px;font-weight:700;color:{_TEXT_DARK};">{_t(loc, "total")}</td>
                  <td style="padding:10px 0 4px;font-size:16px;font-weight:700;color:{_TEXT_DARK};text-align:right;">{_fmt_sek(total)}</td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Divider -->
          <tr>
            <td style="padding:20px 32px 0;">
              <div style="height:1px;background-color:{_BORDER};"></div>
            </td>
          </tr>

          <!-- Delivery / Pickup info -->
          <tr>
            <td style="padding:0 32px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:8px;">
                <tr>
                  <td style="padding:20px 0 8px;font-size:10px;font-weight:600;color:{_TEXT_MUTED};text-transform:uppercase;letter-spacing:2px;">
                    {delivery_method_label}
                  </td>
                </tr>
              </table>
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                {delivery_info_rows}
              </table>
            </td>
          </tr>

          {recipient_section}

          <!-- Customer info -->
          <tr>
            <td style="padding:0 32px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:8px;">
                <tr>
                  <td style="padding:20px 0 8px;font-size:10px;font-weight:600;color:{_TEXT_MUTED};text-transform:uppercase;letter-spacing:2px;">
                    {_t(loc, "your_details")}
                  </td>
                </tr>
              </table>
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                {_build_info_row(_t(loc, "name"), name)}
                {_build_info_row(_t(loc, "email"), customer.get("email", ""))}
                {_build_info_row(_t(loc, "phone"), customer.get("phone", ""))}
              </table>
            </td>
          </tr>

          <!-- Divider -->
          <tr>
            <td style="padding:24px 32px 0;">
              <div style="height:1px;background-color:{_BORDER};"></div>
            </td>
          </tr>

          <!-- CTA button -->
          <tr>
            <td style="padding:24px 32px 0;text-align:center;">
              <a href="{_SITE_URL}"
                 style="display:inline-block;background-color:{_TEXT_DARK};color:#ffffff;font-size:13px;font-weight:500;text-decoration:none;padding:12px 32px;border-radius:50px;text-transform:uppercase;letter-spacing:1.5px;">
                {_t(loc, "visit_shop")}
              </a>
            </td>
          </tr>

          <!-- Help text -->
          <tr>
            <td style="padding:20px 32px 0;text-align:center;">
              <p style="margin:0;font-size:13px;color:{_TEXT_LIGHT};line-height:1.6;">
                {_t(loc, "questions")}
                <a href="mailto:info@mimmiflowers.se" style="color:{_TEXT_DARK};font-weight:500;text-decoration:underline;">info@mimmiflowers.se</a>
              </p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:28px 32px 32px;text-align:center;">
              <!-- Social links -->
              <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 auto 16px;">
                <tr>
                  <td style="padding:0 8px;">
                    <a href="https://instagram.com/mimmi_flowers?igshid=MzMyNGUyNmU2YQ==" style="color:{_TEXT_MUTED};text-decoration:none;font-size:13px;">
                      Instagram
                    </a>
                  </td>
                  <td style="color:{_BORDER};font-size:13px;">&middot;</td>
                  <td style="padding:0 8px;">
                    <a href="https://www.tiktok.com/@mimmi_flowers" style="color:{_TEXT_MUTED};text-decoration:none;font-size:13px;">
                      TikTok
                    </a>
                  </td>
                </tr>
              </table>

              <p style="margin:0;font-size:11px;color:{_TEXT_MUTED};letter-spacing:0.5px;">
                &copy; {datetime.now().year} Mimmi Flowers &middot; Stockholm, Sweden
              </p>
            </td>
          </tr>

        </table>
        <!-- /Card -->

      </td>
    </tr>
  </table>
  <!-- /Outer wrapper -->

</body>
</html>"""


# ── Plain-text builder ────────────────────────────────────────────

def _build_plain_text(order: dict) -> str:
    """Build a plain-text fallback for the order confirmation email."""
    o = _parse_order(order)
    loc = o["locale"]
    customer = o["customer"]
    recipient = o["recipient"]
    items = o["items"]
    pickup = o["pickup"]
    order_for_myself = o["order_for_myself"]
    subtotal = o["subtotal"]
    delivery_fee = o["delivery_fee"]
    total = o["total"]
    moms = o["moms"]
    order_id = o["order_id"]
    name = _customer_name(customer)

    lines = [
        "MIMMI FLOWERS",
        "=" * 40,
        "",
        f"{_t(loc, 'thank_you')}",
        f"{_t(loc, 'greeting', name=name)}",
        "",
        f"{_t(loc, 'order_id')}: {order_id}",
        "",
        "-" * 40,
        _t(loc, "order_summary").upper(),
        "-" * 40,
    ]

    for item in items:
        item_name = item.get("name", "Product")
        qty = item.get("quantity", 1)
        price = item.get("price", 0)
        lines.append(f"  {item_name} x{qty} — {price * qty:,} kr")

    lines.append("-" * 40)
    lines.append(f"  {_t(loc, 'subtotal')}: {_fmt_sek(subtotal)}")
    if delivery_fee > 0:
        lines.append(f"  {_t(loc, 'delivery')}: {_fmt_sek(delivery_fee)}")
    lines.append(f"  {_t(loc, 'vat')}: {_fmt_sek(moms)}")
    lines.append(f"  {_t(loc, 'total').upper()}: {_fmt_sek(total)}")
    lines.append("")

    if pickup:
        lines.append(_t(loc, "pickup").upper())
        lines.append(f"  {_t(loc, 'address')}: {_PICKUP_ADDRESS}")
    else:
        lines.append(_t(loc, "delivery_label").upper())
        if recipient:
            addr = recipient.get("address", "")
            if addr:
                lines.append(f"  {_t(loc, 'address')}: {addr}")

    if recipient:
        r_date = recipient.get("date", "")
        r_time = recipient.get("time", "")
        if r_date:
            lines.append(f"  {_t(loc, 'date')}: {r_date}")
        if r_time:
            lines.append(f"  {_t(loc, 'time')}: {r_time}")

    if not order_for_myself and recipient:
        r_name = f"{recipient.get('firstName', '')} {recipient.get('lastName', '')}".strip()
        r_phone = recipient.get("phone", "")
        if r_name:
            lines.append("")
            lines.append(_t(loc, "recipient").upper())
            lines.append(f"  {_t(loc, 'name')}: {r_name}")
            if r_phone:
                lines.append(f"  {_t(loc, 'phone')}: {r_phone}")

    lines.extend([
        "",
        "-" * 40,
        f"{_t(loc, 'questions')} info@mimmiflowers.se",
        "",
        f"{_t(loc, 'visit_shop')}: {_SITE_URL}",
        f"Instagram: https://instagram.com/mimmi_flowers",
        "",
        f"© {datetime.now().year} Mimmi Flowers · Stockholm, Sweden",
    ])

    return "\n".join(lines)


# ── SMTP send ─────────────────────────────────────────────────────

def _send_email_sync(to_email: str, order: dict) -> None:
    """Blocking SMTP send — meant to be called via asyncio.to_thread()."""
    smtp_server = settings.ZOHO_SMTP_HOST
    smtp_port = int(settings.ZOHO_SMTP_PORT)
    smtp_user = settings.ZOHO_SMTP_USER
    smtp_password = settings.ZOHO_SMTP_PASSWORD
    smtp_sender_name = settings.ZOHO_SMTP_SENDER_NAME

    from_email = smtp_user
    order_id = order["orderID"]
    locale = order.get("locale", "en")

    subject = f"{_t(locale, 'subject')} — {order_id}"

    msg = MIMEMultipart("alternative")
    msg['From'] = formataddr((smtp_sender_name, from_email))
    msg['To'] = to_email
    msg['Subject'] = subject

    msg.attach(MIMEText(_build_plain_text(order), "plain"))
    msg.attach(MIMEText(_build_html_body(order), "html"))

    context = ssl.create_default_context()

    with smtplib.SMTP(smtp_server, smtp_port, timeout=SMTP_TIMEOUT) as server:
        server.starttls(context=context)
        server.login(smtp_user, smtp_password)
        server.sendmail(from_email, to_email, msg.as_string())

    logger.info("Order confirmation email sent to %s for order %s (locale=%s)", to_email, order_id, locale)


async def send_order_confirmation(to_email: str, order: dict) -> None:
    """Send order confirmation email without blocking the event loop.

    Validates the email format before attempting to send. Runs the
    blocking SMTP call in a thread pool. Failures are logged but never
    propagated — email delivery must not crash the webhook.
    """
    if not _EMAIL_RE.match(to_email):
        logger.warning("Invalid email format '%s' for order %s, skipping send", to_email, order.get("orderID"))
        return

    logger.info("Preparing to send email to %s for order %s", to_email, order.get("orderID"))
    try:
        await asyncio.to_thread(_send_email_sync, to_email, order)
    except Exception as e:
        logger.error("Failed to send email to %s: %s", to_email, e)
