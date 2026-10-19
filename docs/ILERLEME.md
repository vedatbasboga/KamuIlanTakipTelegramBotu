# İlerleme

| Aşama | Durum |
|---|---|
| 1 — İskelet ve altyapı | ✅ Tamamlandı (2026-10-19) |
| 2 — Telegram bildirimi | ✅ Tamamlandı (2026-10-19) |
| 3 — Kaynak keşfi | ✅ Tamamlandı (2026-10-19) |
| 4 — Parser'lar | ✅ Tamamlandı (2026-10-19) |
| 5 — Filtre, dedup, orkestrasyon | ✅ Tamamlandı (2026-10-19) |
| 6 — GitHub Actions | 🟡 Devam ediyor |
| 7 — Sağlamlaştırma (opsiyonel) | ⏳ Bekliyor |

---

## Aşama 6 — GitHub Actions

### Tamamlananlar
- `scripts/access_test.py` + `access-test.yml`: her liste uç noktasına istek, durum/boyut/süre,
  engel işaretleri, parse edilen kayıt sayısı → `$GITHUB_STEP_SUMMARY`.
- 🧑 Erişim testi (2026-10-19): kamuilan 403, kariyer_kapisi ve yerel_yonetimler bağlantı zaman
  aşımı; ilan_gov ve iskur erişilebilir (ayrıntı: `docs/kaynaklar.md`).
- 🧑 Karar: **karma** — ilan_gov + iskur GitHub'da 7/24; diğer üçü kullanıcının Windows
  bilgisayarındaki self-hosted runner'da (bilgisayar çoğu zaman açık).
  - `config.yaml → runners` (`github`, `local`) + CLI `--runner NAME`. Bir kaynak tek ortamda
    olabilir (doğrulanıyor), aksi halde iki kez bildirilirdi.
  - Ayrı state dosyaları: `data/state.json` (GitHub), `data/state-local.json` (bilgisayar);
    mevcut state ikiye bölündü. Ayrı concurrency grupları; cron'lar kaydırıldı (:07/:37, :22/:52).
  - `check-local.yml`: `runs-on: [self-hosted, Windows]`, `shell: cmd` (Windows PowerShell 5.1
    git stderr'ini hata sayabiliyor), kalıcı venv `%USERPROFILE%\.ilanbot-venv`. Adımlar yerelde
    `cmd` ile birebir denendi (dry-run başarılı).
- `check.yml` (`--runner github`), `test.yml` (ruff + pytest; state commit'leri tetiklemez).
- Action sürümleri Node 24'e güncellendi (`checkout@v5`, `setup-python@v6`).
- `README.md`: kurulum, self-hosted runner, ayarlar, sorun giderme, Actions notları.

### Kabul kriterleri
- [x] Erişim testi sonuçları `docs/kaynaklar.md`'ye işlendi.
- [ ] Ana workflow'lar en az 3 zamanlanmış çalışmayı hatasız tamamladı; state commit'leri repoda.
- [ ] Test workflow'u yeşil.
- [ ] 🧑 Gerçek bir yeni ilan bildirimi telefona geldi.

## Aşama 5 — Filtre, dedup, orkestrasyon

### Tamamlananlar
- `filters.py`: `matches(ilan, filters) -> (bool, gerekçe)`. Kurallar VE; boş liste atlanır;
  alan yoksa `filtre_belirsizse_gonder`; `exclude_keywords` her zaman öncelikli; "Türkiye geneli /
  tüm iller" her il filtresiyle eşleşir. Anahtar kelimeler başlık + kurum + özet içinde aranır.
- `runner.py`:
  - Sessiz ilk çalışma (bootstrap), sadece yeni ilanlara `enrich` (kaynak başına ≤20; fazlası
    sonraki çalışmaya kalır, `seen`'e yazılmaz), filtreden geçmeyen de `seen`.
  - Gönderim başarısızsa ilan (ve birleştirilen ikizleri) `seen`'den geri alınır.
  - `max_messages_per_run` aşılırsa tek digest. Son başvurusu en yakın önce.
  - Kaynaklar arası tekrar: kurum+başlık `SequenceMatcher` ≥0.9 → tek mesaj + "ayrıca: ...".
    Aynı kaynağın iki ilanı asla birleştirilmez. Öncelik `SOURCE_NAMES` sırası.
  - Sağlık: art arda 6 hata → tek uyarı (iletilemezse sonraki çalışmada tekrar denenir);
    düzelince tek "tekrar çalışıyor". Önceden ≥10 ilan dönen kaynak 0 dönerse hata sayılır.
  - Kaynak bazında asgari aralık (`iskur` 180 dk, 5 dk tolerans).
  - Loglar: `[kaynak] N ilan, X yeni, Y filtreden geçti (t sn)`, toplam özet.
- `__main__.py`: Gerçek modda `.env`/ortamdan notifier (eksikse exit 2), dry-run'da mesajlar
  konsola yazılır.
- 🧑 **Filtreler (kullanıcı kararı, 2026-10-19):** Bot ileride herkese açılabileceği için tüm
  filtreler kapalı (öğrenim, KPSS, il, anahtar kelime boş). `config.yaml`'da örneklerle açıklandı.
- Testler: `test_filters.py`, `test_runner.py` (sahte kaynak/notifier; bootstrap, yeni ilan,
  hata yalıtımı, gönderim hatası, digest, birleştirme, sıralama, enrich sınırı, sağlık uyarısı,
  sıfır şüphesi, asgari aralık, CLI dry-run state'e dokunmuyor). Toplam 233 test.

### Kabul kriterleri
- [x] `pytest -q` yeşil (233 passed).
- [x] Yerelde iki çalışma: ilki 224 ilanı sessizce kaydetti, ikincisi 0 bildirim (iskur aralık
      nedeniyle atlandı).
- [x] 🧑 3 `seen` kaydı silindi (kariyer_kapisi, ilan_gov, yerel_yonetimler); üçüncü çalışma
      "Toplam: 3 bildirim gönderildi" dedi; kullanıcı 3 mesajın telefona geldiğini onayladı.

### Notlar / sonraki iyileştirme adayları
- Kaynaklar arası tekrar önleme basit: kamuilan "13 UZMAN YARDIMCISI ALACAK" ile ilan.gov.tr
  "... Kurumundan Uzman Yardımcılığı Giriş Sınav İlanı" aynı ilan ama benzerlik 0.9'un altında.
  Filtresiz/herkese açık kullanımda aynı ilan 2-3 kaynaktan gelebilir. Aşama 7'de kurum adı +
  son başvuru tarihi eşleşmesi gibi daha akıllı bir kural eklenebilir.
- Herkese açık kullanım için Telegram **kanalı** uygun: bot kanala yönetici olarak eklenir,
  `TELEGRAM_CHAT_ID=@kanal_adi` (kod değişikliği gerekmez).

## Aşama 4 — Parser'lar

### Tamamlananlar
- Her kaynak: saf `parse(raw)` + `Source` sınıfı (`list_items`, gerekiyorsa `enrich`).
  `sources/__init__.py` → `REGISTRY` (5 kaynak; `resmi_gazete` bilinçli olarak yok).
- `sources/base.py`: `BaseSource` (varsayılan `enrich`, `min_interval_minutes`), `parse_rows`
  (bozuk satırı atla + uyar; satırların **hepsi** hata verirse `ParseError`; bilerek atlanan satır,
  ör. süresi geçmiş ilan, hata sayılmaz; ID tekilleştirme).
- `dates.py`: `parse_tr_date` ("28.10.2026", "28/10/2026 17:00", "28 Ekim 2026", ISO),
  `parse_iso` (UTC → İstanbul), `month_number`.
- `http.py`: Ortak `ssl_context()` = certifi + `ilanbot/certs/*.pem` (ilan.gov.tr'nin eksik ara
  sertifikası). Doğrulama hiçbir yerde kapatılmadı. `certifi` requirements'a açıkça eklendi
  (httpx'in zaten bağımlılığı, yeni paket değil).
- Kaynak notları:
  - `kamuilan_sbb`: ⚠️ Logo src'sindeki tarih eki yayın tarihi değil, **her gün değişen bugünün
    tarihi** (önbellek kırıcı) çıktı. ID buna dayansaydı tüm ilanlar her gün yeniden bildirilirdi.
    Yayın günü zaman çizelgesinden (`li > time`) alınıyor, yıl bugüne göre çıkarılıyor. ID'lerin
    iki çekimde ve "ertesi gün" senaryosunda aynı kaldığı test edildi. Kadro sayısı başlıktan
    ("6 UZMAN, 1 DESTEK" → 7). İl, kurum adından (`find_iller`).
  - `ilan_gov`: 2 sayfa × 20; `enrich` detay metninden öğrenim/KPSS/son başvuru. URL'lerdeki
    bölünmez boşluklar temizlendi.
  - `kariyer_kapisi`: süresi geçmiş ilanlar atlanıyor; "KURUM - BAŞLIK" önek tekrarı atılıyor;
    `summary = "İlan türü: ..."`.
  - `iskur`: `min_interval_minutes = 180` (kullanıcı kararı); il listesi + il başına bir istek.
  - `yerel_yonetimler`: il, başlıktaki "X İLİ" kalıbından ya da `find_iller`.
- Testler: `test_dates.py`, `test_sources_base.py`, `test_source_<kaynak>.py` × 5 (fixture'larla,
  ağ yok; `respx` ile istek biçimi doğrulaması). Toplam 192 test.

### Kabul kriterleri
- [x] Kullanılabilir her kaynak için parser ve testler var, `pytest -q` yeşil (192 passed).
- [x] Canlı `--dry-run` (2026-10-19): kamuilan 98, ilan_gov 40, kariyer_kapisi 31,
      yerel_yonetimler 12, iskur 43 ilan (17 il, 5.7 sn). İlk 5 ilan sitelerdekiyle uyumlu —
      **canlı doğrulandı: 2026-10-19**. ilan_gov `enrich` canlıda: `{P3}`, `{lisans}`.
- [x] `ruff check .` temiz.

### Notlar
- `find_iller` kurum adından il çıkarıyor (ör. "KIRIKKALE ÜNİVERSİTESİ" → KIRIKKALE). Merkezi
  kurumlarda il boş kalır → `filtre_belirsizse_gonder` devreye girer.
- `iskur` asgari aralığı ve `enrich` çağrısı Aşama 5 runner'ında uygulanacak.

## Aşama 3 — Kaynak keşfi

### Tamamlananlar
- `docs/kaynaklar.md`: 6 kaynağın hepsi için bölüm.
- Kullanılabilir: `kariyer_kapisi` (JSON, en temiz), `ilan_gov` (JSON; 🧑 kullanıcının cURL'ünden
  gerekli iki başlık bulundu), `yerel_yonetimler` (HTML), `kamuilan_sbb` (HTML), `iskur` (HTML, il
  bazında, ağır).
- Kapatıldı: `resmi_gazete` (ilan sayfaları yanıtsız kalıyor / IP geçici engelleniyor; içeriği
  ilan.gov.tr'de var).
- Fixture'lar `tests/fixtures/<kaynak>/` altında (resmi_gazete hariç). Büyük SVG ve ViewState
  kırpıldı.
- Kariyer Kapısı'nın gerçek adresi `kariyerkapisi.gov.tr`; `DISPLAY_NAMES` ve CLAUDE.md düzeltildi.
- Repo `KamuIlanTakipTelegramBotu` olarak yeniden adlandırılmış; remote ve User-Agent güncellendi.

### Kabul kriterleri
- [x] `docs/kaynaklar.md`'de 6 kaynağın hepsi için bölüm var.
- [x] Kullanılabilir her kaynağın fixture'ı repoda.
- [x] Sorunlu kaynak (`resmi_gazete`) `config.yaml`'da `false` ve burada not edildi.
- [x] 🧑 Kullanıcı kaynak kararlarını verdi (2026-10-19).

### Kullanıcı kararları (2026-10-19)
1. `kamuilan_sbb`: **Bileşik ID** — `sha1(logoId | yayın tarihi | kurum | başlık)[:16]`
   (CLAUDE.md kural 5'ten bilinçli sapma; başlık düzeltilirse ilan bir kez daha bildirilir).
2. `kamuilan_sbb`: **Kategori POST'u yok**, tek `GET /`. Öğretim üyesi/işçi ilanları
   `exclude_keywords` ile başlıktan elenir.
3. `iskur`: **Açık, seyrek** — en fazla 3 saatte bir taranır (kaynak bazında asgari aralık;
   Aşama 4/5'te `last_success`'e göre uygulanacak).
4. `resmi_gazete`: **Kapalı kalsın** (içerik ilan.gov.tr'de).

### Bilinen sorunlar
- ilan.gov.tr sunucu sertifikası 2026-11-29'da bitiyor; yenilenince ara sertifika değişebilir.
- Resmî Gazete IP engeli: Keşif sırasında kısa sürede ~20 istek sonrası ~20+ dk engel.

## Aşama 2 — Telegram bildirimi

### Tamamlananlar
- 🧑 Bot oluşturuldu: **@kamuilan_takip_bot**. Token ve chat_id yerelde `.env`'de (git'e girmez).
- `notifier.py`:
  - `TelegramNotifier.send()`: `sendMessage` (HTML, link önizlemesiz), 429'da `retry_after` kadar
    bekleyip bir kez yeniden deneme, mesajlar arası ~1 sn bekleme, 4096 karakter bölme.
  - `format_ilan()` / `format_digest()` saf fonksiyonlar. Boş alanlar gösterilmez; son başvuruya
    ≤3 gün kala `⚠️`; "bugün/yarın son gün", "süresi doldu" ifadeleri; 3'ten fazla il "+N il".
    `also_in` parametresi Aşama 5'teki "ayrıca: ilan.gov.tr" notu için hazır.
  - Token maskeleme: httpx logger'ına filtre + hata mesajlarında `bot***`.
  - `notifier_from_env()`: eksik ortam değişkeninde anlaşılır hata.
- `__main__.py`: Bağımlılıksız `.env` okuyucu (ortamdaki değeri ezmez), `--test-telegram`.
- `sources.DISPLAY_NAMES`: mesajlarda görünen kaynak adları.
- `tests/test_notifier.py` (24 test): format, eşikler, HTML escape, digest gruplama, bölme,
  429 retry, aralık bekleme, token'ın loglarda olmaması (caplog), `.env` okuma.

### Kabul kriterleri
- [x] `pytest -q` yeşil (114 passed), `ruff` temiz.
- [x] 🧑 Kullanıcı `--test-telegram` ile iki mesajın telefonuna geldiğini onayladı (2026-10-19).
- [x] Token hiçbir dosyada/commit'te yok (`git grep` ile tüm geçmiş tarandı, `.env` ignore'da).

### Notlar
- Token BotFather ekran görüntüsünde sohbette görüldü; kullanıcıya yenilemesi (Revoke) önerildi.

## Aşama 1 — İskelet ve altyapı

### Tamamlananlar
- Proje dosyaları: `requirements*.txt`, `pyproject.toml` (ruff + pytest), `.gitignore`, `config.yaml`.
- `text.py`: `tr_lower`, `tr_upper`, `ascii_fold`, `contains_keyword` (Türkçe `İ/ı` doğru).
- `models.py`: `Ilan` dataclass, `TZ` (Europe/Istanbul), `normalize_url`, `make_id_from_url`,
  `normalize_il` + `find_iller` (81 il, ASCII yazım ve Afyon/Maraş/Urfa/Antep/İçel varyantları),
  `normalize_education`, `normalize_kpss`.
- `config.py`: `load_config` → `Config` dataclass; bilinmeyen anahtar / yanlış tip / tanınmayan
  il, puan türü, öğrenim düzeyi için Türkçe hata mesajı. Filtre değerleri normalize edilir.
- `http.py`: `make_client` (UA, 20 sn timeout, redirect), `get_with_retry` (5xx/timeout/bağlantı
  hatasında 1 sn + 3 sn ile 2 retry, 4xx'te retry yok).
- `state.py`: `load_state` / `save_state` (atomik, sıralı, `indent=2`) / `prune`.
  Tanınmayan üst düzey anahtarlar korunur (Aşama 7'de eklenecek alanlar için).
- `runner.py`: Kaynakları yalıtılmış çalıştıran iskelet; sağlık sayaçlarını günceller.
- `__main__.py`: `--dry-run`, `--source` (tekrarlanabilir), `--config`, `--state`, `--no-save`, `-v`.
  Çıkış kodu: tüm kaynaklar başarısızsa 1, config/state hatasında 2, aksi halde 0.
- `sources/`: `Source` Protocol, `ParseError`, `SOURCE_NAMES`, boş `REGISTRY`, 6 boş kaynak dosyası.
- Testler: `test_models.py`, `test_state.py`, `test_config.py`, `test_http.py` (90 test).

### Kabul kriterleri
- [x] `pytest -q` yeşil (90 passed), `ruff check .` ve `ruff format --check .` temiz.
- [x] `PYTHONPATH=src python -m ilanbot --dry-run` hatasız; "0 kaynak çalıştı: 0 başarılı,
      0 hatalı" yazıyor, çıkış kodu 0.
- [x] `normalize_kpss("KPSSP3 puan türünden 70 puan")` → `{"P3"}`; `normalize_il("izmir")` → `"İZMİR"`.
- [x] `docs/ILERLEME.md` güncellendi.

### Kararlar / sapmalar
- **Python sürümü:** Yerel makinede Python 3.10 kurulu. Kod 3.10 uyumlu yazıldı
  (`requires-python >= 3.10`, ruff `target-version = "py310"`). GitHub Actions'ta 3.12 kullanılacak.
- **Timezone:** `zoneinfo` Windows'ta ek `tzdata` paketi gerektirdiği için `dateutil.tz.gettz`
  kullanıldı (zaten bağımlılık).
- **`text.py`:** Türkçe harf yardımcıları hem `models` hem `config` (ileride `filters`) tarafından
  kullanıldığı için ayrı modüle alındı. Dizin yapısına tek ekleme bu.
- **Bozuk state.json:** Sessizce boş state'e düşmek yerine hata verilir (exit 2). Boş state'e
  düşmek tüm kaynakları yeniden "ilk çalışma" sayıp ilanları kaçırırdı.
- **`--source`** config'te kapalı bir kaynağı da çalıştırabilir (debug için); bilgi notu loglanır.

### Açık sorular / bilinen sorunlar
- `find_iller` serbest metinde "Aydın", "Van", "Ordu", "Batman" gibi özel isim/sözcük olarak da
  geçen illeri yanlışlıkla yakalayabilir. Aşama 4'te parser'lar, yapılandırılmış il alanı varsa
  onu tercih etmeli; serbest metinden il çıkarımı temkinli kullanılmalı.
- `normalize_kpss` metindeki her `P<sayı>` ifadesini puan türü sayar. KPSS bağlamı olmayan
  metinlerde (nadiren) yanlış pozitif olabilir.
