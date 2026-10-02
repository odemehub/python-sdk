"""How a merchant and the gateway vouch for each other's messages."""

from __future__ import annotations

import hashlib
import hmac
import time


class Signature:
    """
    A body travels as plain JSON and, next to it, two headers: the moment it
    was signed, in Unix seconds, in ``X-Timestamp``, and in ``X-Signature``
    an HMAC-SHA256 under the merchant's secret over that moment, the HTTP
    method, the path and the exact text of the body, joined with newlines.
    The secret itself never travels; a message whose signature does not
    match was not written by the holder of the secret, or was changed on the
    way, and one signed more than a few minutes ago is not taken either, so a
    copied message is worth nothing for long.

    A request and its answer are signed the same way, so one calculation
    checks both of them::

        text = f"{timestamp}\\n{METHOD}\\n{path}\\n".encode() + body
        hmac.new(api_secret.encode(), text, hashlib.sha256).hexdigest()

    The path is the one in the address, with its leading slash and without
    the query string; the body is the raw text as sent, and the empty string
    for a GET.

    Test vector: with the secret ``secret_test``, at ``1700000000``, a
    ``POST`` to ``/api/1000000001/gateway/regular-payment`` with the body
    ``{"a":1}`` is signed
    ``4d6225c9dd46837418b40dd8140d76a24cd7520d81ff3b280bf98da8da6a8771``.
    """

    ALGORITHM = "sha256"

    #: The header a signature travels in, both ways.
    HEADER = "X-Signature"

    #: The header the moment of signing travels in, both ways.
    TIMESTAMP_HEADER = "X-Timestamp"

    #: How far from now, either way, a signature's moment may lie and still
    #: be taken, in seconds. The gateway allows the same.
    TIMESTAMP_TOLERANCE = 300

    def __init__(self, api_secret: str) -> None:
        self._api_secret = api_secret.encode("utf-8")

    def __repr__(self) -> str:
        return "Signature(api_secret='*****')"

    def sign(self, method: str, path: str, body: str | bytes, timestamp: int) -> str:
        """The signature that vouches for a message: HMAC-SHA256 over the moment, the method, the path and the body, as lowercase hex."""
        return hmac.new(self._api_secret, self.signed_text(method, path, body, timestamp), hashlib.sha256).hexdigest()

    def verify(self, method: str, path: str, body: str | bytes, timestamp: str | None, signature: str | None) -> bool:
        """
        Whether a signature vouches for a message, and was made recently
        enough to be taken. The timestamp and the signature are the
        ``X-Timestamp`` and ``X-Signature`` headers, as they arrived.
        """
        if not isinstance(timestamp, str) or not timestamp.isdigit():
            return False

        if abs(int(time.time()) - int(timestamp)) > self.TIMESTAMP_TOLERANCE:
            return False

        return isinstance(signature, str) and hmac.compare_digest(self.sign(method, path, body, int(timestamp)), signature)

    def headers(self, method: str, path: str, body: str | bytes) -> dict[str, str]:
        """The two headers that vouch for a message going out, made for now."""
        timestamp = int(time.time())

        return {
            self.TIMESTAMP_HEADER: str(timestamp),
            self.HEADER: self.sign(method, path, body, timestamp),
        }


    @staticmethod
    def signed_text(method: str, path: str, body: str | bytes, timestamp: int) -> bytes:
        """What the signature is taken over."""
        if isinstance(body, str):
            body = body.encode("utf-8")

        return f"{timestamp}\n{method.upper()}\n{path}\n".encode() + body
