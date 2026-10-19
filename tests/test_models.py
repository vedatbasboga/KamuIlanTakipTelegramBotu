import pytest

from ilanbot.models import (
    ILLER,
    Ilan,
    find_iller,
    make_id_from_url,
    normalize_education,
    normalize_il,
    normalize_kpss,
    normalize_url,
)
from ilanbot.text import contains_keyword, tr_lower, tr_upper


class TestText:
    def test_tr_lower(self):
        assert tr_lower("İZMİR") == "izmir"
        assert tr_lower("ISPARTA") == "ısparta"
        assert tr_lower("ÖĞRETMEN") == "öğretmen"

    def test_tr_upper(self):
        assert tr_upper("izmir") == "İZMİR"
        assert tr_upper("ığdır") == "IĞDIR"
        assert tr_upper("öğretmen") == "ÖĞRETMEN"

    def test_contains_keyword(self):
        assert contains_keyword("İZMİR İL SAĞLIK MÜDÜRLÜĞÜ", "sağlık")
        assert contains_keyword("Öğretim Üyesi alımı", "ÖĞRETİM ÜYESİ")
        assert contains_keyword("araştırma   görevlisi", "Araştırma Görevlisi")
        assert not contains_keyword("Memur alımı", "öğretmen")
        assert not contains_keyword("herhangi", "  ")


class TestIlan:
    def test_key(self):
        ilan = Ilan(source="kamuilan_sbb", id="123", title="t", url="https://x")
        assert ilan.key == "kamuilan_sbb:123"

    def test_frozen(self):
        ilan = Ilan(source="s", id="1", title="t", url="https://x")
        with pytest.raises(AttributeError):
            ilan.title = "x"  # type: ignore[misc]


class TestUrlId:
    def test_normalize_url(self):
        assert (
            normalize_url("HTTPS://Www.Ilan.Gov.TR:443/ilan/123/?utm_source=x&b=2&a=1#top")
            == "https://www.ilan.gov.tr/ilan/123?a=1&b=2"
        )

    def test_same_ilan_same_id(self):
        a = make_id_from_url("https://kamuilan.sbb.gov.tr/ilan/42/")
        b = make_id_from_url("HTTPS://KAMUILAN.SBB.GOV.TR/ilan/42?utm_campaign=x")
        assert a == b
        assert len(a) == 16
        assert all(c in "0123456789abcdef" for c in a)

    def test_path_case_matters(self):
        assert make_id_from_url("https://x.gov.tr/Ilan/1") != make_id_from_url(
            "https://x.gov.tr/ilan/1"
        )

    def test_different_query_different_id(self):
        assert make_id_from_url("https://x.gov.tr/i?id=1") != make_id_from_url(
            "https://x.gov.tr/i?id=2"
        )


class TestIl:
    def test_81_il(self):
        assert len(ILLER) == 81

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("izmir", "İZMİR"),
            ("İzmir", "İZMİR"),
            ("IZMIR", "İZMİR"),
            ("Istanbul", "İSTANBUL"),
            ("ığdır", "IĞDIR"),
            ("IGDIR", "IĞDIR"),
            ("Isparta", "ISPARTA"),
            ("Afyon", "AFYONKARAHİSAR"),
            ("afyonkarahisar", "AFYONKARAHİSAR"),
            ("K.Maraş", "KAHRAMANMARAŞ"),
            ("Kahramanmaraş", "KAHRAMANMARAŞ"),
            ("Urfa", "ŞANLIURFA"),
            ("sanliurfa", "ŞANLIURFA"),
            ("İçel", "MERSİN"),
            ("  Çanakkale  ", "ÇANAKKALE"),
            ("Ankara ili", "ANKARA"),
            ("Muğla Valiliği", "MUĞLA"),
            ("İzmir'de", "İZMİR"),
        ],
    )
    def test_normalize_il(self, text, expected):
        assert normalize_il(text) == expected

    @pytest.mark.parametrize("text", ["", None, "Türkiye geneli", "Narnia", "İzmir ve Ankara"])
    def test_normalize_il_none(self, text):
        assert normalize_il(text) is None

    def test_find_iller(self):
        assert find_iller("İzmir, Ankara ve İSTANBUL illerinde") == {"İZMİR", "ANKARA", "İSTANBUL"}
        assert find_iller("Kurum merkezi") == set()


class TestEducation:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("Lisans mezunu", {"lisans"}),
            ("LİSANS", {"lisans"}),
            ("Ön Lisans", {"onlisans"}),
            ("Önlisans", {"onlisans"}),
            ("ÖNLİSANS mezunu", {"onlisans"}),
            ("Yüksek Lisans", {"yuksek_lisans"}),
            ("Doktora", {"doktora"}),
            ("Ortaöğretim", {"ortaogretim"}),
            ("Lise mezunu", {"ortaogretim"}),
            ("Lisans ve Ön Lisans mezunları", {"lisans", "onlisans"}),
            ("Lisans / Yüksek Lisans / Doktora", {"lisans", "yuksek_lisans", "doktora"}),
            ("Ortaöğretim, Önlisans, Lisans", {"ortaogretim", "onlisans", "lisans"}),
            ("Anadolu Lisesi öğretmeni", set()),
            ("", set()),
            (None, set()),
        ],
    )
    def test_normalize_education(self, text, expected):
        assert normalize_education(text) == expected


class TestKpss:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("KPSSP3 puan türünden 70 puan", {"P3"}),
            ("KPSS P 93", {"P93"}),
            ("KPSS-P94", {"P94"}),
            ("kpssp3", {"P3"}),
            ("P3, P93 ve P94 puan türleri", {"P3", "P93", "P94"}),
            ("KPSS (P121)", {"P121"}),
            ("KPSSP03", {"P3"}),
            ("KPSS puanı ile", set()),
            ("Sınavsız alım", set()),
            ("", set()),
            (None, set()),
        ],
    )
    def test_normalize_kpss(self, text, expected):
        assert normalize_kpss(text) == expected
