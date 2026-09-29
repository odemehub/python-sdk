"""Everything the client raises."""

from __future__ import annotations


class OdemehubError(Exception):
    """
    Base class for everything this client raises, so a caller that does not
    care which way a payment failed can catch one thing.
    """


class AuthenticationError(OdemehubError):
    """
    The gateway did not accept the credentials: either the API key is not
    the one issued to the team in the address, or the request was not
    signed with the matching secret.
    """


class SignatureError(OdemehubError):
    """
    The answer did not carry the signature it should have. It was not
    signed with the secret this client holds, so it cannot be shown to have
    come from the gateway and must not be acted on.
    """


class TransportError(OdemehubError):
    """
    The gateway could not be reached at all. Whether the payment was made is
    unknown; the payment record on the gateway says what actually happened.
    """


class UnexpectedResponseError(OdemehubError):
    """
    The gateway answered with something that is neither a payment outcome
    nor a refusal this client knows how to read.
    """

    def __init__(self, message: str, status: int) -> None:
        super().__init__(message)
        self.status = status


class ValidationError(OdemehubError):
    """
    The request reached the gateway and was signed correctly, but its
    contents were refused. No payment was attempted.
    """

    def __init__(self, message: str, errors: dict[str, list[str]] | None = None) -> None:
        super().__init__(message)
        #: The refused fields, each with the reasons it was refused.
        self.errors: dict[str, list[str]] = errors or {}
