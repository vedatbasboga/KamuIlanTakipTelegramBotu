# Kamu İlan Bildirim Botu — Başlangıç Rehberi (Senin için)

Bu klasördeki dosyalar, KPSS ile başvurulan kamu ilanlarını 6 kaynaktan takip edip yeni ilan çıktığında Telegram'dan bildirim atan botu **Claude Code ile aşama aşama** inşa etmen için hazırlandı. Bot GitHub Actions üzerinde cron ile çalışır; 7/24 açık bir sunucu gerekmez.

## Dosyalar

| Dosya | Kimin için | Ne işe yarar |
|---|---|---|
| `00-BASLA.md` | Sen | Bu rehber |
| `CLAUDE.md` | Claude Code | Proje bağlamı, mimari, kurallar. Repo köküne koy; Claude Code her oturumda otomatik okur |
| `docs/asamalar/01-iskelet-ve-altyapi.md` | Claude Code | Proje iskeleti, modeller, HTTP istemcisi, state, config |
| `docs/asamalar/02-telegram-bildirim.md` | İkiniz | Bot oluşturma (sen), bildirim modülü (Claude Code) |
| `docs/asamalar/03-kaynak-kesfi.md` | İkiniz | Her sitenin veriyi nereden çektiğini bulma (JSON API / HTML) |
| `docs/asamalar/04-parserlar.md` | Claude Code | Kaynak başına parser + fixture testleri |
| `docs/asamalar/05-filtre-dedup-orkestrasyon.md` | Claude Code | Filtreleme, tekrar önleme, ana akış, hata takibi |
| `docs/asamalar/06-github-actions.md` | İkiniz | Erişim testi, ana workflow, secrets, yayına alma |
| `docs/asamalar/07-saglamlastirma.md` | Claude Code | Opsiyonel: son başvuru hatırlatması, haftalık "yaşıyorum" mesajı vb. |

## Kurulum

1. Boş bir **private** GitHub reposu aç (ör. `kamu-ilan-bot`) ve klonla.
2. `CLAUDE.md` dosyasını repo köküne, `docs/` klasörünü olduğu gibi kopyala.
3. Repo klasöründe Claude Code'u başlat.
4. Her aşama için şu kalıpla ilerle:

   ```
   docs/asamalar/01-iskelet-ve-altyapi.md dosyasını oku ve uygula.
   Bitince kabul kriterlerini tek tek doğrula ve docs/ILERLEME.md'yi güncelle.
   ```

5. Bir aşamanın kabul kriterleri sağlanmadan sonrakine geçme. Her aşama sonunda commit at.

## Senin elle yapman gerekenler (Claude Code yapamaz)

- **Aşama 2:** BotFather'dan bot oluşturmak, bota bir mesaj atıp `chat_id` almak.
- **Aşama 3:** Claude Code bir sitenin API'sini bulamazsa, tarayıcıda DevTools → Network sekmesinden ilgili isteği "Copy as cURL" ile kopyalayıp ona yapıştırmak.
- **Aşama 6:** GitHub'da `TELEGRAM_BOT_TOKEN` ve `TELEGRAM_CHAT_ID` secret'larını eklemek, workflow'u ilk kez elle tetiklemek.
- **`config.yaml`:** Kendi filtrelerini (öğrenim düzeyi, bölüm, puan türü, şehir) yazmak.

## Önemli notlar

- **Maliyet:** Private repoda GitHub Actions'ın aylık ücretsiz dakika kotası var. Varsayılan plan (TR saatiyle 07:00–23:30 arası her 30 dakikada bir) aylık yaklaşık 1000 dakika eder ve kota içinde kalır. Daha sık çalıştırmak istersen önce kotanı kontrol et.
- **Yurt dışı IP riski:** GitHub'ın runner'ları yurt dışında çalışır ve bazı `.gov.tr` siteleri yabancı IP'leri engelleyebilir. Aşama 6'nın ilk adımı bunu test eder. Engellenen kaynak çıkarsa çözüm, kendi bilgisayarında **self-hosted runner** çalıştırmak (yapı aynı kalır, sadece `runs-on` değişir).
- **Nezaket:** Bot her kaynağa her çalışmada az sayıda istek atar. Daha sık tarama gereksiz, çünkü ilanların başvuru süreleri günlerle ölçülür.
