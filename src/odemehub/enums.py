"""
The fixed sets of values the gateway speaks in. Each is a ``str`` based
``Enum``, so a member is the very string the gateway sends and compares
equal to it: ``TransactionStatus.SUCCESSFUL == "successful"``.

An answer is read into a member wherever the value is one of the set. A
value the gateway sends that this version does not know yet is kept as the
plain string it arrived as rather than raising, so a newer gateway never
breaks an older client.
"""

from __future__ import annotations

from enum import Enum
from typing import TypeVar

E = TypeVar("E", bound=Enum)


class Currency(str, Enum):
    """The money an amount is in."""

    TRY = "TRY"
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"


class Period(str, Enum):
    """How often a subscription renews."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ANNUALLY = "annually"


class OrderStatus(str, Enum):
    """Where an order stands: open until it is paid, then paid."""

    OPEN = "open"
    PAID = "paid"


class SubscriptionStatus(str, Enum):
    """
    Where a subscription stands. A merchant only ever sends ``CANCELLED``,
    to call one off; the rest follow the payments.
    """

    PENDING = "pending"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class TransactionStatus(str, Enum):
    """The state of one attempt at a payment."""

    STARTED = "started"
    REDIRECTED_TO_SECURE_PAGE = "redirected_to_secure_page"
    RETURNED_FROM_SECURE_PAGE = "returned_from_secure_page"
    #: The provider never answered; the attempt needs looking into.
    TIMEOUT = "timeout"
    FAILED = "failed"
    EXPIRED = "expired"
    SUCCESSFUL = "successful"

    def is_finished(self) -> bool:
        """Whether the attempt is over, one way or the other."""
        return self in (TransactionStatus.SUCCESSFUL, TransactionStatus.FAILED, TransactionStatus.EXPIRED)


class WebhookEvent(str, Enum):
    """
    What a webhook says happened. The first part is what it is about —
    order, payment_link, subscription, transaction — and the webhook carries
    that thing's token.
    """

    ORDER_PAID = "order.paid"
    ORDER_PAYMENT_REFUNDED = "order.payment_refunded"
    ORDER_PAYMENT_CANCELLED = "order.payment_cancelled"
    PAYMENT_LINK_PAID = "payment_link.paid"
    PAYMENT_LINK_PAYMENT_REFUNDED = "payment_link.payment_refunded"
    PAYMENT_LINK_PAYMENT_CANCELLED = "payment_link.payment_cancelled"
    SUBSCRIPTION_ACTIVE = "subscription.active"
    SUBSCRIPTION_PAST_DUE = "subscription.past_due"
    SUBSCRIPTION_CANCELLED = "subscription.cancelled"
    SUBSCRIPTION_ENDED = "subscription.ended"
    SUBSCRIPTION_COMPLETED = "subscription.completed"
    SUBSCRIPTION_PAYMENT_REFUNDED = "subscription.payment_refunded"
    SUBSCRIPTION_PAYMENT_CANCELLED = "subscription.payment_cancelled"
    TRANSACTION_SUCCESSFUL = "transaction.successful"
    TRANSACTION_FAILED = "transaction.failed"
    TRANSACTION_EXPIRED = "transaction.expired"
    TRANSACTION_PAYMENT_REFUNDED = "transaction.payment_refunded"
    TRANSACTION_PAYMENT_CANCELLED = "transaction.payment_cancelled"


class PaymentStatus(str, Enum):
    """What became of a payment's money, which can move on long after the attempt is over."""

    UNPAID = "unpaid"
    PAID = "paid"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class SecurityType(str, Enum):
    """How a payment was made: confirmed at the bank, or charged straight to the card."""

    SECURE = "secure"
    REGULAR = "regular"


class RefundType(str, Enum):
    """Which way money went back out of a payment."""

    CANCEL = "cancel"
    REFUND = "refund"


class RefundStatus(str, Enum):
    """Where a giving back stands."""

    PENDING = "pending"
    SUCCESSFUL = "successful"
    FAILED = "failed"


class CardScheme(str, Enum):
    """The network a card belongs to."""

    VISA = "visa"
    MASTERCARD = "mastercard"
    AMERICAN_EXPRESS = "american_express"
    TROY = "troy"
    DISCOVER = "discover"
    DINERS_CLUB = "diners_club"
    JCB = "jcb"
    UNIONPAY = "unionpay"
    MAESTRO = "maestro"


class CardType(str, Enum):
    """Whether a card's money is lent, drawn from an account or loaded beforehand."""

    CREDIT = "credit"
    DEBIT = "debit"
    PREPAID = "prepaid"


def known(kind: type[E], value: str) -> E | str:
    """The member a value stands for, or the value itself when this version does not know it."""
    try:
        return kind(value)
    except ValueError:
        return value
