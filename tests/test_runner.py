import dataclasses
import json
from datetime import timedelta

import httpx
import pytest
from conftest import FIXTURE_NOW

from ilanbot import __main__ as cli
from ilanbot import runner
from ilanbot.config import Config, FiltersConfig, NotifyConfig
from ilanbot.models import Ilan
from ilanbot.state import State, load_state, save_state

NOW = FIXTURE_NOW


def ilan(source: str, id: str, title: str = "Memur Alımı", **kw) -> Ilan:
    return Ilan(source=source, id=id, title=title, url=f"https://{source}/{id}", **kw)


class FakeSource:
    min_interval_minutes = 0

    def __init__(self, name: str, items=None, error: Exception | None = None):
        self.name = name
        self.display_name = name
        self.items = items or []
        self.error = error
        self.enriched: list[str] = []

    def list_items(self, client):
        if self.error:
            raise self.error
        return list(self.items)

    def enrich(self, client, item):
        self.enriched.append(item.id)
        return dataclasses.replace(item, summary="zenginleştirildi")


class FakeDeliver:
    def __init__(self, ok: bool = True):
        self.ok = ok
        self.messages: list[str] = []

    def __call__(self, text: str) -> bool:
        self.messages.append(text)
        return self.ok


def config(**filters) -> Config:
    return Config(filters=FiltersConfig(**filters))


@pytest.fixture
def client():
    with httpx.Client() as c:
        yield c


def run(sources, state, client, deliver=None, cfg=None, now=NOW):
    deliver = deliver or FakeDeliver()
    summary = runner.run(sources, cfg or config(), state, client, deliver, now=now)
    return summary, deliver


def bootstrapped(*names: str) -> State:
    state = State()
    for name in names:
        h = state.health(name)
        h.bootstrapped = True
        h.last_success = (NOW - timedelta(hours=1)).isoformat()
    return state


def test_bootstrap_is_silent(client):
    src = FakeSource("kamuilan_sbb", [ilan("kamuilan_sbb", str(i)) for i in range(5)])
    state = State()
    summary, deliver = run([src], state, client)
    assert deliver.messages == []
    assert len(state.seen) == 5
    assert state.sources["kamuilan_sbb"].bootstrapped
    assert src.enriched == []  # bootstrap'ta detay çekilmez
    assert summary.succeeded == ["kamuilan_sbb"]


def test_second_run_notifies_only_new(client):
    src = FakeSource("kamuilan_sbb", [ilan("kamuilan_sbb", "1")])
    state = State()
    run([src], state, client)
    src.items.append(ilan("kamuilan_sbb", "2", title="Yeni Alım"))
    summary, deliver = run([src], state, client)
    assert len(deliver.messages) == 1
    assert "Yeni Alım" in deliver.messages[0]
    assert [i.id for i in summary.sent] == ["2"]
    assert src.enriched == ["2"]  # sadece yeni ilan zenginleştirilir
    _, deliver = run([src], state, client)
    assert deliver.messages == []  # üçüncü çalışmada tekrar yok


def test_failing_source_does_not_stop_others(client):
    bad = FakeSource("ilan_gov", error=httpx.ReadTimeout("yavaş"))
    good = FakeSource("kariyer_kapisi", [ilan("kariyer_kapisi", "1")])
    state = bootstrapped("ilan_gov", "kariyer_kapisi")
    summary, deliver = run([bad, good], state, client)
    assert summary.failed == ["ilan_gov"]
    assert summary.succeeded == ["kariyer_kapisi"]
    assert len(deliver.messages) == 1
    assert state.sources["ilan_gov"].consecutive_failures == 1
    assert not summary.all_failed


def test_all_failed(client):
    summary, _ = run([FakeSource("iskur", error=RuntimeError("x"))], State(), client)
    assert summary.all_failed


def test_failed_delivery_unmarks_seen(client):
    src = FakeSource("kamuilan_sbb", [ilan("kamuilan_sbb", "1")])
    state = bootstrapped("kamuilan_sbb")
    summary, _ = run([src], state, client, deliver=FakeDeliver(ok=False))
    assert "kamuilan_sbb:1" not in state.seen
    assert summary.sent == []
    _, deliver = run([src], state, client)  # sonraki çalışmada tekrar denenir
    assert len(deliver.messages) == 1


def test_filtered_out_items_are_still_seen(client):
    src = FakeSource("kamuilan_sbb", [ilan("kamuilan_sbb", "1", title="Öğretim Üyesi Alımı")])
    state = bootstrapped("kamuilan_sbb")
    _, deliver = run([src], state, client, cfg=config(exclude_keywords=("öğretim üyesi",)))
    assert deliver.messages == []
    assert "kamuilan_sbb:1" in state.seen


def test_digest_when_over_limit(client):
    src = FakeSource("kamuilan_sbb", [ilan("kamuilan_sbb", str(i), f"İlan {i}") for i in range(4)])
    state = bootstrapped("kamuilan_sbb")
    cfg = Config(notify=NotifyConfig(max_messages_per_run=3))
    summary, deliver = run([src], state, client, cfg=cfg)
    assert len(deliver.messages) == 1
    assert "📋 <b>4 yeni ilan</b>" in deliver.messages[0]
    assert len(summary.sent) == 4


def test_cross_source_duplicates_merge(client):
    kurum = "Sayıştay Başkanlığı"
    a = FakeSource(
        "kamuilan_sbb", [ilan("kamuilan_sbb", "1", "Bilişim Personeli Alımı", institution=kurum)]
    )
    b = FakeSource(
        "ilan_gov", [ilan("ilan_gov", "9", "Bilişim Personeli Alımı.", institution=kurum)]
    )
    c = FakeSource("kariyer_kapisi", [ilan("kariyer_kapisi", "5", "Tamamen Başka Bir İlan")])
    state = bootstrapped("kamuilan_sbb", "ilan_gov", "kariyer_kapisi")
    summary, deliver = run([a, b, c], state, client)
    assert len(deliver.messages) == 2
    merged = next(m for m in deliver.messages if "Bilişim" in m)
    assert "ayrıca: ilan.gov.tr" in merged
    assert "kamuilan.sbb.gov.tr" in merged  # öncelikli kaynak kamuilan
    assert {"kamuilan_sbb:1", "ilan_gov:9"} <= set(state.seen)


def test_merged_twins_unmarked_on_failed_delivery(client):
    kurum = "Sayıştay Başkanlığı"
    a = FakeSource("kamuilan_sbb", [ilan("kamuilan_sbb", "1", "Bilişim Alımı", institution=kurum)])
    b = FakeSource("ilan_gov", [ilan("ilan_gov", "9", "Bilişim Alımı", institution=kurum)])
    state = bootstrapped("kamuilan_sbb", "ilan_gov")
    run([a, b], state, client, deliver=FakeDeliver(ok=False))
    assert "kamuilan_sbb:1" not in state.seen and "ilan_gov:9" not in state.seen


def test_same_source_items_never_merge():
    items = [ilan("kamuilan_sbb", "1", "Uzman Alımı"), ilan("kamuilan_sbb", "2", "Uzman Alımı")]
    assert len(runner.merge_duplicates(items)) == 2


def test_sorted_by_deadline(client):
    items = [
        ilan("kamuilan_sbb", "none", "Tarihsiz"),
        ilan("kamuilan_sbb", "late", "Geç", deadline=NOW + timedelta(days=20)),
        ilan("kamuilan_sbb", "soon", "Yakın", deadline=NOW + timedelta(days=2)),
    ]
    state = bootstrapped("kamuilan_sbb")
    summary, _ = run([FakeSource("kamuilan_sbb", items)], state, client)
    assert [i.id for i in summary.sent] == ["soon", "late", "none"]


def test_enrich_limited_per_run(client):
    items = [ilan("ilan_gov", str(i), f"İlan {i}") for i in range(25)]
    src = FakeSource("ilan_gov", items)
    state = bootstrapped("ilan_gov")
    run([src], state, client)
    assert len(src.enriched) == runner.MAX_ENRICH_PER_SOURCE
    assert sum(k.startswith("ilan_gov:") for k in state.seen) == 20
    run([src], state, client)  # kalan 5'i sonraki çalışmada
    assert sum(k.startswith("ilan_gov:") for k in state.seen) == 25


def test_enrich_failure_keeps_list_data(client):
    src = FakeSource("ilan_gov", [ilan("ilan_gov", "1")])
    src.enrich = lambda client, item: (_ for _ in ()).throw(httpx.ConnectError("yok"))
    state = bootstrapped("ilan_gov")
    _, deliver = run([src], state, client)
    assert len(deliver.messages) == 1


def test_health_warning_once_then_recovery(client):
    src = FakeSource("iskur", error=httpx.ConnectError("kapalı"))
    state = bootstrapped("iskur")
    deliver = FakeDeliver()
    for _ in range(runner.FAILURE_WARN_THRESHOLD + 2):
        runner.run([src], config(), state, client, deliver, now=NOW)
    warnings = [m for m in deliver.messages if m.startswith("⚠️")]
    assert len(warnings) == 1
    assert "iskur.gov.tr" in warnings[0] and "art arda 6 kez" in warnings[0]
    assert state.sources["iskur"].warned

    src.error = None
    src.items = [ilan("iskur", "1")]
    deliver.messages.clear()
    runner.run([src], config(), state, client, deliver, now=NOW)
    runner.run([src], config(), state, client, deliver, now=NOW + timedelta(hours=4))
    assert sum("tekrar çalışıyor" in m for m in deliver.messages) == 1
    assert not state.sources["iskur"].warned
    assert state.sources["iskur"].consecutive_failures == 0


def test_warning_retried_if_delivery_fails(client):
    src = FakeSource("iskur", error=RuntimeError("x"))
    state = bootstrapped("iskur")
    state.sources["iskur"].consecutive_failures = runner.FAILURE_WARN_THRESHOLD - 1
    run([src], state, client, deliver=FakeDeliver(ok=False))
    assert not state.sources["iskur"].warned


def test_zero_items_after_many_is_failure(client):
    src = FakeSource("kamuilan_sbb", [])
    state = bootstrapped("kamuilan_sbb")
    state.sources["kamuilan_sbb"].last_count = 98
    summary, _ = run([src], state, client)
    assert summary.failed == ["kamuilan_sbb"]
    assert state.sources["kamuilan_sbb"].last_count == 98  # şüphe sonraki çalışmada da sürer


def test_min_interval_skips_source(client):
    src = FakeSource("iskur", [ilan("iskur", "1")])
    src.min_interval_minutes = 180
    state = bootstrapped("iskur")  # son başarı 1 saat önce
    summary, _ = run([src], state, client)
    assert summary.skipped == ["iskur"] and summary.ran == 0
    summary, _ = run([src], state, client, now=NOW + timedelta(hours=3))
    assert summary.succeeded == ["iskur"]


# --- CLI ---------------------------------------------------------------------------------


@pytest.fixture
def cli_env(tmp_path, monkeypatch):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("sources:\n  kamuilan_sbb: true\n", encoding="utf-8")
    state_path = tmp_path / "state.json"
    src = FakeSource("kamuilan_sbb", [ilan("kamuilan_sbb", "1")])
    monkeypatch.setattr(cli, "REGISTRY", {"kamuilan_sbb": src})
    monkeypatch.setattr(cli, "load_dotenv", lambda: None)
    return cfg, state_path, src


def test_dry_run_does_not_touch_state(cli_env, capsys):
    cfg, state_path, src = cli_env
    state = bootstrapped("kamuilan_sbb")
    save_state(state_path, state)
    before = state_path.read_text(encoding="utf-8")
    code = cli.main(["--dry-run", "--config", str(cfg), "--state", str(state_path)])
    assert code == 0
    assert state_path.read_text(encoding="utf-8") == before
    assert "Telegram mesajı" in capsys.readouterr().out  # mesaj konsola yazıldı


def test_two_real_runs_bootstrap_then_nothing(cli_env, monkeypatch):
    cfg, state_path, src = cli_env
    sent = []
    monkeypatch.setattr(
        cli, "notifier_from_env", lambda client: type("N", (), {"send": sent.append})()
    )
    args = ["--config", str(cfg), "--state", str(state_path)]
    assert cli.main(args) == 0
    assert json.loads(state_path.read_text(encoding="utf-8"))["seen"]
    assert cli.main(args) == 0
    assert sent == []
    assert load_state(state_path).sources["kamuilan_sbb"].bootstrapped


def test_missing_token_exits_2(cli_env, monkeypatch):
    cfg, state_path, _ = cli_env
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert cli.main(["--config", str(cfg), "--state", str(state_path)]) == 2
    assert not state_path.exists()
