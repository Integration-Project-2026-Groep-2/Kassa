import base64
import requests

USER_ID = "550e8400-e29b-41d4-a716-446655440000"
BASE_URL = "http://localhost:5001/api/qr"

response = requests.post(f"{BASE_URL}/generate", json={"user_id": USER_ID})

if response.status_code == 409:
    print("Wallet bestaat al, ophalen...")
    response = requests.get(f"{BASE_URL}/{USER_ID}")

data = response.json()
print(f"user_id  : {data['user_id']}")
print(f"qr_token : {data['qr_token']}")
print(f"balance  : {data['balance']}")
print(f"is_active: {data['is_active']}")

img_bytes = base64.b64decode(data["qr_image_base64"])
with open("qr_output.png", "wb") as f:
    f.write(img_bytes)

print("\nQR-code opgeslagen als qr_output.png")
