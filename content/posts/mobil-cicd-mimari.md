---
title: "Mobil CI/CD: kurduğum mimari ve verdiğim kararlar"
slug: mobil-cicd-mimari
date: 2026-08-15
description: "Mobil projelerde kurduğum CI/CD yapısı ve arkasındaki kararlar: sırlar neden repoda durmaz, hangi sır nerede saklanır, prod neden sadece master'dan çıkar?"
cover: /assets/covers/mobil-cicd-mimari.jpg
cover_alt: "GitLab CI/CD akışı: CI değişken yönetimi ve erişim kontrolü, build / security scan / static analysis adımları ve merge'den prod dağıtımına uzanan pipeline"
tags: [ci-cd, gitlab, mobil]
---

Her ürünün geliştirme aşamasında değişmeyen bir avuç süreç vardır. Test ve dağıtım da bunların başında gelir. Commit sonrası unit testleri çalıştıran, bir hata varsa sürüm çıkmadan haber veren bir yapıya ihtiyacınız var. Sonra uygulamanın derlenmesi, imzalanması, dağıtılması, dağıtım sonrası testçilere haber verilmesi... Süreç gerçekten uzun ve külfetli.

İşin kötü tarafı şu: elinizin altında bir süper bilgisayar yoksa bu sadece efor değil, aynı zamanda vakit kaybı. Benim bir Android uygulamaya sürüm vermem yarım saatimi alıyordu. CI ile bu süre bana göre sıfıra iniyor. Pipeline tıkır tıkır işlerken unit testleri çalıştırıyor, build alıp imzalıyor, uygulamayı dağıtıyor ve dağıtırken mesajı bile ekliyor.

Bu yazı bir tutorial değil. Kurduğum yapıyı ve o yapıya gelirken verdiğim kararları anlatıyorum. "Nasıl yapılır" kısımlarını platform platform ayrı yazılara bırakıyorum; ilgili yerlerde belirteceğim.

## Temel soru: neye güveniyoruz?

Sır yönetimi konusunda okuduğum her şey bana aynı noktayı gösterdi: önce şu soruyu cevaplamak gerekiyor. Bu akışta kime, neye güveniyoruz?

Benim cevabım şöyle oldu:

- **Repoya güvenmiyoruz.** Repo herkese açıktır — en azından ekipteki herkese. Ve repo geçmişi kalıcıdır.
- **Geliştiricinin lokaline güvenmiyoruz.** Lokal makine kaybolur, formatlanır, işten ayrılan kişiyle birlikte gider.
- **GitLab'ın erişim kontrolüne güveniyoruz.** Zaten koda erişimi orada yönetiyoruz; sırları da aynı yerde yönetmek fazladan bir güven varsayımı eklemiyor.

Aşağıdaki kararların hepsi bu üç maddeden çıktı.

## Karar 1: İmza bilgileri, env değerleri ve google-services dosyaları repoda durmaz

Özellikle kurumsal ürünlerde ekip sürekli değişir ve bu değişime hazır olmak gerekir. Mevcut geliştirici işten ayrılıp yerine bir başkası geldiğinde akışta hiçbir aksaklık olmamalı.

"JKS dosyası kayboldu, önceki geliştiricinin lokalinde kalmış ve silinmiş" cümlesi gerçek bir kâbus. Bu cümlenin kurulabildiği her yapı zaten hatalıdır.

Bunun yerine hem dev hem prod sürümler dağıtılırken imzalama CI variables üzerinden yapılıyor. JKS dosyası hiçbir zaman geliştiricinin lokaline inmiyor; dolayısıyla orada kalması da mümkün değil. API key'lerin bulunduğu env dosyası ve dev konfigürasyonları da aynı şekilde CI variables içinden alınıyor.

Buradaki asıl kazanç güvenlik değil bence — süreklilik. Sır tek bir kişinin diskinde değil, projenin kendisinde duruyor.

## Karar 2: Dosyaları base64'leyip variable'a gömmek yerine Package Registry

Sır yönetiminde en yaygın çözüm dosyayı base64'leyip bir CI variable'ın içine koymak. İşe yarıyor, ama tek yönlü bir çözüm: pipeline o dosyaya ulaşabiliyor, geliştirici ulaşamıyor.

Oysa geliştiricinin de zaman zaman o dosyalara ihtiyacı oluyor. Bu yüzden dosyaları GitLab Package Registry içinde tuttum. Böylece ihtiyacı olan geliştirici, ihtiyacı olan dosyayı rahatlıkla alabiliyor — ve bunu bir başkasına "şu dosyayı bana atar mısın" diye yazmadan, kayıt altında olan bir yerden yapıyor.

Kabaca ayrım şu hâle geldi: **küçük ve metinsel olan sırlar CI variables'ta, dosya olanlar Package Registry'de.** Keystore'u registry'ye koyup pipeline içinde nasıl çektiğimi, Android imzalamayı anlattığım ayrı bir yazıda adım adım göstereceğim.

## Karar 3: Her commit test eder, ama merge'i insan başlatır

CI dosyasını şu şekilde organize ettim:

Her branch için geçerli olmak üzere, commit sonrası unit testler otomatik çalışıyor. Bir sorun varsa commit'i atan kişiye mail gidiyor. Sorun yoksa merge request aşamasına geçiliyor.

Bu kısım şimdilik manuel. Çünkü commit atmak, geliştirmenin bittiği anlamına gelmiyor. Gün içinde defalarca commit atıyorum ve bunların çoğu "bu iş bitti" demek değil, "bu ara kaydı kaybetmeyeyim" demek. Merge'i otomatikleştirmek, bu ikisini birbirine karıştırmak olurdu.

Bir tag yardımıyla bu kısmı da otomatikleştirmek mümkün. İleride yapabilirim. Şu an bilinçli olarak yapmıyorum — bu, çözemediğim bir eksik değil, ertelediğim bir karar.

Yazıyı yazarken fark ettim ki tag'li otomatikleştirmeyi hiç denememişim bile. Bu seri bittiğinde bir bakacağım.

## Karar 4: Prod sadece master'dan çıkar

Geliştirici sürüm vermek istediğinde, unit testi geçmiş bir pipeline'ın içinden hem iOS hem Android dağıtımını başlatabiliyor. İki platformun akışı dışarıdan aynı görünse de içeride hiç aynı değil; iOS tarafındaki sertifika ve provisioning profile işi kendi başına bir yazı konusu, onu ayrıca ele alacağım.

CI dosyasına koyduğum bir koşul sayesinde prod sürüm yalnızca master branch üzerinden dağıtılabiliyor. Bu tek satırlık koşul, "yanlışlıkla feature branch'ten prod çıkmak" diye bir olasılığı tamamen ortadan kaldırıyor.

Bu tip kuralları dokümana yazmak yerine pipeline'a yazmayı tercih ediyorum. Dokümandaki kural hatırlanmayı bekler; pipeline'daki kural kendini uygular.

## Karar 5: Dev sürüm, dev olduğunu bilir

Dev dağıtımı sırasında uygulamaya env üzerinden `type=Dev` argümanını geçiyorum. Uygulama bu argümanı görünce testçi arkadaşların işini kolaylaştıracak araçları aktif ediyor.

Bunun çözdüğü iki klasik sorun var:

- "Prod'a dev API ile çıkmışız."
- "Dev uygulamada testi kolaylaştıran araçlar yok."

İkisi de aynı kök sorundan çıkıyor: hangi yapının hangi ortama ait olduğunun build anında değil, sonradan elle belirlenmesi. Argümanı dağıtım aşamasında verdiğim için, çıkan paket kendi kimliğini taşıyor. Ortam bazlı yapılandırmayı ve hangi sırrın hangi ortamda görünür olduğunu ayrı bir yazıda daha detaylı anlatacağım.

## Karar 6: iOS build'i kendi Mac'imde koşan bir runner alır

Buraya kadar anlattığım her şeyin altında sessiz bir varsayım var: pipeline'ın koşacağı bir makine. Android tarafında bu bir sorun değil, şirket sunucuları Linux tabanlı ve iş görüyor. Ama iOS build'i macOS istiyor ve elimizde macOS koşan bir sunucu yok.

Seçenek ikiye iniyordu: bulutta bir macOS runner kiralamak ya da mevcut bir Mac'i runner'a dönüştürmek. İkincisini seçtim ve kendi cihazıma bir GitLab runner kurdum.

Runner'ı doğrudan makinenin üzerinde çalıştırmak istemedim. Bunun yerine **Tart** ile oluşturduğum, RAM ve CPU sınırları tanımlı bir sanal makinenin içinde koşuyor. İki kazancı var: pipeline gün içinde kullandığım makinenin kaynaklarını sömürmüyor ve build ortamı lokalimden yalıtılmış oluyor. Yani build, benim makinemde çalışıyor ama benim kurulumumla çalışmıyor.

Sonuçta commit attığımda GitLab yine gelip benim cihazımda build alıyor ve uygulamayı dağıtıyor. Akışın geri kalanı — testler, kurallar, sırlar — hiç değişmiyor; değişen tek şey o adımın nerede koştuğu.

Bu yapının bugünkü hâlinde açık bir zayıflık var: tek cihaz. Makinem kapalıysa iOS build'i de yok. Bu yüzden sıradaki adım aynı runner'ı birkaç Mac'te daha kurmak; hem yük dağılacak hem de cihazlardan biri kapalıyken pipeline çalışmaya devam edecek.

Bunu bir eksik olarak yazmam tesadüf değil. Yazının başında reddettiğim şey buydu zaten: tek bir kişinin makinesinde duran bağımlılık. Sır olarak kabul edilemez olan şey, donanım olarak da kabul edilemez.

## Sonuç

Kurduğum yapının özeti tek cümleyle şu: **sırlar projenin kendisinde durur, kurallar pipeline'da yazar, sürümün kimliği build anında belirlenir.**

Bu üçü oturduktan sonra sürüm vermek yarım saatlik bir iş olmaktan çıkıp bir butona basmaya dönüştü. Asıl kazanç kazanılan yarım saat de değil bence — sürüm vermenin artık dikkat gerektiren bir iş olmaması.
