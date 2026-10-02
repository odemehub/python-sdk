"""
What is handed to the gateway. Every request is a small immutable object
whose fields are named in the snake_case the gateway speaks; the client
turns it into the JSON body, signs it and sends it. A field left as
``None`` is left out of the body altogether rather than sent empty.

There is one request per endpoint, named after it: ``create-order`` is
``CreateOrder`` and is sent with ``client.create_order()``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar

from .enums import Currency, Period, SubscriptionStatus

Body = dict[str, Any]


def _value(value: Any) -> Any:
    """What a typed value is sent as: the plain string of a member of one of the fixed sets."""
    return value.value if isinstance(value, Enum) else value


def _said(body: Body) -> Body:
    """Drop what the caller left unsaid, so an optional field is left out of the body rather than sent empty."""
    return {key: value for key, value in body.items() if value is not None}


def _cleared(body: Body, clear: Sequence[str]) -> Body:
    """
    Set the named fields to nothing. A change leaves out what it does not
    name, which keeps what there was, so clearing a field — lifting a
    renewal limit, dropping a description — has to be said on purpose.
    """
    return {**body, **{name: None for name in clear}}


@dataclass(frozen=True, kw_only=True)
class Message:
    """
    Something handed to the gateway: the endpoint it goes to, the method it
    goes with and the body it is sent as. The body is built with the
    client's channel handed in, because a message that speaks for a channel
    puts it where its own endpoint expects it; one that does not, such as a
    refund, never reads it.
    """

    #: The endpoint this is sent to, under the team's gateway.
    endpoint: ClassVar[str]

    #: The HTTP method this goes with. Everything is posted, except asking
    #: after one record by its token.
    method: ClassVar[str] = "POST"

    def path(self) -> str:
        """The endpoint, with the token in the address where the endpoint takes one."""
        return self.endpoint

    def to_body(self, channel_token: str) -> Body:
        """The request body. Empty for a message sent with GET, which carries nothing but its address."""
        raise NotImplementedError


@dataclass(frozen=True, kw_only=True)
class ChannelMessage(Message):
    """
    A message that speaks for one of the team's channels. The channel
    belongs to the integration rather than to any one message, so it is
    named once on the client; a merchant selling on more than one channel
    names another here, on the single message that belongs elsewhere.
    """

    #: Stands for the team's own ödemehub channel, which has no token of its
    #: own and is only ever reached by payment links: the panel opens its
    #: links there. Give it as the channel of a payment link message to reach
    #: those links.
    ODEMEHUB_CHANNEL: ClassVar[str] = "odemehub"

    #: The channel this one message speaks for. Left out, the client's own is used.
    channel_token: str | None = None

    def _channel(self, channel_token: str) -> str:
        return self.channel_token if self.channel_token is not None else channel_token

    def _link_channel(self, channel_token: str) -> str | None:
        """The channel of a payment link message: the one it names, the client's, or none for ``ODEMEHUB_CHANNEL``."""
        return None if self.channel_token == self.ODEMEHUB_CHANNEL else self._channel(channel_token)


@dataclass(frozen=True, kw_only=True)
class Address:
    """
    Where a customer is billed, or where their goods go. A payment and a
    kept card need the whole of the eight person fields on the billing
    address; an order or a subscription takes whatever is known and asks the
    payer for the rest on the checkout page.

    The three company fields are read on the billing address only, and
    always together: the gateway turns down an address that names one of
    them without the others.
    """

    firstname: str | None = None
    lastname: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    district: str | None = None
    province: str | None = None
    country: str | None = None
    #: The company the customer is billed as. Billing address only.
    company_title: str | None = None
    tax_number: str | None = None
    tax_office: str | None = None

    def to_body(self) -> Body:
        return _said({
            "firstname": self.firstname,
            "lastname": self.lastname,
            "email": self.email,
            "phone": self.phone,
            "address": self.address,
            "district": self.district,
            "province": self.province,
            "country": self.country,
            "company_title": self.company_title,
            "tax_number": self.tax_number,
            "tax_office": self.tax_office,
        })


@dataclass(frozen=True, kw_only=True)
class Customer:
    """
    The customer a payment is made for, an order or a subscription is opened
    for, or a card is kept for: the merchant's own key for them, where they
    are billed and, for goods, where those go.

    The reference is what a kept card is held under, together with the
    channel; a payment that keeps its card, a card kept on its own and a
    subscription all need it. An order opened without one is given a
    ``guest-…`` reference by the gateway once somebody pays.

    Payments and kept cards take the reference and the billing address only;
    orders and subscriptions take any part of the three.
    """

    #: The key the merchant keeps this customer under in its own system.
    reference: str | None = None
    billing_address: Address | None = None
    #: Orders and subscriptions only.
    shipping_address: Address | None = None

    def to_body(self) -> Body:
        return _said({
            "reference": self.reference,
            "billing_address": None if self.billing_address is None else self.billing_address.to_body(),
            "shipping_address": None if self.shipping_address is None else self.shipping_address.to_body(),
        })


@dataclass(frozen=True, kw_only=True)
class Card:
    """
    The card a payment is attempted with, or kept without one. The number
    and the security code travel no further than the request body, and are
    kept out of ``repr()`` so they never reach a log: the gateway keeps only
    the head and the tail digits of the number and no digit of the code.
    """

    holder_name: str
    #: The number, 12 to 19 digits; spaces between the groups are taken.
    number: str = field(repr=False)
    #: Two digits, e.g. 04.
    expiry_month: str
    #: Four digits, e.g. 2030.
    expiry_year: str
    #: Three or four digits. A payment always needs it. A card kept without
    #: a payment needs it only at providers that keep a card by charging and
    #: giving back a small amount; left out, it is not sent.
    security_code: str | None = field(default=None, repr=False)
    #: Whether the customer asked for this card to be kept after a
    #: successful payment, so they can pay with it again without typing it
    #: out. Needs a customer reference to be kept under, a plan that covers
    #: saved cards and an account whose provider keeps cards. Read only by
    #: payments; left out, it is not sent.
    should_save: bool | None = None

    def to_body(self) -> Body:
        return _said({
            "holder_name": self.holder_name,
            "number": self.number,
            "security_code": self.security_code,
            "expiry_month": self.expiry_month,
            "expiry_year": self.expiry_year,
            "should_save": self.should_save,
        })


@dataclass(frozen=True, kw_only=True)
class Item:
    """
    One line of what an order, a subscription or a payment link is for. The
    unit price includes the tax: a line of 120 at 20% is 100 of goods and 20
    of tax, and the gateway splits it so. What the whole comes to is never
    sent; the gateway adds the lines up and answers with the total.
    """

    name: str
    #: The price of one, tax included, as digits with the kurus behind a point: '120.00'.
    unit_amount: str
    #: 1 to 9999.
    quantity: int
    #: The tax inside the price, as a percentage: '20' or '20.00'.
    tax_rate: str
    #: The merchant's own key for what is on the line, if it has one.
    channel_reference: str | None = None
    #: The https address of the picture shown beside the line at checkout.
    image: str | None = None

    def to_body(self) -> Body:
        return _said({
            "channel_reference": self.channel_reference,
            "name": self.name,
            "image": self.image,
            "quantity": self.quantity,
            "unit_amount": self.unit_amount,
            "tax_rate": self.tax_rate,
        })


@dataclass(frozen=True, kw_only=True)
class ShippingMethod:
    """
    One way the goods of an order or a subscription may be sent, offered to
    the payer on the checkout page. The one they pick is added to what they
    pay. The handle is the merchant's own key for it and has to be unique
    within the list; the amount includes the tax, like an item's price.
    """

    handle: str
    #: What the payer sees, e.g. 'Standart Kargo'.
    title: str
    #: What it costs, tax included, as digits with the kurus behind a point; '0' for free.
    amount: str
    #: The tax inside the amount, as a percentage.
    tax_rate: str

    def to_body(self) -> Body:
        return {
            "handle": self.handle,
            "title": self.title,
            "amount": self.amount,
            "tax_rate": self.tax_rate,
        }


# Payments ------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class Payment(ChannelMessage):
    """
    A payment handed to the gateway. A payment is made with a card the
    customer typed in or with one they let the merchant keep, never with
    both. With a kept card the payment goes through the account the card is
    kept at, so no account is named either; the gateway turns down a
    payment that names both.
    """

    #: The reference the payment is known by in the calling system, such as
    #: SIP-10231. It has to carry at least one digit: its digits end the order
    #: number the bank is sent, so the payment can be found in the bank's panel.
    channel_reference: str
    #: The amount, as digits with the kurus behind a point: '100', '100.1' or
    #: '100.10'. A comma is refused. It is a string so that it is signed and
    #: sent exactly as it is written here, with no rounding on the way.
    amount: str
    #: 1 to 12. More than one only when the payment is asked for and charged in lira.
    installment_number: int
    #: The address the customer is paying from, as the merchant sees it.
    ip: str
    #: Who is paying: the reference, if any, and the whole billing address.
    customer: Customer
    #: The card typed in. Left out only when a kept card is named instead.
    card: Card | None = None
    #: A card the customer let the merchant keep, by the token the gateway gave it.
    saved_card_token: str | None = None
    #: Left out, the gateway takes the lira.
    currency: Currency | None = None
    #: The payment account to charge through. Left out, the team's routing
    #: rules pick the account, and the team's default account is used when
    #: none of them holds. Never named together with a kept card.
    payment_provider_token: str | None = None
    #: What is being sold, where the customer spreads the amount over months
    #: and the bank takes something for the waiting on top of it. Never more
    #: than the amount. Left out where the two are the same, which is most
    #: payments.
    base_amount: str | None = None

    def to_body(self, channel_token: str) -> Body:
        return _said({
            "transaction": _said({
                "channel_token": self._channel(channel_token),
                "channel_reference": self.channel_reference,
                "payment_provider_token": self.payment_provider_token,
                "amount": self.amount,
                "base_amount": self.base_amount,
                "currency": _value(self.currency),
                "installment_number": self.installment_number,
                "ip": self.ip,
                "saved_card_token": self.saved_card_token,
            }),
            "customer": self.customer.to_body(),
            "card": None if self.card is None else self.card.to_body(),
        })


@dataclass(frozen=True, kw_only=True)
class SecurePayment(Payment):
    """
    A payment the customer confirms with their bank. The gateway does not
    settle it; it hands back the address the customer has to be sent to, and
    posts them back to ``callback_url`` once they are done.
    """

    endpoint: ClassVar[str] = "secure-payment"

    #: Where the customer's browser is posted back to once they are done at
    #: their bank, with the payment's token and a hint at how it went. An
    #: https address reachable from the internet.
    callback_url: str

    def to_body(self, channel_token: str) -> Body:
        body = super().to_body(channel_token)
        body["transaction"] = _said({
            **body["transaction"],
            "callback_url": self.callback_url,
        })

        return body


@dataclass(frozen=True, kw_only=True)
class RegularPayment(Payment):
    """
    A payment charged straight to the card, without sending the customer to
    their bank to confirm it. A successful answer is a settled payment.
    """

    endpoint: ClassVar[str] = "regular-payment"


@dataclass(frozen=True, kw_only=True)
class RefundPayment(Message):
    """
    Money given back out of a payment the provider has already settled,
    whole or in part. The payment is named by the token the gateway gave it.
    """

    endpoint: ClassVar[str] = "refund-payment"

    #: The payment's token in the gateway, as it answered when the payment was made.
    token: str
    #: How much goes back, as digits with the kurus behind a point: '35.50'.
    #: Leave it out and everything the payment has left in it goes back. It
    #: is never more than the payment has left: the gateway turns down
    #: anything larger.
    amount: str | None = None

    def to_body(self, channel_token: str) -> Body:
        return _said({
            "transaction": {"token": self.token},
            "amount": self.amount,
        })


@dataclass(frozen=True, kw_only=True)
class CancelPayment(Message):
    """
    The whole of a payment taken back before the provider has settled it.
    There is no amount to name: anything less goes back as a refund.
    """

    endpoint: ClassVar[str] = "cancel-payment"

    #: The payment's token in the gateway, as it answered when the payment was made.
    token: str

    def to_body(self, channel_token: str) -> Body:
        return {"transaction": {"token": self.token}}


@dataclass(frozen=True, kw_only=True)
class RetrieveBin(Message):
    """
    A question about a card before anything is charged to it: who issued it,
    what kind of card it is, and how the amount may be paid off on it. Only
    the head of the number is sent, never the whole of it.
    """

    endpoint: ClassVar[str] = "retrieve-bin"

    #: The first six to eight digits of the card.
    bin: str
    #: What the payment would come to, as digits with the kurus behind a point: '1000.00'.
    amount: str
    #: The account to ask. Left out, the account the team's routing rules
    #: would send the card to is asked — the default one when none of them
    #: holds — so the instalments match a payment that names no account either.
    payment_provider_token: str | None = None
    #: The money the payment is taken in; the lira unless another is named.
    #: Instalments are only answered in lira.
    currency: Currency | None = None

    def to_body(self, channel_token: str) -> Body:
        return {
            "transaction": _said({
                "payment_provider_token": self.payment_provider_token,
                "amount": self.amount,
                "currency": _value(self.currency),
            }),
            "card": {"bin": self.bin},
        }


# Asking after records ------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class RetrieveByToken(Message):
    """
    One record asked after by the token the gateway gave it, as
    ``GET retrieve-{resource}/{token}``. There is no body: the signature is
    taken over the empty string, and the token travels in the address. A
    caller only ever reaches its own team's records; anybody else's is
    answered as not found.
    """

    method: ClassVar[str] = "GET"

    #: The record's token in the gateway, as it answered when the record was made.
    token: str

    def path(self) -> str:
        return f"{self.endpoint}/{self.token}"

    def to_body(self, channel_token: str) -> Body:
        return {}


@dataclass(frozen=True, kw_only=True)
class RetrieveByReference(ChannelMessage):
    """
    One record asked after by the merchant's own reference for it on a
    channel. The latest record under that pair is answered: the merchant
    that opened something and lost its token, or never heard back, finds it
    again this way. Nothing is changed by asking.
    """

    #: The reference the record was made under in the calling system.
    channel_reference: str

    def to_body(self, channel_token: str) -> Body:
        return {
            "channel_token": self._channel(channel_token),
            "channel_reference": self.channel_reference,
        }


@dataclass(frozen=True, kw_only=True)
class RetrieveByChannelReference(ChannelMessage):
    """
    Every record of a kind made on a channel within a span of days, oldest
    first. The days are given as ``YYYY-MM-DD`` in the team's own timezone,
    both included, and the span may be at most seven days; the two are given
    together or not at all, and left out they mean the last seven days up to
    today. Nothing is changed by asking.
    """

    #: The first day, ``YYYY-MM-DD``. Given together with ``created_to``.
    created_from: str | None = None
    #: The last day, ``YYYY-MM-DD``, at most six days after the first.
    created_to: str | None = None

    def to_body(self, channel_token: str) -> Body:
        return _said({
            "channel_token": self._channel(channel_token),
            "created_from": self.created_from,
            "created_to": self.created_to,
        })


@dataclass(frozen=True, kw_only=True)
class RetrievePayment(RetrieveByToken):
    """
    How a payment went, asked for after the fact. A customer sent to their
    bank comes back carrying the payment's token and nothing more, because
    a browser cannot be given anything to sign with; this is the call that
    says what became of it.
    """

    endpoint: ClassVar[str] = "retrieve-payment"


@dataclass(frozen=True, kw_only=True)
class RetrievePaymentByReference(RetrieveByReference):
    """
    The latest payment made under one of the merchant's own references on a
    channel. The merchant that sent a payment and never heard the answer —
    the connection dropped — finds out here whether it was made, without
    trying it again.
    """

    endpoint: ClassVar[str] = "retrieve-payment-by-reference"


@dataclass(frozen=True, kw_only=True)
class RetrievePaymentsByChannelReference(RetrieveByChannelReference):
    """
    Every payment attempt made on a channel within a span of days, the
    refused and the expired ones included, and the ones made on the
    gateway's own checkout page too.
    """

    endpoint: ClassVar[str] = "retrieve-payments-by-channel-reference"


# Orders and subscriptions --------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class CheckoutMessage(ChannelMessage):
    """
    An order or a subscription, opened or changed, to be paid on the
    gateway's own checkout page. Nothing is charged here: the answer carries
    the address to send the customer to, and they give their card there.

    What it comes to is not sent. The gateway adds up the lines and the
    shipping method the payer picks and answers with the amount, so the
    total can never disagree with what it is made up of. The customer is
    whatever is known: it is filled in on the checkout page and the payer is
    asked for the rest.

    Opening is idempotent per channel and reference: opening again under a
    reference that already has an open order or subscription overwrites it
    with what is sent and answers with the one that was there, under its
    own token. A paid order, or a subscription that has been paid, is not
    touched, and neither is one with a payment under way — the gateway says
    so on ``channel_reference``.
    """

    #: The key the group travels under: order or subscription.
    group: ClassVar[str]

    #: The reference it is known by in the calling system. Has to carry at least one digit.
    channel_reference: str | None = None
    #: Where the customer's browser is posted back to once it is paid, with
    #: the payment's token. An https address reachable from the internet.
    success_url: str | None = None
    #: What it is for; at least one line when opening. Sent on a change, they
    #: replace every line there was.
    items: Sequence[Item] | None = None
    #: Who it is for, as far as it is known.
    customer: Customer | None = None
    #: Where the customer goes if they turn back without paying; shown as a link on the checkout page.
    cancel_url: str | None = None
    description: str | None = None
    #: Left out, the gateway takes the lira.
    currency: Currency | None = None
    #: The payment account it is paid through. Left out, the merchant's Gate
    #: rules pick the account when the customer pays, and its default account
    #: is used where none of them holds.
    payment_provider_token: str | None = None
    #: Whether the checkout page asks the payer where the goods go.
    requires_shipping_address: bool | None = None
    #: How the goods may be sent, for the payer to pick from; up to twenty.
    #: Sent on a change, they replace the ones there were, and an empty list
    #: removes them all.
    shipping_methods: Sequence[ShippingMethod] | None = None

    def _details(self, channel: str | None) -> Body:
        """The group's fields, with what the caller left unsaid left out."""
        return _said({
            "channel_token": channel,
            "channel_reference": self.channel_reference,
            "description": self.description,
            "payment_provider_token": self.payment_provider_token,
            "currency": _value(self.currency),
            "success_url": self.success_url,
            "cancel_url": self.cancel_url,
            "requires_shipping_address": self.requires_shipping_address,
            "items": None if self.items is None else [item.to_body() for item in self.items],
            "shipping_methods": None if self.shipping_methods is None else [method.to_body() for method in self.shipping_methods],
        })

    def _body(self, group: Body) -> Body:
        """The body: the group and, beside it, the customer when one was given."""
        return _said({
            self.group: group,
            "customer": None if self.customer is None else self.customer.to_body(),
        })


@dataclass(frozen=True, kw_only=True)
class CreateOrder(CheckoutMessage):
    """
    An order opened to be paid once on the gateway's own checkout page. The
    answer carries ``checkout_url``; the customer is sent there, pays, and
    is posted back to ``success_url``. The addresses set for the order's
    channel under Webhook in the panel hear that it was paid whether or not
    the customer comes back.
    """

    endpoint: ClassVar[str] = "create-order"
    group: ClassVar[str] = "order"

    channel_reference: str
    success_url: str
    items: Sequence[Item]

    def to_body(self, channel_token: str) -> Body:
        return self._body(self._details(self._channel(channel_token)))


@dataclass(frozen=True, kw_only=True)
class RetrieveOrder(RetrieveByToken):
    """
    Where an order stands: what it is for, whether it has been paid and, if
    so, by which payment. Nothing is changed by asking.
    """

    endpoint: ClassVar[str] = "retrieve-order"


@dataclass(frozen=True, kw_only=True)
class RetrieveOrderByReference(RetrieveByReference):
    """The latest order opened under one of the merchant's own references on a channel."""

    endpoint: ClassVar[str] = "retrieve-order-by-reference"


@dataclass(frozen=True, kw_only=True)
class RetrieveOrdersByChannelReference(RetrieveByChannelReference):
    """Every order opened on a channel within a span of days, each with whose it is."""

    endpoint: ClassVar[str] = "retrieve-orders-by-channel-reference"


@dataclass(frozen=True, kw_only=True)
class UpdateOrder(CheckoutMessage):
    """
    A change to an open order, named by its token in the address and again
    in the body. Only what is sent is written: a field left out keeps what
    there was, lines sent replace every line there was, and the customer
    sent is written over the one the order had. A paid order, or one with a
    payment under way, cannot be changed; the gateway says so on ``token``.

    The channel is written only when this message names one; the client's
    own is not sent, so a change never moves an order between channels by
    accident.
    """

    endpoint: ClassVar[str] = "update-order"
    group: ClassVar[str] = "order"

    #: The order's token in the gateway.
    token: str
    #: Fields to set to nothing: description, cancel_url, payment_provider_token.
    clear: Sequence[str] = ()

    def path(self) -> str:
        return f"{self.endpoint}/{self.token}"

    def to_body(self, channel_token: str) -> Body:
        return {
            "token": self.token,
            **self._body(_cleared(self._details(self.channel_token), self.clear)),
        }


@dataclass(frozen=True, kw_only=True)
class CreateSubscription(CheckoutMessage):
    """
    A subscription opened for a customer, its first renewal paid on the
    gateway's own checkout page. Nothing is charged here: the answer carries
    the address to send the customer to. The card is kept there, because the
    renewals to come are taken from it, so the account has to keep cards and
    take 3D payments, and the customer's reference is required.
    """

    endpoint: ClassVar[str] = "create-subscription"
    group: ClassVar[str] = "subscription"

    channel_reference: str
    success_url: str
    items: Sequence[Item]
    #: Who is subscribing; the reference is required.
    customer: Customer
    #: How often a renewal comes round.
    period: Period
    #: How many renewals are paid in all, 1 to 1000, after which it is
    #: completed. Left out, it runs until it is called off.
    renewal_limit: int | None = None

    def to_body(self, channel_token: str) -> Body:
        return self._body(_said({
            **self._details(self._channel(channel_token)),
            "period": _value(self.period),
            "renewal_limit": self.renewal_limit,
        }))


@dataclass(frozen=True, kw_only=True)
class RetrieveSubscription(RetrieveByToken):
    """
    Where a subscription stands: what it is for, the renewal it is on and
    whether that renewal has been paid for. Nothing is changed by asking.
    """

    endpoint: ClassVar[str] = "retrieve-subscription"


@dataclass(frozen=True, kw_only=True)
class RetrieveSubscriptionByReference(RetrieveByReference):
    """The latest subscription opened under one of the merchant's own references on a channel."""

    endpoint: ClassVar[str] = "retrieve-subscription-by-reference"


@dataclass(frozen=True, kw_only=True)
class RetrieveSubscriptionsByChannelReference(RetrieveByChannelReference):
    """Every subscription opened on a channel within a span of days, each with whose it is."""

    endpoint: ClassVar[str] = "retrieve-subscriptions-by-channel-reference"


@dataclass(frozen=True, kw_only=True)
class UpdateSubscription(CheckoutMessage):
    """
    A change to a subscription, named by its token in the address and again
    in the body. Only what is sent is written; lines sent replace the lines
    from the renewal still owed onwards. Calling it off is a change like any
    other: ``status="cancelled"``, the only status a merchant may send.
    Nothing is given back: the customer is served to the end of what they
    paid for, and nothing is charged after that.

    Until the first payment anything about it may be changed. Once it has
    been paid, what it renews on stays as it was opened — the channel, the
    customer's reference, the account, the money and how often it renews —
    and the gateway turns down a change to any of them.

    The channel is written only when this message names one.
    """

    endpoint: ClassVar[str] = "update-subscription"
    group: ClassVar[str] = "subscription"

    #: The subscription's token in the gateway.
    token: str
    #: Only ``SubscriptionStatus.CANCELLED`` is taken; the other states follow the payments.
    status: SubscriptionStatus | None = None
    period: Period | None = None
    #: 1 to 1000, and never fewer than the renewals already paid.
    renewal_limit: int | None = None
    #: Fields to set to nothing: renewal_limit, description, cancel_url, payment_provider_token.
    clear: Sequence[str] = ()

    def path(self) -> str:
        return f"{self.endpoint}/{self.token}"

    def to_body(self, channel_token: str) -> Body:
        group = _said({
            **self._details(self.channel_token),
            "period": _value(self.period),
            "renewal_limit": self.renewal_limit,
            "status": _value(self.status),
        })

        return {
            "token": self.token,
            **self._body(_cleared(group, self.clear)),
        }


# Payment links -------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class CreatePaymentLink(ChannelMessage):
    """
    A payment link: a page anyone holding it may pay, again and again, until
    it is switched off or its last day has gone by. It has no customer.
    Opened again under the same reference on the same channel, the link
    already there is written over and answered with.

    Left without a channel, the link is opened on the client's channel; give
    ``ODEMEHUB_CHANNEL`` to open it on the team's own ödemehub channel, where
    the panel opens its links.
    """

    endpoint: ClassVar[str] = "create-payment-link"

    #: What the link is for; at least one line.
    items: Sequence[Item]
    currency: Currency
    #: The reference the link is known by in the calling system. Has to carry
    #: at least one digit. Left out, the gateway makes one up.
    channel_reference: str | None = None
    description: str | None = None
    #: The account the link is paid through; it has to take 3D payments. Left
    #: out, Gate rules and the default account decide at pay time.
    payment_provider_token: str | None = None
    #: The last day the link may be paid, as ``YYYY-MM-DD`` in the team's
    #: timezone; today or later. Left out, it never runs out.
    expires_at: str | None = None
    #: Whether the link takes payments. Left out, it does.
    is_active: bool | None = None

    def to_body(self, channel_token: str) -> Body:
        return {
            "payment_link": _said({
                "channel_token": self._link_channel(channel_token),
                "channel_reference": self.channel_reference,
                "description": self.description,
                "payment_provider_token": self.payment_provider_token,
                "currency": _value(self.currency),
                "expires_at": self.expires_at,
                "is_active": self.is_active,
                "items": [item.to_body() for item in self.items],
            }),
        }


@dataclass(frozen=True, kw_only=True)
class RetrievePaymentLink(RetrieveByToken):
    """
    A payment link as it stands, by its token, with how many payments were
    made on it and the latest fifty of them, newest first, the ones the bank
    turned away included.
    """

    endpoint: ClassVar[str] = "retrieve-payment-link"


@dataclass(frozen=True, kw_only=True)
class RetrievePaymentLinkByReference(RetrieveByReference):
    """
    A payment link by the merchant's own reference for it. With
    ``ODEMEHUB_CHANNEL`` as the channel, it is looked for among the links on
    the team's own ödemehub channel.
    """

    endpoint: ClassVar[str] = "retrieve-payment-link-by-reference"

    def to_body(self, channel_token: str) -> Body:
        return _said({
            "channel_token": self._link_channel(channel_token),
            "channel_reference": self.channel_reference,
        })


@dataclass(frozen=True, kw_only=True)
class RetrievePaymentLinksByChannelReference(RetrieveByChannelReference):
    """
    Every payment link opened on a channel within a span of days. With
    ``ODEMEHUB_CHANNEL`` as the channel, the links on the team's own ödemehub
    channel are listed.
    """

    endpoint: ClassVar[str] = "retrieve-payment-links-by-channel-reference"

    def to_body(self, channel_token: str) -> Body:
        return _said({
            "channel_token": self._link_channel(channel_token),
            "created_from": self.created_from,
            "created_to": self.created_to,
        })


@dataclass(frozen=True, kw_only=True)
class UpdatePaymentLink(ChannelMessage):
    """
    A change to a payment link, named by its token in the address and again
    in the body. Only what is sent is written; lines sent replace the lines
    there were. A link whose last day has gone by is switched on again only
    together with a new day.

    The channel is written only when this message names one;
    ``ODEMEHUB_CHANNEL`` moves the link to the team's own ödemehub channel.
    """

    endpoint: ClassVar[str] = "update-payment-link"

    #: The link's token in the gateway.
    token: str
    items: Sequence[Item] | None = None
    currency: Currency | None = None
    channel_reference: str | None = None
    description: str | None = None
    payment_provider_token: str | None = None
    #: As ``YYYY-MM-DD`` in the team's timezone; today or later.
    expires_at: str | None = None
    is_active: bool | None = None
    #: Fields to set to nothing: description, payment_provider_token, expires_at.
    clear: Sequence[str] = ()

    def path(self) -> str:
        return f"{self.endpoint}/{self.token}"

    def to_body(self, channel_token: str) -> Body:
        link = _said({
            "channel_reference": self.channel_reference,
            "description": self.description,
            "payment_provider_token": self.payment_provider_token,
            "currency": _value(self.currency),
            "expires_at": self.expires_at,
            "is_active": self.is_active,
            "items": None if self.items is None else [item.to_body() for item in self.items],
        })

        if self.channel_token is not None:
            link["channel_token"] = self._link_channel(channel_token)

        return {
            "token": self.token,
            "payment_link": _cleared(link, self.clear),
        }


# Saved cards ---------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class CreateSavedCard(ChannelMessage):
    """
    A card kept for a customer without a payment being made on it.

    Providers without a card store of their own keep a card by charging a
    small amount and giving it straight back; those ask for the security
    code, and the ones with a real card store do not, so it may be left out.
    """

    endpoint: ClassVar[str] = "create-saved-card"

    #: Who the card belongs to: the reference and the whole billing address, both required.
    customer: Customer
    card: Card
    #: The payment account to keep the card at; it has to keep cards. Left
    #: out, the team's default account is used.
    payment_provider_token: str | None = None

    def to_body(self, channel_token: str) -> Body:
        card = self.card.to_body()
        card.pop("should_save", None)

        return {
            "saved_card": _said({
                "channel_token": self._channel(channel_token),
                "payment_provider_token": self.payment_provider_token,
            }),
            "customer": self.customer.to_body(),
            "card": card,
        }


@dataclass(frozen=True, kw_only=True)
class RetrieveSavedCard(RetrieveByToken):
    """One kept card, by its token."""

    endpoint: ClassVar[str] = "retrieve-saved-card"


@dataclass(frozen=True, kw_only=True)
class RetrieveSavedCardsByReference(ChannelMessage):
    """
    The cards kept for a customer, named by the two things a card is kept
    under: the channel and the merchant's own key for the customer there.
    The default card comes first.
    """

    endpoint: ClassVar[str] = "retrieve-saved-cards-by-reference"

    #: The key the merchant keeps the customer under.
    customer_reference: str

    def to_body(self, channel_token: str) -> Body:
        return {
            "channel_token": self._channel(channel_token),
            "customer_reference": self.customer_reference,
        }


@dataclass(frozen=True, kw_only=True)
class UpdateSavedCard(Message):
    """
    Making one of a customer's kept cards the one they pay with unless they
    say otherwise. A card stops being the default only when another of the
    customer's cards is made the default instead.
    """

    endpoint: ClassVar[str] = "update-saved-card"

    #: The card's token in the gateway.
    token: str
    #: Has to be True; the gateway turns down anything else.
    is_default: bool = True

    def path(self) -> str:
        return f"{self.endpoint}/{self.token}"

    def to_body(self, channel_token: str) -> Body:
        return {
            "token": self.token,
            "saved_card": {"is_default": self.is_default},
        }


@dataclass(frozen=True, kw_only=True)
class DeleteSavedCard(Message):
    """
    Letting go of a kept card, at the provider first and with the gateway
    after: a card kept at an account whose provider cannot let it go is
    turned down rather than dropped only on the gateway's side.
    """

    endpoint: ClassVar[str] = "delete-saved-card"

    #: The card's token in the gateway.
    token: str

    def path(self) -> str:
        return f"{self.endpoint}/{self.token}"

    def to_body(self, channel_token: str) -> Body:
        return {"token": self.token}
