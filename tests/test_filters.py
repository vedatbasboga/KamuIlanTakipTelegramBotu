import pytest

from ilanbot.config import FiltersConfig
from ilanbot.filters import matches
from ilanbot.models import Ilan


def ilan(**kw) -> Ilan:
    base = dict(source="s", id="1", title="Memur Alımı", url="https://x")
    return Ilan(**{**base, **kw})


def F(**kw) -> FiltersConfig:
    kw.setdefault("filtre_belirsizse_gonder", True)
    for key in ("education_levels", "kpss_types", "locations"):
        if key in kw:
            kw[key] = frozenset(kw[key])
    for key in ("include_keywords", "exclude_keywords"):
        if key in kw:
            kw[key] = tuple(kw[key])
    return FiltersConfig(**kw)


def test_empty_filters_pass_everything():
    assert matches(ilan(), F())[0]


@pytest.mark.parametrize(
    ("field", "wanted", "have", "expected"),
    [
        ("education_levels", {"lisans"}, {"lisans", "onlisans"}, True),
        ("education_levels", {"lisans"}, {"onlisans"}, False),
        ("kpss_types", {"P3"}, {"P3", "P93"}, True),
        ("kpss_types", {"P3"}, {"P94"}, False),
        ("locations", {"İZMİR"}, {"İZMİR"}, True),
        ("locations", {"İZMİR"}, {"ANKARA"}, False),
    ],
)
def test_set_rules(field, wanted, have, expected):
    ok, reason = matches(ilan(**{field: frozenset(have)}), F(**{field: wanted}))
    assert ok is expected, reason


@pytest.mark.parametrize("field", ["education_levels", "kpss_types", "locations"])
def test_unknown_field_follows_uncertainty_setting(field):
    wanted = {"education_levels": {"lisans"}, "kpss_types": {"P3"}, "locations": {"İZMİR"}}[field]
    ok, reason = matches(ilan(), F(**{field: wanted}))
    assert ok and "belirsiz" in reason
    ok, reason = matches(ilan(), F(**{field: wanted}, filtre_belirsizse_gonder=False))
    assert not ok and "belirsiz" in reason


def test_rules_are_anded():
    f = F(education_levels={"lisans"}, kpss_types={"P3"})
    assert matches(ilan(education_levels=frozenset({"lisans"}), kpss_types=frozenset({"P3"})), f)[0]
    assert not matches(
        ilan(education_levels=frozenset({"lisans"}), kpss_types=frozenset({"P94"})), f
    )[0]


def test_exclude_wins_over_everything():
    f = F(include_keywords=["memur"], exclude_keywords=["öğretim üyesi"])
    ok, reason = matches(ilan(title="Memur ve Öğretim Üyesi Alımı"), f)
    assert not ok and "öğretim üyesi" in reason


def test_exclude_ignores_uncertainty_setting():
    f = F(exclude_keywords=["işçi"], filtre_belirsizse_gonder=True)
    assert not matches(ilan(title="Sürekli İşçi Alımı"), f)[0]


@pytest.mark.parametrize(
    ("title", "kw"),
    [
        ("İZMİR İL SAĞLIK MÜDÜRLÜĞÜ", "izmir"),
        ("izmir il sağlık müdürlüğü", "İZMİR"),
        ("ÖĞRETMEN ALIMI", "öğretmen"),
        ("Öğretmen alımı", "ÖĞRETMEN"),
        ("ISPARTA BELEDİYESİ", "ısparta"),
    ],
)
def test_turkish_case_insensitive(title, kw):
    assert matches(ilan(title=title), F(include_keywords=[kw]))[0]
    assert not matches(ilan(title=title), F(exclude_keywords=[kw]))[0]


def test_include_requires_at_least_one():
    f = F(include_keywords=["bilişim", "mühendis"])
    assert matches(ilan(title="Sözleşmeli Bilişim Personeli"), f)[0]
    assert not matches(ilan(title="Zabıta Memuru"), f)[0]


def test_keywords_search_institution_and_summary():
    f = F(include_keywords=["b grubu"])
    assert matches(ilan(summary="İlan türü: B Grubu Memur"), f)[0]
    f = F(exclude_keywords=["üniversitesi"])
    assert not matches(ilan(institution="Ankara Üniversitesi"), f)[0]


def test_nationwide_matches_any_location_filter():
    f = F(locations={"İZMİR"}, filtre_belirsizse_gonder=False)
    assert matches(ilan(title="Türkiye geneli 500 memur alımı"), f)[0]
    assert matches(ilan(title="Tüm illerde istihdam", locations=frozenset({"ANKARA"})), f)[0]
