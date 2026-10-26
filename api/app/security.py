from __future__ import annotations

import os

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from fastapi import Header, HTTPException

JWT_ALGORITHM = "RS256"
JWT_ISSUER = "BCP"
JWT_AUDIENCE = "dev"
JWT_PUBLIC_KEY_ENV = "devpub"


def authenticated_owner(requested_owner: str | None, identity: dict[str, str]) -> str:
    identity_owner = identity["username"]
    if requested_owner is not None and requested_owner != identity_owner:
        raise HTTPException(status_code=403, detail="Forbidden")
    return identity_owner


def authenticated_identity(authorization: str = Header(default="")) -> dict[str, str]:
    scheme, _, token = authorization.partition(" ")
    if scheme != "Bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid token")

    configured_public_key = os.getenv(JWT_PUBLIC_KEY_ENV)
    if not configured_public_key:
        raise RuntimeError(f"JWT public key is missing from {JWT_PUBLIC_KEY_ENV}")

    try:
        public_key = serialization.load_pem_public_key(configured_public_key.encode("utf-8"))
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"JWT public key in {JWT_PUBLIC_KEY_ENV} is invalid") from error

    if not isinstance(public_key, RSAPublicKey):
        raise RuntimeError(f"JWT public key in {JWT_PUBLIC_KEY_ENV} must be an RSA key")

    try:
        claims = jwt.decode(
            token,
            public_key,
            algorithms=[JWT_ALGORITHM],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
            options={"require": ["exp", "iss", "aud", "username", "role"]},
        )
    except jwt.PyJWTError as error:
        raise HTTPException(status_code=401, detail="Invalid token") from error

    username = claims.get("username")
    role = claims.get("role")
    if not isinstance(username, str) or not isinstance(role, str):
        raise HTTPException(status_code=401, detail="Invalid token")
    return {"username": username, "role": role}
