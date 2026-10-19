# Aşama 1 — İskelet ve Altyapı

## Amaç
Kaynaklara ve Telegram'a dokunmadan, botun çalışabilir iskeletini kurmak: modeller, config, HTTP istemcisi, state yönetimi, CLI ve test altyapısı.

## Görevler

### 1.1 Proje dosyaları
- `CLAUDE.md`'deki dizin yapısını oluştur (kaynak dosyaları şimdilik boş iskelet olabilir).
- `requirements.txt`: `httpx`, `beautifulsoup4`, `lxml`, `pyyaml`, `python-dateutil`
- `requirements-dev.txt`: `pytest`, `respx`, `ruff`
- `pyproject.toml`: ruff (line-length 100, `select = ["E","F","I","UP","B"]`), pytest (`pythonpath = ["src"]`, `testpaths = ["tests"]`).
- `.gitignore`: Python standartları ve `.env`. **`data/state.json` ignore edilmez.**
- `docs/ILERLEME.md`'yi aşama başlıklarıyla oluştur.

### 1.2 `models.py`
- `CLAUDE.md`'deki `Ilan` dataclass'ını yaz.
- Yardımcılar:
  - `make_id_from_url(url) -> str`: URL'yi normalize et (şema+host küçük harf, sondaki `/` yok, takip parametreleri `utm_*` atılmış), SHA-1, ilk 16 hex.
  - `normalize_il(text) -> str | None`: 81 il listesine göre eşleştir. Türkçe büyük harf dönüşümüne dikkat et (`i→İ`, `ı→I`), "Afyon"/"Afyonkarahisar" gibi varyantları kapsa.
  - `normalize_education(text) -> set[str]`: "Lisans", "Ön Lisans/Önlisans", "Ortaöğretim/Lise", "Yüksek Lisans", "Doktora".
  - `normalize_kpss(text) -> set[str]`: metindeki `KPSSP3`, `KPSS P 93`, `P94` vb. ifadeleri `{"P3","P93","P94"}` biçimine getir (regex).

### 1.3 `config.py` + `config.yaml`
Örnek `config.yaml` (yorumlarıyla birlikte oluştur):

```yaml
sources:            # kaynak aç/kapa
  kamuilan_sbb: true
  ilan_gov: true
  kariyer_kapisi: true
  iskur: true
  resmi_gazete: true
  yerel_yonetimler: true

filters:
  education_levels: [lisans]          # boş liste = filtre yok
  kpss_types: [P3]                    # boş liste = filtre yok
  locations: []                       # boş = tüm Türkiye
  include_keywords: []                # başlık+özet içinde en az biri geçmeli (boş = şart yok)
  exclude_keywords: ["öğretim üyesi", "doçent", "profesör", "araştırma görevlisi"]
  filtre_belirsizse_gonder: true

notify:
  max_messages_per_run: 15            # aşılırsa tek bir özet mesaj
  show_deadline_days_left: true

state:
  prune_after_days: 120
```

- `load_config(path) -> Config` (dataclass). Bilinmeyen anahtar veya yanlış tipte hata verip anlaşılır Türkçe mesaj göster.
- Anahtar kelime karşılaştırması Türkçe-duyarlı ve büyük/küçük harf duyarsız olmalı (`casefold` Türkçe `İ/ı`'yı doğru işlemez, kendi `tr_lower` fonksiyonunu yaz).

### 1.4 `http.py`
- `make_client() -> httpx.Client`: User-Agent, `timeout=20`, `follow_redirects=True`, `http2=False`.
- `get_with_retry(client, url, **kw)`: 5xx, timeout ve bağlantı hatasında en fazla 2 retry (1 sn, 3 sn). 4xx'te retry yok.
- Not: Bazı `.gov.tr` sitelerinde sertifika zinciri sorunları görülebilir. `verify=False` **varsayılan olmasın**; gerekirse kaynak bazında açıkça ve yorumla yapılsın.

### 1.5 `state.py`
`data/state.json` şeması:

```json
{
  "version": 1,
  "seen": { "kamuilan_sbb:12345": "2026-10-19T12:00:00+03:00" },
  "sources": {
    "kamuilan_sbb": {
      "bootstrapped": true,
      "consecutive_failures": 0,
      "last_success": "2026-10-19T12:00:00+03:00",
      "last_count": 214,
      "warned": false
    }
  },
  "last_heartbeat": null
}
```

- `load_state(path)`: Dosya yoksa boş state döndür.
- `save_state(path, state)`: Atomik yaz (geçici dosya + `os.replace`), anahtarları sıralı ve `indent=2` (git diff okunabilir olsun).
- `prune(state, days)`: `seen` içinden `days` günden eski kayıtları sil.

### 1.6 CLI (`__main__.py`)
`argparse` ile:
- `--dry-run`: Telegram'a göndermez, mesajları stdout'a yazar, state kaydetmez.
- `--source NAME`: Sadece bir kaynağı çalıştırır (tekrarlanabilir).
- `--config PATH` (varsayılan `config.yaml`), `--state PATH` (varsayılan `data/state.json`).
- `--no-save`: Gönderir ama state kaydetmez (debug için).
- Çıkış kodu: Tüm kaynaklar başarısızsa 1, aksi halde 0.
- Şimdilik `runner.run()` boş bir liste ile çalışabilsin.

### 1.7 Testler
- `tests/test_models.py`: ID normalizasyonu, il/öğrenim/KPSS normalize fonksiyonları (Türkçe karakter vakaları dahil).
- `tests/test_state.py`: load/save/prune, atomik yazım.
- `tests/test_config.py`: geçerli config, hatalı config.

## Kabul kriterleri
- [ ] `pytest -q` yeşil, `ruff check .` temiz.
- [ ] `PYTHONPATH=src python -m ilanbot --dry-run` hatasız çalışıyor ve "0 kaynak çalıştı" benzeri bir özet yazıyor.
- [ ] `normalize_kpss("KPSSP3 puan türünden 70 puan")` → `{"P3"}`; `normalize_il("izmir")` → `"İZMİR"`.
- [ ] `docs/ILERLEME.md` güncellendi.
