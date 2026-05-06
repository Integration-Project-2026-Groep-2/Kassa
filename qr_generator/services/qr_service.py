import base64
import io
import logging

import qrcode
import qrcode.constants

logger = logging.getLogger(__name__)


def generate_qr_image(qr_token: str) -> str:
    """
    Genereer een QR-code afbeelding voor het gegeven token.

    Alleen het token wordt in de QR gecodeerd. Wanneer de kassa scant
    krijgt hij dit token terug en kan daarmee het wallet opzoeken.

    Returns:
        Base64 gecodeerde PNG string (geen data-URI prefix).
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_token)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)

    encoded = base64.b64encode(buffer.read()).decode('utf-8')
    logger.debug("QR afbeelding gegenereerd voor token %s", qr_token)
    return encoded
