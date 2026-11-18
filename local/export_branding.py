"""Branding configuration and a real QR code only after a download URL exists."""
import io
import os
from urllib.parse import urlsplit


def download_url():
    value = os.environ.get("SHIYI_APP_DOWNLOAD_URL", "").strip()
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or len(value) > 240:
        return ""
    return value


def config():
    url = download_url()
    return {"brand": "AI 私人衣橱", "download_url": url or None,
            "qr_url": "/api/export/qr.png" if url else None,
            "pending_label": "APP 即将上线"}


def qr_png():
    url = download_url()
    if not url:
        return None
    import qrcode
    code = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=6, border=4)
    code.add_data(url)
    code.make(fit=True)
    image = code.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
