---
title: "Android'de SSL pinning: pratikte neye yarar, neyi kırar"
slug: android-ssl-pinning-pratikte
date: 2026-08-10
description: "Android'de SSL pinning kurmak kolay, yaşatmak zor: hangi yöntemi seçmeli, neyi pinlemeli ve sertifika yenilenirken uygulamayı nasıl kırmazsın?"
cover: /assets/covers/android-ssl-pinning-pratikte.jpg
cover_alt: "Android'de SSL pinning: MITM saldırısının engellenmesi, Burp/Charles gibi araçların devre dışı kalması ve root'lu cihazda Frida/Xposed ile pinning'in aşılması"
tags: [android, kotlin, güvenlik]
---

Kurumsal projelerde kullanıcı verisi taşıyan uygulamalar geliştirirken güvenlik bir "ek özellik" olmaktan çıkıyor. SSL pinning de bu listenin başında geliyor: fikir olarak beş dakikada anlatılır, ama üretimde yanlış kurarsan uygulamayı **uzaktan kapatma düğmesine** dönüşebilir. Bu yazıda hem nasıl kurulacağını hem de asıl önemlisi, nerede tökezlendiğini yazıyorum.

## Pinning tam olarak neyi çözüyor?

HTTPS zaten sunucunun sertifikasını doğruluyor. Ama neye göre? Cihazdaki **güvenilen kök sertifika listesine** göre. Yani o listedeki herhangi bir otorite senin alan adın için bir sertifika üretebilirse, uygulaman bunu sorunsuz kabul eder.

Pinning bu güveni daraltıyor: "bu alan adı için sadece *şu* açık anahtarı kabul ediyorum" diyorsun. Kurumsal proxy'ler, cihaza elle kurulmuş sertifikalar, Burp/mitmproxy gibi araçlar — hepsi bu noktada duvara çarpıyor.

Ama bir nüansı baştan söylemek lazım: **Android 7.0'dan (API 24) itibaren** uygulamalar kullanıcının elle kurduğu sertifika otoritelerine varsayılan olarak güvenmiyor. Yani "telefona sertifika kurup trafiği dinlemek" senaryosunun büyük kısmı, sen hiçbir şey yapmadan zaten kapalı. Pinning'in sana kattığı şey daha çok şu: güvenilen otoritelerden birinin ele geçirilmesi ya da kötüye kullanılması durumunda da korunmak.

## Nasıl kurulur: üç yaklaşım

### 1. Network Security Config (platform seviyesi)

`res/xml/network_security_config.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <domain-config>
        <domain includeSubdomains="true">api.example.com</domain>
        <pin-set expiration="2027-01-01">
            <pin digest="SHA-256">k3XnEYQCK79AtL9GYnT/nyhsabas+HrbBg==</pin>
            <pin digest="SHA-256">YEDEK_ANAHTARIN_HASHI=</pin>
        </pin-set>
    </domain-config>
</network-security-config>
```

Manifest'te bağlıyorsun:

```xml
<application android:networkSecurityConfig="@xml/network_security_config" ... >
```

Avantajı: tek yerde tanımlıyorsun, sistem trust manager'ını kullanan bütün istemcileri kapsıyor. Kod yazmıyorsun.

Buradaki `expiration` alanı bence en değerli detay: o tarih geçtiğinde pinning **kontrol edilmez hale geliyor**. Kulağa güvenlik açığı gibi geliyor, ama aslında bilinçli bir tasarım — pinlerin eskidiği ve senin güncelleme çıkaramadığın bir durumda uygulamanın tamamen çalışmaz hale gelmesini engelliyor. Bunu bir kaza değil, **sigorta** olarak düşün.

### 2. OkHttp CertificatePinner (kod seviyesi)

```kotlin
private val pinner = CertificatePinner.Builder()
    .add("api.example.com", "sha256/k3XnEYQCK79AtL9GYnT/nyhsabas+HrbBg==")
    .add("api.example.com", "sha256/YEDEK_ANAHTARIN_HASHI=")
    .build()

val client = OkHttpClient.Builder()
    .certificatePinner(pinner)
    .build()
```

Avantajı: API seviyesinden bağımsız çalışıyor, pinleri uzaktan yönetilebilir hale getirmek (remote config) mümkün, hata durumunu kodda yakalayıp raporlayabiliyorsun.

Dezavantajı ve gözden kaçan kısım: bu pinning **sadece o OkHttp istemcisinden geçen trafiği** kapsıyor. Uygulamandaki WebView, üçüncü parti bir SDK'nın kendi ağ katmanı ya da başka bir kütüphane bundan habersiz. Pinlediğini düşündüğün uygulamanın yarısı pinsiz olabilir — bunu ayrıca doğrulaman gerekiyor.

### 3. Sertifikanın kendisini gömmek (`res/raw`)

Yukarıdaki iki yol sertifikanın **özetini** gömüyor. Bir üçüncü yol daha var: sertifikanın **kendisini** uygulamaya koyup güven zincirini doğrudan oradan kurmak. Kurumsal projelerde sık karşılaşılan bir durumda — API'yi kendi iç CA'nızla imzalıyorsanız — pratikte tek makul yol bu, çünkü cihazdaki kök sertifika listesinde sizin CA'nız zaten yok.

Sertifikayı `res/raw/api_ca.crt` olarak koyuyorsun (PEM ya da DER olabilir), sonra Network Security Config'te güven çıpası olarak gösteriyorsun:

```xml
<domain-config>
    <domain includeSubdomains="true">api.example.com</domain>
    <trust-anchors>
        <certificates src="@raw/api_ca"/>
    </trust-anchors>
</domain-config>
```

Bu tanım o alan adı için cihazdaki bütün kök sertifika listesini devre dışı bırakıp yerine tek bir otorite koyuyor. Platform CA'larını da korumak istiyorsan ikisini birlikte yazabiliyorsun:

```xml
<trust-anchors>
    <certificates src="@raw/api_ca"/>
    <certificates src="system"/>
</trust-anchors>
```

Aynı şeyi kod tarafında kurmak istersen (`com.squareup.okhttp3:okhttp-tls`):

```kotlin
val ca = context.resources.openRawResource(R.raw.api_ca).use { input ->
    CertificateFactory.getInstance("X.509").generateCertificate(input) as X509Certificate
}

val certs = HandshakeCertificates.Builder()
    .addTrustedCertificate(ca)
    // .addPlatformTrustedCertificates()  // genel CA'lar da gerekiyorsa
    .build()

val client = OkHttpClient.Builder()
    .sslSocketFactory(certs.sslSocketFactory(), certs.trustManager)
    .build()
```

Buradaki tuzağı özellikle işaretlemek istiyorum: `addTrustedCertificate` tek başına kullanıldığında **platform CA'ları devrede olmuyor**. Aynı istemciden analitik, harita, görsel CDN'i gibi başka istekler de geçiyorsa hepsi bir anda bağlanamaz hale gelir. Ya `addPlatformTrustedCertificates()` ekleyeceksin ya da bu istemciyi sadece kendi API'n için ayıracaksın — ikincisi daha temiz bir kurgu.

### Pin mi, sertifika dosyası mı?

| | SPKI pin | Gömülü sertifika (`res/raw`) |
|---|---|---|
| Gömülen şey | Açık anahtarın SHA-256 özeti | Sertifikanın kendisi |
| Sertifika yenilendiğinde | Anahtar aynıysa etkilenmez | Gömülü CA'nın süresi bitene kadar sorun yok |
| Kendi iç CA'n varsa | Tek başına yetmez | Doğru araç |
| Genel CA listesi | Daraltır | Tamamen değiştirebilir |
| En büyük riski | Yanlış/eksik pin | Gömülü sertifikanın süresinin dolması |

Kaba bir kural: **halka açık bir CA'dan sertifika alıyorsan pin**, **kendi PKI'ını işletiyorsan gömülü sertifika**. Bunlar birbirinin alternatifi değil, farklı problemleri çözüyorlar — ve gerektiğinde birlikte de kullanılabilirler.

Katmanları birleştirmek de makul: platform seviyesi geniş güvenlik ağı, OkHttp seviyesi ise kontrol ve gözlemlenebilirlik için.

## Pin değerini nasıl bulursun?

Pinlediğin şey sertifikanın kendisi değil, **açık anahtarın (SPKI) SHA-256 özeti**. Bu ayrım önemli: sertifika yenilendiğinde anahtar aynı kalıyorsa pin'in bozulmuyor.

```bash
openssl s_client -connect api.example.com:443 -servername api.example.com < /dev/null 2>/dev/null \
  | openssl x509 -pubkey -noout \
  | openssl pkey -pubin -outform der \
  | openssl dgst -sha256 -binary \
  | openssl enc -base64
```

Kestirme bir yol da var: OkHttp'ye kasten yanlış bir pin ver, isteği çalıştır. Fırlayan `SSLPeerUnverifiedException` sana zincirdeki sertifikaların beklenen pin değerlerini olduğu gibi yazıyor. Kopyala, yapıştır, geç.

## Hangi sertifikayı pinlemeli?

Burada gerçek bir denge var:

| Ne pinlersin | Ömür | Güvenlik |
|--------------|------|----------|
| Yaprak (leaf) sertifika | Kısa — 90 gün olabilir | En sıkı |
| Ara (intermediate) CA | Yıllar | Daha gevşek |

Yaprak sertifikayı pinlemek en güvenli olan, ama sertifika her yenilendiğinde yeni sürüm çıkarmak zorunda kalırsın. Ara CA'yı pinlemek yıllarca dayanır, ancak o CA'dan sertifika alabilen herkes pinini geçer.

Benim tercihim ortada duruyor: **anahtarı pinle, en az iki pin gönder.** Biri aktif, biri henüz kullanılmayan yedek anahtar (offline saklanan). Sertifika yenilenirken yedeğe geçiyorsun, uygulama hiç kırılmıyor, sonraki sürümde yeni bir yedek ekliyorsun.

## Uygulamayı kırmama meselesi

Bu yazının asıl konusu burası. Web'de yanlış pin bir `Ctrl+R` uzağında; mobilde değil. Store'a yeni sürüm gönderirsin, kullanıcı güncellemeyi ne zaman alır bilmezsin — hiç almayabilir. Yanlış pin, o kullanıcı için uygulamanın **tamamen çalışmaması** demek.

Sahada işe yarayan önlemler:

- **Her zaman en az iki pin** — biri kullanımda olmayan yedek anahtar.
- **`expiration` kullan** — sigortayı devrede tut.
- **Kill switch** — pinning'i sunucudan kapatabileceğin bir uzaktan yapılandırma. Bu yapılandırmanın kendisinin pinli kanaldan gelmemesi gerekiyor, yoksa kilidi kilitli kapının arkasına koymuş olursun.
- **Ölç.** Pinning hatasını sessizce yutma:

```kotlin
try {
    client.newCall(request).execute()
} catch (e: SSLPeerUnverifiedException) {
    Firebase.crashlytics.log("pin_failure host=${request.url.host}")
    Firebase.crashlytics.recordException(e)
    throw e
}
```

Bu log olmadan, sertifika rotasyonunu yanlış yaptığını kullanıcı yorumlarından öğrenirsin. Bunu bir kez yaşamak, bu maddeyi kalıcı olarak hatırlamak için yeterli.

- **Sertifika rotasyonunu takvime yaz.** Pinleri kim yeniliyor, hangi sürümde çıkıyor, backend ekibi sertifikayı değiştirmeden önce kimi haberdar ediyor? Gömülü sertifika kullanıyorsan aynı takvimde onun son kullanma tarihi de olmalı — o gün geldiğinde güncellenmemiş her kurulum kırılıyor. Bu teknik değil, süreç problemi — ve pinning'in en sık kırıldığı yer tam olarak burası.

## Peki gerçekten aşılamaz mı?

Hayır. Root'lu bir cihazda Frida ile `CertificatePinner`'ı ya da trust manager'ı çalışma zamanında değiştirmek bilinen bir iş. Pinning, kararlı bir tersine mühendisin karşısında bir duvar değil, bir **maliyet artırıcı**.

Bu yüzden zihinsel modeli doğru kurmak gerekiyor: pinning, **kullanıcını ağ üzerindeki saldırgana karşı** korur. API'ni, uygulamanı parçalamaya çalışan birine karşı korumaz. "Trafik pinli, o yüzden bu endpoint güvende" cümlesi kurulduğu anda bir yerde hata var — yetkilendirme, oran sınırlama ve sunucu tarafı doğrulama pinning'e devredilebilecek şeyler değil.

## Flutter tarafında kısa not

`dio` ya da `http` kullanıyorsan pinning'i `HttpClient` üzerinden, sertifikanın özetini karşılaştırarak kurabiliyorsun. Ama Android tarafında zaten Network Security Config varsa, platform seviyesindeki tanımın Dart katmanındaki `HttpClient` için de geçerli olduğunu unutma.

---

Özetle: pinning kurmak kolay, **yaşatmak** zor. Kurarken kendine tek bir soru sor — "sertifika beklenmedik şekilde değişirse ne olacak?" Bu sorunun cevabı "kullanıcının uygulaması açılmaz" ise, kurulumun daha bitmemiş demektir.
