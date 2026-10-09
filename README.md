# ödemehub Python SDK

ödemehub ödeme geçidini kendi uygulamanızdan kullanmak için Python istemcisi. Kart çekmek, 3D ödeme başlatmak, sipariş, abonelik ve ödeme linki açmak, kart saklamak, iade ve iptal yapmak, taksit sormak: hepsi burada.

İstemci her isteği gizli anahtarınızla imzalar, gelen her yanıtın imzasını doğrular. Siz imza, başlık ya da JSON ayrıntılarıyla uğraşmazsınız. Her uç nokta için bir metot vardır ve adı uç noktanın adıdır: `create-order` için `create_order()`, `retrieve-saved-cards` için `retrieve_saved_cards()`. Yalnızca standart kütüphaneyi kullanır; kurulacak başka paket yoktur. Tip ipuçları pakettedir.

## Kurulum

Python 3.10 ve üzeri gerekir.

```bash
pip install odemehub
```

## Yapılandırma

Üç bilgi gerekir. Hepsi paneldeki **Entegrasyon** sayfasındadır: Çalışma Alanı Kimliğiniz, API anahtarı ve gizli anahtar.

```python
import os

from odemehub import Client, Options

client = Client(Options(
    base_url="https://app.odemehub.com",
    team="1000000001",                                     # Çalışma Alanı Kimliği
    api_key=os.environ["ODEMEHUB_API_KEY"],
    api_secret=os.environ["ODEMEHUB_API_SECRET"],
))
```

Gizli anahtar hiçbir zaman tel üzerinden gitmez; yalnızca imza üretmekte ve doğrulamakta kullanılır. Anahtarları kodun içine yazmayın, ortam değişkeninde tutun.

Geçit hiçbir yerde veritabanı numarası kullanmaz: ödeme hesabı, işlem, sipariş, abonelik, link, link ödemesi ve kayıtlı kart her zaman token'ıyla anılır. `reference` sizin kendi numaranızdır ve tekil değildir; bir kaydı her zaman token'ı adlandırır.

İstek bir dakika içinde yanıt almazsa kesilir; süreyi `Options(timeout=...)` (saniye) ile değiştirebilirsiniz. İstekler standart kütüphanenin `urllib`'iyle gider; `requests` ya da `httpx` kullanmak isterseniz `send(method, url, headers, body, timeout)` metodu olan bir nesneyi `Client(options, transport=...)` ile verebilirsiniz. Bütün istekler JSON gövdeli POST'tur.

İstekler `odemehub.request` modülündeki değişmez nesnelerdir ve alanları yalnızca adla verilir. Tekil bir kaydı adlandıran alan her istekte `token`'dır (`RetrieveOrders(token=...)`, `RefundPayment(token=...)`). İsteğe bağlı bir alanı vermezseniz gövdeye hiç yazılmaz. Alanları SDK doğrulamaz; her kuralı geçit uygular ve reddettiğini `ValidationError` ile alan alan söyler. Kart numarası ve güvenlik kodu `repr()` çıktısına hiç girmez, böylece kart nesnesi yanlışlıkla loglansa da kart bilgisi görünmez.

## Sabit değerler

Para birimi, dönem, durumlar, kart şeması ve tipi gibi sabit kümeler `odemehub.enums` modülündedir ve `str` tabanlı `Enum`'dur: `Currency`, `Period`, `OrderStatus`, `SubscriptionStatus`, `LinkPaymentStatus`, `TransactionStatus`, `PaymentStatus`, `SecurityType`, `RefundType`, `RefundStatus`, `CardScheme`, `CardType`, `WebhookEvent`, `AmountType`, `CurrencyType`, `TaxMode`. Bir üye geçidin gönderdiği metnin kendisidir ve ona eşittir (`TransactionStatus.SUCCESSFUL == "successful"`).

İsteklerde bu alanlar üyeyle verilir (`currency=Currency.USD`, `period=Period.MONTHLY`). Yanıtlarda okunan değer üyeye çevrilir; geçit bu sürümün bilmediği yeni bir değer gönderirse SDK çökmez, değer geldiği gibi düz metin olarak kalır.

## İmza

Her istek üç başlıkla gider: `X-Api-Key`, `X-Timestamp` (Unix saniye) ve `X-Signature`. İmza, `"{timestamp}\n{METHOD}\n{path}\n{body}"` metni üzerinden gizli anahtarla alınan HMAC-SHA256'nın küçük harfli hex halidir. `path` adresin sorgu dizesiz yolu (`/api/1000000001/gateway/regular-payment`), `body` gönderilen JSON'ın kendisidir. Bütün uç noktalar POST'tur. Zaman damgası sunucu saatinden 5 dakikadan uzak olamaz. Geçit her yanıtı aynı yöntemle imzalar; istemci yanıtı isteğin metodu ve yoluyla, yanıtın kendi `X-Timestamp` değeriyle doğrular.

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
    reference="SIP-10231",     # sizdeki referans; en az bir rakam içermeli
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

Yanıtın `transaction` alanı ödemeyi bütünüyle söyler: `token`, `reference`, `status`, `payment_status`, `security_type`, `amount`, `base_amount`, `currency`, `installment_number`, `is_test`, `created_at`. `customer` ödemenin dondurduğu müşteridir (`reference` ve `billing_address`).

Faturada şirket adı gerekiyorsa `company_title`, `tax_number` ve `tax_office` fatura adresine üçü birlikte verilir.

Kayıtlı kartla ödemede `card` yerine `saved_card_token` verilir; ödeme kartın saklandığı hesaptan geçer, `payment_provider_token` gönderilmez. Kart hangi müşteri referansıyla saklandıysa ödeme de aynı referansı taşımalıdır.

**Müşteriler.** `customer.reference` gönderdiğiniz ödeme başarılı olunca geçit müşteriyi o referansla çalışma alanınızın müşteri listesine yazar ya da günceller; başarısız ödeme müşteriye dokunmaz. Referans göndermezseniz ödeme yine alınır ama müşteri kaydedilmez ve kart saklanamaz. Saklanan kart müşteriye bağlanır; müşterinin son ödeme yaptığı kart varsayılan kartı olur.

Tutarlar nokta ayraçlı ve en çok iki ondalıklı metindir: `"100"`, `"100.1"`, `"100.10"`. İmzalanıp gönderildiği gibi kalır, yolda yuvarlanmaz. Para birimi `Currency` ile verilir (`currency=Currency.USD`), boş bırakılırsa TRY'dir. Kart numarası gruplar arasında boşlukla da gönderilebilir.

## 3D ödeme

Siz ödemeyi başlatırsınız, müşteri bankasına gider, banka müşteriyi sizin adresinize geri yollar.

```python
from odemehub.request import SecurePayment

payment = client.secure_payment(SecurePayment(
    reference="SIP-10232",
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

Banka işini bitirince müşterinin tarayıcısı `callback_url` adresinize şu alanları POST eder: `transaction_token`, `reference`, `successful` (`1`/`0`). Bu POST imzasızdır ve müşterinin tarayıcısından gelir; yalnızca ipucudur. Sonucu kendi imzalı bağlantınızdan sorun:

```python
from odemehub.request import RetrievePayments

@app.post("/odeme/donus")
def odeme_donus():
    payments = client.retrieve_payments(RetrievePayments(token=request.form["transaction_token"])).payments

    if payments and payments[0].is_successful():
        ...  # siparişi ödendi olarak işaretleyin
```

Başkasının işlemini sorarsanız liste boş döner.

## Sipariş

Kart sizde sorulmaz. Siparişi açarsınız, geçit kendi ödeme sayfasının adresini döner, müşteri orada öder. Tutar gönderilmez: geçit kalemleri ve ödeyenin panelinizdeki listeden seçtiği gönderim yöntemini toplar. Birim tutarlar KDV dahildir.

```python
from odemehub.request import CreateOrder, Item

answer = client.create_order(CreateOrder(
    reference="SIP-10233",
    success_url="https://magazam.com/odeme/donus",
    items=[
        Item(name="Kulaklık", unit_amount="1200.00", quantity=1, tax_rate="20", reference="SKU-1", save_as_product=True),
    ],
    customer=customer,                   # bilinen kadarı; kalanı sayfada sorulur. Hiç verilmeyebilir.
    requires_shipping=True,              # ödeyen adresini ve gönderim yöntemini sayfada seçer
    cancel_url="https://magazam.com/sepet",
    emails_customer=True,                # ödeme tamamlanınca fatura adresindeki e-postaya bilgilendirme gider
))

answer.order.checkout_url      # müşteriyi buraya gönderin
answer.order.amount            # geçidin hesapladığı toplam
```

Müşteri istediğiniz kadarıyla verilir: yalnız `reference`, fatura adresi (`billing_address`), gönderim adresi (`shipping_address`) ya da hiçbiri. Verilmeyenler ödeme sayfasında sorulur. Referans verilmezse ödeyen müşteri listenize yazılmaz. `save_as_product=True` olan kalem referansıyla ürün listenize yazılır (referans zorunlu). Gönderim yöntemleri istekte gönderilmez: panelinizdeki **Gönderim Yöntemleri** listesinden ödeyenin adresine uyanlar sunulur.

**Müşteri kilidi.** `locks_customer=True` gönderilirse ödeme sayfası müşteri bilgisi sormaz; gönderdiğiniz müşteriyi değiştirilemez şekilde gösterir ve ödemeyi onunla alır. Bu durumda fatura adresi eksiksiz olmalıdır; `requires_shipping=True` ise gönderim adresi de (gönderilmezse fatura adresi kullanılır). Eksik alan varsa geçit `ValidationError` ile reddeder.

Yanıttaki `order` siparişi bütünüyle taşır (müşteri hem `answer.customer`'da hem `answer.order.customer`'dadır): `token`, `reference`, `description`, `payment_provider_token`, `status` (`open` / `paid`), `requires_shipping`, `locks_customer`, `emails_customer`, `items`, seçilen `shipping_method`, `subtotal`, `shipping_amount`, `tax_amount`, `amount`, `currency`, `discount`, `is_test`, `created_at`, `checkout_url` (ödenince `None`), ödeyen işlem `transaction` (açıkken `None`) ve `customer`.

**Kupon.** API'de kupon alanı yoktur; ödeyen kodu ödeme sayfasında girer. Kupon kullanıldıysa yanıtta `discount` (`Discount`: `code`, `amount`) gelir, yoksa `None`'dır. Siparişin `subtotal`, `tax_amount` ve `amount` değerleri indirim düşülmüş hâlidir; kupon gönderim ücretinden düşülmez.

Ödendiğinde müşteri `success_url` adresinize 3D dönüşüyle aynı alanlarla POST edilir; `retrieve_orders()` kesin sonucu verir.

```python
from odemehub.request import RetrieveOrders, UpdateOrder

order = client.retrieve_orders(RetrieveOrders(token=token)).orders[0]
order.is_paid()
order.transaction.token if order.transaction else None
order.customer.reference if order.customer else None

# Açık siparişte yalnızca gönderilen alanlar değişir; kalemler gönderilirse tamamı yenilenir.
client.update_order(UpdateOrder(token=token, description="Hediye paketi", clear=["cancel_url"]))
```

Bir alanı vermemek onu olduğu gibi bırakır; boşaltmak için adını `clear` listesine yazın.

`create_*` her çağrıda yeni bir kayıt ve yeni bir token açar; aynı `reference` daha önce gönderilmiş olsa da eski kayıt değişmez ve istek reddedilmez. Bu yüzden her `create_*` yanıtındaki token'ı saklayın: kaydı sorgularken ve değiştirirken onu kullanırsınız. Var olan kayıt `update_*` ile değişir. Ödenmiş sipariş değişmez. Ödeme sayfasında son 15 dakika içinde başlamış bir ödeme varken `update_order` ve `update_subscription` `token` alanında reddedilir; link güncellemesini bekleyen ödeme engellemez.

## Ödeme linki

Link, elinde olan herkesin ödeyebileceği bir sayfadır; kapatılana ya da son gününe kadar tekrar tekrar ödenir. Müşterisi yoktur.

```python
from odemehub.enums import Currency
from odemehub.request import CreatePaymentLink, Item, RetrievePaymentLinks, UpdatePaymentLink

answer = client.create_payment_link(CreatePaymentLink(
    items=[Item(name="Kulaklık", unit_amount="1200.00", quantity=1, tax_rate="20")],
    currency=Currency.TRY,
    reference="LNK-1",                  # boş bırakılırsa geçit LINK{n} üretir; tekil değildir
    expires_at="2026-12-31",            # çalışma alanının saat dilimine göre son gün
    emails_customer=True,               # ödeme tamamlanınca ödeyene, sayfada verdiği adrese e-posta gider
))

link = answer.payment_link
link.token                              # saklayın: link bununla sorulur ve değiştirilir
link.checkout_url                       # linkin kendisi; ödenemezken None
link.expires_at                         # son an, UTC ISO 8601

detail = client.retrieve_payment_links(RetrievePaymentLinks(token=link.token)).payment_links[0]
detail.transactions_count               # linkteki bütün ödeme denemeleri
detail.transactions                     # son 50 deneme, yeniden eskiye
detail.successful()                     # bunlardan başarılı olanlar

client.update_payment_link(UpdatePaymentLink(token=link.token, is_active=False))
```

`is_active` linkin şu an ödeme alıp almadığını (açık ve süresi dolmamış), `is_test` ödemelerinin test ortamında alındığını söyler. Panelden açtığınız linkler de aynı uçlarla bulunur. Linkle ödeyen kişi müşteri listenize yazılmaz ve kartı saklanmaz. Süresi geçmiş link yalnızca yeni bir `expires_at` ile yeniden açılır.

**Tutar tipleri.** `amount_type` (`AmountType`) linkin neyi tahsil ettiğini söyler:

| Tip | Ödeyen ne öder |
| --- | --- |
| `FIXED` (varsayılan) | Kalemlerin toplamını; `items` zorunlu |
| `CUSTOM` | Kendi yazdığı tutarı |
| `PREDEFINED` | `predefined_amounts` içinden seçtiğini (en çok 10) |
| `PREDEFINED_AND_CUSTOM` | Hazır tutarlardan birini ya da kendi yazdığını |

Ödeyenin seçtiği tiplerde `items` gönderilmez (gönderilirse yok sayılır), `item_name` zorunludur: ödeme bu adla tek kalem olarak yazılır. `tax_rate` bu tutara uygulanır; `tax_mode` (`TaxMode`) vergi tutarın içinde mi (`INCLUSIVE`, varsayılan) yoksa üstüne mi eklenecek (`EXCLUSIVE`) söyler. Bu tiplerde yanıttaki `subtotal`, `tax_amount` ve `amount` `None`'dır; ödenen tutar link ödemesindedir.

**Para birimi seçimi.** `currency_type=CurrencyType.SELECTABLE` ile ödeyen para birimini seçer; `currencies` ödeyenin `currency` dışında seçebileceklerini verir. Yanıttaki `currencies` `currency` dahil listedir, `FIXED`'de `None`'dır.

```python
from odemehub.enums import AmountType, Currency, CurrencyType

answer = client.create_payment_link(CreatePaymentLink(
    amount_type=AmountType.PREDEFINED_AND_CUSTOM,
    item_name="Bağış",
    predefined_amounts=["100.00", "250.00", "500.00"],
    tax_rate="0",
    currency=Currency.TRY,
    currency_type=CurrencyType.SELECTABLE,
    currencies=[Currency.USD, Currency.EUR],
))

answer.payment_link.amount              # None: tutarı ödeyen seçer
```

Güncellemede `clear` listesi `description`, `payment_provider_token`, `expires_at`, `item_name`, `predefined_amounts`, `tax_rate` ve `currencies` alanlarını boşaltabilir. Ödeyenin seçtiği tipten `FIXED`'e dönen link kalem göndermek zorundadır.

**Link ödemeleri.** Linkte kimin ne ödediği `retrieve_link_payments()` ile okunur. Her ödeme yapıldığında geçit bir link ödemesi (`LinkPayment`) açar; referansı geçidin verdiği `LINKPAY{n}`'dir.

```python
from odemehub.request import RetrieveLinkPayments

payments = client.retrieve_link_payments(RetrieveLinkPayments(created_from="2026-09-26", created_to="2026-10-02"))

for link_payment in payments.link_payments:
    link_payment.payment_link.token     # hangi link
    link_payment.status                 # LinkPaymentStatus.OPEN ya da PAID
    link_payment.amount                 # ödenen tutar, indirim düşülmüş
    link_payment.currency               # ödenen para birimi
    link_payment.discount               # ödeyen kupon girdiyse Discount, yoksa None
    link_payment.customer.billing_address if link_payment.customer else None
    link_payment.transaction.token if link_payment.transaction else None   # iade ve iptal bununla

payments.paid()                         # ödenmiş olanlar
```

`LinkPayment` alanları: `token`, `reference`, `payment_link` (`token`, `reference`), `payment_provider_token`, `status`, `items` (görselsiz), `subtotal`, `tax_amount`, `amount`, `discount`, `currency`, `customer` (yalnız `billing_address`; yoksa `None`), `is_test`, `created_at` ve ödeyen işlem `transaction` (`token`, `reference`, `payment_status`; açıkken `None`).

## Abonelik

İlk yenileme ödeme sayfasında ödenir ve kart orada müşteriye saklanır; sonrakiler müşterinin varsayılan kartından çekilir. Müşteri referansı zorunludur. Hesap kart saklamalı ve 3D ödeme almalıdır.

```python
from odemehub.enums import Period, SubscriptionStatus
from odemehub.request import CreateSubscription, Item, RetrieveSubscriptions, UpdateSubscription

answer = client.create_subscription(CreateSubscription(
    reference="ABO-1",
    period=Period.MONTHLY,              # DAILY | WEEKLY | MONTHLY | ANNUALLY
    success_url="https://magazam.com/abonelik/donus",
    items=[Item(name="Premium", unit_amount="99.90", quantity=1, tax_rate="20")],
    customer=customer,
    renewal_limit=12,                   # boş: iptale kadar
    emails_customer=True,               # her durum değişiminde fatura adresindeki e-postaya bilgilendirme gider
))

answer.subscription.checkout_url

current = client.retrieve_subscriptions(RetrieveSubscriptions(token=token)).subscriptions[0]
current.status                          # SubscriptionStatus.ACTIVE, PAST_DUE, ...
current.renewal.paid_at                 # içinde bulunulan yenileme
current.next_payment_at
current.customer.reference

# Dönem, kalemler, ödeme sayısı değişir; iptal de buradan:
client.update_subscription(UpdateSubscription(token=token, status=SubscriptionStatus.CANCELLED))
```

İlk ödeme alındıktan sonra yalnızca iptal (`status`), ödeme sayısı (`renewal_limit`), dönem (`period`) ve aynı kalemlerin birim fiyatı değişebilir; müşteri dahil başka bir alan gönderilirse geçit `ValidationError` ile reddeder. İptalde para iade edilmez; ödenmiş dönem sonuna kadar sürer, sonra abonelik biter. Ödenmiş dönem yoksa hemen `cancelled` olur.

`locks_customer` siparişteki gibi çalışır; yanıt da siparişteki gibi `requires_shipping`, `locks_customer` ve `emails_customer` taşır. `emails_customer` açıkken dönem ödemesi alınamazsa ödeme sayfasının bağlantısı doğrudan müşteriye gider, size ayrıca e-posta gelmez.

Ödeyen ilk ödemede kupon girdiyse `subscription.discount` (`code`, `amount`) dolu gelir; kupon yalnızca ilk ödemeye uygulanır. Aboneliğin kendi `subtotal`, `tax_amount` ve `amount` değerleri indirimsizdir; ilk ödemede çekilen tutar o yenilemenin `renewal.amount` değeridir.

## Kayıtlı kartlar

Kart ödeme sırasında (`should_save=True`) ya da ödemesiz saklanır; ikisinde de `customer.reference` zorunludur. Kart o müşteriye bağlanır ve müşteri referansıyla bulunur. Ödemesiz saklamada müşteri, sağlayıcı kartı kabul edince gönderdiğiniz bilgilerle listenize yazılır.

```python
from odemehub.request import CreateSavedCard, DeleteSavedCard, RetrieveSavedCards, UpdateSavedCard

saved = client.create_saved_card(CreateSavedCard(customer=customer, card=card))
saved.saved_card.token if saved.saved_card else None   # sağlayıcı saklamadıysa None, nedeni result.message

cards = client.retrieve_saved_cards(RetrieveSavedCards(reference="musteri-88"))   # müşterinin referansı
cards.default()                         # varsayılan kart, varsa
cards.saved_cards[0].customer.reference if cards.saved_cards else None

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

## Sorgulama

Her kaynak tek bir `retrieve_*` metoduyla sorulur ve yanıt her zaman bir listedir (eskiden yeniye); eşleşen yoksa boş liste döner. Kayıt üç yoldan biriyle adlandırılır: `token`, sizdeki `reference` ya da açıldığı günler (`created_from` / `created_to`). Aralık en çok 7 gündür ve çalışma alanının saat dilimindedir; hiçbiri verilmezse son 7 gün.

```python
from odemehub.request import RetrievePayments

# Yanıtı alınamayan bir ödemenin akıbeti: referanstaki bütün denemeler
client.retrieve_payments(RetrievePayments(reference="SIP-10231"))

# Belli günlerdeki bütün denemeler, reddedilenler dahil, durumu ve tutarıyla
payments = client.retrieve_payments(RetrievePayments(created_from="2026-09-26", created_to="2026-10-02"))

for transaction in payments.payments:
    transaction.status                  # TransactionStatus; TIMEOUT: sağlayıcı yanıt vermedi
    transaction.is_finished()           # SUCCESSFUL, FAILED ya da EXPIRED
    transaction.payment_status          # PaymentStatus: PAID, REFUNDED, PARTIALLY_REFUNDED...
    transaction.order_token             # ödeme sayfasından geldiyse sipariş, link ya da abonelik token'ı
    transaction.link_payment_token      # linkte alınan ödemede payment_link_token ile birlikte link ödemesinin token'ı

client.retrieve_payments()              # son 7 gün
```

Aynısı `retrieve_orders()` (`RetrieveOrders`), `retrieve_subscriptions()` (`RetrieveSubscriptions`), `retrieve_payment_links()` (`RetrievePaymentLinks`), `retrieve_link_payments()` (`RetrieveLinkPayments`; `reference` geçidin verdiği `LINKPAY{n}`'dir) ve `retrieve_saved_cards()` (`RetrieveSavedCards`; `reference` müşterinin referansıdır) için de geçerlidir. Sipariş ve abonelik listelerinde her kayıt kendi `customer` bilgisini taşır.

## Webhook

Sipariş ödendiğinde, link ödemesi alındığında, abonelik durum değiştirdiğinde, API ödemesi bittiğinde ve bir ödeme iade ya da iptal edildiğinde geçit imzalı JSON POST eder. Adresler kodda verilmez; panelde **Ayarlar → Webhook** sayfasında olay ve adres seçilerek tanımlanır.

| Kaynak | Olaylar |
| --- | --- |
| Sipariş | `order.paid`, `order.payment_refunded`, `order.payment_cancelled` |
| Ödeme linki | `payment_link.paid`, `payment_link.payment_refunded`, `payment_link.payment_cancelled` |
| Abonelik | `subscription.active`, `subscription.past_due`, `subscription.cancelled`, `subscription.ended`, `subscription.completed`, `subscription.payment_refunded`, `subscription.payment_cancelled` |
| API ödemesi | `transaction.successful`, `transaction.failed`, `transaction.expired`, `transaction.payment_refunded`, `transaction.payment_cancelled` |

Sipariş, link ya da abonelikte alınan ödeme için `transaction.*` gelmez; o kaynağın kendi olayı gelir.

**Webhook nihai sonuç değildir.** Gövde yalnızca kaynağın token'ını (para hareketi varsa yanında ödemenin token'ını; `payment_link.*` olaylarında ayrıca link ödemesinin token'ını) taşır; `discount` gibi ayrıntılar gövdede yoktur. Kararı, token ile geçide sorduğunuz yanıta göre verin ve yanıtı kendi kaydınızla (referans, tutar, durum) karşılaştırın. Gövdeyi **ham** okuyun; ayrıştırıp yeniden yazarsanız imza tutmaz.

```python
from odemehub import SignatureError
from odemehub.request import RetrieveLinkPayments, RetrieveOrders, RetrievePayments, RetrieveSubscriptions

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
        order = client.retrieve_orders(RetrieveOrders(token=webhook.order_token)).orders[0]
        order.status                          # OrderStatus.PAID
        order.transaction.payment_status      # PaymentStatus.REFUNDED ...
    elif webhook.link_payment_token is not None:  # payment_link.*
        link_payment = client.retrieve_link_payments(RetrieveLinkPayments(token=webhook.link_payment_token)).link_payments[0]
        link_payment.payment_link.token       # webhook.payment_link_token ile aynı
        link_payment.status                   # LinkPaymentStatus.PAID
        link_payment.transaction.payment_status if link_payment.transaction else None   # PaymentStatus.REFUNDED ...
    elif webhook.subscription_token is not None:
        subscription = client.retrieve_subscriptions(RetrieveSubscriptions(token=webhook.subscription_token)).subscriptions[0]
    elif webhook.transaction_token is not None:   # transaction.*
        transaction = client.retrieve_payments(RetrievePayments(token=webhook.transaction_token)).payments[0]

    return "", 204
```

Sipariş, abonelik ve link olaylarında para hareketi varsa `transaction_token` da gelir; `retrieve_payments()` yanıtındaki `order_token` / `payment_link_token` / `link_payment_token` / `subscription_token` ödemenin gerçekten o kaynağa ait olduğunu gösterir. Yalnızca doğrulamak için `client.verify_webhook(...)` `bool` döner. Geçit 2xx yanıt alana kadar 60 sn, 5 dk, 15 dk ve 30 dk arayla toplam 5 kez dener; yönlendirmeleri izlemez.

## Hatalar

Bütün hatalar `OdemehubError`'dan türer; tek bir `except` hepsini yakalar.

| Hata | Durum | Anlamı |
| --- | --- | --- |
| `AuthenticationError` | 401 | API anahtarı yanlış, imza tutmuyor ya da zaman damgası aralık dışında |
| `ForbiddenError` | 403 | Çalışma alanı işlem yapamıyor (ödenmemiş bakiye, plan) ya da plan bu özelliği kapsamıyor / modül kapalı |
| `NotFoundError` | 404 | Güncellenmek, silinmek, iade ya da iptal edilmek istenen kayıt yok (sorgularda boş liste döner) |
| `ValidationError` | 422 | Alan hataları; `error.errors` noktalı alan adıyla (`transaction.amount`, `order.items.0.name`) |
| `RateLimitError` | 429 | İstek sınırı; `error.retry_after` saniye |
| `SignatureError` | — | Yanıtın ya da bildirimin imzası doğrulanamadı; içeriğe güvenmeyin |
| `TransportError` | — | Geçide ulaşılamadı; ödemenin akıbetini `retrieve_payments(RetrievePayments(reference=...))` ile sorun |
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

## 1.0.3'teki değişiklikler

- **Müşteri kilidi ve müşteriye e-posta:** `CreateOrder`, `UpdateOrder`, `CreateSubscription` ve `UpdateSubscription` `locks_customer` ve `emails_customer` alır. `Order` ve `Subscription` yanıtları `requires_shipping`, `locks_customer` ve `emails_customer` taşır.
- **Kırıcı: ödeme linkinde `emails_payer` → `emails_customer`.** `CreatePaymentLink`, `UpdatePaymentLink` ve `PaymentLink` yanıtında alanın adı değişti; geçit eski `emails_payer` adını artık kabul etmez.

## 1.0.2'deki değişiklikler

1.0.2, SDK'yı geçidin bugünkü API'sine taşır. Eklenenler:

- **Link ödemeleri:** yeni `retrieve_link_payments()` (`RetrieveLinkPayments`: `token`, `reference` ya da `created_from`/`created_to`), yanıt modelleri `LinkPayment` / `LinkPaymentList` ve `LinkPaymentStatus` (`OPEN`, `PAID`). `PaymentTransaction`, `Transaction` ve `Webhook` linkte alınan ödemede `payment_link_token`'ın yanında `link_payment_token` taşır.
- **Ödeme linki tutar ve para birimi:** `CreatePaymentLink` ve `UpdatePaymentLink` yeni `amount_type` (`AmountType`), `item_name`, `predefined_amounts`, `tax_rate`, `tax_mode` (`TaxMode`), `currency_type` (`CurrencyType`), `currencies` ve `emails_payer` alanlarını alır; `PaymentLink` yanıtı da bu sekiz alanı taşır. Güncellemenin `clear` listesi `item_name`, `predefined_amounts`, `tax_rate` ve `currencies` alanlarını da boşaltır.
- **Kupon:** `Order`, `Subscription` ve `LinkPayment` yanıtlarında `discount` (`Discount`: `code`, `amount`; kupon yoksa `None`). Webhook gövdesinde yoktur.

Küçük kırıcı değişiklikler:

- **`create_*` artık kaydı yeniden yazmaz.** `create_order`, `create_subscription` ve `create_payment_link` her çağrıda yeni kayıt ve yeni token açar; aynı `reference` ile tekrar çağırmak eski kaydı güncellemez ve 422 dönmez. Referans tekil değildir. Her yanıtın token'ını saklayın ve değişiklik için `update_*` kullanın.
- **`CreatePaymentLink.items` isteğe bağlı oldu** (yalnızca `FIXED` tipte zorunludur); alan sıralı değil adla verildiği için mevcut çağrılar etkilenmez.
- **`PaymentLink.subtotal`, `tax_amount` ve `amount` artık `str | None`.** Ödeyenin tutarı seçtiği linklerde `None` gelir; eskiden boş metin (`''`) okunuyordu.
- **Yanıt modellerine zorunlu alanlar eklendi** (`PaymentLink`, `Order`, `Subscription`, `Transaction`, `Webhook`). Bu sınıfları testlerde elle kuruyorsanız yeni alanları da verin ya da `from_body()` kullanın.
- **Bekleyen ödeme:** son 15 dakikada başlamış ödeme yalnızca `update_order` ve `update_subscription` çağrılarını engeller; `create_*` ve `update_payment_link` çağrılarını engellemez.

## 1.0.1'deki kırıcı değişiklikler

1.0.1, SDK'yı geçidin bugünkü API'sine taşır ve 1.0.0 koduyla uyumlu değildir. 1.0.0'dan geçerken dikkat edilecekler:

- **Uçlar:** `order_payment`, `subscription_payment`, `save_product`, `cancel_subscription`, `retrieve_transactions`, `save_card`, `saved_cards` ve `default_saved_card` kaldırıldı. Yerlerine `create_order`, `create_subscription`, `update_subscription(status=CANCELLED)`, `retrieve_payments`, `create_saved_card`, `retrieve_saved_cards` ve `update_saved_card` geldi; ödeme linki, `update_*` uçları ve her kaynakta tek `retrieve_*` sorgusu eklendi. Ürün kataloğu yok: kalemler (`Item`) adı ve fiyatıyla gönderilir.
- **İmza:** gövde tek başına değil, `"{timestamp}\n{METHOD}\n{path}\n{body}"` imzalanır ve `X-Timestamp` başlığı eklenir.
- **Transport:** özel transport'lar `post(url, headers, body, timeout)` yerine `send(method, url, headers, body, timeout)` uygular.
- **İstekler:** tekil kaydı adlandıran alan her yerde `token` (`transaction_token`, `order_token`, `subscription_token`, `saved_card_token` istek alanları kalktı; kayıtlı kartla ödemedeki `saved_card_token` duruyor). Müşteri `reference` + `billing_address` / `shipping_address` (`Address`) oldu; şirket alanları fatura adresinde. Para birimi, dönem ve abonelik durumu `odemehub.enums` üyeleriyle verilir. `card` ile `saved_card_token`'ın birlikte verilmesi artık istemcide değil geçitte reddedilir.
- **Yanıtlar:** geçidin JSON'unu iç içe yansıtır: `payment.transaction.token`, `payment.transaction.status`, `payment.customer.reference`, `refund.refund.amount`, `answer.order`, `answer.subscription`, `answer.payment_link`. `OrderDetails` / `SubscriptionDetails` müşteriyi üst seviyede `customer` olarak da taşır. Sabit kümeler `odemehub.enums` üyesi olarak okunur.
- **Hatalar:** güncellenen, silinen, iade ya da iptal edilen kaydın token'ı bulunamazsa `NotFoundError` (404) atılır; eskiden bu durum 422 dönüyordu. Sorgular bulunamayan kayıtta boş liste döner. Yeni istisnalar: `ForbiddenError` (403), `NotFoundError` (404), `RateLimitError` (429, `retry_after`).
- **Webhook:** `order_webhook()`, `subscription_webhook()`, `transaction_webhook()` yerine tek `webhook(method, path, body, timestamp, signature)` (ve `verify_webhook()`); imza istek ve yanıtlarla aynı şemadadır. Gövde yalnızca token taşır (`order_token`, `payment_link_token`, `subscription_token`, `transaction_token`); durum `retrieve_*()` ile sorulur. Adresler panelde tanımlandığı için `SecurePayment`, `CreateOrder`, `UpdateOrder`, `CreateSubscription`, `UpdateSubscription` artık `webhook_url` almaz. `Signature.verify_body()` kalktı.
- **Kanal kalktı.** `Options.channel_token`, isteklerdeki `channel_token` ve `ChannelMessage` yoktur. Referans alanları `channel_reference` yerine `reference` adını taşır (ödeme, sipariş, abonelik, link, kalem); yanıtlarda `channel_token` yoktur. Geri dönüşte tarayıcı `channel_reference` değil `reference` POST eder.
- **Sorgular tek uçta.** Her kaynakta tek sorgu metodu vardır: `retrieve_payments`, `retrieve_orders`, `retrieve_subscriptions`, `retrieve_payment_links`, `retrieve_saved_cards`. İstek `token`, `reference`, `created_from`/`created_to` alır ya da boş verilir; yanıt her zaman listedir, bulunamayan kayıt `NotFoundError` değil boş listedir. GET isteği kalmadı.
- **Gönderim:** sipariş ve abonelik `requires_shipping` ile ödeme sayfasında gönderim adresi ister; gönderim yöntemleri panelde tanımlanır, istekte gönderilmez. Yanıtta yalnızca ödeyenin seçtiği yöntem (`shipping_method`: `reference`, `title`, `amount`, `tax_rate`) gelir.
- **Kalemler:** `tax_rate` isteğe bağlı; yeni `save_as_product`.
- **Müşteri:** referans gönderilmeyebilir; o zaman müşteri kaydedilmez ve kart saklanamaz. Abonelikte ve kart saklamada zorunludur. `reference` ve `billing_address` `None` olabilir.
- **Ödeme linki:** son 50 deneme ve `transactions_count` `retrieve_payment_links()` yanıtında her `PaymentLink` üzerindedir; `PaymentLinkDetails` yalnızca linki taşır.
- **Kayıtlı kart:** listede her kart kendi `customer`'ını taşır; `SavedCardList.customer` kalktı. Listelenen ödemede `saved_card`, kartın saklanması istendiyse saklanan kartı verir.

