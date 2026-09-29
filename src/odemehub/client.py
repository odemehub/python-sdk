"""The gateway, as the merchant's application talks to it."""

from __future__ import annotations

import http.client
import json
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from . import request, response
from .errors import (
    AuthenticationError,
    SignatureError,
    TransportError,
    UnexpectedResponseError,
    ValidationError,
)
from .signature import Signature

Body = dict[str, Any]


@dataclass(frozen=True, kw_only=True)
class Options:
    """
    The address the gateway is reached at, the credentials it is reached
    with and the channel the caller speaks for. A credential pair belongs to
    a single team, and the team is part of the address, so a pair only ever
    opens its own team's endpoints.
    """

    #: The address the application is served from, e.g. https://odeme.gurmehub.com.
    base_url: str
    #: The team the payments are made on behalf of, as the Entegrasyon page names it.
    team: str
    #: The channel every request speaks for: the shop, the marketplace or the
    #: branch the customer reached the merchant through, by the token the
    #: team's own Kanallar page gives it. A merchant selling on more than one
    #: channel may still name another on a single request.
    channel_token: str
    api_key: str = field(repr=False)
    api_secret: str = field(repr=False)
    #: How long a request may take, in seconds.
    timeout: float = 60.0

    def url(self, path: str) -> str:
        """The full address of a gateway endpoint for this team."""
        return f"{self.base_url.rstrip('/')}/api/{self.team}/gateway/{path}"


@dataclass(frozen=True)
class HttpResponse:
    """What came back over the wire, before anything is made of it."""

    status: int
    headers: Mapping[str, str]
    body: bytes

    def header(self, name: str) -> str | None:
        for key, value in self.headers.items():
            if key.lower() == name.lower():
                return value

        return None


class Transport(Protocol):
    """
    How a signed body reaches the gateway. The client posts through urllib
    unless it is handed another, e.g. one built on requests or httpx.
    """

    def post(self, url: str, headers: Mapping[str, str], body: bytes, timeout: float) -> HttpResponse: ...


class UrllibTransport:
    """Posts with the standard library, so the client needs nothing installed."""

    def post(self, url: str, headers: Mapping[str, str], body: bytes, timeout: float) -> HttpResponse:
        http_request = urllib.request.Request(url, data=body, headers=dict(headers), method="POST")

        try:
            with urllib.request.urlopen(http_request, timeout=timeout) as answer:
                return HttpResponse(answer.status, dict(answer.headers.items()), answer.read())
        except urllib.error.HTTPError as answer:
            return HttpResponse(answer.code, dict(answer.headers.items()), answer.read())


class Client:
    """
    Every request leaves signed with the team's secret and every answer is
    checked against it, so both sides can tell the other is really who it
    says it is.
    """

    #: The header the API key travels in.
    API_KEY_HEADER = "X-Api-Key"

    def __init__(self, options: Options, transport: Transport | None = None) -> None:
        self._options = options
        self._transport = transport or UrllibTransport()
        self._signature = Signature(options.api_secret)

    def secure_payment(self, payment: request.SecurePayment) -> response.SecurePayment:
        """
        Start a payment the customer confirms with their bank. A successful
        answer is not a settled payment: the customer is still to be sent to
        the address it comes back with.
        """
        return response.SecurePayment.from_body(self._send(payment))

    def regular_payment(self, payment: request.RegularPayment) -> response.RegularPayment:
        """Charge a payment straight to the card. A successful answer is a settled payment."""
        return response.RegularPayment.from_body(self._send(payment))

    def order_payment(self, order_payment: request.OrderPayment) -> response.OrderPayment:
        """Open an order to be paid on the gateway's own page, and get back the address to send the customer to."""
        return response.OrderPayment.from_body(self._send(order_payment))

    def subscription_payment(self, subscription: request.SubscriptionPayment) -> response.Subscription:
        """
        Open a subscription. The customer is sent to the address it comes back
        with and pays there, and the periods after that are taken from the
        card they pay with.
        """
        return response.Subscription.from_body(self._send(subscription))

    def refund_payment(self, refund: request.RefundPayment) -> response.GiveBack:
        """
        Give money back out of a payment the provider has settled, whole or
        in part. A refund that names no amount gives back everything the
        payment has left in it.
        """
        return response.GiveBack.from_body(self._send(refund))

    def cancel_payment(self, cancel: request.CancelPayment) -> response.GiveBack:
        """
        Take back the whole of a payment the provider has not settled yet.
        Anything less than the whole of it goes back as a refund instead.
        """
        return response.GiveBack.from_body(self._send(cancel))

    def retrieve_payment(self, payment: request.RetrievePayment) -> response.Payment:
        """
        How a payment went. A customer sent to their bank comes back to the
        merchant with the payment's token and a hint at how it went; the hint
        is worth nothing on its own, and this call says what really became of it.
        """
        return response.Payment.from_body(self._send(payment))

    def retrieve_bin(self, retrieve_bin: request.RetrieveBin) -> response.Bin:
        """
        Ask what the gateway's provider knows about a card by the head of its
        number, and how an amount may be paid off on it. Nothing is charged
        and nothing is written down.
        """
        return response.Bin.from_body(self._send(retrieve_bin))

    def save_product(self, product: request.SaveProduct) -> response.Product:
        """
        Save a product in the merchant's catalogue at the gateway, or change
        the one already saved under the same key on the same channel. Order
        lines and subscriptions name products by key.
        """
        return response.Product.from_body(self._send(product))

    def retrieve_subscription(self, subscription: request.RetrieveSubscription) -> response.Subscription:
        """
        Where a subscription stands: what it is for, the period it is on and
        whether that period has been paid for.
        """
        return response.Subscription.from_body(self._send(subscription))

    def cancel_subscription(self, subscription: request.CancelSubscription) -> response.Subscription:
        """
        Call a subscription off. Nothing is given back: the customer keeps
        the days they already paid for and is served to the end of them, and
        nothing is charged after that.
        """
        return response.Subscription.from_body(self._send(subscription))

    def save_card(self, save_card: request.SaveCard) -> response.KeptCard:
        """Keep a card for a customer without making a payment on it."""
        return response.KeptCard.from_body(self._send(save_card))

    def saved_cards(self, saved_cards: request.SavedCards) -> response.KeptCards:
        """The cards a customer let the merchant keep, the default one first."""
        return response.KeptCards.from_body(self._send(saved_cards))

    def default_saved_card(self, default_saved_card: request.DefaultSavedCard) -> response.KeptCard:
        """Make one of a customer's kept cards the one they pay with unless they say otherwise."""
        return response.KeptCard.from_body(self._send(default_saved_card))

    def delete_saved_card(self, delete_saved_card: request.DeleteSavedCard) -> response.KeptCard:
        """Let go of one of a customer's kept cards, at the provider and here."""
        return response.KeptCard.from_body(self._send(delete_saved_card))

    def subscription_webhook(self, payload: str | bytes, signature: str | None) -> response.SubscriptionWebhook:
        """
        Read the word the gateway sent about a subscription: posted to the
        address the subscription was opened with, as plain JSON signed in the
        ``X-Signature`` header. Hand it the body exactly as it arrived, byte
        for byte, together with the header; nothing in it is to be believed
        until the signature holds.

        :raises SignatureError: when the signature does not hold.
        """
        if not self._signature.verify(payload, signature):
            raise SignatureError("Bildirimin imzası doğrulanamadı; bildirim ödeme geçidinden gelmemiş olabilir.")

        text = payload.decode("utf-8") if isinstance(payload, bytes) else payload

        return response.SubscriptionWebhook.from_body(self._decode(text, 0))

    def _send(self, message: request.Message) -> Body:
        """
        Sign what is being asked for, hand it to the gateway and read the
        answer back. The body is signed exactly as it is sent, byte for byte,
        so it is written once and used for both.
        """
        payload = json.dumps(
            message.to_body(self._options.channel_token),
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

        try:
            answer = self._transport.post(
                self._options.url(message.path),
                {
                    self.API_KEY_HEADER: self._options.api_key,
                    Signature.HEADER: self._signature.sign(payload),
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                payload,
                self._options.timeout,
            )
        except (OSError, http.client.HTTPException) as error:
            raise TransportError(f"Ödeme geçidine ulaşılamadı: {error}") from error

        return self._read(answer)

    def _read(self, answer: HttpResponse) -> Body:
        """
        Read the answer. An outcome is answered with 200 and signed, however
        the payment itself turned out: a payment the provider declined is an
        outcome like any other and comes back rather than being raised.

        Anything else is a refusal — the request never became a payment — and
        the status says which kind. The gateway signs some of those too, but a
        signature does not make a refusal an outcome, so the status is read
        first.
        """
        payload = answer.body.decode("utf-8", errors="replace")

        if answer.status == 200:
            if not self._signature.verify(answer.body, answer.header(Signature.HEADER) or None):
                raise SignatureError("Yanıtın imzası doğrulanamadı; yanıt ödeme geçidinden gelmemiş olabilir.")

            return self._decode(payload, answer.status)

        message, errors = self._refusal(payload)

        if answer.status == 401:
            raise AuthenticationError(message)

        if answer.status == 422:
            raise ValidationError(message, errors)

        raise UnexpectedResponseError(message, answer.status)

    def _refusal(self, payload: str) -> tuple[str, dict[str, list[str]]]:
        """
        What a refusal says. The gateway answers in the one shape it answers
        everything in, so what went wrong and which fields it is about are
        found under ``result``.
        """
        body = self._parse(payload) or {}
        result = body.get("result") if isinstance(body.get("result"), dict) else {}

        if isinstance(result.get("message"), str):
            message = result["message"]
        elif isinstance(body.get("message"), str):
            message = body["message"]
        else:
            message = "Ödeme geçidi isteği reddetti."

        if isinstance(result.get("errors"), dict):
            errors = result["errors"]
        elif isinstance(body.get("errors"), dict):
            errors = body["errors"]
        else:
            errors = {}

        return message, errors

    def _decode(self, payload: str, status: int) -> Body:
        """Read a body the signature has already vouched for."""
        body = self._parse(payload)

        if body is None:
            raise UnexpectedResponseError(f"Ödeme geçidi {status} durumuyla okunamayan bir yanıt döndü.", status)

        return body

    @staticmethod
    def _parse(payload: str) -> Body | None:
        try:
            body = json.loads(payload)
        except ValueError:
            return None

        return body if isinstance(body, dict) else None
