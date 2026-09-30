# ödemehub Python SDK

ödemehub ödeme geçidini kendi uygulamanızdan kullanmak için hazırlanmış Python istemcisi. Kart çekmek, 3D ödeme başlatmak, müşteriyi ödeme sayfasına yollamak, ürün kataloğunuzu eşlemek, abonelik açmak, kart saklamak, iade ve iptal yapmak ve bir kartın taksit seçeneklerini sormak için gereken her şey burada.

İstemci her isteği takımınızın gizli anahtarıyla imzalar, gelen her yanıtın imzasını doğrular. Siz imza, başlık ya da JSON ayrıntılarıyla uğraşmazsınız. Yalnızca standart kütüphaneyi kullanır; kurulacak başka paket yoktur. Tip ipuçları pakettedir.

## Kurulum

Python 3.10 ve üzeri gerekir.

```bash
pip install odemehub
```

## Yapılandırma

Dört bilgiye ihtiyacınız var. Hepsi paneldeki **Entegrasyon** sayfasındadır (menünün en altında): API anahtarı, gizli anahtar, Çalışma Alanı Kimliğiniz ve kanallarınızla ödeme hesaplarınızın token'ları.

```python
import os

from odemehub import Client, Options

client = Client(Options(
    base_url="https://odeme.gurmehub.com",
    team="4829301756",                                   # Çalışma Alanı Kimliğiniz
    channel_token="6f1c2e7a-4b3d-4c8e-9a61-2f5d7b0c3e14", # müşterinin size ulaştığı kanal
    api_key=os.environ["ODEMEHUB_API_KEY"],
    api_secret=os.environ["ODEMEHUB_API_SECRET"],
))
```

Gizli anahtar hiçbir zaman tel üzerinden gitmez; yalnızca imza üretmekte kullanılır. Anahtarları kodun içine yazmayın, ortam değişkeninde tutun.

Kanal token'ı entegrasyonun tamamı için bir kez verilir. Birden çok kanalda satıyorsanız tek bir istekte `channel_token` vererek o isteği başka kanala yazdırabilirsiniz. Geçit hiçbir yerde veritabanı numarası kullanmaz: kanal, ödeme hesabı, işlem, kayıtlı kart, abonelik ve sipariş her zaman token'ıyla adlanır.

İstek bir dakika içinde yanıt almazsa kesilir; süreyi `Options(timeout=...)` (saniye) ile değiştirebilirsiniz. İstekler standart kütüphanenin `urllib`'iyle gider; `requests` ya da `httpx` kullanmak isterseniz `post(url, headers, body, timeout)` metodu olan bir nesneyi `Client(options, transport=...)` ile verebilirsiniz.

İstekler `odemehub.request` modülündeki değişmez nesnelerdir ve alanları yalnızca adla verilir. İsteğe bağlı bir alanı vermezseniz gövdeye hiç yazılmaz. Kart numarası ve güvenlik kodu `repr()` çıktısına hiç girmez, böylece kart nesnesi yanlışlıkla loglansa da kart bilgisi görünmez.

## Karttan doğrudan çekim

Müşteriyi bankasına göndermeden çekim yapar. Başarılı yanıt, paranın alındığı anlamına gelir.

```python
from odemehub.request import Card, Customer, RegularPayment

payment = client.regular_payment(RegularPayment(
    channel_reference="SIP-10231",          # işlemin sizdeki referansı
    amount="450.00",
    installment_number=1,
    ip=request.remote_addr,
    customer=Customer(
        channel_reference="musteri-88",
        firstname="Ahmet",
        lastname="Yılmaz",
        email="ahmet@ornek.com",
        phone="05551112233",
        address="Kızılırmak Mah. Dumlupınar Blv. No:3",
        district="Çankaya",
        province="Ankara",
        country="Türkiye",
    ),
    card=Card(
        holder_name="AHMET YILMAZ",
        number="5400360000000003",
        expiry_month="12",
        expiry_year="2030",
        security_code="000",
    ),
))

if payment.result.successful:
    ...  # payment.transaction_token — ödemenin geçitteki token'ı; iade ve iptalde bununla adlandırılır
```

Tutarlar her zaman metindir (`"450.00"`): imzalanıp gönderildiği gibi kalır, yolda yuvarlanmaz.

## 3D ödeme

3D'de çekim iki adımdır: siz ödemeyi başlatırsınız, müşteri bankasına gider, banka sonucu sizin adresinize gönderir.

```python
from odemehub.request import SecurePayment

payment = client.secure_payment(SecurePayment(
    channel_reference="SIP-10232",
    amount="450.00",
    installment_number=1,
    ip=request.remote_addr,
    callback_url="https://magazam.com/odeme/donus",
    customer=customer,
    card=card,
))

if payment.result.successful:
    return redirect(payment.redirect_url)   # müşteriyi bankaya gönderin
```

Başarılı yanıt **ödeme alındı demek değildir**; yalnızca müşterinin gideceği adres hazır demektir.

Müşteriyi **15 dakika içinde** bu adrese yönlendirin. Sayfası o süre içinde açılmayan ödemenin süresi dolar (`expired`). Süresi dolmuş bağlantıyı açan müşteri doğrudan `callback_url` adresinize, `successful=0` ile geri gönderilir; `retrieve_payment()` sorgusu da başarısız sonucu ve nedenini döner.

Banka işini bitirince müşteri, tarayıcısı üzerinden `callback_url` adresinize döner. O POST (form gövdesi) **sonucu taşımaz**, yalnızca sonucun hazır olduğunu haber verir:

| Alan | Anlamı |
| --- | --- |
| `transaction_token` | ödemenin geçitteki token'ı |
| `channel_reference` | sizin kendi referansınız |
| `successful` | `1` / `0` — yalnızca ipucu, **güvenilmez** |

Sonucu kendi imzalı bağlantınızdan sorun:

```python
from odemehub.request import RetrievePayment

@app.post("/odeme/donus")
def odeme_donus():
    outcome = client.retrieve_payment(RetrievePayment(
        transaction_token=request.form["transaction_token"],
    ))

    if outcome.result.successful:
        ...  # siparişi ödendi olarak işaretleyin
```

Neden böyle: o POST'u bizim sunucumuz değil, müşterinin tarayıcısı gönderir; tarayıcıya imzalayacak bir sır verilemez. `successful` alanına bakıp sipariş kapatmayın — onu herkes gönderebilir; yalnız "başarısız" ipucunda gereksiz sorgudan kaçınmak için kullanın. Geçide sorduğunuz yanıt ise her zaman imzalıdır ve SDK imzayı sizin için doğrular. Başkasının işlemini sorarsanız `ValidationError` alırsınız.

## Ürünler

Sipariş kalemleri ve abonelikler ürünleri **sizdeki referanslarıyla** adlandırır. Ürünü panelde (Ürünler sayfası) tanımlayabilir ya da kendi kataloğunuzdan geçide yazabilirsiniz:

```python
from odemehub.request import SaveProduct

product = client.save_product(SaveProduct(
    channel_reference="KAHVE-MAKINESI",
    name="Kahve makinesi",
    type="simple",          # simple | recurring
    amount="450.00",
    tax_rate="20",          # fiyatın içindeki KDV oranı
))

client.save_product(SaveProduct(
    channel_reference="PREMIUM-AYLIK",
    name="Premium üyelik",
    type="recurring",
    amount="149.90",
    tax_rate="20",
    period="monthly",       # monthly | annually — yalnız recurring için zorunlu
))
```

Aynı kanalda aynı referans aynı üründür: tekrar gönderirseniz ikinci ürün açılmaz, mevcut olan güncellenir. `currency` verilmezse TRY, `is_active` verilmezse `True` kabul edilir. Ürün silinmez; `is_active=False` ile satışa kapatılır.

Ödeme istekleri ürünü hiçbir zaman değiştirmez; ürünün tek yazıldığı yer bu çağrı ve panel.

## Ödeme sayfası

Kart bilgisini hiç görmek istemiyorsanız sipariş açıp müşteriyi geçidin kendi sayfasına yollayabilirsiniz.

```python
from odemehub.request import OrderItem, OrderPayment

order = client.order_payment(OrderPayment(
    channel_reference="SIPARIS-10233",
    success_url="https://magazam.com/tesekkurler",
    cancel_url="https://magazam.com/sepet",
    customer=customer,
    items=[
        OrderItem(channel_reference="KAHVE-MAKINESI"),
        OrderItem(channel_reference="KAHVE-500G", quantity=2, unit_amount="180.00"),
        OrderItem(channel_reference="HEDIYE-PAKETI", name="Hediye paketi", unit_amount="25.00"),
    ],
))

return redirect(order.checkout_url)
```

Sipariş tutarını göndermezsiniz; geçit kalemleri toplar ve `order.amount` olarak döner. Bir kalemin boş bıraktığı ad, fiyat ve KDV oranı kayıtlı üründen gelir; kalemde verdiğiniz değerler yalnızca o sipariş için geçerlidir, ürünü değiştirmez. Kayıtlı olmayan bir referansla da kalem gönderebilirsiniz, ama o zaman `name` ve `unit_amount` zorunludur.

Ödeme tamamlanınca müşteri, 3D'dekiyle aynı biçimde `success_url` adresinize döner: aynı üç alan gelir, sonucu yine `retrieve_payment()` ile sorarsınız. Müşteri ödeme sayfasında karttan kaynaklı bir hata alırsa size dönmez, sayfada kalıp başka kartla dener.

## Abonelikler

Müşteriden dönem dönem tahsilat yapmak için abonelik açarsınız. Neye abone olunduğu bir ya da birkaç **abonelik ürünüdür** (`type="recurring"`), sizdeki referanslarıyla adlandırılır; fiyatı, para birimini ve dönemini ürün taşır. Aynı aboneliğe konan ürünlerin dönemi ve para birimi aynı olmalıdır.

```python
from odemehub.request import SubscriptionItem, SubscriptionPayment

subscription = client.subscription_payment(SubscriptionPayment(
    channel_reference="UYELIK-4471",
    items=[
        SubscriptionItem(channel_reference="PREMIUM-AYLIK"),
        SubscriptionItem(channel_reference="EK-KULLANICI", quantity=3),
    ],
    success_url="https://magazam.com/tesekkurler",
    customer=customer,
))

subscription.token  # aboneliği sonra sorgulamak ve iptal etmek için saklayın

return redirect(subscription.checkout_url)
```

Bir kaleme `unit_amount` verirseniz o fiyat **yalnızca ilk dönem** için geçerlidir (ör. ilk ay yarı fiyat); sonraki dönemler ürünün kendi fiyatından çekilir.

İlk ödeme her zaman geçidin kendi sayfasında yapılır ve kart zorunlu olarak saklanır: sonraki dönemler o karttan çekilir. Ödeme tamamlanınca müşteri `success_url` adresinize döner ve sonucu yine `retrieve_payment()` ile sorarsınız; abonelik `active` olur ve aşağıdaki bildirim de gider.

Dönem bitince yeni dönem açılır ve müşterinin varsayılan kartından çekilir. Banka kabul etmezse çekim bir buçuk gün içinde beş kez denenir (araları 3, 6, 9 ve 12 saat); bu sırada abonelik `active` kalır. Beşinci deneme de olmazsa abonelik `past_due` olur; çalışma alanı yöneticilerinize e-posta, `webhook_url` adresinize bildirim gider. İkisi de o dönemin dilediği kartla ödenebileceği bağlantıyı taşır; bağlantıyı müşterinize siz iletirsiniz. Süre sınırı yoktur; müşteri ödediği anda abonelik kaldığı yerden devam eder.

Aboneliğin durumunu sorabilirsiniz:

```python
from odemehub.request import RetrieveSubscription

subscription = client.retrieve_subscription(RetrieveSubscription(subscription_token=token))

subscription.status        # pending | active | past_due | cancelled
subscription.amount        # 149.90 — içinde bulunulan dönemin fiyatı
subscription.ends_at       # sonraki tahsilat zamanı
subscription.checkout_url  # ödenmemiş dönem varsa müşteriye verilecek adres

for item in subscription.items:
    print(f"{item.quantity} x {item.name} ({item.channel_reference})")

if subscription.is_past_due():
    ...  # müşteriyi kendi ödeme sayfanızda uyarabilirsiniz
```

Tutar, aboneliğin **içinde bulunduğu dönemin** fiyatıdır. Ürünün fiyatını yükseltirseniz yürüyen dönem çekildiği fiyatta kalır, yeni fiyat sonraki dönemden itibaren işler.

İptalde ödenmiş günler yanmaz:

```python
from odemehub.request import CancelSubscription

subscription = client.cancel_subscription(CancelSubscription(subscription_token=token))

subscription.cancelled_at    # iptal edildiği an
subscription.ends_at         # hizmetin süreceği son gün
subscription.is_cancelled()  # ödenmiş dönem sürüyorsa henüz False
```

Müşteri, ödediği dönemin sonuna kadar hizmeti almaya devam eder; o güne kadar abonelik `active` görünür, dönem bitince `cancelled` olur ve bir daha tahsilat yapılmaz. Ödenmemiş bir aboneliğin (ilk ödemesi yapılmamış ya da `past_due`) iptali hemen geçerlidir. İade yapılmaz.

Aboneliğin açılabilmesi için varsayılan ödeme hesabınızın kart saklayabiliyor olması gerekir; saklamayan bir hesapla açmaya çalışırsanız istek `subscription.payment_provider_token` alanında reddedilir.

### Abonelik bildirimleri (webhook)

Abonelik açarken `webhook_url` verirseniz, aboneliğin durumu her değiştiğinde o adrese imzalı bir POST gönderilir. Gövde düz JSON'dur ve imza `X-Signature` başlığındadır — yani geçidin API yanıtlarıyla aynı yöntem.

```python
subscription = client.subscription_payment(SubscriptionPayment(
    channel_reference="UYELIK-4471",
    items=[SubscriptionItem(channel_reference="PREMIUM-AYLIK")],
    success_url="https://magazam.com/tesekkurler",
    customer=customer,
    webhook_url="https://magazam.com/odemehub/abonelik",
))
```

Bildirimi karşılayan uçta gövdeyi **ham** okuyup imzayla birlikte SDK'ya verin. İmza gövdenin bayt bayt kendisini kapsar; gövdeyi ayrıştırıp yeniden yazarsanız imza tutmaz.

```python
from odemehub import SignatureError

@app.post("/odemehub/abonelik")
def abonelik_bildirimi():
    try:
        webhook = client.subscription_webhook(
            request.get_data(),                  # Django: request.body
            request.headers.get("X-Signature"),
        )
    except SignatureError:
        return "", 400

    subscription = webhook.subscription   # sorgudakiyle aynı nesne

    if webhook.is_active():
        abonelige_erisim_ac(subscription.channel_reference, subscription.ends_at)
    elif webhook.is_past_due():
        musteriyi_uyar(subscription.checkout_url)
    elif webhook.is_cancelled():
        yenilemeyi_durdur(subscription.ends_at)
    elif webhook.is_ended():
        erisimi_kapat(subscription.channel_reference)

    return "", 200
```

Gönderilen olaylar aboneliğin **durumudur**, yapılan işlem değil:

| Olay | Ne zaman gider |
| --- | --- |
| `active` | bir dönem ödendi (ilk ödeme ya da yenileme) |
| `past_due` | dönem kayıtlı karttan tahsil edilemedi, müşteriden bekleniyor |
| `cancelled` | abonelik iptal edildi; müşteri `ends_at` tarihine kadar hizmeti almaya devam eder |
| `ended` | ödenmiş dönem doldu, abonelik kapandı |

2xx dışında bir yanıt (ya da yanıtsızlık) başarısız sayılır; bildirim 5 dakika sonra bir kez daha denenir. Ulaşmayan bildirimler panelde aboneliğin sayfasında HTTP kodu ve yanıtıyla listelenir.

## Ödeme hangi hesaptan geçer

`payment_provider_token` verirseniz ödeme o hesaptan geçer; sipariş ve abonelik açarken de aynı alan vardır ve müşteri ödeme sayfasında o hesaptan öder. Vermezseniz hesabı çalışma alanınız seçer: panelde **Ödeme Ayarları → Gate (Yönlendirme)** altındaki kurallar sırayla denenir ve ödemenin karşıladığı ilk kural hesabı belirler. Kurallar kartın bankasına, şemasına, programına, tipine, ticari kart olup olmadığına, tutara ve para birimine bakabilir. Hiçbir kural tutmazsa ödeme varsayılan hesaptan geçer.

- Kuralın hesabı ödemeyi alamıyorsa (ödeme türünü ya da para birimini desteklemiyorsa) o kural atlanır.
- Kayıtlı kartla ödeme her zaman kartın saklandığı hesaptan geçer.
- Taksitleri `retrieve_bin()` ile gösteriyorsanız orada da hesap vermeyin: taksitler ödemenin gideceği hesaptan gelir ve çekilen tutar gösterdiğinizle aynı olur.

## Kur çevirisi

Panelde **Ödeme Ayarları → Kur Çevirici** altında bir kural tanımladıysanız, o para biriminde gelen ödeme karttan kuralın para biriminde çekilir. Örneğin 100 USD istersiniz, karttan 4.985,56 TRY çekilir. Kur, TCMB'nin güncel döviz satış kuru ve üzerine eklediğiniz marjdır ya da sizin girdiğiniz sabit kurdur.

İsteğinizde hiçbir şey değişmez: tutarı ve para birimini her zamanki gibi gönderirsiniz. Yanıttaki `conversion` karttan ne çekildiğini söyler:

```python
payment = client.regular_payment(RegularPayment(
    amount="100.00",
    currency="USD",
    # ...
))

if payment.conversion is not None:
    payment.conversion.amount    # 4985.56
    payment.conversion.currency  # TRY
    payment.conversion.rate      # 49.855560
```

- Çevrilmeyen ödemede `conversion` `None` gelir. `retrieve_payment()` aynı bilgiyi yeniden verir.
- İade tutarını çekilen para biriminde gönderin (yukarıdaki örnekte TRY).
- Güncel kur alınamıyorsa ödeme alınmaz; `422` ile `transaction.currency` alanında hata döner. Birkaç dakika sonra tekrar deneyin.

## Kart sorgusu ve taksitler

Kart numarasının ilk hanelerinden kartın kim tarafından verildiğini, hangi programa ait olduğunu ve tutarın kaç taksite bölünebileceğini sorar. Hiçbir şey çekilmez.

```python
from odemehub.request import RetrieveBin

bin = client.retrieve_bin(RetrieveBin(bin="54003600", amount="450.00"))

if bin.result.successful:
    bin.issuer_name     # Garanti Bankası
    bin.program         # Bonus
    bin.scheme          # mastercard
    bin.type            # credit
    bin.is_commercial

    for installment in bin.installments:
        # 3 taksitte ayda 157.87, toplam 473.60
        print(f"{installment.number} x {installment.amount} = {installment.total}")
```

Kartın tamamını göndermeyin; ilk 6-8 hane yeter ve yalnızca o kadarı kabul edilir.

Sorgu başarısız dönebilir: kart tanınmıyor olabilir ya da hesabınızın sağlayıcısı taksit vermiyor olabilir. İki durumda da satışı durdurmayın, tek çekimle devam edin.

## Tutarlar ve taksit

İki tutar vardır ve karıştırılmamalıdır:

| Alan | Anlamı |
| --- | --- |
| `amount` | **Karttan çekilecek** tutar. Vade farkı varsa içindedir. |
| `base_amount` | **Sattığınız** tutar, vade farkından önceki hâli. Gönderilmezse `amount` ile aynı kabul edilir. |

Taksit yalnızca Türk Lirası ödemelerde yapılır. USD, EUR ya da GBP ödemede `installment_number` `1` olmalıdır ve `retrieve_bin()` taksit listesini boş döner; kur çevirisiyle TRY'den başka bir para birimine çekilen ödeme için de aynısı geçerlidir.

Taksitsiz satışta ikisi eşittir ve `base_amount` göndermenize gerek yoktur. Taksitli satışta `retrieve_bin` size o taksidin toplamını verir; onu `amount` olarak, sattığınız tutarı `base_amount` olarak gönderin:

```python
payment = client.regular_payment(RegularPayment(
    channel_reference="SIP-10234",
    amount="473.60",        # 3 taksitin toplamı
    base_amount="450.00",   # satılan tutar
    installment_number=3,
    # ...
))
```

Bazı sağlayıcılar vade farkını kendileri ekler; geçit bunu bilir ve gerekirse sağlayıcıya taban tutarı gönderir. Sizin tarafınızda değişen bir şey yoktur.

## Kayıtlı kartlar

Müşterinin kartını saklayıp sonraki ödemelerde numara sormadan çekim yapabilirsiniz.

```python
from odemehub.request import DefaultSavedCard, DeleteSavedCard, NamedCustomer, SaveCard, SavedCards

# Ödeme sırasında saklamak için: Card'a should_save=True verin.
# Ödeme olmadan saklamak için:
kept = client.save_card(SaveCard(customer=customer, card=card))

musteri = NamedCustomer(channel_reference="musteri-88")

# Müşterinin kartları
cards = client.saved_cards(SavedCards(customer=musteri))

# Varsayılan yapma / silme
token = cards.saved_cards[0].token

client.default_saved_card(DefaultSavedCard(customer=musteri, saved_card_token=token))
client.delete_saved_card(DeleteSavedCard(customer=musteri, saved_card_token=token))
```

Kayıtlı kartla ödeme alırken `card` yerine kartın token'ını verin:

```python
payment = client.regular_payment(RegularPayment(
    channel_reference="SIP-10235",
    amount="120.00",
    installment_number=1,
    ip=request.remote_addr,
    customer=customer,
    saved_card_token=token,
))
```

`card` ile `saved_card_token` birlikte ya da hiçbiri verilmezse istek nesnesi oluşturulurken `ValueError` fırlatılır.

Kart saklayan bir ödemenin yanıtında `payment.saved_card` dolu gelir; kartın token'ını oradan öğrenirsiniz. Kart her yerde token ile adlandırılır.

## İade ve iptal

```python
from odemehub.request import CancelPayment, RefundPayment

# Gün sonu almamış ödemenin tamamını geri alır
client.cancel_payment(CancelPayment(transaction_token=payment.transaction_token))

# Tutar verilirse kısmi, verilmezse kalanın tamamı iade edilir.
# Kur çevirisiyle çekilen ödemede tutar çekilen para birimindedir.
client.refund_payment(RefundPayment(transaction_token=payment.transaction_token, amount="100.00"))
```

## Hatalar

Bütün hatalar `OdemehubError`'dan türer; tek bir `except` hepsini yakalar.

| Hata | Ne demek |
| --- | --- |
| `ValidationError` | Gönderdiğiniz alanlar kabul edilmedi. Ödeme denenmedi. `error.errors` alan alan söyler. |
| `AuthenticationError` | API anahtarı bu takıma ait değil ya da imza gizli anahtarla tutmuyor. |
| `SignatureError` | Gelen yanıtın ya da bildirimin imzası tutmadı. Geçitten geldiği kanıtlanamaz; **işleme almayın**. |
| `TransportError` | Geçide ulaşılamadı ya da yanıt okunamadı. Ödemenin ne olduğu belirsizdir; geçitteki kayıt asıl doğruyu söyler. |
| `UnexpectedResponseError` | Beklenmeyen bir yanıt geldi. `error.status` HTTP kodunu verir. |

```python
from odemehub import OdemehubError, ValidationError

try:
    client.regular_payment(payment)
except ValidationError as error:
    print(error.errors)  # {'transaction.amount': ['...']}
except OdemehubError as error:
    print(error)
```

Ağ hatasında ödemeyi körlemesine tekrarlamayın: `TransportError` "olmadı" demek değil, "bilmiyorum" demektir.

## İmzayı elle doğrulamak

İmza, gövdenin tam metninin gizli anahtarla HMAC-SHA256'sıdır, küçük harf hex olarak yazılır. SDK bunu `Signature` sınıfıyla yapar; aynı hesabı kendiniz de yapabilirsiniz:

```python
import hashlib
import hmac

hmac.new(api_secret.encode(), body, hashlib.sha256).hexdigest()
```

Test vektörü: `secret_test` anahtarıyla `{"a":1}` gövdesinin imzası `6d0c951564cdd2b6b70e75b214293a8cd2542815ba54fe91c7f6ce105bc3d592`'dir.
