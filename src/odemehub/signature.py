"""How a merchant and the gateway vouch for each other's bodies."""

from __future__ import annotations

import hashlib
import hmac


class Signature:
    """
    A body travels as plain JSON and, next to it in the ``X-Signature``
    header, an HMAC-SHA256 of that exact text under the merchant's secret.
    The secret itself never travels; a body whose signature does not match
    was not written by the holder of the secret, or was changed on the way.

    This is the same calculation the application makes in its own
    ``Services\\Gateway\\Signer``. Nothing is layered on top, so a body can
    be signed and checked by hand::

        hmac.new(api_secret.encode(), body, hashlib.sha256).hexdigest()

    Test vector: with the secret ``secret_test`` the body ``{"a":1}`` is
    signed ``6d0c951564cdd2b6b70e75b214293a8cd2542815ba54fe91c7f6ce105bc3d592``.
    """

    ALGORITHM = "sha256"

    #: The header both the request and the answer carry the signature in.
    HEADER = "X-Signature"

    def __init__(self, api_secret: str) -> None:
        self._api_secret = api_secret.encode("utf-8")

    def __repr__(self) -> str:
        return "Signature(api_secret='*****')"

    def sign(self, body: str | bytes) -> str:
        """The signature that vouches for a body: HMAC-SHA256 over the exact text, as lowercase hex."""
        if isinstance(body, str):
            body = body.encode("utf-8")

        return hmac.new(self._api_secret, body, hashlib.sha256).hexdigest()

    def verify(self, body: str | bytes, signature: str | None) -> bool:
        """Whether a signature vouches for a body."""
        return isinstance(signature, str) and hmac.compare_digest(self.sign(body), signature)
