# Kamu İlan Takip Botu

KPSS ile başvurulan kamu personel ilanlarını resmi kaynaklardan takip eder, yeni ilan çıktığında
Telegram'dan bildirim gönderir. GitHub Actions üzerinde zamanlanmış olarak çalışır; 7/24 açık bir
sunucu gerekmez.

## Kaynaklar

| Kaynak | Ne alınıyor | Sıklık | Nerede çalışır |
|---|---|---|---|
| [kamuilan.sbb.gov.tr](https://kamuilan.sbb.gov.tr) | Cumhurbaşkanlığı SBB kamu personel ilanları | 30 dk | Bilgisayar |
| [ilan.gov.tr](https://www.ilan.gov.tr) | Basın İlan Kurumu "Kamu-Akademik Personel" (Resmî Gazete ilanları dahil) | 30 dk | GitHub |
| [kariyerkapisi.gov.tr](https://kariyerkapisi.gov.tr/isealim) | Kariyer Kapısı aktif ilanlar | 30 dk | Bilgisayar |
| [iskur.gov.tr](https://www.iskur.gov.tr/ilanlar/kamu-memur-alim-ilanlari/) | İŞKUR kamu memur alım ilanları | 3 saat | GitHub |
| [yerelyonetimler.csb.gov.tr](https://yerelyonetimler.csb.gov.tr/duyurular) | Belediye personel alım duyuruları | 30 dk | Bilgisayar |
| resmigazete.gov.tr | **Kapalı** — erişim güvenilmez, içerik ilan.gov.tr'de | — | — |

**Neden iki yer?** GitHub'ın sunucuları yurt dışında; kamuilan, Kariyer Kapısı ve Yerel Yönetimler
yabancı IP'leri engelliyor. Bu üç kaynak, bir Windows bilgisayardaki **self-hosted runner** ile
Türkiye IP'sinden çalışır (bilgisayar kapalıyken bu üçü taranmaz, açılınca kaldığı yerden devam
eder). Dağılım `config.yaml → runners` ile değiştirilebilir.

Teknik ayrıntılar: [docs/kaynaklar.md](docs/kaynaklar.md).

## Nasıl çalışır

1. GitHub Actions, TR saatiyle 07:07–23:37 arası her 30 dakikada bir `python -m ilanbot --runner
   github` (GitHub sunucusunda) ve :22/:52'de `--runner local` (bilgisayarda) çalıştırır.
2. Bot her kaynaktan ilan listesini çeker, daha önce görmediği ilanları bulur.
3. Filtrelerden (`config.yaml`) geçenleri Telegram'a gönderir. Aynı ilan birden çok kaynakta
   varsa tek mesaj gider ("ayrıca: ..." notuyla). Çok sayıda yeni ilan varsa tek özet mesaj gider.
4. Görülen ilanlar `data/state.json` (GitHub) ve `data/state-local.json` (bilgisayar) dosyalarına
   yazılır; workflow'lar bunları repoya commit'ler.

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
4. **Actions → "İlan kontrolü (GitHub)" → Run workflow**: önce `dry_run` işaretli, log'u kontrol
   et; sonra işaretsiz.

### 3. Self-hosted runner (Windows bilgisayar)
1. Repo → **Settings → Actions → Runners → New self-hosted runner** → **Windows**, **x64**.
2. GitHub'ın gösterdiği PowerShell komutlarını sırayla çalıştır (klasör olarak `C:\actions-runner`
   önerilir; repo klasörünün içine kurma).
3. `config.cmd` soruları: hepsine **Enter** (varsayılan etiketler `self-hosted, Windows, X64`);
   **"run as service?" → N**. (Servis olarak çalışırsa kullanıcıya özel Python'u bulamayabilir.)
4. `run.cmd` ile başlat → "Listening for Jobs" yazmalı.
5. Oturum açılınca otomatik başlasın: `Win+R` → `shell:startup` → açılan klasöre
   `C:\actions-runner\run.cmd` için kısayol oluştur.
6. Bilgisayarda Python 3.10+ `python` komutuyla erişilebilir olmalı. Workflow ilk çalışmada
   `%USERPROFILE%\.ilanbot-venv` ortamını kendisi kurar.
7. **Actions → "İlan kontrolü (bilgisayar)" → Run workflow** ile test et.

### 4. Yerelde çalıştırma (isteğe bağlı)
```bash
python -m venv .venv && .venv/Scripts/activate      # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
# .env dosyası (git'e girmez):
#   TELEGRAM_BOT_TOKEN=...
#   TELEGRAM_CHAT_ID=...
PYTHONPATH=src python -m ilanbot --test-telegram      # bağlantı testi
PYTHONPATH=src python -m ilanbot --dry-run -v         # göndermeden konsola yaz
PYTHONPATH=src python -m ilanbot --source ilan_gov --dry-run
PYTHONPATH=src python -m ilanbot --runner local --state data/state-local.json --dry-run
pytest -q
```

## Ayarlar (`config.yaml`)

| Ayar | Açıklama |
|---|---|
| `sources.<kaynak>` | Kaynağı aç/kapa |
| `runners.<ortam>` | O ortamda (`--runner <ortam>`) çalışan kaynaklar; bir kaynak tek ortamda olmalı |
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
- **Bir kaynak yurt dışı IP'yi engelliyor:** `config.yaml → runners` içinde onu `github`'dan
  `local`'e taşı (self-hosted runner'da çalışır). State dosyasındaki kayıtlarını da diğer dosyaya
  taşı, yoksa ilk çalışma "sessiz bootstrap" olur.
- **Bilgisayar tarafı çalışmıyor:** Settings → Actions → Runners'da runner "Idle" mı? Değilse
  `C:\actions-runner\run.cmd`'yi başlat.
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
