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

from .enums import AmountType, Currency, CurrencyType, Period, SubscriptionStatus, TaxMode

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
    Something handed to the gateway: the endpoint it is posted to and the
    body it is sent as.
    """

    #: The endpoint this is sent to, under the team's gateway.
    endpoint: ClassVar[str]

    def path(self) -> str:
        """The endpoint, with the token in the address where the endpoint takes one."""
        return self.endpoint

    def to_body(self) -> Body:
        """The request body."""
        raise NotImplementedError


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

    The reference is what makes them one of the team's customers: the
    customer is written under it once a payment for them goes through, and
    their cards are kept for them and found again by it. It may be left out
    of a payment or an order, and the payer is then nobody the team keeps;
    but a payment that keeps its card, a card kept on its own and a
    subscription have to carry it.

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
    #: out. Needs a customer reference to be kept for, a plan that covers
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
    #: The tax inside the price, as a percentage: '20' or '20.00'. Left out, the line carries no tax.
    tax_rate: str | None = None
    #: The merchant's own key for what is on the line, if it has one.
    reference: str | None = None
    #: The https address of the picture shown beside the line at checkout.
    image: str | None = None
    #: Whether the line is also kept on the team's product list: written
    #: there under its reference, or the product with that reference
    #: brought up to the line. A line kept so has to carry a reference.
    save_as_product: bool | None = None

    def to_body(self) -> Body:
        return _said({
            "reference": self.reference,
            "name": self.name,
            "image": self.image,
            "quantity": self.quantity,
            "unit_amount": self.unit_amount,
            "tax_rate": self.tax_rate,
            "save_as_product": self.save_as_product,
        })


# Payments ------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class Payment(Message):
    """
    A payment handed to the gateway. A payment is made with a card the
    customer typed in or with one they let the merchant keep, never with
    both. With a kept card the payment goes through the account the card is
    kept at, so no account is named either; the gateway turns down a
    payment that names both.
    """

    #: The reference the payment is known by in the calling system, such as
    #: SIP-10231. It has to carry at least one digit: its digits end the
    #: order number the bank is sent, so the payment can be found in the
    #: bank's panel by it.
    reference: str
    #: The amount, as digits with the kurus behind a point: '100', '100.1'
    #: or '100.10'. A comma is refused. It is a string so that it is signed
    #: and sent exactly as it is written here, with no rounding on the way.
    amount: str
    #: 1 to 12. More than one only for a payment asked for and charged in lira.
    installment_number: int
    #: The address the customer is paying from, as the merchant sees it.
    ip: str
    #: Who is paying: the whole billing address and, when the merchant keeps
    #: them, their reference. A payment that keeps its card, or is made with
    #: a kept one, has to name the customer the card is theirs.
    customer: Customer
    #: The card typed in. Left out only when a kept card is named instead.
    card: Card | None = None
    #: A card the customer let the merchant keep, by the token the gateway
    #: gave it.
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

    def to_body(self) -> Body:
        return _said({
            "transaction": _said({
                "reference": self.reference,
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

    #: Where the customer's browser is posted back to once the bank has
    #: answered. An https address reachable from the internet.
    callback_url: str

    def to_body(self) -> Body:
        body = super().to_body()
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

    #: The payment's token in the gateway.
    token: str
    #: How much goes back, as digits with the kurus behind a point: '35.50'.
    #: Left out, everything the payment has left in it goes back.
    amount: str | None = None

    def to_body(self) -> Body:
        return _said({
            "transaction": {"token": self.token},
            "amount": self.amount,
        })


@dataclass(frozen=True, kw_only=True)
class CancelPayment(Message):
    """
    The whole of a payment taken back before the provider has settled it.
    """

    endpoint: ClassVar[str] = "cancel-payment"

    #: The payment's token in the gateway.
    token: str

    def to_body(self) -> Body:
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
    #: What the payment would come to, as digits with the kurus behind a point.
    amount: str
    #: The account to ask. Left out, the account the team's routing rules
    #: would send the card to is asked.
    payment_provider_token: str | None = None
    #: The money the payment is taken in; the lira unless another is named.
    currency: Currency | None = None

    def to_body(self) -> Body:
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
class Retrieve(Message):
    """
    Asking after records of one kind. They are named one of three ways: by
    the token the gateway gave one, by the merchant's own reference for
    them, or by the days they were made on, as ``YYYY-MM-DD`` in the team's
    own timezone, both included and at most seven days apart. Asked with
    none of these, it is the last seven days up to today. The answer is
    always a list, oldest first, and an empty one when nothing matches.
    Nothing is changed by asking.
    """

    #: The field the merchant's own reference travels in.
    reference_field: ClassVar[str] = "reference"

    #: The record's token in the gateway.
    token: str | None = None
    #: The merchant's own reference for them.
    reference: str | None = None
    #: The first day, as ``YYYY-MM-DD``. Given together with ``created_to``.
    created_from: str | None = None
    #: The last day, as ``YYYY-MM-DD``, at most six days after the first.
    created_to: str | None = None

    def to_body(self) -> Body:
        return _said({
            "token": self.token,
            self.reference_field: self.reference,
            "created_from": self.created_from,
            "created_to": self.created_to,
        })


@dataclass(frozen=True, kw_only=True)
class RetrievePayments(Retrieve):
    """
    Payments asked after: one by its token, every attempt made under the
    merchant's reference, or the ones made between two days — the ones the
    bank turned away included, and the ones made on the gateway's own
    checkout page too.
    """

    endpoint: ClassVar[str] = "retrieve-payments"


@dataclass(frozen=True, kw_only=True)
class RetrieveOrders(Retrieve):
    """Orders asked after, each with its customer."""

    endpoint: ClassVar[str] = "retrieve-orders"


@dataclass(frozen=True, kw_only=True)
class RetrieveSubscriptions(Retrieve):
    """Subscriptions asked after, each with its customer and the renewal it is on."""

    endpoint: ClassVar[str] = "retrieve-subscriptions"


@dataclass(frozen=True, kw_only=True)
class RetrievePaymentLinks(Retrieve):
    """
    Payment links asked after, each with how many payments were made on it
    and the latest fifty of them.
    """

    endpoint: ClassVar[str] = "retrieve-payment-links"


@dataclass(frozen=True, kw_only=True)
class RetrieveLinkPayments(Retrieve):
    """
    Payments at the team's links asked after: one by its token, one by the
    reference the gateway gave it (``LINKPAY{n}``), or the ones made between
    two days. A payment at a link is opened by the payer paying there, never
    by the merchant, so it is only ever asked after.
    """

    endpoint: ClassVar[str] = "retrieve-link-payments"


@dataclass(frozen=True, kw_only=True)
class RetrieveSavedCards(Retrieve):
    """
    Kept cards asked after: one by its token, every card of a customer by
    the merchant's reference for them (``reference``), or the ones kept
    between two days. A customer's cards come with the one they pay with by
    default first.
    """

    endpoint: ClassVar[str] = "retrieve-saved-cards"
    reference_field: ClassVar[str] = "customer_reference"


# Orders and subscriptions --------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class CheckoutMessage(Message):
    """
    An order or a subscription, opened or changed, to be paid on the
    gateway's own checkout page. Nothing is charged here: the answer carries
    the address to send the customer to, and they give their card there.

    What it comes to is not sent. The gateway adds up the lines and the
    shipping method the payer picks from the team's own list and answers
    with the amount, so the total can never disagree with what it is made
    up of. The customer is whatever is known: it is filled in on the
    checkout page and the payer is asked for the rest.

    Every opening opens a new one under a new token, even under a reference
    sent before: the reference is the merchant's own and may repeat, so
    nothing already there is written over. Keep the token each answer comes
    back with; it is what names the record to ask after or change it.
    """

    #: The key the group travels under: order or subscription.
    group: ClassVar[str]

    #: The reference it is known by in the calling system. Has to carry at
    #: least one digit; it need not be unique.
    reference: str | None = None
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
    #: Whether the checkout page asks the payer where the goods go. One who
    #: is picks a way of sending from the team's own list, of those that
    #: send there, and its price is added to the amount.
    requires_shipping: bool | None = None

    def _details(self) -> Body:
        return _said({
            "reference": self.reference,
            "description": self.description,
            "payment_provider_token": self.payment_provider_token,
            "currency": _value(self.currency),
            "success_url": self.success_url,
            "cancel_url": self.cancel_url,
            "requires_shipping": self.requires_shipping,
            "items": None if self.items is None else [item.to_body() for item in self.items],
        })

    def _body(self, group: Body) -> Body:
        return _said({
            self.group: group,
            "customer": None if self.customer is None else self.customer.to_body(),
        })


@dataclass(frozen=True, kw_only=True)
class CreateOrder(CheckoutMessage):
    """
    An order opened to be paid once on the gateway's own checkout page. The
    answer carries ``checkout_url``; the customer is sent there, pays, and
    is posted back to ``success_url``. The addresses the team set under
    Webhook in the panel hear that it was paid whether or not the customer
    comes back. The customer may be left out, or sent without a reference:
    the payer then says who they are on the checkout, and is not kept as
    one of the team's customers.
    """

    endpoint: ClassVar[str] = "create-order"
    group: ClassVar[str] = "order"

    reference: str
    success_url: str
    items: Sequence[Item]

    def to_body(self) -> Body:
        return self._body(self._details())


@dataclass(frozen=True, kw_only=True)
class UpdateOrder(CheckoutMessage):
    """
    A change to an open order, named by its token in the address and again
    in the body. Only what is sent is written: a field left out keeps what
    there was, lines sent replace every line there was, and the customer
    sent is written over the one the order had; a reference sent takes the
    place of the one there was. A paid order, or one with a payment under
    way, cannot be changed; the gateway says so on ``token``.
    """

    endpoint: ClassVar[str] = "update-order"
    group: ClassVar[str] = "order"

    #: The order's token in the gateway.
    token: str
    #: Fields to set to nothing: description, cancel_url, payment_provider_token.
    clear: Sequence[str] = ()

    def path(self) -> str:
        return f"{self.endpoint}/{self.token}"

    def to_body(self) -> Body:
        return {
            "token": self.token,
            **self._body(_cleared(self._details(), self.clear)),
        }


@dataclass(frozen=True, kw_only=True)
class CreateSubscription(CheckoutMessage):
    """
    A subscription opened for a customer, its first renewal paid on the
    gateway's own checkout page. Nothing is charged here: the answer carries
    the address to send the customer to. The card is kept there for the
    customer, because the renewals to come are taken from it, so the account
    has to keep cards and take 3D payments, and the customer's reference is
    required.
    """

    endpoint: ClassVar[str] = "create-subscription"
    group: ClassVar[str] = "subscription"

    reference: str
    success_url: str
    items: Sequence[Item]
    #: Who it is for; the reference is required, the rest is asked on the checkout page.
    customer: Customer
    #: How often it renews.
    period: Period
    #: How many renewals are paid in all, 1 to 1000. Left out, it runs until it is called off.
    renewal_limit: int | None = None

    def to_body(self) -> Body:
        return self._body(_said({
            **self._details(),
            "period": _value(self.period),
            "renewal_limit": self.renewal_limit,
        }))


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
    been paid, only the status, the period, the renewal limit and the
    prices of the same lines may change; the gateway turns down anything
    else, the customer included.
    """

    endpoint: ClassVar[str] = "update-subscription"
    group: ClassVar[str] = "subscription"

    #: The subscription's token in the gateway.
    token: str
    #: Only ``cancelled`` is taken; the other states follow the payments.
    status: SubscriptionStatus | None = None
    period: Period | None = None
    #: 1 to 1000, and never fewer than the renewals already paid.
    renewal_limit: int | None = None
    #: Fields to set to nothing: renewal_limit, description, cancel_url, payment_provider_token.
    clear: Sequence[str] = ()

    def path(self) -> str:
        return f"{self.endpoint}/{self.token}"

    def to_body(self) -> Body:
        group = _said({
            **self._details(),
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
class PaymentLinkMessage(Message):
    """
    A payment link, opened or changed: a page anyone holding it may pay,
    again and again, until it is switched off or its last day has gone by.
    It has no customer.

    What it charges is one of two things. A link of lines (``FIXED``, the
    default) charges what its lines add up to, the gateway working the total
    out. A link whose amount the payer picks — any amount they write
    (``CUSTOM``), one of those offered (``PREDEFINED``), or either
    (``PREDEFINED_AND_CUSTOM``) — is paid as one line named ``item_name``,
    with ``tax_rate`` read against it the way ``tax_mode`` says; any lines
    sent with it are passed over. The money may be the one the link is
    written in (``CurrencyType.FIXED``, the default), or one the payer picks
    from ``currencies`` (``SELECTABLE``).
    """

    #: The reference the link is known by in the calling system. Has to carry
    #: at least one digit; it need not be unique.
    reference: str | None = None
    description: str | None = None
    #: The account the link is paid through; it has to take 3D payments.
    payment_provider_token: str | None = None
    #: What the payer pays. Left out on opening, the lines.
    amount_type: AmountType | None = None
    #: The name of the one line a payer-picked amount is paid as; needed by
    #: every type but ``FIXED``.
    item_name: str | None = None
    #: The amounts the payer may pick from, at most ten, each as digits with
    #: the kurus behind a point: '100.00'. Needed by ``PREDEFINED`` and
    #: ``PREDEFINED_AND_CUSTOM``.
    predefined_amounts: Sequence[str] | None = None
    #: The tax on a payer-picked amount, as a percentage: '20'. Left out, it carries none.
    tax_rate: str | None = None
    #: Whether ``tax_rate`` is inside the amount paid or added on top of it.
    #: Left out on opening, inside.
    tax_mode: TaxMode | None = None
    #: The money the link is written in, and the one picked to begin with
    #: when the payer may pick another.
    currency: Currency | None = None
    #: Whether the payer may pick the money. Left out on opening, they may not.
    currency_type: CurrencyType | None = None
    #: The money the payer may pick besides ``currency``; needed when
    #: ``currency_type`` is ``SELECTABLE``.
    currencies: Sequence[Currency] | None = None
    #: Whether the payer is sent an e-mail once their payment goes through.
    #: Left out on opening, they are not.
    emails_payer: bool | None = None
    #: The last day the link may be paid, as ``YYYY-MM-DD`` in the team's
    #: timezone; today or later. Left out, it never runs out.
    expires_at: str | None = None
    #: Whether the link takes payments. Left out, it does.
    is_active: bool | None = None
    #: What a link of lines is for. Sent on a change, they replace every line
    #: there was.
    items: Sequence[Item] | None = None

    def _details(self) -> Body:
        return _said({
            "reference": self.reference,
            "description": self.description,
            "payment_provider_token": self.payment_provider_token,
            "amount_type": _value(self.amount_type),
            "item_name": self.item_name,
            "predefined_amounts": None if self.predefined_amounts is None else list(self.predefined_amounts),
            "tax_rate": self.tax_rate,
            "tax_mode": _value(self.tax_mode),
            "currency": _value(self.currency),
            "currency_type": _value(self.currency_type),
            "currencies": None if self.currencies is None else [_value(currency) for currency in self.currencies],
            "emails_payer": self.emails_payer,
            "expires_at": self.expires_at,
            "is_active": self.is_active,
            "items": None if self.items is None else [item.to_body() for item in self.items],
        })


@dataclass(frozen=True, kw_only=True)
class CreatePaymentLink(PaymentLinkMessage):
    """
    A payment link opened. Every opening opens a new link under a new token,
    even under a reference sent before; nothing already there is written
    over. Keep the token the answer comes back with. A link of lines needs at
    least one line; a link whose amount the payer picks needs none.
    """

    endpoint: ClassVar[str] = "create-payment-link"

    #: Left out, the gateway gives the link a reference of the form ``LINK{n}``.
    reference: str | None = None
    currency: Currency

    def to_body(self) -> Body:
        return {"payment_link": self._details()}


@dataclass(frozen=True, kw_only=True)
class UpdatePaymentLink(PaymentLinkMessage):
    """
    A change to a payment link, named by its token in the address and again
    in the body. Only what is sent is written; lines sent replace the lines
    there were. A link left as, or turned back into, a link of lines has to
    have lines, so one turned back from a payer-picked amount sends them. A
    link whose last day has gone by is switched on again by a new day alone.
    """

    endpoint: ClassVar[str] = "update-payment-link"

    #: The link's token in the gateway.
    token: str
    #: Fields to set to nothing: description, payment_provider_token,
    #: expires_at, item_name, predefined_amounts, tax_rate, currencies.
    clear: Sequence[str] = ()

    def path(self) -> str:
        return f"{self.endpoint}/{self.token}"

    def to_body(self) -> Body:
        return {
            "token": self.token,
            "payment_link": _cleared(self._details(), self.clear),
        }


# Saved cards ---------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class CreateSavedCard(Message):
    """
    A card kept for a customer without a payment being made on it. Once the
    provider takes it, the team's customer under the reference is written
    from what was sent and the card is kept for them.

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

    def to_body(self) -> Body:
        card = self.card.to_body()
        card.pop("should_save", None)

        return _said({
            "saved_card": None if self.payment_provider_token is None else {"payment_provider_token": self.payment_provider_token},
            "customer": self.customer.to_body(),
            "card": card,
        })


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

    def to_body(self) -> Body:
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

    def to_body(self) -> Body:
        return {"token": self.token}
