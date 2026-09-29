"""
What is handed to the gateway. Every request is a small immutable object
whose fields are named in the snake_case the gateway speaks; the client
turns it into the JSON body, signs it and sends it. A field left as
``None`` is left out of the body altogether rather than sent empty.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal

Body = dict[str, Any]


def _said(body: Body) -> Body:
    """Drop what the caller left unsaid, so an optional field is left out of the body rather than sent empty."""
    return {key: value for key, value in body.items() if value is not None}


@dataclass(frozen=True, kw_only=True)
class Message:
    """
    Something handed to the gateway: the endpoint it goes to and the body it
    is sent as. The body is built with the client's channel handed in,
    because a message that speaks for a channel puts it where its own
    endpoint expects it; one that does not, such as a refund, never reads it.
    """

    #: The endpoint this is sent to, under the team's gateway.
    path: ClassVar[str]

    def to_body(self, channel_token: str) -> Body:
        raise NotImplementedError


@dataclass(frozen=True, kw_only=True)
class ChannelMessage(Message):
    """
    A message that speaks for one of the team's channels. The channel
    belongs to the integration rather than to any one message, so it is
    named once on the client; a merchant selling on more than one channel
    names another here, on the single message that belongs elsewhere.
    """

    #: The channel this one message speaks for. Left out, the client's own is used.
    channel_token: str | None = None

    def _channel(self, channel_token: str) -> str:
        return self.channel_token if self.channel_token is not None else channel_token


@dataclass(frozen=True, kw_only=True)
class Card:
    """
    The card a payment is attempted with. The number and the security code
    travel no further than the request body, and are kept out of ``repr()``
    so they never reach a log: the gateway keeps only the head and the tail
    digits of the number and no digit of the code.
    """

    holder_name: str
    #: The number, digits only, without spaces.
    number: str = field(repr=False)
    security_code: str = field(repr=False)
    #: Two digits, e.g. 04.
    expiry_month: str
    #: Four digits, e.g. 2030.
    expiry_year: str
    #: Whether the customer asked for this card to be kept, so they can pay
    #: with it again without typing it out. The account's provider has to be
    #: able to charge a kept card; one that cannot turns the payment down on
    #: this field rather than declining it.
    should_save: bool = False

    def to_body(self) -> Body:
        return {
            "holder_name": self.holder_name,
            "number": self.number,
            "security_code": self.security_code,
            "expiry_month": self.expiry_month,
            "expiry_year": self.expiry_year,
            "should_save": self.should_save,
        }


@dataclass(frozen=True, kw_only=True)
class TaxDetails:
    """
    Who a customer is billed as when they buy for a company. The three are
    always given together: the gateway turns down a customer that names one
    of them without the others.
    """

    company_title: str
    tax_number: str
    tax_office: str

    def to_body(self) -> Body:
        return {
            "company_title": self.company_title,
            "tax_number": self.tax_number,
            "tax_office": self.tax_office,
        }


@dataclass(frozen=True, kw_only=True)
class Customer:
    """
    The customer a payment is made for, an order is opened for or a card is
    kept for. The merchant names them by its own key for them on the channel
    they came in on: the same key twice is the same customer, and what is
    said of them here becomes the latest the gateway knows.
    """

    #: The key the merchant keeps this customer under in its own system.
    channel_reference: str
    firstname: str
    lastname: str
    email: str
    phone: str
    address: str
    district: str
    province: str
    country: str
    #: The company they are billed as, for a customer buying for one.
    tax: TaxDetails | None = None

    def to_body(self) -> Body:
        body: Body = {
            "channel_reference": self.channel_reference,
            "firstname": self.firstname,
            "lastname": self.lastname,
            "email": self.email,
            "phone": self.phone,
            "address": self.address,
            "district": self.district,
            "province": self.province,
            "country": self.country,
        }

        if self.tax is not None:
            body["tax"] = self.tax.to_body()

        return body


@dataclass(frozen=True, kw_only=True)
class NamedCustomer:
    """
    A customer the gateway already knows, named and nothing more. It is what
    the endpoints that only look a customer up take, such as listing the
    cards kept for them.
    """

    channel_reference: str

    def to_body(self, channel_token: str) -> Body:
        return {
            "channel_token": channel_token,
            "channel_reference": self.channel_reference,
        }


@dataclass(frozen=True, kw_only=True)
class Payment(ChannelMessage):
    """
    A payment handed to the gateway. A payment is made with a card the
    customer typed in or with one they let the merchant keep, never with
    both: naming a kept card and a card at once is turned down by the
    gateway, so it is turned down here first.
    """

    #: The reference the payment is known by in the calling system, such as
    #: SIP-10231. It has to carry at least one digit: its digits end the order
    #: number the bank is sent, so the payment can be found in the bank's panel.
    channel_reference: str
    #: The amount, as digits with the kurus behind a point: '100', '100.1' or
    #: '100.10'. A comma is refused. It is a string so that it is signed and
    #: sent exactly as it is written here, with no rounding on the way.
    amount: str
    installment_number: int
    #: The address the customer is paying from, as the merchant sees it.
    ip: str
    customer: Customer
    #: The card typed in. Left out only when a kept card is named instead.
    card: Card | None = None
    #: A card the customer let the merchant keep, by the token the gateway gave it.
    saved_card_token: str | None = None
    #: Three letters, e.g. TRY. Left out, the gateway takes the lira.
    currency: str | None = None
    #: The payment account to charge through. Left out, the team's routing
    #: rules pick the account, and the team's default account is used when
    #: none of them holds. A payment with a kept card always goes through the
    #: account the card is kept at.
    payment_provider_token: str | None = None
    #: What is being sold, where the customer spreads the amount over months
    #: and the bank takes something for the waiting on top of it. Left out
    #: where the two are the same, which is most payments.
    base_amount: str | None = None

    def __post_init__(self) -> None:
        if (self.card is None) == (self.saved_card_token is None):
            raise ValueError("Bir ödeme ya bir kartla ya da kayıtlı bir kartla yapılır; ikisi birden ya da hiçbiri verilemez.")

    def to_body(self, channel_token: str) -> Body:
        body: Body = {
            "transaction": _said({
                "channel_token": self._channel(channel_token),
                "channel_reference": self.channel_reference,
                "payment_provider_token": self.payment_provider_token,
                "amount": self.amount,
                "base_amount": self.base_amount,
                "currency": self.currency,
                "installment_number": self.installment_number,
                "ip": self.ip,
                "saved_card_token": self.saved_card_token,
            }),
            "customer": self.customer.to_body(),
        }

        if self.card is not None:
            body["card"] = self.card.to_body()

        return body


@dataclass(frozen=True, kw_only=True)
class SecurePayment(Payment):
    """
    A payment the customer confirms with their bank. The gateway does not
    settle it; it hands back the address the customer has to be sent to, and
    posts them back to ``callback_url`` once they are done.
    """

    path: ClassVar[str] = "secure-payment"

    #: Where the customer is posted back to, with the signed outcome, once they are done at their bank.
    callback_url: str

    def to_body(self, channel_token: str) -> Body:
        body = super().to_body(channel_token)
        body["transaction"]["callback_url"] = self.callback_url

        return body


@dataclass(frozen=True, kw_only=True)
class RegularPayment(Payment):
    """
    A payment charged straight to the card, without sending the customer to
    their bank to confirm it. A successful answer is a settled payment.
    """

    path: ClassVar[str] = "regular-payment"


@dataclass(frozen=True, kw_only=True)
class OrderItem:
    """
    One line of what an order is made up of. A line names one of the
    merchant's products by its own key for it; whatever it leaves unsaid —
    name, price, tax — is filled in from the product saved with
    ``save_product()``. What it does say holds for this order alone.

    A line whose key names no product still goes through, as long as it
    brings its own name and price.
    """

    #: The key the product is saved under on the order's channel.
    channel_reference: str
    #: Left out, the product's own name is shown.
    name: str | None = None
    #: Left out, the line is for one.
    quantity: int | None = None
    #: The price of one, as digits with the kurus behind a point. Left out, the product's own price is charged.
    unit_amount: str | None = None
    #: The tax included in the price, as a percentage, e.g. '20'. Left out, the product's own rate is used.
    tax_rate: str | None = None

    def to_body(self) -> Body:
        return _said({
            "channel_reference": self.channel_reference,
            "name": self.name,
            "quantity": self.quantity,
            "unit_amount": self.unit_amount,
            "tax_rate": self.tax_rate,
        })


@dataclass(frozen=True, kw_only=True)
class OrderPayment(ChannelMessage):
    """
    An order opened to be paid on the gateway's own page. Nothing is charged
    here: the answer carries the address to send the customer to, and they
    give their card there. What the order comes to is not sent; the gateway
    adds up the lines and answers with the amount.
    """

    path: ClassVar[str] = "order-payment"

    #: The number the order is known by in the calling system.
    channel_reference: str
    #: Where the customer is posted back to, with the signed outcome, once the order is paid.
    success_url: str
    customer: Customer
    #: What the order is made up of; at least one line.
    items: list[OrderItem]
    #: Where the customer goes if they turn back without paying.
    cancel_url: str | None = None
    description: str | None = None
    #: Three letters, e.g. TRY. Left out, the gateway takes the lira.
    currency: str | None = None
    #: The payment account the order is paid through, by its token. Left out,
    #: the merchant's Gate rules pick the account, and its default account is
    #: used where none of them holds.
    payment_provider_token: str | None = None

    def to_body(self, channel_token: str) -> Body:
        return {
            "order": _said({
                "channel_token": self._channel(channel_token),
                "channel_reference": self.channel_reference,
                "payment_provider_token": self.payment_provider_token,
                "description": self.description,
                "currency": self.currency,
                "success_url": self.success_url,
                "cancel_url": self.cancel_url,
                "items": [item.to_body() for item in self.items],
            }),
            "customer": self.customer.to_body(),
        }


@dataclass(frozen=True, kw_only=True)
class SubscriptionItem:
    """
    One line of what a subscription is for: one of the merchant's recurring
    products, named by its own key for it. What it costs and how often it
    comes round are the product's, as saved with ``save_product()``.
    """

    #: The key the recurring product is saved under on the subscription's channel.
    channel_reference: str
    #: Left out, the line is for one.
    quantity: int | None = None
    #: The price of one for the first period only, as digits with the kurus
    #: behind a point: an opening offer. The periods after it are charged at
    #: the product's own price. Left out, the first period is charged at that
    #: price too.
    unit_amount: str | None = None

    def to_body(self) -> Body:
        return _said({
            "channel_reference": self.channel_reference,
            "quantity": self.quantity,
            "unit_amount": self.unit_amount,
        })


@dataclass(frozen=True, kw_only=True)
class SubscriptionPayment(ChannelMessage):
    """
    A subscription opened for a customer and paid for the first time on the
    gateway's own page. Nothing is charged here: the answer carries the
    address to send the customer to. The card is kept, because the periods
    to come are taken from it.

    The products subscribed to come round at the same frequency and are
    priced in the same money, because a subscription is charged as one thing.
    """

    path: ClassVar[str] = "subscription-payment"

    #: The key the subscription is known by in the calling system.
    channel_reference: str
    #: What is subscribed to; at least one line, each product once.
    items: list[SubscriptionItem]
    #: Where the customer is posted back to, with the signed outcome, once the first period is paid.
    success_url: str
    customer: Customer
    #: Where the customer goes if they turn back without paying.
    cancel_url: str | None = None
    #: Where the merchant is told, signed, whenever the subscription's state changes.
    webhook_url: str | None = None
    #: The payment account the subscription is paid through, by its token;
    #: the card is kept there and renewals are taken there. Left out, the
    #: merchant's Gate rules pick the account, and its default account is
    #: used where none of them holds.
    payment_provider_token: str | None = None

    def to_body(self, channel_token: str) -> Body:
        return {
            "subscription": _said({
                "channel_token": self._channel(channel_token),
                "channel_reference": self.channel_reference,
                "payment_provider_token": self.payment_provider_token,
                "items": [item.to_body() for item in self.items],
                "success_url": self.success_url,
                "cancel_url": self.cancel_url,
                "webhook_url": self.webhook_url,
            }),
            "customer": self.customer.to_body(),
        }


@dataclass(frozen=True, kw_only=True)
class PaymentMessage(Message):
    """
    Something asked of a payment that has already been made. The payment is
    named by the token the gateway gave it, and nothing else is sent.
    """

    #: The payment's token in the gateway, as it answered when the payment was made.
    transaction_token: str

    def to_body(self, channel_token: str) -> Body:
        return {"transaction": {"token": self.transaction_token}}


@dataclass(frozen=True, kw_only=True)
class RefundPayment(PaymentMessage):
    """
    Money given back out of a payment the provider has already settled,
    whole or in part.
    """

    path: ClassVar[str] = "refund-payment"

    #: How much goes back, as digits with the kurus behind a point: '35.50'.
    #: Leave it out and everything the payment has left in it goes back. It
    #: is never more than the payment has left: the gateway turns down
    #: anything larger.
    amount: str | None = None

    def to_body(self, channel_token: str) -> Body:
        return _said({**super().to_body(channel_token), "amount": self.amount})


@dataclass(frozen=True, kw_only=True)
class CancelPayment(PaymentMessage):
    """
    The whole of a payment taken back before the provider has settled it.
    There is no amount to name: anything less goes back as a refund.
    """

    path: ClassVar[str] = "cancel-payment"


@dataclass(frozen=True, kw_only=True)
class RetrievePayment(PaymentMessage):
    """
    How a payment went, asked for after the fact. A customer sent to their
    bank comes back carrying the payment's token and nothing more; this is
    the call that says what became of it.
    """

    path: ClassVar[str] = "retrieve-payment"


@dataclass(frozen=True, kw_only=True)
class RetrieveBin(Message):
    """
    A question about a card before anything is charged to it: who issued it,
    what kind of card it is, and how the amount may be paid off on it. Only
    the head of the number is sent, never the whole of it.
    """

    path: ClassVar[str] = "retrieve-bin"

    #: The first six to eight digits of the card.
    bin: str
    #: What the payment would come to, as digits with the kurus behind a point: '1000.00'.
    amount: str
    #: The account to ask. Left out, the account the team's routing rules
    #: would send the card to is asked — the default one when none of them
    #: holds — so the instalments match a payment that names no account either.
    payment_provider_token: str | None = None
    #: The money the payment is taken in; the lira unless another is named.
    currency: str | None = None

    def to_body(self, channel_token: str) -> Body:
        return {
            "transaction": _said({
                "payment_provider_token": self.payment_provider_token,
                "amount": self.amount,
                "currency": self.currency,
            }),
            "card": {"bin": self.bin},
        }


@dataclass(frozen=True, kw_only=True)
class SaveProduct(ChannelMessage):
    """
    A product written down in the merchant's catalogue at the gateway, under
    the merchant's own key for it on one of its channels. The same key on
    the same channel is the same product: sending it again changes the one
    already saved. A product is never deleted; it is taken off sale by
    sending it with ``is_active=False``.
    """

    path: ClassVar[str] = "save-product"

    #: The key the product is known by in the calling system.
    channel_reference: str
    name: str
    #: simple for something sold once, recurring for something subscribed to.
    type: Literal["simple", "recurring"]
    #: The price of one, as digits with the kurus behind a point.
    amount: str
    #: The tax included in the price, as a percentage, e.g. '20'.
    tax_rate: str
    #: How often a recurring product comes round. Only a recurring product has one.
    period: Literal["monthly", "yearly"] | None = None
    #: Three letters, e.g. TRY. Left out, the gateway takes the lira.
    currency: str | None = None
    #: Whether it is on sale. Left out, it is.
    is_active: bool | None = None

    def to_body(self, channel_token: str) -> Body:
        return {
            "product": _said({
                "channel_token": self._channel(channel_token),
                "channel_reference": self.channel_reference,
                "name": self.name,
                "type": self.type,
                "amount": self.amount,
                "currency": self.currency,
                "tax_rate": self.tax_rate,
                "period": self.period,
                "is_active": self.is_active,
            }),
        }


@dataclass(frozen=True, kw_only=True)
class SubscriptionMessage(Message):
    """
    Something asked of a subscription that has already been opened, named by
    the token the gateway gave it.
    """

    #: The subscription's token in the gateway, as it answered when it was opened.
    subscription_token: str

    def to_body(self, channel_token: str) -> Body:
        return {"subscription": {"token": self.subscription_token}}


@dataclass(frozen=True, kw_only=True)
class RetrieveSubscription(SubscriptionMessage):
    """Where a subscription stands. Nothing is changed by asking."""

    path: ClassVar[str] = "retrieve-subscription"


@dataclass(frozen=True, kw_only=True)
class CancelSubscription(SubscriptionMessage):
    """
    A subscription called off. Nothing is given back: the customer keeps the
    days they have already paid for, and nothing is charged after that.
    """

    path: ClassVar[str] = "cancel-subscription"


@dataclass(frozen=True, kw_only=True)
class SaveCard(ChannelMessage):
    """
    A card kept for a customer without a payment being made on it.

    Providers without a card store of their own keep a card by charging one
    lira and giving it straight back; those ask for the security code, and
    the ones with a real card store do not, so it may be left empty.
    """

    path: ClassVar[str] = "save-card"

    customer: Customer
    card: Card
    #: The payment account to keep the card at. Left out, the team's default account is used.
    payment_provider_token: str | None = None

    def to_body(self, channel_token: str) -> Body:
        card = self.card.to_body()
        del card["should_save"]

        if card["security_code"] == "":
            del card["security_code"]

        return {
            "saved_card": _said({
                "channel_token": self._channel(channel_token),
                "payment_provider_token": self.payment_provider_token,
            }),
            "customer": self.customer.to_body(),
            "card": card,
        }


@dataclass(frozen=True, kw_only=True)
class SavedCards(ChannelMessage):
    """
    The cards a customer has let the merchant keep. The card that is theirs
    by default comes first.
    """

    path: ClassVar[str] = "saved-cards"

    customer: NamedCustomer

    def to_body(self, channel_token: str) -> Body:
        return {"customer": self.customer.to_body(self._channel(channel_token))}


@dataclass(frozen=True, kw_only=True)
class SavedCardMessage(ChannelMessage):
    """
    Something done to one of a customer's kept cards. The card is named by
    the token the gateway gave it, and the customer alongside it, so a card
    can only ever be reached through the customer it belongs to.
    """

    customer: NamedCustomer
    #: The card's token in the gateway, as a listing of the customer's cards gave it.
    saved_card_token: str

    def to_body(self, channel_token: str) -> Body:
        return {
            "customer": self.customer.to_body(self._channel(channel_token)),
            "saved_card": {"token": self.saved_card_token},
        }


@dataclass(frozen=True, kw_only=True)
class DefaultSavedCard(SavedCardMessage):
    """
    Making one of a customer's kept cards the one they pay with unless they
    say otherwise.
    """

    path: ClassVar[str] = "default-saved-card"


@dataclass(frozen=True, kw_only=True)
class DeleteSavedCard(SavedCardMessage):
    """
    Letting go of a kept card, at the provider first and with the gateway
    after: a card the provider would not let go of stays, and the answer
    says why.
    """

    path: ClassVar[str] = "delete-saved-card"
