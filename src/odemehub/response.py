"""
What the gateway answers with, read out of its JSON body. A field the
gateway left out reads as an empty string, or as ``None`` where the answer
may genuinely not carry it. The answers are read defensively: one
unexpected key never hides the outcome of a payment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

from .enums import (
    CardScheme,
    CardType,
    Currency,
    OrderStatus,
    PaymentStatus,
    Period,
    RefundType,
    SecurityType,
    SubscriptionStatus,
    TransactionStatus,
    WebhookEvent,
    known,
)

Body = dict[str, Any]
E = TypeVar("E", bound=Enum)


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
    if value is None or isinstance(value, (dict, list)):
        return None

    text = _text(value)

    return text if text != "" else None


def _boolean(value: Any) -> bool:
    return bool(value) and value != "0"


def _optional_boolean(value: Any) -> bool | None:
    return None if value is None else _boolean(value)


def _integer(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _optional_integer(value: Any) -> int | None:
    return None if value is None else _integer(value)


def _known(kind: type[E], value: Any) -> E | str:
    """A value of one of the fixed sets: its member, or the plain string for one this version does not know."""
    return known(kind, _string(value))


def _optional_known(kind: type[E], value: Any) -> E | str | None:
    """The same, for a value the gateway may have left unsaid."""
    text = _said(value)

    return None if text is None else known(kind, text)


@dataclass(frozen=True, kw_only=True)
class Result:
    """
    How a request went, as every answer opens: whether it worked and, only
    when it did not, what went wrong, in Turkish.
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
    charged in another money than it was asked in: 100 USD asked for,
    3450.00 TRY taken from the card. The payment's own amount stays what
    was asked for.
    """

    #: What was taken from the card.
    amount: str
    #: The money it was taken in.
    currency: Currency | str
    #: What a unit of the asked-for money was charged as, with any margin on top.
    rate: str

    @classmethod
    def from_body(cls, conversion: Body) -> Conversion:
        return cls(
            amount=_string(conversion.get("amount")),
            currency=_known(Currency, conversion.get("currency")),
            rate=_string(conversion.get("rate")),
        )


@dataclass(frozen=True, kw_only=True)
class Address:
    """
    An address as the gateway answers it: only the fields that were said.
    A payment's billing address carries the person fields alone; an order's
    or a subscription's carries the company fields too, when the customer
    buys for one.
    """

    firstname: str | None
    lastname: str | None
    email: str | None
    phone: str | None
    address: str | None
    district: str | None
    province: str | None
    country: str | None
    company_title: str | None
    tax_number: str | None
    tax_office: str | None

    @classmethod
    def from_body(cls, address: Body) -> Address:
        return cls(
            firstname=_said(address.get("firstname")),
            lastname=_said(address.get("lastname")),
            email=_said(address.get("email")),
            phone=_said(address.get("phone")),
            address=_said(address.get("address")),
            district=_said(address.get("district")),
            province=_said(address.get("province")),
            country=_said(address.get("country")),
            company_title=_said(address.get("company_title")),
            tax_number=_said(address.get("tax_number")),
            tax_office=_said(address.get("tax_office")),
        )


@dataclass(frozen=True, kw_only=True)
class PaymentCustomer:
    """
    Who a payment was made for, as the payment froze it: the merchant's own
    key for them, if the payment named one, and the billing address as it
    was at the time.
    """

    #: The merchant's own key; None for a payer the merchant never named.
    reference: str | None
    billing_address: Address

    @classmethod
    def from_body(cls, customer: Body) -> PaymentCustomer:
        return cls(
            reference=_said(customer.get("reference")),
            billing_address=Address.from_body(_object(customer.get("billing_address"))),
        )


@dataclass(frozen=True, kw_only=True)
class NamedCustomer:
    """
    Who an order or a subscription is for, as the gateway holds them: the
    merchant's own key for them, where they are billed, and where the goods
    go when somebody said. The key is None for an order opened for somebody
    the team does not keep; the addresses are None until somebody gives them.
    """

    reference: str | None
    billing_address: Address | None
    shipping_address: Address | None

    @classmethod
    def from_body(cls, customer: Body) -> NamedCustomer:
        billing = customer.get("billing_address")
        shipping = customer.get("shipping_address")

        return cls(
            reference=_said(customer.get("reference")),
            billing_address=Address.from_body(billing) if isinstance(billing, dict) else None,
            shipping_address=Address.from_body(shipping) if isinstance(shipping, dict) else None,
        )


@dataclass(frozen=True, kw_only=True)
class SavedCardCustomer:
    """The customer a kept card belongs to, by the merchant's own key for them, which the card is found by again."""

    reference: str

    @classmethod
    def from_body(cls, customer: Body) -> SavedCardCustomer:
        return cls(reference=_string(customer.get("reference")))


@dataclass(frozen=True, kw_only=True)
class SavedCard:
    """
    A card a customer let the merchant keep, as the gateway shows it: enough
    to draw the card and to name it again, and nothing that could charge it.
    """

    #: The card's token in the gateway, which names it again later.
    token: str
    #: The account the card is kept at; it can only be charged there.
    payment_provider_token: str
    holder_name: str
    #: The network the card belongs to, as far as it is known.
    scheme: CardScheme | str | None
    #: The head of the number: eight digits, or six for a number shorter than sixteen digits.
    first_digits: str
    last_four_digit: str
    expiry_month: str
    expiry_year: str
    #: Whether this is the card the customer pays with unless they say otherwise.
    is_default: bool
    created_at: str | None
    #: Who the card is kept for; listed cards only, the other answers carry it beside the card.
    customer: SavedCardCustomer | None = None

    @classmethod
    def from_body(cls, card: Body) -> SavedCard:
        customer = card.get("customer")

        return cls(
            token=_string(card.get("token")),
            payment_provider_token=_string(card.get("payment_provider_token")),
            holder_name=_string(card.get("holder_name")),
            scheme=_optional_known(CardScheme, card.get("scheme")),
            first_digits=_string(card.get("first_digits")),
            last_four_digit=_string(card.get("last_four_digit")),
            expiry_month=_string(card.get("expiry_month")),
            expiry_year=_string(card.get("expiry_year")),
            is_default=_boolean(card.get("is_default")),
            created_at=_said(card.get("created_at")),
            customer=SavedCardCustomer.from_body(customer) if isinstance(customer, dict) else None,
        )


@dataclass(frozen=True, kw_only=True)
class TransactionReference:
    """
    A payment named, and nothing more: its token in the gateway, the
    reference it was made under and what became of its money. It is how a paid order points at the payment that paid it, and
    shows whether that money has since gone back.
    """

    #: The payment's token in the gateway, which names it again to ask after or give back.
    token: str
    #: The reference the payment was made under in the calling system.
    reference: str
    #: What became of the money: paid, cancelled, refunded, partially refunded.
    payment_status: PaymentStatus | str | None = None

    @classmethod
    def from_body(cls, transaction: Body) -> TransactionReference:
        return cls(
            token=_string(transaction.get("token")),
            reference=_string(transaction.get("reference")),
            payment_status=_optional_known(PaymentStatus, transaction.get("payment_status")),
        )


@dataclass(frozen=True, kw_only=True)
class PaymentTransaction:
    """
    The payment a payment answer is about, said in full: which one it is,
    where it stands, what became of its money and what it was charged. A
    payment made at an order, a payment link or a subscription names it, so
    a webhook about one of them can be checked against the payment it names.
    """

    #: The payment's token in the gateway, which names it again to ask after or give back.
    token: str
    #: The reference the payment was made under in the calling system.
    reference: str
    #: The attempt's state.
    status: TransactionStatus | str
    #: What became of the money.
    payment_status: PaymentStatus | str
    #: How it was made: confirmed at the bank or charged straight to the card.
    security_type: SecurityType | str
    #: What the card was charged, with the kurus behind a point.
    amount: str
    #: What was being sold, before anything added for instalments.
    base_amount: str
    currency: Currency | str
    installment_number: int
    #: Whether it was made in the test environment.
    is_test: bool
    created_at: str | None
    #: The order the payment was made at, when it was made at one.
    order_token: str | None = None
    #: The payment link the payment was made on, when it was made on one.
    payment_link_token: str | None = None
    #: The subscription whose renewal the payment paid, when it paid one.
    subscription_token: str | None = None

    def is_successful(self) -> bool:
        """Whether the payment went through."""
        return self.status == TransactionStatus.SUCCESSFUL

    @classmethod
    def from_body(cls, transaction: Body) -> PaymentTransaction:
        return cls(
            token=_string(transaction.get("token")),
            reference=_string(transaction.get("reference")),
            status=_known(TransactionStatus, transaction.get("status")),
            payment_status=_known(PaymentStatus, transaction.get("payment_status")),
            security_type=_known(SecurityType, transaction.get("security_type")),
            amount=_string(transaction.get("amount")),
            base_amount=_string(transaction.get("base_amount")),
            currency=_known(Currency, transaction.get("currency")),
            installment_number=_integer(transaction.get("installment_number")) or 1,
            is_test=_boolean(transaction.get("is_test")),
            created_at=_said(transaction.get("created_at")),
            order_token=_said(_object(transaction.get("order")).get("token")),
            payment_link_token=_said(_object(transaction.get("payment_link")).get("token")),
            subscription_token=_said(_object(transaction.get("subscription")).get("token")),
        )


@dataclass(frozen=True, kw_only=True)
class Payment:
    """
    The outcome of a payment, as the gateway reports it — whether it answers
    straight away or is asked after. The two are the same shape, so a
    merchant reads them the same way: how it went, which payment it was, and
    whose.

    A payment that was turned down is an outcome like any other and arrives
    here with ``result.successful`` False; only answers that were never a
    payment outcome are raised.
    """

    result: Result
    #: Which payment it is, where it stands and what it was charged.
    transaction: PaymentTransaction
    #: Who it was made for, as the payment froze them.
    customer: PaymentCustomer | None
    #: What reached the card, for a payment the merchant's conversion rules
    #: charged in another money than it was asked in; None for a payment
    #: charged as it was asked.
    conversion: Conversion | None = None
    #: The card the payment kept, for a payment that asked for one to be
    #: kept. It is None while nothing was kept: because the payment did not
    #: go through, because the provider handed nothing back, because a 3D
    #: payment has not been finished yet, or because the payment never asked.
    saved_card: SavedCard | None = None

    @classmethod
    def from_body(cls, body: Body) -> Payment:
        return cls(**cls._parts(body))

    @staticmethod
    def _parts(body: Body) -> dict[str, Any]:
        """
        The pieces every payment outcome is read out of, so a kind of
        payment that says more can add to them rather than read the body again.
        """
        customer = body.get("customer")
        conversion = body.get("conversion")
        saved_card = body.get("saved_card")

        return {
            "result": Result.from_body(body),
            "transaction": PaymentTransaction.from_body(_object(body.get("transaction"))),
            "customer": PaymentCustomer.from_body(customer) if isinstance(customer, dict) else None,
            "conversion": Conversion.from_body(conversion) if isinstance(conversion, dict) else None,
            "saved_card": SavedCard.from_body(saved_card) if isinstance(saved_card, dict) else None,
        }


@dataclass(frozen=True, kw_only=True)
class SecurePayment(Payment):
    """
    A 3D payment that has been started. A successful answer is not a settled
    payment: the customer still has to be sent to ``redirect_url``, which is
    good for fifteen minutes and opens once.
    """

    #: Where the customer has to be sent. There whenever the payment started.
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
class Refund:
    """
    What went back out of a payment: which of the two ways it went, and how
    much. A cancellation is always for the whole payment; a refund is for
    what was asked, or everything the payment had left when nothing was.
    """

    #: Which of the two it was.
    type: RefundType | str
    #: How much actually went back, as digits with the kurus behind a point.
    amount: str

    @classmethod
    def from_body(cls, refund: Body) -> Refund:
        return cls(
            type=_known(RefundType, refund.get("type")),
            amount=_string(refund.get("amount")),
        )


@dataclass(frozen=True, kw_only=True)
class GiveBack(Payment):
    """
    What became of money asked back out of a payment: a cancellation or a
    refund. An attempt the provider turned down is an outcome like any other
    and arrives here with ``result.successful`` False.
    """

    #: What went back; None when the gateway answered without it.
    refund: Refund | None = None

    @classmethod
    def from_body(cls, body: Body) -> GiveBack:
        refund = body.get("refund")

        return cls(
            **cls._parts(body),
            refund=Refund.from_body(refund) if isinstance(refund, dict) else None,
        )


@dataclass(frozen=True, kw_only=True)
class Webhook:
    """
    A word the gateway sent about something of the merchant's: an order
    paid, a link paid, a subscription's state changed, a payment finished,
    money given back. It goes to the addresses the team set for the event
    under Webhook in the panel, as plain JSON signed the way every answer is.

    It is a notification, never the answer. It names the thing by token —
    and the payment beside it when money moved — and nothing else; ask the
    gateway what became of it (``retrieve_orders``, ``retrieve_payment_links``,
    ``retrieve_subscriptions``, ``retrieve_payments``, by its token) and act
    on that. A word may arrive more than once; the id tells the copies apart.
    """

    #: The word's own token, the same on every delivery of it.
    id: str
    event: WebhookEvent | str
    created_at: str | None
    #: The order, for the ``order.*`` events.
    order_token: str | None
    #: The payment link, for the ``payment_link.*`` events.
    payment_link_token: str | None
    #: The subscription, for the ``subscription.*`` events.
    subscription_token: str | None
    #: The payment: for the ``transaction.*`` events, and beside the thing wherever money moved at it.
    transaction_token: str | None

    @classmethod
    def from_body(cls, body: Body) -> Webhook:
        return cls(
            id=_string(body.get("id")),
            event=_known(WebhookEvent, body.get("event")),
            created_at=_said(body.get("created_at")),
            order_token=_said(_object(body.get("order")).get("token")),
            payment_link_token=_said(_object(body.get("payment_link")).get("token")),
            subscription_token=_said(_object(body.get("subscription")).get("token")),
            transaction_token=_said(_object(body.get("transaction")).get("token")),
        )


@dataclass(frozen=True, kw_only=True)
class Transaction:
    """
    One attempt at a payment, as the gateway lists it: enough to tell the
    attempts apart and see where each got to. Where it stands is said twice
    on purpose — the attempt's own state, and what became of the money, which
    can move on to refunded long after the attempt is over. An attempt made
    on the checkout page says which order, link or subscription it was for.
    """

    #: The payment's token in the gateway, which names it again to ask after or give back.
    token: str
    #: The reference the payment was made under in the calling system.
    reference: str
    #: The attempt's state.
    status: TransactionStatus | str
    #: What became of the money.
    payment_status: PaymentStatus | str
    #: How it was made: confirmed at the bank or charged straight to the card.
    security_type: SecurityType | str
    #: What the card was charged, with the kurus behind a point.
    amount: str
    #: What was being sold, before anything added for instalments.
    base_amount: str
    currency: Currency | str
    installment_number: int
    #: Whether it was made in the test environment.
    is_test: bool
    #: What the provider called the refusal, for an attempt that failed.
    error_code: str | None
    #: Why it failed, written for a person.
    error_message: str | None
    created_at: str | None
    #: Who it was made for, as the payment froze them.
    customer: PaymentCustomer | None
    #: What reached the card when it was charged in another money; None when charged as asked.
    conversion: Conversion | None
    #: The token of the order this attempt was at, when it was at one.
    order_token: str | None
    #: The token of the payment link this attempt was at, when it was at one.
    payment_link_token: str | None
    #: The token of the subscription this attempt paid a renewal of, when it did.
    subscription_token: str | None
    #: The card the payment kept, when it asked to keep one and went through; None otherwise.
    saved_card: SavedCard | None = None

    def is_successful(self) -> bool:
        """Whether the attempt went through."""
        return self.status == TransactionStatus.SUCCESSFUL

    def is_finished(self) -> bool:
        """
        Whether the attempt is over, one way or the other. An attempt the
        provider never answered (timeout) is not, and needs looking into.
        """
        return isinstance(self.status, TransactionStatus) and self.status.is_finished()

    @classmethod
    def from_body(cls, transaction: Body) -> Transaction:
        customer = transaction.get("customer")
        conversion = transaction.get("conversion")

        return cls(
            token=_string(transaction.get("token")),
            reference=_string(transaction.get("reference")),
            status=_known(TransactionStatus, transaction.get("status")),
            payment_status=_known(PaymentStatus, transaction.get("payment_status")),
            security_type=_known(SecurityType, transaction.get("security_type")),
            amount=_string(transaction.get("amount")),
            base_amount=_string(transaction.get("base_amount")),
            currency=_known(Currency, transaction.get("currency")),
            installment_number=_integer(transaction.get("installment_number")) or 1,
            is_test=_boolean(transaction.get("is_test")),
            error_code=_said(transaction.get("error_code")),
            error_message=_said(transaction.get("error_message")),
            created_at=_said(transaction.get("created_at")),
            customer=PaymentCustomer.from_body(customer) if isinstance(customer, dict) else None,
            conversion=Conversion.from_body(conversion) if isinstance(conversion, dict) else None,
            order_token=_said(_object(transaction.get("order")).get("token")),
            payment_link_token=_said(_object(transaction.get("payment_link")).get("token")),
            subscription_token=_said(_object(transaction.get("subscription")).get("token")),
            saved_card=SavedCard.from_body(transaction["saved_card"]) if isinstance(transaction.get("saved_card"), dict) else None,
        )


@dataclass(frozen=True, kw_only=True)
class PaymentList:
    """
    Payments asked after, each with its state, amount, customer and what
    became of its money, the ones the bank turned away included. The answer is always a list, oldest first, and an empty one when
    nothing matched. The days are the ones the gateway used, when the
    records were asked for by the days they were made on: the ones asked
    for, or the last seven when none were.
    """

    result: Result
    #: The first day listed, ``YYYY-MM-DD`` in the team's timezone; None
    #: when they were asked for by token or reference.
    created_from: str | None
    #: The last day listed, the same way.
    created_to: str | None
    payments: list[Transaction]

    def successful(self) -> list[Transaction]:
        """The payments that went through."""
        return [payment for payment in self.payments if payment.is_successful()]

    @classmethod
    def from_body(cls, body: Body) -> PaymentList:
        return cls(
            result=Result.from_body(body),
            created_from=_said(body.get("created_from")),
            created_to=_said(body.get("created_to")),
            payments=[Transaction.from_body(_object(entry)) for entry in _list(body.get("payments"))],
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
    #: The scheme the card is issued on.
    scheme: CardScheme | str | None
    #: Whether the money is lent, drawn from an account or loaded beforehand.
    type: CardType | str | None
    #: The programme the card is sold under, such as Bonus or Maximum.
    program: str | None
    #: Whether the card belongs to a company rather than to a person.
    is_commercial: bool | None
    #: The ways the amount may be paid off, a single payment first; empty outside the lira.
    installments: list[Installment]

    @classmethod
    def from_body(cls, body: Body) -> Bin:
        card = _object(body.get("card"))

        return cls(
            result=Result.from_body(body),
            bin=_string(card.get("bin")),
            issuer_name=_said(card.get("issuer_name")),
            issuer_code=_said(card.get("issuer_code")),
            scheme=_optional_known(CardScheme, card.get("scheme")),
            type=_optional_known(CardType, card.get("type")),
            program=_said(card.get("program")),
            is_commercial=_optional_boolean(card.get("is_commercial")),
            installments=[Installment.from_body(_object(item)) for item in _list(body.get("installments"))],
        )


@dataclass(frozen=True, kw_only=True)
class Item:
    """One line of what an order, a subscription or a payment link is for, as it was written down."""

    #: The merchant's own key for what is on the line, if it gave one.
    reference: str | None
    name: str
    #: The picture the line is shown with, if any.
    image: str | None
    quantity: int
    #: The price of one, tax included, as digits with the kurus behind a point.
    unit_amount: str
    #: The tax included in the price, as a percentage.
    tax_rate: str | None

    @classmethod
    def from_body(cls, item: Body) -> Item:
        return cls(
            reference=_said(item.get("reference")),
            name=_string(item.get("name")),
            image=_said(item.get("image")),
            quantity=_integer(item.get("quantity")),
            unit_amount=_string(item.get("unit_amount")),
            tax_rate=_said(item.get("tax_rate")),
        )


@dataclass(frozen=True, kw_only=True)
class ShippingMethod:
    """One way the goods may be sent, as the merchant offered it."""

    #: The merchant's own key for it.
    reference: str
    #: What the payer sees.
    title: str
    #: What it costs, tax included.
    amount: str
    #: The tax inside the amount, as a percentage.
    tax_rate: str

    @classmethod
    def from_body(cls, method: Body) -> ShippingMethod:
        return cls(
            reference=_string(method.get("reference")),
            title=_string(method.get("title")),
            amount=_string(method.get("amount")),
            tax_rate=_string(method.get("tax_rate")),
        )


@dataclass(frozen=True, kw_only=True)
class Order:
    """
    An order as the gateway keeps it: what is being paid for, what it comes
    to, where it stands and — once it is paid — the payment that paid it.
    """

    #: The order's token in the gateway; name it to ask after or change it later.
    token: str
    #: The reference the order is known by in the calling system.
    reference: str
    description: str | None
    #: The account the order was opened with; None when none was named, in
    #: which case it is picked when the customer pays.
    payment_provider_token: str | None
    #: Where the order stands: open until it is paid, then paid.
    status: OrderStatus | str
    items: list[Item]
    #: The way the payer picked; None until they have.
    shipping_method: ShippingMethod | None
    #: What the lines come to before tax.
    subtotal: str
    #: What the picked shipping method costs before tax.
    shipping_amount: str
    #: The tax on the lines and the shipping together.
    tax_amount: str
    #: What the order comes to in all, which is what the card is charged.
    amount: str
    currency: Currency | str
    #: Whether it was paid in the test environment; None until it is paid.
    is_test: bool | None
    created_at: str | None
    #: Where the customer pays, while the order is still open; None once it is paid.
    checkout_url: str | None
    #: The payment that paid the order, which names it again for a refund; None while it is open.
    transaction: TransactionReference | None
    #: Who the order is for; None while nobody has said.
    customer: NamedCustomer | None

    def is_paid(self) -> bool:
        """Whether the order has been paid."""
        return self.status == OrderStatus.PAID

    @classmethod
    def from_body(cls, order: Body) -> Order:
        shipping_method = order.get("shipping_method")
        transaction = order.get("transaction")
        customer = order.get("customer")

        return cls(
            token=_string(order.get("token")),
            reference=_string(order.get("reference")),
            description=_said(order.get("description")),
            payment_provider_token=_said(order.get("payment_provider_token")),
            status=_known(OrderStatus, order.get("status")),
            items=[Item.from_body(_object(item)) for item in _list(order.get("items"))],
            shipping_method=ShippingMethod.from_body(shipping_method) if isinstance(shipping_method, dict) else None,
            subtotal=_string(order.get("subtotal")),
            shipping_amount=_string(order.get("shipping_amount")),
            tax_amount=_string(order.get("tax_amount")),
            amount=_string(order.get("amount")),
            currency=_known(Currency, order.get("currency")),
            is_test=_optional_boolean(order.get("is_test")),
            created_at=_said(order.get("created_at")),
            checkout_url=_said(order.get("checkout_url")),
            transaction=TransactionReference.from_body(transaction) if isinstance(transaction, dict) else None,
            customer=NamedCustomer.from_body(customer) if isinstance(customer, dict) else None,
        )


@dataclass(frozen=True, kw_only=True)
class OrderDetails:
    """
    One order, as the gateway answers when it is opened or changed: the
    order, and beside it who it is for. The customer is also on
    the order itself, the way a listed one carries it.
    """

    result: Result
    order: Order
    #: Who the order is for; None while nobody has said.
    customer: NamedCustomer | None

    @classmethod
    def from_body(cls, body: Body) -> OrderDetails:
        customer = body.get("customer")

        return cls(
            result=Result.from_body(body),
            order=Order.from_body({**_object(body.get("order")), "customer": customer}),
            customer=NamedCustomer.from_body(customer) if isinstance(customer, dict) else None,
        )


@dataclass(frozen=True, kw_only=True)
class OrderList:
    """
    Orders asked after, each with its customer on ``Order.customer``. The answer is always a list, oldest first, and an empty one when
    nothing matched. The days are the ones the gateway used, when the
    records were asked for by the days they were made on: the ones asked
    for, or the last seven when none were.
    """

    result: Result
    #: The first day listed, ``YYYY-MM-DD`` in the team's timezone; None
    #: when they were asked for by token or reference.
    created_from: str | None
    #: The last day listed, the same way.
    created_to: str | None
    orders: list[Order]

    @classmethod
    def from_body(cls, body: Body) -> OrderList:
        return cls(
            result=Result.from_body(body),
            created_from=_said(body.get("created_from")),
            created_to=_said(body.get("created_to")),
            orders=[Order.from_body(_object(entry)) for entry in _list(body.get("orders"))],
        )


@dataclass(frozen=True, kw_only=True)
class PaymentLink:
    """
    A payment link as it stands: what it sells, what it comes to now,
    whether it takes payments and until when, and the address it is paid at.
    """

    #: The link's token in the gateway; name it to ask after or change it later.
    token: str
    #: The reference the link is known by: the merchant's, or one the gateway made up.
    reference: str
    description: str | None
    #: The account the link is paid through; None when none was named.
    payment_provider_token: str | None
    items: list[Item]
    #: What the lines come to before tax.
    subtotal: str
    #: The tax on the lines.
    tax_amount: str
    #: What the link comes to in all, which is what each payment charges.
    amount: str
    currency: Currency | str
    #: Whether the link takes payments right now: switched on and not past its last day.
    is_active: bool
    #: Whether its payments are taken in the test environment now.
    is_test: bool
    #: The last moment it may be paid, as an ISO 8601 time in UTC; None for one that never runs out.
    expires_at: str | None
    #: The link itself, where the customer pays; None while it cannot be paid.
    checkout_url: str | None
    created_at: str | None

    #: The latest attempts made on the link, at most fifty, newest first, the
    #: refused ones included; listed links only.
    transactions: list[Transaction] = field(default_factory=list)
    #: How many attempts have been made on the link in all, however many are
    #: listed; None but on a listed link.
    transactions_count: int | None = None

    def successful(self) -> list[Transaction]:
        """The listed attempts that went through."""
        return [transaction for transaction in self.transactions if transaction.is_successful()]

    @classmethod
    def from_body(cls, link: Body) -> PaymentLink:
        return cls(
            token=_string(link.get("token")),
            reference=_string(link.get("reference")),
            description=_said(link.get("description")),
            payment_provider_token=_said(link.get("payment_provider_token")),
            items=[Item.from_body(_object(item)) for item in _list(link.get("items"))],
            subtotal=_string(link.get("subtotal")),
            tax_amount=_string(link.get("tax_amount")),
            amount=_string(link.get("amount")),
            currency=_known(Currency, link.get("currency")),
            is_active=_boolean(link.get("is_active")),
            is_test=_boolean(link.get("is_test")),
            expires_at=_said(link.get("expires_at")),
            checkout_url=_said(link.get("checkout_url")),
            created_at=_said(link.get("created_at")),
            transactions=[Transaction.from_body(_object(transaction)) for transaction in _list(link.get("transactions"))],
            transactions_count=_optional_integer(link.get("transactions_count")),
        )


@dataclass(frozen=True, kw_only=True)
class PaymentLinkDetails:
    """
    The answer to opening or changing a payment link: the link as it now
    stands. Its payments are on the link when it is asked after with
    ``retrieve_payment_links()``.
    """

    result: Result
    payment_link: PaymentLink

    @classmethod
    def from_body(cls, body: Body) -> PaymentLinkDetails:
        return cls(
            result=Result.from_body(body),
            payment_link=PaymentLink.from_body(_object(body.get("payment_link"))),
        )


@dataclass(frozen=True, kw_only=True)
class PaymentLinkList:
    """
    Payment links asked after, each with how many payments were made on it
    and the latest fifty of them. The answer is always a list, oldest first, and an empty one when
    nothing matched. The days are the ones the gateway used, when the
    records were asked for by the days they were made on: the ones asked
    for, or the last seven when none were.
    """

    result: Result
    #: The first day listed, ``YYYY-MM-DD`` in the team's timezone; None
    #: when they were asked for by token or reference.
    created_from: str | None
    #: The last day listed, the same way.
    created_to: str | None
    payment_links: list[PaymentLink]

    @classmethod
    def from_body(cls, body: Body) -> PaymentLinkList:
        return cls(
            result=Result.from_body(body),
            created_from=_said(body.get("created_from")),
            created_to=_said(body.get("created_to")),
            payment_links=[PaymentLink.from_body(_object(entry)) for entry in _list(body.get("payment_links"))],
        )


@dataclass(frozen=True, kw_only=True)
class Renewal:
    """The stretch of a subscription it is on: what it costs and whether it has been paid for."""

    #: The renewal's token in the gateway.
    token: str
    #: What the renewal costs, with the kurus behind a point.
    amount: str
    currency: Currency | str
    #: When the stretch began, once it has been paid for.
    starts_at: str | None
    #: When the stretch runs out, which is when the next is charged.
    ends_at: str | None
    #: When it was paid for, if it has been.
    paid_at: str | None

    def is_paid(self) -> bool:
        """Whether the renewal has been paid for."""
        return self.paid_at is not None

    @classmethod
    def from_body(cls, renewal: Body) -> Renewal:
        return cls(
            token=_string(renewal.get("token")),
            amount=_string(renewal.get("amount")),
            currency=_known(Currency, renewal.get("currency")),
            starts_at=_said(renewal.get("starts_at")),
            ends_at=_said(renewal.get("ends_at")),
            paid_at=_said(renewal.get("paid_at")),
        )


@dataclass(frozen=True, kw_only=True)
class Subscription:
    """
    A subscription as it stands: what it is written as, how often it renews,
    where it stands, the renewal it is on, when the next one falls due, and
    the address a renewal still owed is paid at.
    """

    #: The subscription's token in the gateway; name it to ask after, change or cancel it.
    token: str
    #: The reference the subscription is known by in the calling system.
    reference: str
    description: str | None
    #: The account it was opened with; None when none was named.
    payment_provider_token: str | None
    #: Where it stands.
    status: SubscriptionStatus | str
    #: How often a renewal comes round.
    period: Period | str
    #: How many renewals are paid in all; None for one that runs until it is called off.
    renewal_limit: int | None
    #: How many renewals have been paid so far.
    renewals_paid: int
    items: list[Item]
    #: The way the payer picked; None until they have.
    shipping_method: ShippingMethod | None
    subtotal: str
    shipping_amount: str
    tax_amount: str
    #: What a renewal comes to in all, as the lines are priced today.
    amount: str
    currency: Currency | str
    #: Whether it is paid for in the test environment; None until the first payment.
    is_test: bool | None
    #: The renewal it is on: the latest one.
    renewal: Renewal
    #: When the kept card is next charged; None for one that is called off or not paid yet.
    next_payment_at: str | None
    #: When it was called off, if it has been.
    cancelled_at: str | None
    created_at: str | None
    #: Where the customer pays the renewal it is on, while that is still owed.
    checkout_url: str | None
    #: Who the subscription is for.
    customer: NamedCustomer | None

    def is_active(self) -> bool:
        """
        Whether the subscription is being paid for: a customer who has been
        through the checkout and whose card has not since been turned away.
        """
        return self.status == SubscriptionStatus.ACTIVE

    def is_pending(self) -> bool:
        """Whether the first renewal has yet to be paid for."""
        return self.status == SubscriptionStatus.PENDING

    def is_past_due(self) -> bool:
        """
        Whether a renewal has been left unpaid: the card was tried and turned
        away every time, and the customer has been asked to pay it themselves
        at ``checkout_url``.
        """
        return self.status == SubscriptionStatus.PAST_DUE

    def is_cancelled(self) -> bool:
        """
        Whether it is over after being called off. A subscription that has
        been called off but is still serving days that were paid for is not
        over yet — read ``cancelled_at`` for that.
        """
        return self.status == SubscriptionStatus.CANCELLED

    def is_completed(self) -> bool:
        """Whether every renewal it was opened for has been paid and served."""
        return self.status == SubscriptionStatus.COMPLETED

    @classmethod
    def from_body(cls, subscription: Body) -> Subscription:
        shipping_method = subscription.get("shipping_method")
        customer = subscription.get("customer")

        return cls(
            token=_string(subscription.get("token")),
            reference=_string(subscription.get("reference")),
            description=_said(subscription.get("description")),
            payment_provider_token=_said(subscription.get("payment_provider_token")),
            status=_known(SubscriptionStatus, subscription.get("status")),
            period=_known(Period, subscription.get("period")),
            renewal_limit=_optional_integer(subscription.get("renewal_limit")),
            renewals_paid=_integer(subscription.get("renewals_paid")),
            items=[Item.from_body(_object(item)) for item in _list(subscription.get("items"))],
            shipping_method=ShippingMethod.from_body(shipping_method) if isinstance(shipping_method, dict) else None,
            subtotal=_string(subscription.get("subtotal")),
            shipping_amount=_string(subscription.get("shipping_amount")),
            tax_amount=_string(subscription.get("tax_amount")),
            amount=_string(subscription.get("amount")),
            currency=_known(Currency, subscription.get("currency")),
            is_test=_optional_boolean(subscription.get("is_test")),
            renewal=Renewal.from_body(_object(subscription.get("renewal"))),
            next_payment_at=_said(subscription.get("next_payment_at")),
            cancelled_at=_said(subscription.get("cancelled_at")),
            created_at=_said(subscription.get("created_at")),
            checkout_url=_said(subscription.get("checkout_url")),
            customer=NamedCustomer.from_body(customer) if isinstance(customer, dict) else None,
        )


@dataclass(frozen=True, kw_only=True)
class SubscriptionDetails:
    """
    One subscription, as the gateway answers when it is opened or changed:
    the subscription, and beside it who it is for. The customer is also on
    the subscription itself, the way a listed one carries it.
    """

    result: Result
    subscription: Subscription
    #: Who the subscription is for.
    customer: NamedCustomer | None

    @classmethod
    def from_body(cls, body: Body) -> SubscriptionDetails:
        customer = body.get("customer")

        return cls(
            result=Result.from_body(body),
            subscription=Subscription.from_body({**_object(body.get("subscription")), "customer": customer}),
            customer=NamedCustomer.from_body(customer) if isinstance(customer, dict) else None,
        )


@dataclass(frozen=True, kw_only=True)
class SubscriptionList:
    """
    Subscriptions asked after, each with its customer on
    ``Subscription.customer``. The answer is always a list, oldest first, and an empty one when
    nothing matched. The days are the ones the gateway used, when the
    records were asked for by the days they were made on: the ones asked
    for, or the last seven when none were.
    """

    result: Result
    #: The first day listed, ``YYYY-MM-DD`` in the team's timezone; None
    #: when they were asked for by token or reference.
    created_from: str | None
    #: The last day listed, the same way.
    created_to: str | None
    subscriptions: list[Subscription]

    @classmethod
    def from_body(cls, body: Body) -> SubscriptionList:
        return cls(
            result=Result.from_body(body),
            created_from=_said(body.get("created_from")),
            created_to=_said(body.get("created_to")),
            subscriptions=[Subscription.from_body(_object(entry)) for entry in _list(body.get("subscriptions"))],
        )


@dataclass(frozen=True, kw_only=True)
class SavedCardDetails:
    """A kept card, as the gateway answers when it is kept or made the default."""

    result: Result
    #: The card as it now stands, or None when the provider would not keep it.
    saved_card: SavedCard | None
    #: The customer the card belongs to.
    customer: SavedCardCustomer

    @classmethod
    def from_body(cls, body: Body) -> SavedCardDetails:
        saved_card = body.get("saved_card")

        return cls(
            result=Result.from_body(body),
            saved_card=SavedCard.from_body(saved_card) if isinstance(saved_card, dict) else None,
            customer=SavedCardCustomer.from_body(_object(body.get("customer"))),
        )


@dataclass(frozen=True, kw_only=True)
class SavedCardList:
    """
    Kept cards asked after, each with the customer it is kept for. A
    customer's cards come with the one they pay with by default first. The answer is always a list, oldest first, and an empty one when
    nothing matched. The days are the ones the gateway used, when the
    records were asked for by the days they were made on: the ones asked
    for, or the last seven when none were.
    """

    result: Result
    #: The first day listed, ``YYYY-MM-DD`` in the team's timezone; None
    #: when they were asked for by token or reference.
    created_from: str | None
    #: The last day listed, the same way.
    created_to: str | None
    saved_cards: list[SavedCard]

    def default(self) -> SavedCard | None:
        """The card the customer pays with unless they say otherwise, when the cards were asked for by the customer's reference."""
        return next((card for card in self.saved_cards if card.is_default), None)

    @classmethod
    def from_body(cls, body: Body) -> SavedCardList:
        return cls(
            result=Result.from_body(body),
            created_from=_said(body.get("created_from")),
            created_to=_said(body.get("created_to")),
            saved_cards=[SavedCard.from_body(_object(entry)) for entry in _list(body.get("saved_cards"))],
        )


@dataclass(frozen=True, kw_only=True)
class DeletedSavedCard:
    """
    A kept card let go of, or not: a provider that would not let it go
    leaves it kept, and the result says why.
    """

    result: Result
    #: The token the card had.
    saved_card_token: str
    #: The customer the card belonged to.
    customer: SavedCardCustomer

    @classmethod
    def from_body(cls, body: Body) -> DeletedSavedCard:
        return cls(
            result=Result.from_body(body),
            saved_card_token=_string(_object(body.get("saved_card")).get("token")),
            customer=SavedCardCustomer.from_body(_object(body.get("customer"))),
        )
