import base64
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import init_db
from services import wallet_service, qr_service

USER_ID = "550e8400-e29b-41d4-a716-446655440000"

init_db()

try:
    wallet = wallet_service.create_wallet(USER_ID)
    print("Nieuw wallet aangemaakt")
except ValueError:
    print("Wallet bestaat al, ophalen...")
    wallet = wallet_service.get_wallet_by_user(USER_ID)

print(f"user_id  : {wallet.user_id}")
print(f"qr_token : {wallet.qr_token}")
print(f"balance  : {wallet.balance}")
print(f"is_active: {wallet.is_active}")

img_bytes = base64.b64decode(qr_service.generate_qr_image(wallet.qr_token))
with open("qr_output.png", "wb") as f:
    f.write(img_bytes)

print("\nQR-code opgeslagen als qr_output.png")
