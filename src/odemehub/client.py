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
    ForbiddenError,
    NotFoundError,
    RateLimitError,
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
    The address the gateway is reached at and the credentials it is reached
    with. A credential pair belongs to a single team, and the team is part of
    the address, so a pair only ever opens its own team's endpoints.
    """

    #: The address the application is served from, e.g. https://app.odemehub.com.
    base_url: str
    #: The team the payments are made on behalf of: the ten-digit workspace id
    #: the Entegrasyon page shows.
    team: str
    api_key: str = field(repr=False)
    api_secret: str = field(repr=False)
    #: How long a request may take, in seconds.
    timeout: float = 60.0

    def path(self, endpoint: str) -> str:
        """The path of a gateway endpoint for this team, as it is signed: with its leading slash and nothing in front of it."""
        return f"/api/{self.team}/gateway/{endpoint}"

    def url(self, endpoint: str) -> str:
        """The full address of a gateway endpoint for this team."""
        return self.base_url.rstrip("/") + self.path(endpoint)


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
    How a signed request reaches the gateway. The client sends through
    urllib unless it is handed another, e.g. one built on requests or httpx.
    Every request is a POST with a JSON body.
    """

    def send(self, method: str, url: str, headers: Mapping[str, str], body: bytes | None, timeout: float) -> HttpResponse: ...


class UrllibTransport:
    """Sends with the standard library, so the client needs nothing installed."""

    def send(self, method: str, url: str, headers: Mapping[str, str], body: bytes | None, timeout: float) -> HttpResponse:
        http_request = urllib.request.Request(url, data=body, headers=dict(headers), method=method)

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

    There is one method per endpoint, named after it: ``create-order`` is
    ``create_order()``, and takes a ``request.CreateOrder``.
    """

    #: The header the API key travels in.
    API_KEY_HEADER = "X-Api-Key"

    def __init__(self, options: Options, transport: Transport | None = None) -> None:
        self._options = options
        self._transport = transport or UrllibTransport()
        self._signature = Signature(options.api_secret)

    # Payments --------------------------------------------------------------

    def secure_payment(self, payment: request.SecurePayment) -> response.SecurePayment:
        """
        Start a payment the customer confirms with their bank. A successful
        answer is not a settled payment: the customer is still to be sent to
        the address it comes back with, and ``retrieve_payments()`` says what
        became of it once they are back.
        """
        return response.SecurePayment.from_body(self._send(payment))

    def regular_payment(self, payment: request.RegularPayment) -> response.RegularPayment:
        """Charge a payment straight to the card. A successful answer is a settled payment."""
        return response.RegularPayment.from_body(self._send(payment))

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

    def retrieve_payments(self, payments: request.RetrievePayments | None = None) -> response.PaymentList:
        """
        Payments as they stand — by token, every attempt under one of the
        merchant's own references, or the ones made between two days; the
        last seven days when nothing is named.
        """
        return response.PaymentList.from_body(self._send(payments or request.RetrievePayments()))

    def retrieve_bin(self, retrieve_bin: request.RetrieveBin) -> response.Bin:
        """
        Ask what the gateway's provider knows about a card by the head of its
        number, and how an amount may be paid off on it. Nothing is charged
        and nothing is written down.
        """
        return response.Bin.from_body(self._send(retrieve_bin))

    # Orders ----------------------------------------------------------------

    def create_order(self, order: request.CreateOrder) -> response.OrderDetails:
        """
        Open an order to be paid on the gateway's own page, or overwrite the
        open one already under the same reference. Nothing is charged here;
        the customer is sent to the address that comes back and pays there.
        """
        return response.OrderDetails.from_body(self._send(order))

    def retrieve_orders(self, orders: request.RetrieveOrders | None = None) -> response.OrderList:
        """Orders as they stand, each with its customer."""
        return response.OrderList.from_body(self._send(orders or request.RetrieveOrders()))

    def update_order(self, order: request.UpdateOrder) -> response.OrderDetails:
        """Change an open order. Only what is sent is written."""
        return response.OrderDetails.from_body(self._send(order))

    # Payment links ---------------------------------------------------------

    def create_payment_link(self, link: request.CreatePaymentLink) -> response.PaymentLinkDetails:
        """
        Open a payment link, or overwrite the one already under the same
        reference. The address that comes back is the link itself.
        """
        return response.PaymentLinkDetails.from_body(self._send(link))

    def retrieve_payment_links(self, links: request.RetrievePaymentLinks | None = None) -> response.PaymentLinkList:
        """
        Payment links as they stand, each with the latest fifty payment
        attempts made on it and how many there have been in all.
        """
        return response.PaymentLinkList.from_body(self._send(links or request.RetrievePaymentLinks()))

    def update_payment_link(self, link: request.UpdatePaymentLink) -> response.PaymentLinkDetails:
        """Change a payment link: its lines, its last day, whether it takes payments. Only what is sent is written."""
        return response.PaymentLinkDetails.from_body(self._send(link))

    # Subscriptions ---------------------------------------------------------

    def create_subscription(self, subscription: request.CreateSubscription) -> response.SubscriptionDetails:
        """
        Open a subscription, its first renewal to be paid on the gateway's
        own page and the rest taken from the card kept then; or overwrite
        the one already under the same reference while nothing has been
        paid on it.
        """
        return response.SubscriptionDetails.from_body(self._send(subscription))

    def retrieve_subscriptions(self, subscriptions: request.RetrieveSubscriptions | None = None) -> response.SubscriptionList:
        """Subscriptions as they stand, each with its customer and the renewal it is on."""
        return response.SubscriptionList.from_body(self._send(subscriptions or request.RetrieveSubscriptions()))

    def update_subscription(self, subscription: request.UpdateSubscription) -> response.SubscriptionDetails:
        """
        Change a subscription, or call it off with the status ``cancelled``.
        Only what is sent is written. Nothing is given back on a
        cancellation: the customer is served to the end of what they paid
        for, and nothing is charged after that.
        """
        return response.SubscriptionDetails.from_body(self._send(subscription))

    # Saved cards -----------------------------------------------------------

    def create_saved_card(self, saved_card: request.CreateSavedCard) -> response.SavedCardDetails:
        """Keep a card for a customer without making a payment on it."""
        return response.SavedCardDetails.from_body(self._send(saved_card))

    def retrieve_saved_cards(self, saved_cards: request.RetrieveSavedCards | None = None) -> response.SavedCardList:
        """
        Kept cards — by token, every card of a customer by their reference, or
        the ones kept between two days — each with its customer, the default
        first.
        """
        return response.SavedCardList.from_body(self._send(saved_cards or request.RetrieveSavedCards()))

    def update_saved_card(self, saved_card: request.UpdateSavedCard) -> response.SavedCardDetails:
        """Make one of a customer's kept cards the one they pay with unless they say otherwise."""
        return response.SavedCardDetails.from_body(self._send(saved_card))

    def delete_saved_card(self, saved_card: request.DeleteSavedCard) -> response.DeletedSavedCard:
        """Let go of a kept card, at the provider and here."""
        return response.DeletedSavedCard.from_body(self._send(saved_card))

    # Webhooks --------------------------------------------------------------

    def webhook(self, method: str, path: str, payload: str | bytes, timestamp: str | None, signature: str | None) -> response.Webhook:
        """
        Read a word the gateway posted to one of the merchant's webhook
        addresses. Hand it the request exactly as it arrived — the method,
        the path of the address it came to (without the query string), the
        raw body byte for byte and the two headers — and nothing in it is
        believed until the signature is checked against the secret.

        The word only names what it is about; ask the gateway what became of
        it before acting on it. Answer with any 2xx once the word is taken;
        the gateway tries again, up to five times, until it hears one.

        :raises SignatureError: when the signature does not hold.
        """
        if not self.verify_webhook(method, path, payload, timestamp, signature):
            raise SignatureError("Bildirimin imzası doğrulanamadı; bildirim ödeme geçidinden gelmemiş olabilir.")

        text = payload.decode("utf-8") if isinstance(payload, bytes) else payload

        return response.Webhook.from_body(self._decode(text, 0))

    def verify_webhook(self, method: str, path: str, payload: str | bytes, timestamp: str | None, signature: str | None) -> bool:
        """
        Whether a word that arrived at a webhook address was signed by the
        gateway with this team's secret, recently enough to be taken. The
        path is the address's own, with its leading slash and without the
        query string; the body is the raw text, byte for byte.
        """
        return self._signature.verify(method, path, payload, timestamp, signature)

    # The wire --------------------------------------------------------------

    def _send(self, message: request.Message) -> Body:
        """
        Sign what is being asked for, hand it to the gateway and read the
        answer back. The body is signed exactly as it is sent, byte for byte,
        so it is written once and used for both.
        """
        endpoint = message.path()
        path = self._options.path(endpoint)
        payload = json.dumps(message.to_body(), ensure_ascii=False, separators=(",", ":")).encode("utf-8")

        headers = {
            self.API_KEY_HEADER: self._options.api_key,
            **self._signature.headers("POST", path, payload),
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        try:
            answer = self._transport.send("POST", self._options.url(endpoint), headers, payload, self._options.timeout)
        except (OSError, http.client.HTTPException) as error:
            raise TransportError(f"Ödeme geçidine ulaşılamadı: {error}") from error

        return self._read(answer, "POST", path)

    def _read(self, answer: HttpResponse, method: str, path: str) -> Body:
        """
        Read the answer. An outcome is answered with 200 and signed, however
        the payment itself turned out: a payment the provider declined is an
        outcome like any other and comes back rather than being raised. The
        signature is checked over the method and path of the request and the
        answer's own moment and body.

        Anything else is a refusal — the request never became an outcome —
        and the status says which kind. The gateway signs most of those too,
        but a signature does not make a refusal an outcome, so the status is
        read first.
        """
        payload = answer.body.decode("utf-8", errors="replace")

        if answer.status == 200:
            verified = self._signature.verify(
                method,
                path,
                answer.body,
                answer.header(Signature.TIMESTAMP_HEADER) or None,
                answer.header(Signature.HEADER) or None,
            )

            if not verified:
                raise SignatureError("Yanıtın imzası doğrulanamadı; yanıt ödeme geçidinden gelmemiş olabilir.")

            return self._decode(payload, answer.status)

        message, errors = self._refusal(payload)

        if answer.status == 401:
            raise AuthenticationError(message)

        if answer.status == 403:
            raise ForbiddenError(message)

        if answer.status == 404:
            raise NotFoundError(message)

        if answer.status == 422:
            raise ValidationError(message, errors)

        if answer.status == 429:
            raise RateLimitError(message, self._retry_after(answer))

        raise UnexpectedResponseError(message, answer.status)

    @staticmethod
    def _retry_after(answer: HttpResponse) -> int | None:
        """How long the gateway asked to wait before trying again, in seconds."""
        value = answer.header("Retry-After")

        return int(value) if value is not None and value.isdigit() else None

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
