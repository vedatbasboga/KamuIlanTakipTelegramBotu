# İlerleme

| Aşama | Durum |
|---|---|
| 1 — İskelet ve altyapı | ✅ Tamamlandı (2026-10-19) |
| 2 — Telegram bildirimi | ✅ Tamamlandı (2026-10-19) |
| 3 — Kaynak keşfi | ⏳ Bekliyor |
| 4 — Parser'lar | ⏳ Bekliyor |
| 5 — Filtre, dedup, orkestrasyon | ⏳ Bekliyor |
| 6 — GitHub Actions | ⏳ Bekliyor |
| 7 — Sağlamlaştırma (opsiyonel) | ⏳ Bekliyor |

---

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
