import httpx
import pytest
import respx

from ilanbot.http import USER_AGENT, get_with_retry, make_client

URL = "https://ornek.gov.tr/ilanlar"


@pytest.fixture
def client():
    with make_client() as c:
        yield c


@respx.mock
def test_user_agent_and_success(client):
    route = respx.get(URL).respond(200, text="ok")
    assert get_with_retry(client, URL).text == "ok"
    assert route.calls.last.request.headers["User-Agent"] == USER_AGENT


@respx.mock
def test_retries_5xx_then_succeeds(client):
    route = respx.get(URL).mock(
        side_effect=[httpx.Response(503), httpx.Response(502), httpx.Response(200, text="ok")]
    )
    sleeps = []
    assert get_with_retry(client, URL, sleep=sleeps.append).text == "ok"
    assert route.call_count == 3
    assert sleeps == [1.0, 3.0]


@respx.mock
def test_gives_up_after_two_retries(client):
    route = respx.get(URL).respond(500)
    with pytest.raises(httpx.HTTPStatusError):
        get_with_retry(client, URL, sleep=lambda _: None)
    assert route.call_count == 3


@respx.mock
def test_no_retry_on_4xx(client):
    route = respx.get(URL).respond(404)
    with pytest.raises(httpx.HTTPStatusError):
        get_with_retry(client, URL, sleep=lambda _: None)
    assert route.call_count == 1


@respx.mock
def test_retries_timeout(client):
    route = respx.get(URL).mock(
        side_effect=[httpx.ReadTimeout("yavaş"), httpx.Response(200, text="ok")]
    )
    assert get_with_retry(client, URL, sleep=lambda _: None).text == "ok"
    assert route.call_count == 2


@respx.mock
def test_timeout_exhausted_raises(client):
    respx.get(URL).mock(side_effect=httpx.ConnectError("yok"))
    with pytest.raises(httpx.ConnectError):
        get_with_retry(client, URL, sleep=lambda _: None)
