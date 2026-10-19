# Aşama 3 — Kaynak Keşfi

## Amaç
Altı kaynağın her biri için ilan listesinin **gerçekte nereden ve hangi biçimde** geldiğini bulmak, kaydetmek ve test için örnek yanıtları (fixture) toplamak. Parser yazmak bu aşamada yok.

## Neden ayrı bir aşama?
Modern siteler listeyi çoğu zaman sayfa yüklendikten sonra bir JSON API'den çeker. HTML'i kazımak yerine o API'yi kullanmak daha sağlam, daha hızlı ve filtrelemesi daha kolay olur. Tahmin edilen URL'lerle parser yazmak boşa iş demektir.

## Yöntem (her kaynak için, sırayla)

1. **Ana sayfayı çek** (`httpx`, proje User-Agent'ıyla) ve ham HTML'i `scratch/<kaynak>/index.html` olarak kaydet (`scratch/` git'e girmez, `.gitignore`'a ekle).
2. **İlanlar HTML'in içinde mi?** İlan başlıkları sayfanın ham HTML'inde görünüyorsa → HTML kaynağı.
3. **Değilse API ara:**
   - HTML içindeki `<script>` dosyalarını çek, içinde `/api/`, `fetch(`, `axios`, `.json`, `ilan`, `Ilan`, `list`, `search` geçen yerleri ara.
   - Next.js/Nuxt ise `__NEXT_DATA__` / `__NUXT__` gibi gömülü JSON bloklarına bak.
   - Bulunan aday uç noktayı dene; yanıtın yapısını incele (ID alanı, başlık, kurum, tarih, sayfalama).
4. **RSS/Atom var mı?** `<link rel="alternate" type="application/rss+xml">` ve `/rss`, `/feed` yollarını dene. Varsa çoğu zaman en kolay yoldur.
5. **🧑 KULLANICI — bulunamazsa:** Claude Code dur ve kullanıcıdan şunu iste:
   > Tarayıcıda {site}'yi aç → F12 → Network → "Fetch/XHR" filtresi → sayfayı yenile / ilan listesine git → ilan verisini içeren isteğe sağ tık → "Copy as cURL (bash)" → buraya yapıştır.

   Yapıştırılan cURL'den **çerez/oturum başlıklarını çıkar**; uç nokta onlarsız çalışmalı. Çalışmıyorsa not et ve kullanıcıya sor.
6. **Bot koruması / engel:** 403, Cloudflare/challenge sayfası, boş yanıt gibi durumları not et. Headless tarayıcıya geçmeden önce kullanıcıya sor (CLAUDE.md kuralı).

## Kaynaklara özel ipuçları (doğrulanmamış, sadece başlangıç noktası)

- **kamuilan_sbb:** Ana liste sayfası; muhtemelen bir API'den kurum, öğrenim düzeyi ve puan türü alanlarıyla birlikte geliyor. En değerli kaynak, en zengin alanlar burada olabilir.
- **ilan_gov:** "Personel Alımı" kategorisi var. Sitenin arama sayfası büyük ihtimalle bir JSON API kullanıyor; kategori ve il filtresinin parametrelerini bul.
- **kariyer_kapisi:** Başvuru e-Devlet ile yapılıyor, ama ilan listesinin girişsiz görünür olması gerekir. Girişsiz liste yoksa kaynağı `false` yapıp not düş.
- **iskur:** "Kamu Memur Alımı" ilanları ayrı bir sayfa/başlık altında; `esube.iskur.gov.tr` tarafını da kontrol et.
- **resmi_gazete:** Günlük sayı yapısı. O günün "İlan Bölümü" sayfasını bul (URL'de tarih kalıbı olabilir, ör. `YYYYMMDD`). Personel ilanlarını başlıktan ayıklamak gerekecek (ör. "personel alım", "öğretim üyesi" gibi bölüm başlıkları). Bildirim birimi "ilan bölümündeki tek bir personel ilanı" olmalı.
- **yerel_yonetimler:** Belediye personel ilanları; liste sayfası ve sayfalama yapısını incele.

## Çıktılar

### `docs/kaynaklar.md`
Her kaynak için şu şablon:

```markdown
## kamuilan_sbb
- Yöntem: JSON API | HTML | RSS
- Liste uç noktası: GET https://...  (parametreler: ...)
- Sayfalama: ...
- İlan ID alanı: ... (yoksa: URL'den türetilecek)
- Mevcut alanlar: başlık ✓, kurum ✓, yayın tarihi ✓, son başvuru ✗, öğrenim ✓, KPSS ✗, il ✓, kadro sayısı ✗
- Detay sayfası gerekiyor mu: Evet/Hayır (gerekiyorsa hangi alan için)
- Gerekli başlıklar: ...
- Sorunlar: (403, SSL, rate limit vb.)
- Fixture: tests/fixtures/kamuilan_sbb/list_page1.json
```

### Fixture'lar
- Her kaynak için en az 1 liste yanıtı `tests/fixtures/<kaynak>/` altına kaydedilir.
- Detay sayfası gerekiyorsa en az 2 detay örneği.
- Fixture'larda kişisel veri olmamalı (zaten ilan verisi kamuya açık, yine de kontrol et).
- Büyük dosyaları kırp (ör. ilk 20 ilan), ama yapıyı bozma.

## Kabul kriterleri
- [ ] `docs/kaynaklar.md`'de 6 kaynağın hepsi için bölüm var (kullanılamayan kaynaklar için "kullanılamıyor + neden").
- [ ] Kullanılabilir her kaynağın fixture'ı repoda.
- [ ] Engelli/sorunlu kaynaklar `config.yaml`'da `false` ve `ILERLEME.md`'de not edilmiş.
- [ ] 🧑 Kullanıcı `docs/kaynaklar.md`'yi gözden geçirdi.
