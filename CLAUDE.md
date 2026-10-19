# CLAUDE.md — Kamu İlan Bildirim Botu

## Proje amacı

Türkiye'de KPSS puanıyla başvurulan kamu personel ilanlarını aşağıdaki kaynaklardan periyodik olarak çekmek, kullanıcının filtrelerine uyan **yeni** ilanları tespit etmek ve Telegram üzerinden bildirim göndermek.

Kaynaklar:

| Kod adı | Site | Not |
|---|---|---|
| `kamuilan_sbb` | https://kamuilan.sbb.gov.tr | Cumhurbaşkanlığı SBB merkezi kamu ilan sayfası, en yoğun kaynak |
| `ilan_gov` | https://www.ilan.gov.tr | Basın İlan Kurumu, "Personel Alımı" kategorisi |
| `kariyer_kapisi` | https://kariyerkapisi.cbiko.gov.tr | CBİKO Kariyer Kapısı ilan listesi (başvurular e-Devlet ile, liste herkese açık olmalı) |
| `iskur` | https://www.iskur.gov.tr / https://esube.iskur.gov.tr | "Kamu Memur Alımı" ilanları |
| `resmi_gazete` | https://www.resmigazete.gov.tr | Günlük sayı, İlan Bölümü (personel/öğretim üyesi alım ilanları) |
| `yerel_yonetimler` | https://yerelyonetimler.csb.gov.tr | Belediye ve bağlı kuruluş personel ilanları |

Her kaynağın gerçek veri uç noktası (JSON API mi, HTML mi, sayfalama vs.) **Aşama 3'te keşfedilir** ve `docs/kaynaklar.md`'ye yazılır. Bu dosyada tahmin edilmiş URL'lere güvenme; `docs/kaynaklar.md` esas alınır.

## Çalışma modeli

- Uzun süre çalışan bir süreç **yoktur**. GitHub Actions cron ile `python -m ilanbot` çalıştırılır. Script çalışır, yeni ilanları bulur, Telegram'a gönderir, state'i kaydeder ve çıkar.
- State (görülen ilanlar, kaynak sağlık durumu) `data/state.json` dosyasında tutulur. Workflow bu dosyayı her çalışmadan sonra repoya commit'ler.
- Telegram'a sadece Bot API'nin `sendMessage` metodu ile HTTPS POST atılır. Polling ya da webhook yoktur.

## Teknoloji

- Python 3.12
- `httpx` (HTTP), `beautifulsoup4` + `lxml` (HTML), `pyyaml` (config), `python-dateutil` (tarih)
- Test: `pytest`, `respx` (httpx mock)
- Lint/format: `ruff`
- Ek bağımlılık eklemeden önce gerekçesini belirt. Headless tarayıcıya (Playwright vb.) **son çare** olarak başvurulur ve önce kullanıcıya sorulur.

## Dizin yapısı (hedef)

```
.
├── CLAUDE.md
├── config.yaml                  # kullanıcı filtreleri ve kaynak aç/kapa
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml               # ruff + pytest ayarları
├── data/
│   └── state.json               # bot tarafından yönetilir, elle düzenlenmez
├── docs/
│   ├── asamalar/                # aşama talimatları
│   ├── kaynaklar.md             # Aşama 3 çıktısı: her kaynağın teknik detayı
│   └── ILERLEME.md              # aşama durumu, notlar, açık sorular
├── src/ilanbot/
│   ├── __init__.py
│   ├── __main__.py              # CLI giriş noktası
│   ├── models.py                # Ilan dataclass
│   ├── config.py                # config.yaml yükleme + doğrulama
│   ├── http.py                  # ortak httpx client (UA, timeout, retry)
│   ├── state.py                 # state.json yükle/kaydet/prune
│   ├── filters.py               # filtre mantığı
│   ├── notifier.py              # Telegram gönderimi
│   ├── runner.py                # orkestrasyon
│   └── sources/
│       ├── __init__.py          # kaynak kayıt defteri (registry)
│       ├── base.py              # Source arayüzü
│       ├── kamuilan_sbb.py
│       ├── ilan_gov.py
│       ├── kariyer_kapisi.py
│       ├── iskur.py
│       ├── resmi_gazete.py
│       └── yerel_yonetimler.py
├── tests/
│   ├── fixtures/<kaynak>/...    # gerçek yanıtlardan kaydedilmiş örnekler
│   └── test_*.py
└── .github/workflows/
    ├── check.yml                # ana cron workflow
    └── access-test.yml          # kaynaklara erişim testi (manuel)
```

## Komutlar

```bash
pip install -r requirements.txt -r requirements-dev.txt
PYTHONPATH=src python -m ilanbot --dry-run            # göndermeden konsola yaz, state kaydetme
PYTHONPATH=src python -m ilanbot --source kamuilan_sbb --dry-run
PYTHONPATH=src python -m ilanbot                      # gerçek çalışma
pytest -q
ruff check . && ruff format --check .
```

## Kurallar

1. **Testler ağa çıkmaz.** Tüm parser testleri `tests/fixtures/` altındaki kayıtlı yanıtlarla çalışır. Ağ gerektiren keşif işleri testlerin dışında, elle yapılır.
2. **Kaynaklar birbirinden yalıtılmıştır.** Bir kaynağın hata vermesi diğerlerini durdurmaz. Hata loglanır, state'teki sağlık sayacı artar, çalışma devam eder.
3. **Sır yok.** Token ve chat_id sadece ortam değişkeninden okunur (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`). Hiçbir dosyaya, loga veya commit'e yazılmaz.
4. **Sessiz ilk çalışma (bootstrap).** Bir kaynak state'te ilk kez görülüyorsa, o kaynaktan gelen tüm ilanlar bildirim gönderilmeden "görüldü" işaretlenir. Böylece ilk çalışmada yüzlerce mesaj gitmez.
5. **Kararlı ID.** Her ilanın tekrar önleme anahtarı `"{source}:{id}"` şeklindedir. `id` mümkünse kaynağın kendi ilan ID'sidir; yoksa normalize edilmiş URL'nin SHA-1'inin ilk 16 karakteri kullanılır. Başlık ya da tarih **ID olarak kullanılmaz**, çünkü düzeltilebilirler.
6. **Filtre şüphede gönderir.** Bir ilanda filtrelenen alan (ör. öğrenim düzeyi) parse edilemediyse ilan elenmez, gönderilir. Kaçırılan ilan, fazladan gelen bildirimden daha kötüdür. Bu davranış `config.yaml`'da `filtre_belirsizse_gonder: true` ile kontrol edilir.
7. **Nazik istemci.** Anlamlı bir User-Agent kullanılır (`KamuIlanBot/1.0 (+repo-url)`). Timeout 20 sn, en fazla 2 retry (exponential backoff). Kaynak başına bir çalışmada makul sayıda istek atılır (sayfalama en fazla 3 sayfa).
8. **Dil.** Kod, değişken ve fonksiyon adları İngilizce; kullanıcıya giden Telegram mesajları ve loglar Türkçe; dokümantasyon Türkçe.
9. **Zaman.** İçeride tüm zamanlar timezone-aware tutulur (`Europe/Istanbul`). State'e ISO 8601 formatında yazılır.
10. **İnsan kontrol noktaları.** Aşama dosyalarında `🧑 KULLANICI` ile işaretli adımlarda dur ve kullanıcıdan girdi iste. Tahmin ederek devam etme.
11. **İlerleme kaydı.** Her aşama bitiminde `docs/ILERLEME.md`'ye şunları yaz: tamamlanan maddeler, kabul kriterlerinin durumu, açık sorular, bilinen sorunlar.

## Ilan modeli (sözleşme)

```python
@dataclass(frozen=True)
class Ilan:
    source: str  # "kamuilan_sbb" vb.
    id: str  # kural 5
    title: str
    url: str  # mutlak URL
    institution: str | None = None  # kurum adı
    published_at: datetime | None = None
    deadline: datetime | None = None  # son başvuru
    education_levels: frozenset[str] = (
        frozenset()
    )  # {"lisans","onlisans","ortaogretim","yuksek_lisans","doktora"}
    kpss_types: frozenset[str] = frozenset()  # {"P3","P93","P94",...} normalize edilmiş
    locations: frozenset[str] = frozenset()  # il adları, normalize (büyük harf, Türkçe karakterli)
    position_count: int | None = None
    summary: str | None = None  # kısa açıklama (filtre için metin)

    @property
    def key(self) -> str:
        return f"{self.source}:{self.id}"
```

Alanlar boş olabilir; parser'lar sadece kaynağın gerçekten verdiği bilgiyi doldurur.

## Source arayüzü

```python
class Source(Protocol):
    name: str  # registry anahtarı
    display_name: str  # mesajlarda görünen ad, ör. "kamuilan.sbb.gov.tr"

    def list_items(self, client: httpx.Client) -> list[Ilan]: ...  # liste sayfası/API → ilanlar
    def enrich(
        self, client: httpx.Client, ilan: Ilan
    ) -> Ilan: ...  # gerekiyorsa detay sayfasından eksik alanları doldurur; gerekmiyorsa ilanı aynen döndürür
```

`list_items` ağdan çeker ve parse eder. Parse mantığı ayrı, saf (pure) bir fonksiyonda olmalıdır (`parse(raw: str | dict) -> list[Ilan]`). Böylece fixture ile test edilebilir. `enrich` sadece yeni (state'te olmayan) ilanlar için çağrılır (bkz. Aşama 4 ve 5).
