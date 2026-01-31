import secrets
from typing import Optional

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


def build_serializer(secret_key: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret_key, salt="email-verification")


def generate_verification_token(serializer: URLSafeTimedSerializer, email: str) -> str:
    payload = {
        "email": email,
        "nonce": secrets.token_urlsafe(16),
    }
    return serializer.dumps(payload)


def verify_token(
    serializer: URLSafeTimedSerializer,
    token: str,
    max_age_seconds: int,
) -> Optional[str]:
    try:
        data = serializer.loads(token, max_age=max_age_seconds)
    except (SignatureExpired, BadSignature):
        return None
    return data.get("email")
