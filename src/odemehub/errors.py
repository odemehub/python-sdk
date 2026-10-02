"""Everything the client raises."""

from __future__ import annotations


class OdemehubError(Exception):
    """
    Base class for everything this client raises, so a caller that does not
    care which way a payment failed can catch one thing.
    """


class AuthenticationError(OdemehubError):
    """
    The gateway did not accept the credentials (HTTP 401): the API key is
    not the one issued to the team in the address, the request was not
    signed with the matching secret, or its timestamp is too far from the
    gateway's clock.
    """


class ForbiddenError(OdemehubError):
    """
    The credentials were fine but the team may not do this (HTTP 403): it
    has an unpaid balance, its plan could not be charged or has run out, its
    plan does not include the feature the endpoint belongs to, or the module
    is turned off. The message says which.
    """


class NotFoundError(OdemehubError):
    """
    The record the request names is not there (HTTP 404): no payment,
    order, payment link, subscription or kept card of the team's carries
    that token, or that reference on that channel. Somebody else's record
    is answered the same way.
    """


class RateLimitError(OdemehubError):
    """
    The team sent more requests in a minute than the gateway takes (HTTP
    429): 300 across every endpoint, 60 for the ones that move money or keep
    a card. Nothing was done; the same request can be sent again once the
    wait is over.
    """

    def __init__(self, message: str, retry_after: int | None = None) -> None:
        super().__init__(message)
        #: How many seconds to wait before trying again, as the gateway said
        #: it in ``Retry-After``; None when it did not say.
        self.retry_after = retry_after


class SignatureError(OdemehubError):
    """
    The answer did not carry the signature it should have. It was not
    signed with the secret this client holds, or was signed too long ago,
    so it cannot be shown to have come from the gateway and must not be
    acted on.
    """


class TransportError(OdemehubError):
    """
    The gateway could not be reached at all. Whether the payment was made is
    unknown; the payment record on the gateway says what actually happened.
    """


class UnexpectedResponseError(OdemehubError):
    """
    The gateway answered with something that is neither an outcome nor a
    refusal this client knows how to read, such as an error on its side
    (HTTP 500).
    """

    def __init__(self, message: str, status: int) -> None:
        super().__init__(message)
        self.status = status


class ValidationError(OdemehubError):
    """
    The request reached the gateway and was signed correctly, but its
    contents were refused (HTTP 422). Nothing was done.
    """

    def __init__(self, message: str, errors: dict[str, list[str]] | None = None) -> None:
        super().__init__(message)
        #: The refused fields, each with the reasons it was refused.
        self.errors: dict[str, list[str]] = errors or {}
