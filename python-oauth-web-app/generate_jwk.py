import time
from authlib.jose import JsonWebKey

if __name__ == "__main__":
    now = int(time.time())
    key = JsonWebKey.generate_key(
        "EC", "P-256", options={"kid": f"demo-{now}"}, is_private=True
    )
    print(key.as_json(is_private=True))
