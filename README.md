# Kamu İlan Takip Botu

KPSS ile başvurulan kamu personel ilanlarını resmi kaynaklardan takip eder, yeni ilan çıktığında
Telegram'dan bildirim gönderir. GitHub Actions üzerinde zamanlanmış olarak çalışır; 7/24 açık bir
sunucu gerekmez.

## Kaynaklar

| Kaynak | Ne alınıyor | Sıklık |
|---|---|---|
| [kamuilan.sbb.gov.tr](https://kamuilan.sbb.gov.tr) | Cumhurbaşkanlığı SBB kamu personel ilanları | 30 dk |
| [ilan.gov.tr](https://www.ilan.gov.tr) | Basın İlan Kurumu "Kamu-Akademik Personel" (Resmî Gazete ilanları dahil) | 30 dk |
| [kariyerkapisi.gov.tr](https://kariyerkapisi.gov.tr/isealim) | Kariyer Kapısı aktif ilanlar | 30 dk |
| [iskur.gov.tr](https://www.iskur.gov.tr/ilanlar/kamu-memur-alim-ilanlari/) | İŞKUR kamu memur alım ilanları | 3 saat |
| [yerelyonetimler.csb.gov.tr](https://yerelyonetimler.csb.gov.tr/duyurular) | Belediye personel alım duyuruları | 30 dk |
| resmigazete.gov.tr | **Kapalı** — erişim güvenilmez, içerik ilan.gov.tr'de | — |

Teknik ayrıntılar: [docs/kaynaklar.md](docs/kaynaklar.md).

## Nasıl çalışır

1. GitHub Actions, TR saatiyle 07:07–23:37 arası her 30 dakikada bir `python -m ilanbot` çalıştırır.
2. Bot her kaynaktan ilan listesini çeker, daha önce görmediği ilanları bulur.
3. Filtrelerden (`config.yaml`) geçenleri Telegram'a gönderir. Aynı ilan birden çok kaynakta
   varsa tek mesaj gider ("ayrıca: ..." notuyla). Çok sayıda yeni ilan varsa tek özet mesaj gider.
4. Görülen ilanlar `data/state.json`'a yazılır ve workflow bu dosyayı repoya commit'ler.

Bir kaynak ilk kez çalıştığında mevcut ilanlar **bildirim gönderilmeden** kaydedilir; böylece ilk
çalışmada yüzlerce mesaj gelmez.

## Kurulum

### 1. Telegram botu
1. Telegram'da [@BotFather](https://t.me/BotFather) → `/newbot` → token'ı al.
2. Bota `/start` yaz. `https://api.telegram.org/bot<TOKEN>/getUpdates` adresinden `chat.id`'yi al.
   - **Kanal kullanmak için:** Herkese açık bir kanal aç, botu kanala **yönetici** (mesaj gönderme
     izniyle) ekle; chat_id olarak `@kanal_adi` kullan.

### 2. GitHub
1. Repo → **Settings → Secrets and variables → Actions → New repository secret**:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
2. **Settings → Actions → General → Workflow permissions → Read and write permissions**.
3. **Actions → "Erişim testi" → Run workflow**: kaynaklara GitHub sunucularından erişilebiliyor mu?
4. **Actions → "İlan kontrolü" → Run workflow**: önce `dry_run` işaretli, log'u kontrol et; sonra
   işaretsiz.

### 3. Yerelde çalıştırma (isteğe bağlı)
```bash
python -m venv .venv && .venv/Scripts/activate      # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
# .env dosyası (git'e girmez):
#   TELEGRAM_BOT_TOKEN=...
#   TELEGRAM_CHAT_ID=...
PYTHONPATH=src python -m ilanbot --test-telegram      # bağlantı testi
PYTHONPATH=src python -m ilanbot --dry-run -v         # göndermeden konsola yaz
PYTHONPATH=src python -m ilanbot --source ilan_gov --dry-run
pytest -q
```

## Ayarlar (`config.yaml`)

| Ayar | Açıklama |
|---|---|
| `sources.<kaynak>` | Kaynağı aç/kapa |
| `filters.education_levels` | `ortaogretim`, `onlisans`, `lisans`, `yuksek_lisans`, `doktora`. Boş = filtre yok |
| `filters.kpss_types` | `P3`, `P93`, `P94` ... Boş = filtre yok |
| `filters.locations` | İl adları. "Türkiye geneli" ilanlar her il filtresiyle eşleşir |
| `filters.include_keywords` | Başlık/kurum/özette en az biri geçmeli |
| `filters.exclude_keywords` | Biri geçerse ilan her zaman elenir (ör. `"öğretim üyesi"`, `"işçi"`) |
| `filters.filtre_belirsizse_gonder` | İlanda öğrenim/KPSS/il bilgisi yoksa yine de gönder (önerilen: `true`) |
| `notify.max_messages_per_run` | Bu sayı aşılırsa tek özet mesaj |
| `state.prune_after_days` | Bu kadar günden eski "görüldü" kayıtları silinir |

Not: Filtreden geçmeyen ilanlar da "görüldü" sayılır. Filtreyi sonradan değiştirirsen eski ilanlar
geriye dönük gelmez.

## Sorun giderme

- **"⚠️ ... art arda 6 kez okunamadı" mesajı:** Site kapalı, yapısı değişmiş ya da GitHub IP'lerini
  engelliyor olabilir. Actions log'unda `[kaynak] HATA: ...` satırına bak. Düzelince
  "✅ ... tekrar çalışıyor" mesajı gelir.
- **Hiç bildirim gelmiyor:** Actions → "İlan kontrolü" log'unda `Toplam: N bildirim` satırına bak.
  Secrets doğru mu? `--test-telegram` yerelde çalışıyor mu?
- **Bir kaynak yurt dışı IP'yi engelliyor:** O kaynağı `config.yaml`'da kapat ya da kendi
  bilgisayarında [self-hosted runner](https://docs.github.com/actions/hosting-your-own-runners)
  kurup `runs-on: self-hosted` kullan (bilgisayar kapalıyken çalışmaz).
- **Belirli bir ilanı tekrar almak (test):** `data/state.json` → `seen` içinden o ilanın satırını
  sil, commit'le; bir sonraki çalışmada (filtreye uyuyorsa) tekrar gelir.

## GitHub Actions notları

- **60 gün kuralı:** GitHub, 60 gün commit almayan repolarda zamanlanmış workflow'ları durdurur.
  State commit'leri bunu çoğunlukla önler; uzun süre hiç yeni ilan çıkmazsa Actions sekmesinden
  workflow'u yeniden etkinleştir.
- **Dakika kotası:** Her çalışma ~30–60 sn. Günde ~34 çalışma ≈ ayda ~1000 dk. Public repolarda
  sınırsız; private repoda ücretsiz kota içinde kalır (Settings → Billing'den izlenebilir).
- **Gecikme:** GitHub cron'u yoğun saatlerde birkaç dakika gecikebilir; ilan takibi için önemsiz.

## Geliştirme

- Kod İngilizce, mesajlar/loglar/dokümantasyon Türkçe.
- Testler ağa çıkmaz; `tests/fixtures/` altındaki kayıtlı yanıtlarla çalışır.
- Proje kuralları: [CLAUDE.md](CLAUDE.md). İlerleme: [docs/ILERLEME.md](docs/ILERLEME.md).
