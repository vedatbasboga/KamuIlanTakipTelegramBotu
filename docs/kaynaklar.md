# Kaynaklar — teknik keşif notları (Aşama 3)

Keşif tarihi: 2026-10-19, yerel makineden (Türkiye IP'si).

## GitHub runner'larından erişim (Aşama 6.1, 2026-10-19)

`Erişim testi` workflow'u, `ubuntu-latest` (yurt dışı IP):

| Kaynak | Sonuç | Karar |
|---|---|---|
| `kamuilan_sbb` | ❌ HTTP 403, "access denied" (2 KB) | Bilgisayarda (self-hosted) |
| `ilan_gov` | ✅ 200, 20 kayıt | GitHub |
| `kariyer_kapisi` | ❌ ConnectTimeout (25 sn) | Bilgisayarda (self-hosted) |
| `iskur` | ✅ 200, il listesi 17 + Ankara 20 kayıt | GitHub |
| `yerel_yonetimler` | ❌ ConnectTimeout (25 sn) | Bilgisayarda (self-hosted) |
| `resmi_gazete` (kapalı) | ✅ ana sayfa 200 (5 sn) | Kapalı kalıyor; ilan sayfaları test edilmedi |

→ Kullanıcı kararı: **karma** çalışma. `config.yaml → runners` ile ayrılır; GitHub tarafı
`data/state.json`, bilgisayar tarafı `data/state-local.json` kullanır (aynı dosyaya iki yerden
yazılmaz, git çakışması olmaz).

Özet:

| Kaynak | Yöntem | Kararlı ID | İstek/çalışma | Durum |
|---|---|---|---|---|
| `kamuilan_sbb` | HTML (ASP.NET WebForms) | ❌ yok → bileşik anahtar | 1 (+ isteğe bağlı kategori POST'ları) | ✅ Kullanılabilir |
| `ilan_gov` | JSON API (ABP) | ✅ `id` | 2 liste + ≤20 detay | ✅ Kullanılabilir (özel başlıklar + ara sertifika) |
| `kariyer_kapisi` | JSON API | ✅ `guid` | 1 | ✅ Kullanılabilir (en temiz kaynak) |
| `iskur` | HTML, il bazında | ✅ medya ID | 1 + ilan olan il sayısı (~17) | ✅ Kullanılabilir (ağır) |
| `resmi_gazete` | HTML (günlük sayı) | ? | ? | ⛔ Kapalı — ilan sayfaları güvenilmez yanıt veriyor; içerik ilan.gov.tr'de var |
| `yerel_yonetimler` | HTML | ✅ URL sonundaki sayı | 1 | ✅ Kullanılabilir |

---

## kamuilan_sbb
- **Yöntem:** HTML. İlanlar ana sayfanın ham HTML'inde, `ul#nav2` içinde (`TÜM İLANLAR`, ~98 ilan).
- **Liste uç noktası:** `GET https://kamuilan.sbb.gov.tr/`
- **Sayfalama:** Yok; tüm aktif ilanlar tek sayfada.
- **Satır yapısı:** `ul#nav2 > li` her biri bir yayın günü (`time.cbp_tmtime` → `h4` gün, `h3` ay).
  İçinde her ilan bir `a.xx`:
  - `img.limg2[src]` → `./ilan_dosyalar/logolar/<kurumLogoId>.png#19.10.2026 00:00:00`.
    ⚠️ Fragment yayın tarihi **değil**: tüm satırlarda o günün tarihi (önbellek kırıcı), her gün
    değişir → ID'ye girmemeli. Belediyelerde logo `BEL2.png` ve fragment yok.
  - Yayın günü: üstteki `li > time` (`h4` gün, `h3` ay); yıl yok → bugüne göre çıkarılır.
  - `p.alt_p1` → kurum adı
  - `p.alt_p2` → başlık; içindeki `em` → başvuru aralığı `( 19 Ekim - 2 Kasım)` (yıl yok;
    bitiş ayı başlangıçtan küçükse sonraki yıl)
- **İlan ID alanı:** ❌ **Kararlı ID yok.** Link `ilanDetay.aspx?kod=<şifreli>` her istekte farklı
  (rastgele IV ile şifrelenmiş; aynı ilan iki istekte farklı `kod`). Detay PDF'inin
  `Content-Disposition` dosya adı (ör. `2026-23-221-....pdf`) kararlı ama ilan başına ayrı istek
  gerektiriyor.
  → **Karar:** `sha1(logoId | yayın günü (zaman çizelgesi) | normalize(kurum) |
  normalize(başlık))[:16]`. 98 ilanda 98 benzersiz; iki ayrı çekimde ve fragment'ı değişmiş
  "ertesi gün" senaryosunda aynı ID'ler üretildiği test edildi. **CLAUDE.md kural 5'ten sapma:**
  başlık ID'ye giriyor; başlık düzeltilirse ilan bir kez daha bildirilir (kaçırmaktan iyidir).
- **Mevcut alanlar:** başlık ✓, kurum ✓, yayın tarihi ✓, son başvuru ✓ (gün, saat yok),
  öğrenim ✗, KPSS ✗, il ✗, kadro sayısı ~ (başlıktan: "153 SÖZLEŞMELİ PERSONEL ALACAK").
- **Kategori:** Sol menüdeki düğmeler ASP.NET postback'i (`POST /` + `__VIEWSTATE`,
  `__EVENTVALIDATION`, `ButtonN=<değer>`). Çalışıyor; ör. `Button2=B Grubu Memur` → 17 ilan.
  Kategoriler: A Grubu Memur (Button1), B Grubu Memur (Button2), Kariyer Sözleşmeli (Button21),
  4/B Sözleşmeli (Button16), KİT Sözleşmeli (Button17), Kurumsal Sözleşmeli (Button18),
  Öğretim Üyesi (19), Öğretim Görevlisi (20), Araştırma Görevlisi (23), işçi türleri (22,7,8,9,11),
  Askeri (13), Yargı (6). Her POST ~90 KB ViewState gönderir, ~185 KB yanıt alır.
  → Aşama 4'te karar: Sadece `GET /` (1 istek) mi, yoksa KPSS'yle ilgili 6 kategori için POST
  yapıp ilanlara `summary="Kategori: B Grubu Memur"` gibi etiket mi eklensin?
- **Detay sayfası:** `ilanDetay.aspx?kod=...` → doğrudan **PDF** döner. **`Referer:
  https://kamuilan.sbb.gov.tr/` başlığı zorunlu**, yoksa 404 sayfası. Aynı oturum (çerez)
  gerekmiyor ama `kod` o anki liste yanıtından alınmalı. PDF'ten öğrenim/KPSS çıkarmak ek
  bağımlılık (`pypdf`) ister → kullanıcıya sorulacak; şimdilik gerek yok.
- **Kullanıcıya giden URL:** Test edildi: `kod` linki başka bir oturumda da çalışıyor ama sadece
  `Referer` ile; Referer'sız 404 sayfası dönüyor. Telegram'dan tıklanan link Referer göndermez →
  mesajdaki link `https://kamuilan.sbb.gov.tr/` olmalı (kullanıcı ilanı listede bulur).
- **Gerekli başlıklar:** Liste için yok. Detay için `Referer`.
- **Sorunlar:** Yok (hızlı, 0.3 sn).
- **Fixture:** `tests/fixtures/kamuilan_sbb/list.html` (98 ilan, ViewState kırpıldı),
  `tests/fixtures/kamuilan_sbb/kategori_b_grubu.html` (17 ilan).

## ilan_gov
- **Yöntem:** JSON API (Angular SPA, ASP.NET Boilerplate). API kökü
  `https://www.ilan.gov.tr/api` (`/assets/appconfig.production.json`).
- **Liste uç noktası:** `POST https://www.ilan.gov.tr/api/api/services/app/Ad/AdsByFilter`
  gövde `{"keys": {"txv": ["8"]}, "skipCount": 0, "maxResultCount": 20}`
  (`txv=8` = "Kamu-Akademik Personel" kategorisi; boş `keys` tüm ilan türlerini döndürür: emlak,
  icra, ihale...).
- **Gerekli başlıklar:** 🔑 `X-Request-Origin: IGT-UI` **ve** `X-Requested-With: XMLHttpRequest`
  (ikisi birlikte; biri eksikse tüm API boş gövdeli 403). Ayrıca
  `Content-Type: application/json-patch+json`. Tarayıcı UA'sı, çerez, Origin/Referer **gerekmiyor**
  (kullanıcının "Copy as cURL" çıktısından eleme ile bulundu; projenin kendi UA'sıyla çalışıyor).
- **Sayfalama:** `skipCount` / `maxResultCount`; sunucu en fazla **20** döndürüyor (50 istenince
  20). Sıralama yayın tarihine göre yeniden eskiye (kesin değil; aynı gün içinde karışık).
  Kategoride ~134 aktif ilan. Çalışma başına 2 sayfa (40 ilan) yeterli.
- **İlan ID alanı:** ✅ `id` (sayısal metin, ör. `"2261370"`). Ayrıca `adNo` (ör. `DPB845523`).
- **Liste alanları:** `title`, `advertiserName` (kurum), `addressCityName` (il, büyük harf),
  `publishStartDate` (UTC, `Z`), `urlStr` (göreli link), `values[key=Kategori]` (alt kategori:
  "KPSS B ve Mahalli İdareler Kadro Alımları", "Sözleşmeli Personel ve 4/B Alımları",
  "Öğretim Üyesi Alımları ...", "Sürekli İşçi Alımı" ...), `adTypeFilters` ("Resmî Gazete Yayım
  Tarihi", nadiren "Son başvuru Tarihi"), `adSourceCode` (`DPB` Devlet Personel Başkanlığı,
  `YOK`, `ILN`).
  başlık ✓, kurum ✓, yayın tarihi ✓, il ✓, **kategori ✓**, son başvuru ~ (nadiren),
  öğrenim/KPSS → detaydan.
- **Detay:** `GET https://www.ilan.gov.tr/api/api/services/app/AdDetail/GetAdDetail?id=<id>`
  (aynı iki başlık) → `result.content` ilanın **tam metni (HTML)**. Metinden `normalize_kpss` /
  `normalize_education` ile KPSS ve öğrenim çıkarılabiliyor (test: bilişim ilanı → `{P3}`,
  `{lisans}`). Sadece yeni ilanlar için `enrich` (çalışma başına ≤20 istek).
- **Kullanıcıya giden URL:** `https://www.ilan.gov.tr` + `urlStr`.
- **Not:** ilan.gov.tr, Resmî Gazete'de yayımlanan personel ilanlarını da içeriyor
  ("Resmî Gazete Yayım Tarihi" alanı, kaynak `DPB`/`YOK`) → `resmi_gazete` kaynağıyla büyük ölçüde
  örtüşür.
- **SSL:** Sunucu ara sertifikayı göndermiyor (`GeoTrust TLS RSA CA G1`, DigiCert Global Root G2
  altında). Tarayıcılar AIA ile tamamlıyor; Python/OpenSSL "unable to get local issuer
  certificate" veriyor. **Çözüm:** `verify=False` değil; ara sertifika repoya PEM olarak eklenir,
  `certifi` + bu PEM ile `ssl.SSLContext` kurulur (doğrulama açık kalır; test edildi).
  Ara sertifika SHA-256:
  `C0:6E:30:7F:7C:FC:1D:32:FA:72:A4:C0:33:C8:7B:90:01:9A:F2:16:F0:77:5D:64:97:8A:2E:CA:6C:8A:23:0E`,
  geçerlilik 2027-11-02. Sunucu sertifikası 2026-11-29'da bitiyor; yenilenince ara sertifika
  değişebilir → SSL hatası sağlık uyarısı olarak görünür.
- **Diğer:** RSS yok; `robots.txt`'deki sitemap'ler 404.
- **Fixture:** `tests/fixtures/ilan_gov/list_personel_page1.json` (20 ilan, `cityCounts`
  kırpıldı), `tests/fixtures/ilan_gov/detail_2261370.json`, `detail_2261004.json`.

## kariyer_kapisi
- **Gerçek adres:** `https://kariyerkapisi.gov.tr/isealim` (`kariyerkapisi.cbiko.gov.tr` DNS'te
  yok).
- **Yöntem:** JSON API, girişsiz.
- **Liste uç noktası:** `POST https://api.kariyerkapisi.gov.tr/api/ilan/SearchIlanPublic`
  gövde `{"krM_ID": 0, "searchText": "", "il": "0", "ilanTuru": "0"}` → ilan dizisi (~31).
  (Alternatif: `.../ilan/GetIseAlimPage` aynı gövdeyle; ilan türü, şehir, kurum listelerini de
  döner.)
- **Sayfalama:** Yok, tüm aktif ilanlar tek yanıtta. Süresi geçmiş ilanlar da dönebilir; site
  istemci tarafında `bitTarih < şimdi` olanları gizliyor → parser da gizlemeli.
- **İlan ID alanı:** ✅ `guid` (UUID).
- **Alanlar:** `kurumAdi`, `birimAdi`, `ilanBaslik`, `ilanTuru` (ör. "B Grubu Memur",
  "Sözleşmeli Personel İlanları", "Öğretim Üyesi"; bazen sonda virgül), `ilanTipi` (1 = Kariyer
  Kapısı'ndan başvuru, 2 = dış link), `basTarih`, `bitTarih` (yerel saat, tz bilgisi yok →
  Europe/Istanbul), `basvuruLinki`, `sonDurumu`.
  başlık ✓, kurum ✓, yayın/başlangıç ✓, son başvuru ✓ (saatli), öğrenim ✗, KPSS ✗, il ✗,
  kadro ✗, **kategori ✓**.
- **Kullanıcıya giden URL:** `ilanTipi == 1` → `https://kariyerkapisi.gov.tr/isealim/IlanDetay?i={guid}`,
  `ilanTipi == 2` → `basvuruLinki`.
- **Detay sayfası gerekiyor mu:** Hayır. (Detay sayfası botun UA'sına WAF 406 dönüyor; zaten
  e-Devlet girişi isteyen başvuru sayfası.)
- **Gerekli başlıklar:** Yok (Origin/Referer gönderildi ama şart olup olmadığı önemsiz).
- **Fixture:** `tests/fixtures/kariyer_kapisi/search_ilan_public.json` (ilk 20 ilan).

## iskur
- **Yöntem:** HTML, il bazında sunucu tarafında oluşturulmuş tablo.
- **Liste uç noktası:** `GET https://www.iskur.gov.tr/ilanlar/kamu-memur-alim-ilanlari/?il=<İl Adı>`
  (ör. `?il=Ankara`, `?il=İstanbul`). Parametresiz sayfada liste yok; "tüm iller" seçeneği
  çalışmıyor.
- **İl listesi:** Parametresiz sayfadaki `select#city-dropdown option` → metin "Ankara (20)";
  sayı olan iller ilan içerir (keşif günü 17 il, toplam ~45 ilan, 20'si Ankara).
  → Çalışma başına 1 + ilan olan il sayısı istek. Sayfalar ~600 KB (%60'ı SVG Türkiye haritası).
- **Satır yapısı:** `tr.clickable-row[data-file-url]`: 1. hücre son başvuru `23.10.2026 17:00`,
  2. hücre başlık ("Ankara Pursaklar Belediyesi Zabıta Memuru Alım İlanı 23.10.2026").
- **İlan ID alanı:** ✅ `data-file-url` = `/medya/<medyaId>/<dosya>.pdf` → `medyaId`
  (ör. `tfnpxax1`, Umbraco medya ID'si).
- **Alanlar:** başlık ✓, kurum ~ (başlığın içinde), son başvuru ✓ (saatli), il ✓ (sorgulanan il),
  öğrenim ✗, KPSS ✗, kadro ✗, yayın tarihi ✗.
- **Detay:** PDF (`https://www.iskur.gov.tr/medya/...pdf`). Gerek yok.
- **Not:** İlanların büyük kısmı `kamuilan_sbb` ile örtüşüyor (kaynaklar arası tekrar önleme
  Aşama 5'te). "Kurumdışı Kamu İşçi Alım İlanları" KPSS'siz işçi alımı → kapsam dışı.
- **Fixture:** `tests/fixtures/iskur/memur_index.html` (il listesi),
  `tests/fixtures/iskur/memur_ankara.html` (Ankara, 20 ilan). Büyük SVG'ler kırpıldı.

## resmi_gazete
- **Yöntem:** HTML, günlük sayı.
- **Günün ilan bölümü:** Ana sayfada `https://www.resmigazete.gov.tr/ilanlar/eskiilanlar/YYYY/MM/YYYYMMDD-N.htm`
  linkleri: `-2` Yargı İlânları, `-3` Artırma/Eksiltme/İhale, `-4` Çeşitli İlânlar, `-5` ...
  (numaralar günden güne değişebilir; ana sayfadaki link metninden seçilmeli).
  Personel/öğretim üyesi alım ilanları genelde "Çeşitli İlânlar" altında.
- **Sorunlar:** ⚠️ Site yoğun istekte **IP'yi geçici olarak engelliyor**: istek reddedilmiyor,
  bağlantı yanıtsız kalıp zaman aşımına düşüyor. İlk ~10 istek sorunsuzdu, kısa sürede ~20
  istekten sonra ana sayfa dahil tüm istekler yanıtsız kaldı. Engel UA'dan bağımsız (aynı UA
  bir dakika arayla hem geçti hem takıldı). Başka siteler aynı anda erişilebilirdi.
  → Bot çalışma başına en fazla 2 istek atmalı (ana sayfa + Çeşitli İlânlar), kısa timeout.
- **Ek gözlem (2026-10-19, ~25 dk sonra):** Ana sayfa tekrar açıldı (0.5 sn) ama ilan sayfası
  (`...-4.htm`) yine 25 sn yanıtsız kaldı. `/ilanlar/` ve `/eskiler/` altındaki sayfalar,
  ana sayfaya göre çok daha seçici engelleniyor.
- **Karar (öneri):** **Kullanılamıyor → `config.yaml`'da `false`.** Gerekçe: (1) ilan sayfalarına
  erişim güvenilmez; (2) ilan.gov.tr, Resmî Gazete'de yayımlanan personel ilanlarını zaten
  içeriyor (`adTypeFilters` → "Resmî Gazete Yayım Tarihi", kaynak `DPB`/`YOK`), yani bildirim
  kaybı beklenmiyor. Gerekirse ileride, çalışma başına 2 istekle (ana sayfa + Çeşitli İlânlar)
  yeniden denenebilir; GitHub runner IP'lerinde davranış farklı olabilir (Aşama 6.1).
- **Fixture:** Yok.

## yerel_yonetimler
- **Yöntem:** HTML.
- **Liste uç noktası:** `GET https://yerelyonetimler.csb.gov.tr/duyurular`
- **Sayfalama:** `/duyurular/2`, `/duyurular/3` ...; sayfa başına 12 duyuru, ~10 günlük ilan.
  Çalışma başına 1 sayfa yeterli (30 dk aralıkla 12'den fazla yeni duyuru beklenmez).
- **Satır yapısı:** `a.duyurular-wrapper[href]`, `.date span` ("16 Ekim 2026"), `.info p` (başlık,
  uzunsa sonunda "..." ile kesilmiş).
- **İlan ID alanı:** ✅ URL'nin sonundaki sayı (`...-duyuru-478289` → `478289`).
- **Alanlar:** başlık ✓ (kesik olabilir), yayın tarihi ✓, il ✓ (başlıkta "İZMİR İLİ ..."
  ya da "RİZE BELEDİYESİ"), kurum ~ (başlıktan), son başvuru ✗, öğrenim ✗, KPSS ✗, kadro ✗.
- **İçerik:** Sadece belediye personel ilanları değil; "DÜZELTME İLANI", "İPTAL İLANI" da var
  (kullanıcı `exclude_keywords` ile eleyebilir).
- **Detay sayfası:** Sadece ilan metni .docx linki; gerek yok.
- **Fixture:** `tests/fixtures/yerel_yonetimler/duyurular_page1.html` (12 duyuru).
