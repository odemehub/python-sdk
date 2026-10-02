# ödemehub Python SDK

ödemehub ödeme geçidini kendi uygulamanızdan kullanmak için Python istemcisi. Kart çekmek, 3D ödeme başlatmak, sipariş, abonelik ve ödeme linki açmak, kart saklamak, iade ve iptal yapmak, taksit sormak: hepsi burada.

İstemci her isteği gizli anahtarınızla imzalar, gelen her yanıtın imzasını doğrular. Siz imza, başlık ya da JSON ayrıntılarıyla uğraşmazsınız. Her uç nokta için bir metot vardır ve adı uç noktanın adıdır: `create-order` için `create_order()`, `retrieve-saved-cards-by-reference` için `retrieve_saved_cards_by_reference()`. Yalnızca standart kütüphaneyi kullanır; kurulacak başka paket yoktur. Tip ipuçları pakettedir.

## Kurulum

Python 3.10 ve üzeri gerekir.

```bash
pip install odemehub
```

## Yapılandırma

Dört bilgi gerekir. Hepsi paneldeki **Entegrasyon** sayfasındadır: Çalışma Alanı Kimliğiniz, API anahtarı, gizli anahtar ve kanalınızın token'ı.

```python
import os

from odemehub import Client, Options

client = Client(Options(
    base_url="https://app.odemehub.com",
    team="1000000001",                                     # Çalışma Alanı Kimliği
    channel_token="6f1c2e7a-4b3d-4c8e-9a61-2f5d7b0c3e14",  # müşterinin size ulaştığı kanal
    api_key=os.environ["ODEMEHUB_API_KEY"],
    api_secret=os.environ["ODEMEHUB_API_SECRET"],
))
```

Gizli anahtar hiçbir zaman tel üzerinden gitmez; yalnızca imza üretmekte ve doğrulamakta kullanılır. Anahtarları kodun içine yazmayın, ortam değişkeninde tutun.

Kanal token'ı entegrasyon için bir kez verilir ve her isteğe istemci yazar. Birden çok kanalda satıyorsanız tek bir istekte `channel_token` vererek o isteği başka kanala yazdırabilirsiniz. Geçit hiçbir yerde veritabanı numarası kullanmaz: kanal, ödeme hesabı, işlem, sipariş, abonelik, link ve kayıtlı kart her zaman token'ıyla anılır.

İstek bir dakika içinde yanıt almazsa kesilir; süreyi `Options(timeout=...)` (saniye) ile değiştirebilirsiniz. İstekler standart kütüphanenin `urllib`'iyle gider; `requests` ya da `httpx` kullanmak isterseniz `send(method, url, headers, body, timeout)` metodu olan bir nesneyi `Client(options, transport=...)` ile verebilirsiniz (GET isteklerinde `body` `None` gelir).

İstekler `odemehub.request` modülündeki değişmez nesnelerdir ve alanları yalnızca adla verilir. Tekil bir kaydı adlandıran alan her istekte `token`'dır (`RetrieveOrder(token=...)`, `RefundPayment(token=...)`). İsteğe bağlı bir alanı vermezseniz gövdeye hiç yazılmaz. Alanları SDK doğrulamaz; her kuralı geçit uygular ve reddettiğini `ValidationError` ile alan alan söyler. Kart numarası ve güvenlik kodu `repr()` çıktısına hiç girmez, böylece kart nesnesi yanlışlıkla loglansa da kart bilgisi görünmez.

## Sabit değerler

Para birimi, dönem, durumlar, kart şeması ve tipi gibi sabit kümeler `odemehub.enums` modülündedir ve `str` tabanlı `Enum`'dur: `Currency`, `Period`, `OrderStatus`, `SubscriptionStatus`, `TransactionStatus`, `PaymentStatus`, `SecurityType`, `RefundType`, `RefundStatus`, `CardScheme`, `CardType`, `WebhookEvent`. Bir üye geçidin gönderdiği metnin kendisidir ve ona eşittir (`TransactionStatus.SUCCESSFUL == "successful"`).

İsteklerde bu alanlar üyeyle verilir (`currency=Currency.USD`, `period=Period.MONTHLY`). Yanıtlarda okunan değer üyeye çevrilir; geçit bu sürümün bilmediği yeni bir değer gönderirse SDK çökmez, değer geldiği gibi düz metin olarak kalır.

## İmza

Her istek üç başlıkla gider: `X-Api-Key`, `X-Timestamp` (Unix saniye) ve `X-Signature`. İmza, `"{timestamp}\n{METHOD}\n{path}\n{body}"` metni üzerinden gizli anahtarla alınan HMAC-SHA256'nın küçük harfli hex halidir. `path` adresin sorgu dizesiz yolu (`/api/1000000001/gateway/regular-payment`), `body` gönderilen JSON'ın kendisidir; GET isteklerinde boş dizedir. Zaman damgası sunucu saatinden 5 dakikadan uzak olamaz. Geçit her yanıtı aynı yöntemle imzalar; istemci yanıtı isteğin metodu ve yoluyla, yanıtın kendi `X-Timestamp` değeriyle doğrular.

```python
import hashlib
import hmac

text = f"{timestamp}\n{method}\n{path}\n".encode() + body
hmac.new(api_secret.encode(), text, hashlib.sha256).hexdigest()
```

Test vektörü: `secret_test` anahtarıyla, `1700000000` anında, `/api/1000000001/gateway/regular-payment` yoluna `{"a":1}` gövdesiyle yapılan `POST` isteğinin imzası `4d6225c9dd46837418b40dd8140d76a24cd7520d81ff3b280bf98da8da6a8771`'dir. Aynı hesap `odemehub.Signature` sınıfındadır.

## Karttan doğrudan çekim

Müşteri hiçbir yere gitmez. Başarılı yanıt, paranın alındığı anlamına gelir.

```python
from odemehub.request import Address, Card, Customer, RegularPayment

customer = Customer(
    reference="musteri-88",            # sizdeki müşteri anahtarı; kart saklanacaksa zorunlu
    billing_address=Address(
        firstname="Ahmet", lastname="Yılmaz",
        email="ahmet@ornek.com", phone="05551112233",
        address="Kızılırmak Mah. Dumlupınar Blv. No:3",
        district="Çankaya", province="Ankara", country="TR",
    ),
)

card = Card(
    holder_name="AHMET YILMAZ",
    number="5400360000000003",
    expiry_month="12", expiry_year="2030",
    security_code="000",
    should_save=True,                  # isteğe bağlı: başarılı ödemeden sonra kartı sakla
)

payment = client.regular_payment(RegularPayment(
    channel_reference="SIP-10231",     # sizdeki referans; en az bir rakam içermeli
    amount="450.00",
    installment_number=1,
    ip=request.remote_addr,
    customer=customer,
    card=card,
))

if payment.result.successful:
    payment.transaction.token          # iade ve iptalde ödeme bununla adlandırılır
    payment.transaction.payment_status # PaymentStatus.PAID
    payment.saved_card                 # should_save verildiyse ve kart saklandıysa
```

Reddedilen ödeme de bir sonuçtur: `result.successful` `False`, `result.message` neden. Yalnızca geçit isteğin kendisini reddederse (hatalı alan, yetki, hız sınırı) hata fırlatılır.

Yanıtın `transaction` alanı ödemeyi bütünüyle söyler: `token`, `channel_token`, `channel_reference`, `status`, `payment_status`, `security_type`, `amount`, `base_amount`, `currency`, `installment_number`, `is_test`, `created_at`. `customer` ödemenin dondurduğu müşteridir (`reference` ve `billing_address`).

Faturada şirket adı gerekiyorsa `company_title`, `tax_number` ve `tax_office` fatura adresine üçü birlikte verilir.

Kayıtlı kartla ödemede `card` yerine `saved_card_token` verilir; ödeme kartın saklandığı hesaptan geçer, `payment_provider_token` gönderilmez. Kart hangi kanal ve müşteri referansıyla saklandıysa ödeme de aynılarını taşımalıdır.

Tutarlar nokta ayraçlı ve en çok iki ondalıklı metindir: `"100"`, `"100.1"`, `"100.10"`. İmzalanıp gönderildiği gibi kalır, yolda yuvarlanmaz. Para birimi `Currency` ile verilir (`currency=Currency.USD`), boş bırakılırsa TRY'dir. Kart numarası gruplar arasında boşlukla da gönderilebilir.

## 3D ödeme

Siz ödemeyi başlatırsınız, müşteri bankasına gider, banka müşteriyi sizin adresinize geri yollar.

```python
from odemehub.request import SecurePayment

payment = client.secure_payment(SecurePayment(
    channel_reference="SIP-10232",
    amount="450.00",
    installment_number=1,
    ip=request.remote_addr,
    customer=customer,
    callback_url="https://magazam.com/odeme/donus",
    card=card,
))

if payment.redirect_url is not None:
    return redirect(payment.redirect_url)              # müşteriyi bankaya gönderin
```

Başarılı yanıt ödeme alındı demek değildir; müşterinin gideceği adres hazır demektir. Adres 15 dakika geçerlidir ve bir kez açılır; süresinde açılmayan ödeme `expired` olur.

Banka işini bitirince müşterinin tarayıcısı `callback_url` adresinize şu alanları POST eder: `transaction_token`, `channel_reference`, `successful` (`1`/`0`). Bu POST imzasızdır ve müşterinin tarayıcısından gelir; yalnızca ipucudur. Sonucu kendi imzalı bağlantınızdan sorun:

```python
from odemehub.request import RetrievePayment

@app.post("/odeme/donus")
def odeme_donus():
    outcome = client.retrieve_payment(RetrievePayment(token=request.form["transaction_token"]))

    if outcome.result.successful:
        ...  # siparişi ödendi olarak işaretleyin
```

Başkasının işlemini sorarsanız kayıt yokmuş gibi `NotFoundError` alırsınız.

## Sipariş

Kart sizde sorulmaz. Siparişi açarsınız, geçit kendi ödeme sayfasının adresini döner, müşteri orada öder. Tutar gönderilmez: geçit kalemleri ve seçilen gönderim yöntemini toplar. Birim tutarlar KDV dahildir.

```python
from odemehub.request import CreateOrder, Item, ShippingMethod

answer = client.create_order(CreateOrder(
    channel_reference="SIP-10233",
    success_url="https://magazam.com/odeme/donus",
    items=[
        Item(name="Kulaklık", unit_amount="1200.00", quantity=1, tax_rate="20", channel_reference="SKU-1"),
    ],
    customer=customer,                                   # bilinen kadarı; kalanı sayfada sorulur
    shipping_methods=[
        ShippingMethod(handle="standart", title="Standart Kargo", amount="49.90", tax_rate="20"),
    ],
    requires_shipping_address=True,
    cancel_url="https://magazam.com/sepet",
))

answer.order.checkout_url      # müşteriyi buraya gönderin
answer.order.amount            # geçidin hesapladığı toplam
```

Müşteri istediğiniz kadarıyla verilir: yalnız `reference`, fatura adresi (`billing_address`), gönderim adresi (`shipping_address`) ya da hiçbiri. Verilmeyenler ödeme sayfasında sorulur; referans verilmemişse geçit ödemede `guest-…` biçiminde bir referans üretir (`order.customer.is_guest()`).

Yanıttaki `order` siparişi bütünüyle taşır (müşteri hem `answer.customer`'da hem `answer.order.customer`'dadır): `token`, `channel_reference`, `description`, `payment_provider_token`, `status` (`open` / `paid`), `items`, `shipping_methods`, seçilen `shipping_method`, `subtotal`, `shipping_amount`, `tax_amount`, `amount`, `currency`, `is_test`, `created_at`, `checkout_url` (ödenince `None`), ödeyen işlem `transaction` (açıkken `None`) ve `customer`.

Ödendiğinde müşteri `success_url` adresinize 3D dönüşüyle aynı alanlarla POST edilir; `retrieve_order()` kesin sonucu verir.

```python
from odemehub.request import RetrieveOrder, UpdateOrder

answer = client.retrieve_order(RetrieveOrder(token=token))
answer.order.is_paid()
answer.order.transaction.token if answer.order.transaction else None

# Açık siparişte yalnızca gönderilen alanlar değişir; kalemler gönderilirse tamamı yenilenir.
client.update_order(UpdateOrder(token=token, description="Hediye paketi", clear=["cancel_url"]))
```

Bir alanı vermemek onu olduğu gibi bırakır; boşaltmak için adını `clear` listesine yazın.

`create_*` çağrıları aynı kanal ve referans için tekrarlanabilir: aynı referansla ikinci kez açılan sipariş, link ya da (henüz ödenmemiş) abonelik yeni gönderilenlerle güncellenir ve kendi token'ıyla döner. Ödenmiş sipariş değişmez. Ödeme sayfasında son 15 dakika içinde başlamış bir ödeme varken `create_*` ve `update_*` çağrıları `channel_reference` / `token` alanında reddedilir.

## Ödeme linki

Link, elinde olan herkesin ödeyebileceği bir sayfadır; kapatılana ya da son gününe kadar tekrar tekrar ödenir. Müşterisi yoktur.

```python
from odemehub.enums import Currency
from odemehub.request import CreatePaymentLink, Item, RetrievePaymentLink, UpdatePaymentLink

answer = client.create_payment_link(CreatePaymentLink(
    items=[Item(name="Bağış", unit_amount="100.00", quantity=1, tax_rate="0")],
    currency=Currency.TRY,
    channel_reference="LNK-1",          # boş bırakılırsa geçit üretir
    expires_at="2026-12-31",            # çalışma alanının saat dilimine göre son gün
))

link = answer.payment_link
link.checkout_url                       # linkin kendisi; ödenemezken None
link.expires_at                         # son an, UTC ISO 8601

detail = client.retrieve_payment_link(RetrievePaymentLink(token=link.token))
detail.transactions_count               # linkteki bütün ödemeler
detail.transactions                     # son 50 ödeme, yeniden eskiye
detail.successful()                     # bunlardan başarılı olanlar

client.update_payment_link(UpdatePaymentLink(token=link.token, is_active=False))
```

`is_active` linkin şu an ödeme alıp almadığını (açık ve süresi dolmamış), `is_test` ödemelerinin test ortamında alındığını söyler. Kanal verilmezse link istemcinin kanalına açılır. Panelin açtığı linklere ulaşmak için kanal olarak `ChannelMessage.ODEMEHUB_CHANNEL` verin. 50'den eski ödemeler `retrieve_payments_by_channel_reference()` ile okunur.

## Abonelik

İlk yenileme ödeme sayfasında ödenir ve kart orada saklanır; sonrakiler o karttan çekilir. Müşteri referansı zorunludur. Hesap kart saklamalı ve 3D ödeme almalıdır.

```python
from odemehub.enums import Period, SubscriptionStatus
from odemehub.request import CreateSubscription, Item, RetrieveSubscription, UpdateSubscription

answer = client.create_subscription(CreateSubscription(
    channel_reference="ABO-1",
    period=Period.MONTHLY,              # DAILY | WEEKLY | MONTHLY | ANNUALLY
    success_url="https://magazam.com/abonelik/donus",
    items=[Item(name="Premium", unit_amount="99.90", quantity=1, tax_rate="20")],
    customer=customer,
    renewal_limit=12,                   # boş: iptale kadar
))

answer.subscription.checkout_url

current = client.retrieve_subscription(RetrieveSubscription(token=token)).subscription
current.status                          # SubscriptionStatus.ACTIVE, PAST_DUE, ...
current.renewal.paid_at                 # içinde bulunulan yenileme
current.next_payment_at
current.customer.reference

# Dönem, kalemler, ödeme sayısı değişir; iptal de buradan:
client.update_subscription(UpdateSubscription(token=token, status=SubscriptionStatus.CANCELLED))
```

İlk ödeme alındıktan sonra kanal, ödeme hesabı, para birimi, dönem ve `customer.reference` değiştirilemez; geçit bunları `ValidationError` ile reddeder. İptalde para iade edilmez; ödenmiş dönem sonuna kadar sürer, sonra abonelik biter. Ödenmiş dönem yoksa hemen `cancelled` olur.

## Kayıtlı kartlar

Kart ödeme sırasında (`should_save=True`) ya da ödemesiz saklanır. Kanal ve müşteri referansı ikilisinin altında durur.

```python
from odemehub.request import CreateSavedCard, DeleteSavedCard, RetrieveSavedCardsByReference, UpdateSavedCard

saved = client.create_saved_card(CreateSavedCard(customer=customer, card=card))
saved.saved_card.token if saved.saved_card else None   # sağlayıcı saklamadıysa None, nedeni result.message

cards = client.retrieve_saved_cards_by_reference(RetrieveSavedCardsByReference(customer_reference="musteri-88"))
cards.default()                         # varsayılan kart, varsa
cards.customer.reference

client.update_saved_card(UpdateSavedCard(token=card_token))   # varsayılan yap
client.delete_saved_card(DeleteSavedCard(token=card_token))
```

Ödemesiz saklamada güvenlik kodu yalnızca bunu isteyen sağlayıcılarda gerekir; `security_code` verilmezse gönderilmez. Kayıtlı kart yanıtlarında kartın yalnızca ilk haneleri ve son dördü vardır.

## İade ve iptal

Ödemenin token'ı yeter. İade, sağlayıcının kapattığı ödemeden kısmen ya da tamamen; iptal, henüz kapatılmamış ödemenin tamamı.

```python
from odemehub.request import CancelPayment, RefundPayment

refund = client.refund_payment(RefundPayment(token=token, amount="50.00"))  # tutar boş: kalanın tamamı
refund.refund.amount if refund.refund else None    # gerçekten geri giden tutar

cancel = client.cancel_payment(CancelPayment(token=token))
```

Kur çevirisiyle çekilen ödemede iade tutarı çekilen para birimindedir.

## Kart sorgusu ve taksitler

Kartın ilk 6–8 hanesiyle bankası, tipi ve tutara göre taksit seçenekleri. Hiçbir şey çekilmez.

```python
from odemehub.request import RetrieveBin

bin = client.retrieve_bin(RetrieveBin(bin="415565", amount="1200.00"))

bin.issuer_name                         # Yapı Kredi
bin.scheme                              # visa
for installment in bin.installments:
    print(f"{installment.number} x {installment.amount} = {installment.total}")
```

Hesap vermezseniz taksitler ödemenin yönlendirileceği hesaptan gelir; böylece çekilen tutar gösterdiğinizle aynı olur. Taksit yalnızca TRY ödemelerde vardır; başka para biriminde liste boş döner. Taksitli satışta taksidin toplamını `amount`, sattığınız tutarı `base_amount` olarak gönderin. Sorgu başarısız dönerse satışı durdurmayın, tek çekimle devam edin.

## Referansla ve tarihle listeleme

Her kaynak kendi referansıyla ya da bir tarih aralığıyla bulunur. Aralık en çok 7 gündür ve çalışma alanının saat dilimindedir; boş bırakılırsa son 7 gün.

```python
from odemehub.request import RetrievePaymentByReference, RetrievePaymentsByChannelReference

# Yanıtı alınamayan bir ödemenin akıbeti: referanstaki son ödeme
client.retrieve_payment_by_reference(RetrievePaymentByReference(channel_reference="SIP-10231"))

# Kanaldaki bütün denemeler, reddedilenler dahil, durumu ve tutarıyla
payments = client.retrieve_payments_by_channel_reference(RetrievePaymentsByChannelReference(
    created_from="2026-09-26",
    created_to="2026-10-02",
))

for transaction in payments.payments:
    transaction.status                  # TransactionStatus; TIMEOUT: sağlayıcı yanıt vermedi
    transaction.is_finished()           # SUCCESSFUL, FAILED ya da EXPIRED
    transaction.payment_status          # PaymentStatus: PAID, REFUNDED, PARTIALLY_REFUNDED...
    transaction.order_token             # ödeme sayfasından geldiyse sipariş, link ya da abonelik token'ı
```

Aynısı `retrieve_order_by_reference()` / `retrieve_orders_by_channel_reference()`, `retrieve_subscription_by_reference()` / `retrieve_subscriptions_by_channel_reference()`, `retrieve_payment_link_by_reference()` / `retrieve_payment_links_by_channel_reference()` için de geçerlidir. Sipariş ve abonelik listelerinde her kayıt kendi `customer` bilgisini taşır.

## Webhook

Sipariş ödendiğinde, link ödemesi alındığında, abonelik durum değiştirdiğinde, API ödemesi bittiğinde ve bir ödeme iade ya da iptal edildiğinde geçit imzalı JSON POST eder. Adresler kodda verilmez; panelde **Ayarlar → Webhook** sayfasında kanal, olay ve adres seçilerek tanımlanır.

| Kaynak | Olaylar |
| --- | --- |
| Sipariş | `order.paid`, `order.payment_refunded`, `order.payment_cancelled` |
| Ödeme linki | `payment_link.paid`, `payment_link.payment_refunded`, `payment_link.payment_cancelled` |
| Abonelik | `subscription.active`, `subscription.past_due`, `subscription.cancelled`, `subscription.ended`, `subscription.completed`, `subscription.payment_refunded`, `subscription.payment_cancelled` |
| API ödemesi | `transaction.successful`, `transaction.failed`, `transaction.expired`, `transaction.payment_refunded`, `transaction.payment_cancelled` |

Sipariş, link ya da abonelikte alınan ödeme için `transaction.*` gelmez; o kaynağın kendi olayı gelir.

**Webhook nihai sonuç değildir.** Gövde yalnızca kaynağın token'ını (para hareketi varsa yanında ödemenin token'ını) taşır. Kararı, token ile geçide sorduğunuz yanıta göre verin ve yanıtı kendi kaydınızla (referans, tutar, durum) karşılaştırın. Gövdeyi **ham** okuyun; ayrıştırıp yeniden yazarsanız imza tutmaz.

```python
from odemehub import SignatureError
from odemehub.request import RetrieveOrder, RetrievePayment, RetrieveSubscription

@app.post("/odemehub/webhook")
def webhook():
    try:
        webhook = client.webhook(
            request.method,
            request.path,
            request.get_data(),
            request.headers.get("X-Timestamp"),
            request.headers.get("X-Signature"),
        )
    except SignatureError:
        return "", 401

    webhook.id      # aynı bildirim tekrar gelebilir; bununla ayıklayın
    webhook.event   # WebhookEvent.ORDER_PAID ...

    if webhook.order_token is not None:
        order = client.retrieve_order(RetrieveOrder(token=webhook.order_token)).order
        order.status                          # OrderStatus.PAID
        order.transaction.payment_status      # PaymentStatus.REFUNDED ...
    elif webhook.subscription_token is not None:
        subscription = client.retrieve_subscription(RetrieveSubscription(token=webhook.subscription_token)).subscription
    elif webhook.transaction_token is not None:   # transaction.* ve payment_link.*
        transaction = client.retrieve_payment(RetrievePayment(token=webhook.transaction_token)).transaction
        transaction.payment_link_token        # linkte alınan ödemede linkin token'ı

    return "", 204
```

Abonelik ve link ödemelerinin iade/iptal olaylarında `transaction_token` da gelir; `retrieve_payment()` yanıtındaki `order_token` / `payment_link_token` / `subscription_token` ödemenin gerçekten o kaynağa ait olduğunu gösterir. Yalnızca doğrulamak için `client.verify_webhook(...)` `bool` döner. Geçit 2xx yanıt alana kadar 60 sn, 5 dk, 15 dk ve 30 dk arayla toplam 5 kez dener; yönlendirmeleri izlemez.

## Hatalar

Bütün hatalar `OdemehubError`'dan türer; tek bir `except` hepsini yakalar.

| Hata | Durum | Anlamı |
| --- | --- | --- |
| `AuthenticationError` | 401 | API anahtarı yanlış, imza tutmuyor ya da zaman damgası aralık dışında |
| `ForbiddenError` | 403 | Çalışma alanı işlem yapamıyor (ödenmemiş bakiye, plan) ya da plan bu özelliği kapsamıyor / modül kapalı |
| `NotFoundError` | 404 | Token ya da referansla adlandırılan kayıt yok (başkasının kaydı da böyle yanıtlanır) |
| `ValidationError` | 422 | Alan hataları; `error.errors` noktalı alan adıyla (`transaction.amount`, `order.items.0.name`) |
| `RateLimitError` | 429 | İstek sınırı; `error.retry_after` saniye |
| `SignatureError` | — | Yanıtın ya da bildirimin imzası doğrulanamadı; içeriğe güvenmeyin |
| `TransportError` | — | Geçide ulaşılamadı; ödemenin akıbetini `retrieve_payment_by_reference()` ile sorun |
| `UnexpectedResponseError` | diğer | Okunamayan yanıt ya da geçitte beklenmeyen hata (500); `error.status` |

```python
from odemehub import OdemehubError, ValidationError

try:
    payment = client.regular_payment(payment_request)
except ValidationError as error:
    print(error.errors)  # {'transaction.amount': ['...']}
except OdemehubError as error:
    print(error)         # Türkçe
```

Reddedilen ödeme, iade ya da kart saklama hata değildir; `result.successful` `False` ve `result.message` dolu döner. Ağ hatasında ödemeyi körlemesine tekrarlamayın: `TransportError` "olmadı" demek değil, "bilmiyorum" demektir.

## İstek sınırları

Sınırlar çalışma alanı başına ve dakikalıktır:

| Sınır | Kapsam |
| --- | --- |
| 300 istek / dk | bütün uç noktalar |
| 60 istek / dk | `secure-payment`, `regular-payment`, `refund-payment`, `cancel-payment`, `create-saved-card`, `delete-saved-card` (300'e ek olarak) |

Aşıldığında 429 ve `RateLimitError` döner; `retry_after` kadar bekleyip aynı isteği yeniden gönderin.

## 2.0.0'daki kırıcı değişiklikler

1.x geçidin eski API'sine yazılmıştı; 2.0.0 bugünkü API'yi birebir izler.

- **Uçlar:** `order_payment`, `subscription_payment`, `save_product`, `cancel_subscription`, `retrieve_transactions`, `save_card`, `saved_cards` ve `default_saved_card` kaldırıldı. Yerlerine `create_order`, `create_subscription`, `update_subscription(status=CANCELLED)`, `retrieve_payments_by_channel_reference`, `create_saved_card`, `retrieve_saved_cards_by_reference` ve `update_saved_card` geldi; ödeme linki, `update_*`, `*_by_reference` ve `*_by_channel_reference` uçları eklendi. Ürün kataloğu yok: kalemler (`Item`) adı ve fiyatıyla gönderilir.
- **İmza:** gövde tek başına değil, `"{timestamp}\n{METHOD}\n{path}\n{body}"` imzalanır ve `X-Timestamp` başlığı eklenir. Tek bir kaydı soran `retrieve-*/{token}` uçları GET'tir.
- **Transport:** özel transport'lar `post(url, headers, body, timeout)` yerine `send(method, url, headers, body, timeout)` uygular.
- **İstekler:** tekil kaydı adlandıran alan her yerde `token` (`transaction_token`, `order_token`, `subscription_token`, `saved_card_token` istek alanları kalktı; kayıtlı kartla ödemedeki `saved_card_token` duruyor). Müşteri `reference` + `billing_address` / `shipping_address` (`Address`) oldu; şirket alanları fatura adresinde. Para birimi, dönem ve abonelik durumu `odemehub.enums` üyeleriyle verilir. `card` ile `saved_card_token`'ın birlikte verilmesi artık istemcide değil geçitte reddedilir.
- **Yanıtlar:** geçidin JSON'unu iç içe yansıtır: `payment.transaction.token`, `payment.transaction.status`, `payment.customer.reference`, `refund.refund.amount`, `answer.order`, `answer.subscription`, `answer.payment_link`. `OrderDetails` / `SubscriptionDetails` müşteriyi üst seviyede `customer` olarak da taşır. Sabit kümeler `odemehub.enums` üyesi olarak okunur.
- **Hatalar:** `ForbiddenError` (403), `NotFoundError` (404, eskiden 422 dönen bulunamayan kayıtlar) ve `RateLimitError` (429) eklendi.
- **Webhook:** `order_webhook()`, `subscription_webhook()`, `transaction_webhook()` yerine tek `webhook(method, path, body, timestamp, signature)` (ve `verify_webhook()`); imza istek ve yanıtlarla aynı şemadadır. Gövde yalnızca token taşır (`order_token`, `payment_link_token`, `subscription_token`, `transaction_token`); durum `retrieve_*()` ile sorulur. Adresler panelde tanımlandığı için `SecurePayment`, `CreateOrder`, `UpdateOrder`, `CreateSubscription`, `UpdateSubscription` artık `webhook_url` almaz. `Signature.verify_body()` kalktı.
