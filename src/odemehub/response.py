"""
What the gateway answers with, read out of its JSON body. A field the
gateway left out reads as an empty string, or as ``None`` where the answer
may genuinely not carry it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

Body = dict[str, Any]


def _object(value: Any) -> Body:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value

    return list(value.values()) if isinstance(value, dict) else []


def _string(value: Any) -> str:
    return "" if value is None else _text(value)


def _optional_string(value: Any) -> str | None:
    return None if value is None else _text(value)


def _text(value: Any) -> str:
    if isinstance(value, bool):
        return "1" if value else ""

    return str(value)


def _said(value: Any) -> str | None:
    """A field the gateway left empty reads as nothing rather than as an empty string."""
    return value if isinstance(value, str) and value != "" else None


def _boolean(value: Any) -> bool:
    return bool(value) and value != "0"


def _optional_boolean(value: Any) -> bool | None:
    return None if value is None else _boolean(value)


def _integer(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


@dataclass(frozen=True, kw_only=True)
class Result:
    """
    How a request went, as every answer opens: whether it worked and, only
    when it did not, what went wrong.
    """

    successful: bool
    message: str | None

    @classmethod
    def from_body(cls, body: Body) -> Result:
        result = _object(body.get("result"))

        return cls(
            successful=_boolean(result.get("successful")),
            message=_said(result.get("message")),
        )


@dataclass(frozen=True, kw_only=True)
class Conversion:
    """
    What reached the card, for a payment the merchant's conversion rules
    charged in another money than it was asked in.
    """

    #: What was taken from the card.
    amount: str
    #: The money it was taken in, e.g. TRY.
    currency: str
    #: What a unit of the asked-for money was charged as, with any margin on top.
    rate: str

    @classmethod
    def from_body(cls, conversion: Body) -> Conversion:
        return cls(
            amount=_string(conversion.get("amount")),
            currency=_string(conversion.get("currency")),
            rate=_string(conversion.get("rate")),
        )


@dataclass(frozen=True, kw_only=True)
class SavedCard:
    """A card a customer let the merchant keep."""

    #: The card's token in the gateway, which names it again later.
    token: str
    #: The account the card is kept at; it can only be charged there.
    payment_provider_token: str | None
    holder_name: str
    #: The network the card belongs to, e.g. visa, as far as it is known.
    scheme: str | None
    #: The head of the number: eight digits, or six for a number shorter than sixteen digits.
    first_digits: str
    last_four_digit: str
    expiry_month: str
    expiry_year: str
    #: Whether this is the card the customer pays with unless they say otherwise.
    is_default: bool
    created_at: str | None

    @classmethod
    def from_body(cls, card: Body) -> SavedCard:
        return cls(
            token=_string(card.get("token")),
            payment_provider_token=_optional_string(card.get("payment_provider_token")),
            holder_name=_string(card.get("holder_name")),
            scheme=_optional_string(card.get("scheme")),
            first_digits=_string(card.get("first_digits")),
            last_four_digit=_string(card.get("last_four_digit")),
            expiry_month=_string(card.get("expiry_month")),
            expiry_year=_string(card.get("expiry_year")),
            is_default=_boolean(card.get("is_default")),
            created_at=_optional_string(card.get("created_at")),
        )


@dataclass(frozen=True, kw_only=True)
class Payment:
    """
    The outcome of a payment, as the gateway reports it — whether it answers
    straight away or posts the outcome back once the customer is home from
    their bank. The two are the same shape, so a merchant reads them the
    same way: how it went, which payment it was, and whose.

    A payment that was turned down is an outcome like any other and arrives
    here; only answers that were never a payment outcome are raised.
    """

    result: Result
    #: The payment's token in the gateway, which names it again for a refund.
    transaction_token: str
    #: The channel the payment came in on.
    channel_token: str
    #: The reference the payment is known by in the calling system.
    channel_reference: str
    #: The merchant's own key for the customer the payment was made for.
    customer_channel_reference: str
    #: The card the payment kept, for a payment that asked for one to be
    #: kept. It is None while nothing was kept: because the payment did not
    #: go through, because the provider handed nothing back, or because the
    #: payment never asked.
    saved_card: SavedCard | None = None
    #: What reached the card, for a payment the merchant's conversion rules
    #: charged in another money than it was asked in; None for a payment
    #: charged as it was asked.
    conversion: Conversion | None = None

    @classmethod
    def from_body(cls, body: Body) -> Payment:
        return cls(**cls._parts(body))

    @staticmethod
    def _parts(body: Body) -> dict[str, Any]:
        """
        The pieces every payment outcome is read out of, so a kind of
        payment that says more can add to them rather than read the body again.
        """
        transaction = _object(body.get("transaction"))
        saved_card = body.get("saved_card")
        conversion = body.get("conversion")

        return {
            "result": Result.from_body(body),
            "transaction_token": _string(transaction.get("token")),
            "channel_token": _string(transaction.get("channel_token")),
            "channel_reference": _string(transaction.get("channel_reference")),
            "customer_channel_reference": _string(_object(body.get("customer")).get("channel_reference")),
            "saved_card": SavedCard.from_body(saved_card) if isinstance(saved_card, dict) else None,
            "conversion": Conversion.from_body(conversion) if isinstance(conversion, dict) else None,
        }


@dataclass(frozen=True, kw_only=True)
class SecurePayment(Payment):
    """
    A 3D payment that has been started. A successful answer is not a settled
    payment: the customer still has to be sent to ``redirect_url``.
    """

    #: Where the customer has to be sent. Always there when the payment started.
    redirect_url: str | None = None

    @classmethod
    def from_body(cls, body: Body) -> SecurePayment:
        return cls(
            **cls._parts(body),
            redirect_url=_said(_object(body.get("result")).get("redirect_url")),
        )


@dataclass(frozen=True, kw_only=True)
class RegularPayment(Payment):
    """A payment charged straight to the card. A successful answer is a settled payment."""


@dataclass(frozen=True, kw_only=True)
class GiveBack(Payment):
    """Money given back out of a payment: a cancellation or a refund."""

    #: Which of the two it was: a cancellation or a refund.
    type: str = ""
    #: How much actually went back, whether or not it was asked for by name.
    amount: str | None = None

    @classmethod
    def from_body(cls, body: Body) -> GiveBack:
        refund = _object(body.get("refund"))

        return cls(
            **cls._parts(body),
            type=_string(refund.get("type")),
            amount=_optional_string(refund.get("amount")),
        )


@dataclass(frozen=True, kw_only=True)
class TransactionWebhook(Payment):
    """
    Word the gateway sent about a payment the merchant started and the
    customer finished — or did not — at their bank. It is the same answer
    ``retrieve_payment()`` gives, with the state reached on top: the customer
    may have closed the page before their browser could bring the outcome
    back, and then this is the only word the merchant hears.
    """

    #: The state reached: successful, failed or expired.
    event: str

    def is_successful(self) -> bool:
        """Whether the payment went through."""
        return self.event == "successful"

    def is_failed(self) -> bool:
        """Whether the bank turned the payment away."""
        return self.event == "failed"

    def is_expired(self) -> bool:
        """Whether the customer never opened the bank's page in time, so the payment was closed without being tried."""
        return self.event == "expired"

    @classmethod
    def from_body(cls, body: Body) -> TransactionWebhook:
        return cls(event=_string(body.get("event")), **cls._parts(body))


@dataclass(frozen=True, kw_only=True)
class OrderItem:
    """One line of what an order is made up of, as it was written down when the order was opened."""

    #: The merchant's own key for what is on the line.
    channel_reference: str
    name: str
    #: The picture the line is shown with, if any.
    image: str | None
    quantity: int
    #: The price of one, as digits with the kurus behind a point.
    unit_amount: str
    #: The tax included in the price, as a percentage; None for a line with no rate.
    tax_rate: str | None
    #: The tax the line comes to; None for a line with no rate.
    tax_amount: str | None

    @classmethod
    def from_body(cls, item: Body) -> OrderItem:
        return cls(
            channel_reference=_string(item.get("channel_reference")),
            name=_string(item.get("name")),
            image=_optional_string(item.get("image")),
            quantity=_integer(item.get("quantity")),
            unit_amount=_string(item.get("unit_amount")),
            tax_rate=_optional_string(item.get("tax_rate")),
            tax_amount=_optional_string(item.get("tax_amount")),
        )


@dataclass(frozen=True, kw_only=True)
class Order:
    """
    An order as the gateway keeps it: what is being paid for, what it comes
    to, where it stands and — once it is paid — the payment that paid it. The
    same answer comes back whether the order has just been opened, asked
    after, or the gateway is telling the merchant it was paid.
    """

    result: Result
    #: The order's token in the gateway; name it to ask after it later.
    token: str
    #: The channel the order was opened on.
    channel_token: str
    #: The number the order is known by in the calling system.
    channel_reference: str
    description: str | None
    #: Where the order stands: open until it is paid, then paid.
    status: str
    #: What the order is made up of.
    items: list[OrderItem]
    #: What the lines come to before tax; None when no line carried a rate.
    subtotal: str | None
    #: The tax the order carries; None when no line carried a rate.
    tax_amount: str | None
    #: What the order comes to, added up from its lines by the gateway.
    amount: str
    currency: str
    #: Whether it was paid in the test environment; None until it is paid.
    is_test: bool | None
    created_at: str | None
    #: Where the customer pays, while the order is still open; None once it is paid.
    checkout_url: str | None
    #: The token of the payment that paid the order, which names it again for a refund; None while it is open.
    transaction_token: str | None
    #: The merchant's own key for the customer the order is for; None for an order opened without one.
    customer_channel_reference: str | None

    def is_paid(self) -> bool:
        """Whether the order has been paid."""
        return self.status == "paid"

    @classmethod
    def from_body(cls, body: Body) -> Order:
        order = _object(body.get("order"))
        transaction = _object(order.get("transaction"))

        return cls(
            result=Result.from_body(body),
            token=_string(order.get("token")),
            channel_token=_string(order.get("channel_token")),
            channel_reference=_string(order.get("channel_reference")),
            description=_said(order.get("description")),
            status=_string(order.get("status")),
            items=[OrderItem.from_body(_object(item)) for item in _list(order.get("items"))],
            subtotal=_said(order.get("subtotal")),
            tax_amount=_said(order.get("tax_amount")),
            amount=_string(order.get("amount")),
            currency=_string(order.get("currency")),
            is_test=_optional_boolean(order.get("is_test")),
            created_at=_said(order.get("created_at")),
            checkout_url=_said(order.get("checkout_url")),
            transaction_token=_said(transaction.get("token")),
            customer_channel_reference=_said(_object(body.get("customer")).get("channel_reference")),
        )


@dataclass(frozen=True, kw_only=True)
class OrderWebhook:
    """
    Word the gateway sent about one of the merchant's orders: that it was
    paid, with the payment that paid it. An order is only ever told of once;
    an attempt that fails leaves it open and the customer trying again.
    """

    #: The state reached: paid.
    event: str
    #: The order as it stands now, with the payment that paid it.
    order: Order

    def is_paid(self) -> bool:
        """Whether the order has been paid, which is the one thing said here."""
        return self.event == "paid"

    @classmethod
    def from_body(cls, body: Body) -> OrderWebhook:
        return cls(event=_string(body.get("event")), order=Order.from_body(body))


@dataclass(frozen=True, kw_only=True)
class Transaction:
    """
    One attempt at a payment, as the gateway lists it: enough to tell the
    attempts apart and see where each got to. Where it stands is said twice
    on purpose — the attempt's own state, and what became of the money, which
    can move on to refunded long after the attempt is over.
    """

    #: The payment's token in the gateway, which names it again to ask after or give back.
    token: str
    #: The channel the payment came in on.
    channel_token: str
    #: The reference the payment was made under in the calling system.
    channel_reference: str
    #: The attempt's state: started, redirected_to_secure_page, returned_from_secure_page, failed, expired or successful.
    status: str
    #: What became of the money: unpaid, paid, cancelled, refunded or partially_refunded.
    payment_status: str
    #: How it was made: secure (confirmed at the bank) or regular.
    security_type: str
    #: What the card was charged, with the kurus behind a point.
    amount: str
    #: What was being sold, before anything added for instalments.
    base_amount: str
    currency: str
    installment_number: int
    #: Whether it was made in the test environment.
    is_test: bool
    #: What the provider called the refusal, for an attempt that failed.
    error_code: str | None
    #: Why it failed, written for a person.
    error_message: str | None
    created_at: str | None
    #: The merchant's own key for the customer; None for a payer the merchant never named.
    customer_channel_reference: str | None
    #: What reached the card when it was charged in another money; None when charged as asked.
    conversion: Conversion | None
    #: The token of the order this attempt was at, when it was at one.
    order_token: str | None
    #: The token of the subscription this attempt paid a period of, when it did.
    subscription_token: str | None

    def is_successful(self) -> bool:
        """Whether the attempt went through."""
        return self.status == "successful"

    @classmethod
    def from_body(cls, transaction: Body) -> Transaction:
        conversion = transaction.get("conversion")

        return cls(
            token=_string(transaction.get("token")),
            channel_token=_string(transaction.get("channel_token")),
            channel_reference=_string(transaction.get("channel_reference")),
            status=_string(transaction.get("status")),
            payment_status=_string(transaction.get("payment_status")),
            security_type=_string(transaction.get("security_type")),
            amount=_string(transaction.get("amount")),
            base_amount=_string(transaction.get("base_amount")),
            currency=_string(transaction.get("currency")),
            installment_number=_integer(transaction.get("installment_number")) or 1,
            is_test=_boolean(transaction.get("is_test")),
            error_code=_said(transaction.get("error_code")),
            error_message=_said(transaction.get("error_message")),
            created_at=_said(transaction.get("created_at")),
            customer_channel_reference=_said(_object(transaction.get("customer")).get("channel_reference")),
            conversion=Conversion.from_body(conversion) if isinstance(conversion, dict) else None,
            order_token=_said(_object(transaction.get("order")).get("token")),
            subscription_token=_said(_object(transaction.get("subscription")).get("token")),
        )


@dataclass(frozen=True, kw_only=True)
class Transactions:
    """
    Every attempt made under one of the merchant's own numbers on a channel,
    oldest first, so they read as the attempts were made.
    """

    result: Result
    transactions: list[Transaction]

    def successful(self) -> Transaction | None:
        """The attempt that went through, if one did."""
        return next((transaction for transaction in self.transactions if transaction.is_successful()), None)

    @classmethod
    def from_body(cls, body: Body) -> Transactions:
        return cls(
            result=Result.from_body(body),
            transactions=[Transaction.from_body(_object(transaction)) for transaction in _list(body.get("transactions"))],
        )


@dataclass(frozen=True, kw_only=True)
class Product:
    """A product in the merchant's catalogue at the gateway."""

    result: Result
    #: The channel the product is sold on.
    channel_token: str
    #: The key the product is known by in the calling system.
    channel_reference: str
    name: str
    #: The address of the picture the checkout shows it with, if it has one.
    image: str | None
    #: simple or recurring.
    type: str
    #: The price of one, as digits with the kurus behind a point.
    amount: str
    currency: str
    #: The tax included in the price, as a percentage.
    tax_rate: str
    #: monthly or annually for a recurring product; None for a simple one.
    period: str | None
    #: Whether it is on sale.
    is_active: bool

    @classmethod
    def from_body(cls, body: Body) -> Product:
        product = _object(body.get("product"))

        return cls(
            result=Result.from_body(body),
            channel_token=_string(product.get("channel_token")),
            channel_reference=_string(product.get("channel_reference")),
            name=_string(product.get("name")),
            image=_optional_string(product.get("image")),
            type=_string(product.get("type")),
            amount=_string(product.get("amount")),
            currency=_string(product.get("currency")),
            tax_rate=_string(product.get("tax_rate")),
            period=_optional_string(product.get("period")),
            is_active=_boolean(product.get("is_active")),
        )


@dataclass(frozen=True, kw_only=True)
class Installment:
    """One way an amount may be paid off on a card."""

    number: int
    #: What is charged each month, as digits with the kurus behind a point.
    amount: str
    #: What the card is charged in all, the same way.
    total: str

    @classmethod
    def from_body(cls, installment: Body) -> Installment:
        return cls(
            number=_integer(installment.get("number")),
            amount=_string(installment.get("amount")),
            total=_string(installment.get("total")),
        )


@dataclass(frozen=True, kw_only=True)
class Bin:
    """
    What the gateway's provider knows about a card by the head of its
    number, and how an amount may be paid off on it.
    """

    result: Result
    #: The digits the question was asked with.
    bin: str
    #: The institution that issued the card.
    issuer_name: str | None
    issuer_code: str | None
    #: The scheme the card is issued on, e.g. visa, as the issuer reports it.
    scheme: str | None
    #: Whether the money is lent, drawn from an account or loaded beforehand: credit, debit or prepaid.
    type: str | None
    #: The programme the card is sold under, such as Bonus or Maximum.
    program: str | None
    #: Whether the card belongs to a company rather than to a person.
    is_commercial: bool | None
    #: The ways the amount may be paid off, a single payment first.
    installments: list[Installment]

    @classmethod
    def from_body(cls, body: Body) -> Bin:
        card = _object(body.get("card"))

        return cls(
            result=Result.from_body(body),
            bin=_string(card.get("bin")),
            issuer_name=_optional_string(card.get("issuer_name")),
            issuer_code=_optional_string(card.get("issuer_code")),
            scheme=_optional_string(card.get("scheme")),
            type=_optional_string(card.get("type")),
            program=_optional_string(card.get("program")),
            is_commercial=_optional_boolean(card.get("is_commercial")),
            installments=[Installment.from_body(_object(item)) for item in _list(body.get("installments"))],
        )


@dataclass(frozen=True, kw_only=True)
class KeptCard:
    """A card kept, made the default or let go of."""

    result: Result
    #: The card as it now stands, or None when there was none to keep.
    saved_card: SavedCard | None
    #: The merchant's own key for the customer the card belongs to.
    customer_channel_reference: str

    @classmethod
    def from_body(cls, body: Body) -> KeptCard:
        saved_card = body.get("saved_card")

        return cls(
            result=Result.from_body(body),
            saved_card=SavedCard.from_body(saved_card) if isinstance(saved_card, dict) else None,
            customer_channel_reference=_string(_object(body.get("customer")).get("channel_reference")),
        )


@dataclass(frozen=True, kw_only=True)
class KeptCards:
    """The cards a customer let the merchant keep, the default one first."""

    result: Result
    saved_cards: list[SavedCard]
    #: The merchant's own key for the customer the cards belong to.
    customer_channel_reference: str

    @classmethod
    def from_body(cls, body: Body) -> KeptCards:
        return cls(
            result=Result.from_body(body),
            saved_cards=[SavedCard.from_body(_object(card)) for card in _list(body.get("saved_cards"))],
            customer_channel_reference=_string(_object(body.get("customer")).get("channel_reference")),
        )


@dataclass(frozen=True, kw_only=True)
class SubscriptionItem:
    """One line of what a subscription is for."""

    #: The merchant's own key for the product.
    channel_reference: str
    name: str
    #: The picture shown for the line: the one named when the subscription was opened, or else the product's.
    image: str | None
    quantity: int
    #: The price of one, as digits with the kurus behind a point.
    unit_amount: str
    #: The tax included in the price, as a percentage.
    tax_rate: str | None

    @classmethod
    def from_body(cls, item: Body) -> SubscriptionItem:
        return cls(
            channel_reference=_string(item.get("channel_reference")),
            name=_string(item.get("name")),
            image=_optional_string(item.get("image")),
            quantity=_integer(item.get("quantity")),
            unit_amount=_string(item.get("unit_amount")),
            tax_rate=_optional_string(item.get("tax_rate")),
        )


@dataclass(frozen=True, kw_only=True)
class Subscription:
    """
    A subscription as it stands: what it is for, the period it is on and
    whether that period has been paid for.
    """

    result: Result
    #: The subscription's token in the gateway; name it to ask after it later.
    token: str
    #: The channel the subscription was opened on.
    channel_token: str
    #: The key the subscription is known by in the calling system.
    channel_reference: str
    #: What is subscribed to.
    items: list[SubscriptionItem]
    #: Where it stands: pending, active, past_due or cancelled.
    status: str
    #: How often a period comes round: monthly or annually.
    period: str
    #: What the period it is on costs, with the kurus behind a point.
    amount: str
    currency: str
    #: When the period it is on began, once it has been paid for.
    starts_at: str | None
    #: When the period it is on runs out, which is when the next is charged.
    ends_at: str | None
    #: When the period it is on was paid for, if it has been.
    paid_at: str | None
    #: The day it was called off on, if it has been.
    cancelled_at: str | None
    #: Where the customer pays the period it is on, while that is still owed.
    checkout_url: str | None
    #: Whether it was paid for in the test environment; None until the first payment.
    is_test: bool | None
    #: The merchant's own key for the customer, answered when the subscription is opened.
    customer_channel_reference: str | None

    def is_active(self) -> bool:
        """
        Whether the subscription is being paid for: a customer who has been
        through the checkout and whose card has not since been turned away.
        """
        return self.status == "active"

    def is_pending(self) -> bool:
        """
        Whether the first period has yet to be paid for. A subscription stays
        here until the customer has been through the checkout.
        """
        return self.status == "pending"

    def is_past_due(self) -> bool:
        """
        Whether a period has been left unpaid: the card was tried and turned
        away every time, and the customer has been asked to pay it themselves
        at ``checkout_url``.
        """
        return self.status == "past_due"

    def is_cancelled(self) -> bool:
        """
        Whether it is over. A subscription that has been called off but is
        still serving days that were paid for is not over yet — read
        ``cancelled_at`` for that.
        """
        return self.status == "cancelled"

    @classmethod
    def from_body(cls, body: Body) -> Subscription:
        subscription = _object(body.get("subscription"))

        return cls(
            result=Result.from_body(body),
            token=_string(subscription.get("token")),
            channel_token=_string(subscription.get("channel_token")),
            channel_reference=_string(subscription.get("channel_reference")),
            items=[SubscriptionItem.from_body(_object(item)) for item in _list(subscription.get("items"))],
            status=_string(subscription.get("status")),
            period=_string(subscription.get("period")),
            amount=_string(subscription.get("amount")),
            currency=_string(subscription.get("currency")),
            starts_at=_said(subscription.get("starts_at")),
            ends_at=_said(subscription.get("ends_at")),
            paid_at=_said(subscription.get("paid_at")),
            cancelled_at=_said(subscription.get("cancelled_at")),
            checkout_url=_said(subscription.get("checkout_url")),
            is_test=_optional_boolean(subscription.get("is_test")),
            customer_channel_reference=_said(_object(body.get("customer")).get("channel_reference")),
        )


@dataclass(frozen=True, kw_only=True)
class SubscriptionWebhook:
    """
    Word the gateway sent about a subscription: the state it has reached and
    the subscription as it stands now.
    """

    #: The state reached: active, past_due, cancelled or ended.
    event: str
    #: The subscription as it stands now.
    subscription: Subscription

    def is_active(self) -> bool:
        """
        Whether the subscription is being paid for: the customer has just
        paid a period, whether the first or a later one.
        """
        return self.event == "active"

    def is_past_due(self) -> bool:
        """
        Whether a period was left unpaid. The card was tried and turned away
        every time, and the customer has been asked to pay it themselves at
        the subscription's ``checkout_url``.
        """
        return self.event == "past_due"

    def is_cancelled(self) -> bool:
        """
        Whether the subscription has been called off. Nothing more will be
        charged, but the customer is served until ``ends_at``.
        """
        return self.event == "cancelled"

    def is_ended(self) -> bool:
        """
        Whether it is over: the days that were paid for have run out and the
        customer's access can be closed.
        """
        return self.event == "ended"

    @classmethod
    def from_body(cls, body: Body) -> SubscriptionWebhook:
        return cls(
            event=_string(body.get("event")),
            subscription=Subscription.from_body(body),
        )
