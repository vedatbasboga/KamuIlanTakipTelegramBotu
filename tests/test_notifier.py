import json
import logging
import os
from datetime import datetime, timedelta

import httpx
import pytest
import respx

from ilanbot.__main__ import load_dotenv
from ilanbot.models import TZ, Ilan
from ilanbot.notifier import (
    MAX_MESSAGE_LEN,
    NotifierConfigError,
    TelegramNotifier,
    format_digest,
    format_ilan,
    mask_token,
    notifier_from_env,
    split_message,
)

TOKEN = "123456:TEST-gizli_token"
SEND_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
NOW = datetime(2026, 10, 19, 12, 0, tzinfo=TZ)


def make_ilan(**kw) -> Ilan:
    base = dict(source="kamuilan_sbb", id="1", title="Memur Alımı", url="https://x.gov.tr/i/1")
    return Ilan(**{**base, **kw})


class FakeClock:
    def __init__(self):
        self.t = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.t += seconds


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def notifier(clock):
    with httpx.Client() as client:
        yield TelegramNotifier(TOKEN, "42", client, sleep=clock.sleep, clock=clock)


# --- format_ilan ---------------------------------------------------------------------


def test_format_ilan_full():
    ilan = make_ilan(
        institution="İzmir İl Sağlık Müdürlüğü",
        title="Sözleşmeli Personel Alımı",
        deadline=NOW + timedelta(days=9),
        education_levels=frozenset({"onlisans", "lisans"}),
        kpss_types=frozenset({"P93", "P3"}),
        locations=frozenset({"İZMİR"}),
        position_count=12,
    )
    assert format_ilan(ilan, NOW) == (
        "🆕 <b>İzmir İl Sağlık Müdürlüğü</b>\n"
        "Sözleşmeli Personel Alımı\n"
        "\n"
        "🎓 Ön Lisans, Lisans · 📊 KPSS P3, P93 · 📍 İZMİR\n"
        "👥 12 kadro\n"
        "⏳ Son başvuru: 28.10.2026 (9 gün kaldı)\n"
        "\n"
        '🔗 <a href="https://x.gov.tr/i/1">İlana git</a> · <i>kamuilan.sbb.gov.tr</i>'
    )


def test_format_ilan_minimal_hides_empty_fields():
    text = format_ilan(make_ilan(), NOW)
    assert text == (
        "🆕 <b>Memur Alımı</b>\n"
        "\n"
        '🔗 <a href="https://x.gov.tr/i/1">İlana git</a> · <i>kamuilan.sbb.gov.tr</i>'
    )
    for icon in ("🎓", "📊", "📍", "👥", "⏳", "⚠️"):
        assert icon not in text


@pytest.mark.parametrize(
    ("days", "expected"),
    [
        (4, "⏳ Son başvuru: 23.10.2026 (4 gün kaldı)"),
        (3, "⚠️ Son başvuru: 22.10.2026 (3 gün kaldı)"),
        (1, "⚠️ Son başvuru: 20.10.2026 (yarın son gün)"),
        (0, "⚠️ Son başvuru: 19.10.2026 (bugün son gün)"),
        (-1, "⚠️ Son başvuru: 18.10.2026 (süresi doldu)"),
    ],
)
def test_deadline_warning_threshold(days, expected):
    assert expected in format_ilan(make_ilan(deadline=NOW + timedelta(days=days)), NOW)


def test_deadline_days_left_can_be_hidden():
    text = format_ilan(make_ilan(deadline=NOW + timedelta(days=9)), NOW, show_days_left=False)
    assert "⏳ Son başvuru: 28.10.2026\n" in text + "\n"
    assert "kaldı" not in text


def test_html_escape():
    ilan = make_ilan(
        institution="Ar-Ge & İnovasyon <Daire>",
        title='Uzman "Yardımcısı" <b>alımı</b>',
        url="https://x.gov.tr/i?a=1&b=2",
    )
    text = format_ilan(ilan, NOW)
    assert "<b>Ar-Ge &amp; İnovasyon &lt;Daire&gt;</b>" in text
    assert "Uzman &quot;Yardımcısı&quot; &lt;b&gt;alımı&lt;/b&gt;" in text
    assert 'href="https://x.gov.tr/i?a=1&amp;b=2"' in text


def test_many_locations_are_truncated():
    ilan = make_ilan(locations=frozenset({"ANKARA", "BURSA", "İZMİR", "ADANA", "VAN"}))
    assert "📍 ADANA, ANKARA, BURSA +2 il" in format_ilan(ilan, NOW)


def test_also_in_note():
    text = format_ilan(make_ilan(), NOW, also_in=["ilan_gov"])
    assert text.endswith("<i>ayrıca: ilan.gov.tr</i>")


# --- format_digest -------------------------------------------------------------------


def test_digest_groups_by_source_in_registry_order():
    ilanlar = [
        make_ilan(source="ilan_gov", id="a", title="A", institution="Kurum A"),
        make_ilan(source="kamuilan_sbb", id="b", title="B & C", url="https://x/b"),
        make_ilan(source="ilan_gov", id="c", title="C", deadline=NOW + timedelta(days=2)),
    ]
    assert format_digest(ilanlar, NOW) == (
        "📋 <b>3 yeni ilan</b>\n"
        "\n"
        "<b>kamuilan.sbb.gov.tr</b>\n"
        '• <a href="https://x/b">B &amp; C</a>\n'
        "\n"
        "<b>ilan.gov.tr</b>\n"
        '• Kurum A — <a href="https://x.gov.tr/i/1">A</a>\n'
        '• <a href="https://x.gov.tr/i/1">C</a> <i>(son: 21.10)</i>'
    )


# --- split_message -------------------------------------------------------------------


def test_split_short_message_untouched():
    assert split_message("kısa") == ["kısa"]


def test_split_on_line_boundaries():
    lines = [f"satır {i} " + "x" * 90 for i in range(100)]  # ~10.000 karakter
    chunks = split_message("\n".join(lines))
    assert len(chunks) == 3
    assert all(len(c) <= MAX_MESSAGE_LEN for c in chunks)
    assert "\n".join(chunks) == "\n".join(lines)  # hiçbir satır bölünmedi/kaybolmadı


def test_split_overlong_single_line():
    chunks = split_message("a" * 5000 + "\nson")
    assert [len(c) for c in chunks] == [4096, 904 + 4]


# --- gönderim --------------------------------------------------------------------------


@respx.mock
def test_send_payload(notifier):
    route = respx.post(SEND_URL).respond(200, json={"ok": True})
    assert notifier.send("<b>merhaba</b>") is True
    sent = route.calls.last.request

    body = json.loads(sent.content)
    assert body == {
        "chat_id": "42",
        "text": "<b>merhaba</b>",
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }


@respx.mock
def test_429_waits_retry_after_then_retries_once(notifier, clock):
    route = respx.post(SEND_URL).mock(
        side_effect=[
            httpx.Response(429, json={"ok": False, "parameters": {"retry_after": 7}}),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    assert notifier.send("x") is True
    assert route.call_count == 2
    assert 7.0 in clock.sleeps


@respx.mock
def test_429_twice_gives_up(notifier):
    route = respx.post(SEND_URL).respond(429, json={"parameters": {"retry_after": 1}})
    assert notifier.send("x") is False
    assert route.call_count == 2


@respx.mock
def test_long_message_sent_in_parts_with_interval(notifier, clock):
    route = respx.post(SEND_URL).respond(200, json={"ok": True})
    text = "\n".join("y" * 100 for _ in range(100))
    assert notifier.send(text) is True
    assert route.call_count == 3
    assert clock.sleeps == [1.0, 1.0]  # parçalar arası ~1 sn


@respx.mock
def test_error_response_returns_false(notifier):
    respx.post(SEND_URL).respond(400, json={"ok": False, "description": "can't parse entities"})
    assert notifier.send("x") is False


@respx.mock
def test_token_never_logged(notifier, caplog):
    caplog.set_level(logging.DEBUG)
    respx.post(SEND_URL).mock(
        side_effect=[
            httpx.Response(200, json={"ok": True}),
            httpx.Response(400, json={"description": f"bad url {SEND_URL}"}),
            httpx.ConnectError(f"bağlanılamadı: {SEND_URL}"),
        ]
    )
    notifier.send("1")
    notifier.send("2")
    notifier.send("3")
    assert caplog.records  # httpx ve notifier gerçekten log üretti
    assert TOKEN not in caplog.text
    assert "TEST-gizli_token" not in caplog.text


def test_mask_token():
    assert mask_token(f"POST {SEND_URL}") == "POST https://api.telegram.org/bot***/sendMessage"


# --- ortam / .env ---------------------------------------------------------------------


def test_notifier_from_env_missing(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    with httpx.Client() as client, pytest.raises(NotifierConfigError, match="TELEGRAM_BOT_TOKEN"):
        notifier_from_env(client)


def test_load_dotenv(tmp_path, monkeypatch):
    monkeypatch.delenv("ILANBOT_TEST_A", raising=False)
    monkeypatch.delenv("ILANBOT_TEST_B", raising=False)
    monkeypatch.setenv("ILANBOT_TEST_C", "ortamdaki")
    env = tmp_path / ".env"
    env.write_text(
        "# yorum\n\nILANBOT_TEST_A=1:abc\n"
        'export ILANBOT_TEST_B="tırnaklı"\n'
        "ILANBOT_TEST_C=dosyadaki\n",
        encoding="utf-8",
    )
    load_dotenv(env)

    assert os.environ["ILANBOT_TEST_A"] == "1:abc"
    assert os.environ["ILANBOT_TEST_B"] == "tırnaklı"
    assert os.environ["ILANBOT_TEST_C"] == "ortamdaki"  # ortam önceliklidir
    monkeypatch.delenv("ILANBOT_TEST_A")
    monkeypatch.delenv("ILANBOT_TEST_B")


API = f"https://api.telegram.org/bot{TOKEN}"


@respx.mock
@pytest.mark.parametrize(
    ("chat", "member", "expected"),
    [
        ({"type": "private", "first_name": "Vedat"}, None, True),
        (
            {"type": "channel", "title": "Kanal"},
            {"status": "administrator", "can_post_messages": True},
            True,
        ),
        (
            {"type": "channel", "title": "Kanal"},
            {"status": "administrator", "can_post_messages": False},
            False,
        ),
        ({"type": "channel", "title": "Kanal"}, {"status": "left"}, False),
    ],
)
def test_can_post(notifier, chat, member, expected):
    respx.get(f"{API}/getMe").respond(200, json={"ok": True, "result": {"id": 7}})
    respx.get(f"{API}/getChat").respond(200, json={"ok": True, "result": chat})
    respx.get(f"{API}/getChatMember").respond(200, json={"ok": True, "result": member or {}})
    sent = respx.post(SEND_URL).respond(200, json={"ok": True})
    ok, detail = notifier.can_post()
    assert ok is expected, detail
    assert not sent.called  # hiçbir mesaj gönderilmez


@respx.mock
def test_can_post_api_error_masks_token(notifier):
    respx.get(f"{API}/getMe").respond(401, json={"ok": False, "description": "Unauthorized"})
    ok, detail = notifier.can_post()
    assert not ok and "Unauthorized" in detail and TOKEN not in detail


@respx.mock
def test_test_telegram_never_posts_to_channel_when_admin_set(monkeypatch):
    from ilanbot import __main__ as cli

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "@kanal")
    monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_ID", "42")
    respx.get(f"{API}/getMe").respond(200, json={"ok": True, "result": {"id": 7}})
    respx.get(f"{API}/getChat").respond(200, json={"ok": True, "result": {"type": "channel"}})
    respx.get(f"{API}/getChatMember").respond(
        200, json={"ok": True, "result": {"status": "administrator", "can_post_messages": True}}
    )
    sent = respx.post(SEND_URL).respond(200, json={"ok": True})
    assert cli.test_telegram() == 0
    chats = {json.loads(c.request.content)["chat_id"] for c in sent.calls}
    assert chats == {"42"}
