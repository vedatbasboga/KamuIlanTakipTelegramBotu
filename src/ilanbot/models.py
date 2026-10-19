"""İlan modeli ve normalizasyon yardımcıları."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dateutil import tz

from .text import ascii_fold, squash_spaces, tr_lower, tr_upper

# zoneinfo Windows'ta ek `tzdata` paketi ister; dateutil kendi tz veritabanını taşır.
TZ = tz.gettz("Europe/Istanbul")

EDUCATION_LEVELS = frozenset({"ortaogretim", "onlisans", "lisans", "yuksek_lisans", "doktora"})


@dataclass(frozen=True)
class Ilan:
    source: str  # "kamuilan_sbb" vb.
    id: str  # CLAUDE.md kural 5
    title: str
    url: str  # mutlak URL
    institution: str | None = None  # kurum adı
    published_at: datetime | None = None
    deadline: datetime | None = None  # son başvuru
    education_levels: frozenset[str] = frozenset()  # EDUCATION_LEVELS alt kümesi
    kpss_types: frozenset[str] = frozenset()  # {"P3","P93",...} normalize edilmiş
    locations: frozenset[str] = frozenset()  # il adları: büyük harf, Türkçe karakterli
    position_count: int | None = None
    summary: str | None = None  # kısa açıklama (filtre için metin)

    @property
    def key(self) -> str:
        return f"{self.source}:{self.id}"


def now() -> datetime:
    """Europe/Istanbul timezone'lu şimdiki zaman."""
    return datetime.now(TZ)


# --- URL / ID ---------------------------------------------------------------

_TRACKING_PARAMS = frozenset({"fbclid", "gclid", "yclid", "mc_cid", "mc_eid"})


def normalize_url(url: str) -> str:
    """Kararlı karşılaştırma için URL'yi normalize eder.

    Şema ve host küçük harfe çevrilir, varsayılan port, fragment, sondaki `/` ve
    takip parametreleri (`utm_*`, `fbclid` ...) atılır, kalan parametreler sıralanır.
    """
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    port = parts.port
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        host = f"{host}:{port}"
    path = parts.path.rstrip("/")
    query = sorted(
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in _TRACKING_PARAMS
    )
    return urlunsplit((scheme, host, path, urlencode(query), ""))


def make_id_from_url(url: str) -> str:
    """Normalize edilmiş URL'nin SHA-1 özetinin ilk 16 hex karakteri."""
    return hashlib.sha1(normalize_url(url).encode("utf-8")).hexdigest()[:16]


# --- İller ------------------------------------------------------------------

ILLER: tuple[str, ...] = (
    "ADANA", "ADIYAMAN", "AFYONKARAHİSAR", "AĞRI", "AMASYA", "ANKARA", "ANTALYA", "ARTVİN",
    "AYDIN", "BALIKESİR", "BİLECİK", "BİNGÖL", "BİTLİS", "BOLU", "BURDUR", "BURSA",
    "ÇANAKKALE", "ÇANKIRI", "ÇORUM", "DENİZLİ", "DİYARBAKIR", "EDİRNE", "ELAZIĞ", "ERZİNCAN",
    "ERZURUM", "ESKİŞEHİR", "GAZİANTEP", "GİRESUN", "GÜMÜŞHANE", "HAKKARİ", "HATAY", "ISPARTA",
    "MERSİN", "İSTANBUL", "İZMİR", "KARS", "KASTAMONU", "KAYSERİ", "KIRKLARELİ", "KIRŞEHİR",
    "KOCAELİ", "KONYA", "KÜTAHYA", "MALATYA", "MANİSA", "KAHRAMANMARAŞ", "MARDİN", "MUĞLA",
    "MUŞ", "NEVŞEHİR", "NİĞDE", "ORDU", "RİZE", "SAKARYA", "SAMSUN", "SİİRT",
    "SİNOP", "SİVAS", "TEKİRDAĞ", "TOKAT", "TRABZON", "TUNCELİ", "ŞANLIURFA", "UŞAK",
    "VAN", "YOZGAT", "ZONGULDAK", "AKSARAY", "BAYBURT", "KARAMAN", "KIRIKKALE", "BATMAN",
    "ŞIRNAK", "BARTIN", "ARDAHAN", "IĞDIR", "YALOVA", "KARABÜK", "KİLİS", "OSMANİYE",
    "DÜZCE",
)  # fmt: skip

_IL_VARIANTS = {
    "AFYON": "AFYONKARAHİSAR",
    "MARAŞ": "KAHRAMANMARAŞ",
    "K.MARAŞ": "KAHRAMANMARAŞ",
    "K. MARAŞ": "KAHRAMANMARAŞ",
    "URFA": "ŞANLIURFA",
    "Ş.URFA": "ŞANLIURFA",
    "ANTEP": "GAZİANTEP",
    "İÇEL": "MERSİN",
}


def _il_key(text: str) -> str:
    return ascii_fold(tr_upper(squash_spaces(text)))


# ASCII'ye indirgenmiş anahtar → resmi il adı. "Izmir", "IZMIR", "izmir" hepsi eşleşir.
_IL_LOOKUP: dict[str, str] = {_il_key(il): il for il in ILLER}
_IL_LOOKUP.update({_il_key(k): v for k, v in _IL_VARIANTS.items()})
_IL_SUFFIX_RE = re.compile(r"\s+(İLİ|VALİLİĞİ|BELEDİYESİ)$")
# "K.Maraş" → "K", "MARAŞ"; "MARAŞ" varyantı zaten tanınıyor.
_WORD_RE = re.compile(r"[^\W\d_]+")

assert len(ILLER) == 81 and len(set(ILLER)) == 81


def normalize_il(text: str | None) -> str | None:
    """Metni 81 ilden birine eşler; eşleşmezse None.

    Önce tüm metin bir il adı (veya bilinen varyantı) olarak denenir. Olmazsa metinde
    tam olarak bir il adı geçiyorsa o döner (ör. "İzmir'de" → "İZMİR").
    """
    if not text:
        return None
    cleaned = tr_upper(squash_spaces(text)).strip(" .,;:-/()")
    cleaned = _IL_SUFFIX_RE.sub("", cleaned)
    hit = _IL_LOOKUP.get(_il_key(cleaned))
    if hit:
        return hit
    found = find_iller(text)
    return next(iter(found)) if len(found) == 1 else None


def find_iller(text: str | None) -> set[str]:
    """Serbest metinde geçen il adlarını bulur.

    Dikkat: "Aydın", "Van", "Ordu" gibi iller özel isim/sözcük olarak da geçebilir.
    Parser'lar bu fonksiyonu yapılandırılmış il alanı yoksa, temkinli kullanmalı.
    """
    if not text:
        return set()
    upper = tr_upper(text)
    return {
        _IL_LOOKUP[key] for word in _WORD_RE.findall(upper) if (key := _il_key(word)) in _IL_LOOKUP
    }


# --- Öğrenim düzeyi -----------------------------------------------------------

# Desenler ascii_fold(tr_lower(metin)) üzerinde, sırayla uygulanır. Eşleşen kısım metinden
# silinir; böylece "yüksek lisans" ya da "ön lisans" ayrıca "lisans" olarak sayılmaz.
_EDUCATION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("yuksek_lisans", re.compile(r"\byuksek\s*-?\s*lisans\w*|\blisansustu\w*")),
    ("onlisans", re.compile(r"\bon\s*-?\s*lisans\w*")),
    ("doktora", re.compile(r"\bdoktora\w*")),
    ("ortaogretim", re.compile(r"\borta\s*-?\s*ogretim\w*|\blise\b|\blise\s+mezun\w*")),
    ("lisans", re.compile(r"\blisans\w*")),
)


def normalize_education(text: str | None) -> set[str]:
    """Metindeki öğrenim düzeylerini `EDUCATION_LEVELS` kodlarına çevirir."""
    if not text:
        return set()
    work = ascii_fold(tr_lower(text))
    levels: set[str] = set()
    for code, pattern in _EDUCATION_PATTERNS:
        work, n = pattern.subn(" ", work)
        if n:
            levels.add(code)
    return levels


# --- KPSS puan türü -----------------------------------------------------------

_KPSS_GLUE_RE = re.compile(r"KPSS(?=P)")
_KPSS_RE = re.compile(r"\bP\s*[-_]?\s*(\d{1,3})\b")


def normalize_kpss(text: str | None) -> set[str]:
    """Metindeki KPSS puan türlerini {"P3", "P93", ...} biçimine getirir.

    "KPSSP3", "KPSS P 93", "KPSS-P94", "P121" gibi yazımları tanır.
    """
    if not text:
        return set()
    upper = _KPSS_GLUE_RE.sub("KPSS ", tr_upper(text))
    return {f"P{int(num)}" for num in _KPSS_RE.findall(upper)}
