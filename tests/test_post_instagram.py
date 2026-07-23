from unittest.mock import patch, MagicMock

import post_instagram
from post_instagram import post_to_instagram


def test_load_env_var_reads_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("IG_USER_ID=28194940543437064\nMETA_ACCESS_TOKEN=dummy-token\n")
    monkeypatch.chdir(tmp_path)
    assert post_instagram.load_env_var("IG_USER_ID") == "28194940543437064"
    assert post_instagram.load_env_var("META_ACCESS_TOKEN") == "dummy-token"


def test_load_env_var_missing_file_returns_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert post_instagram.load_env_var("IG_USER_ID") is None


def test_load_env_var_missing_key_returns_none(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("SOME_OTHER_KEY=x\n")
    monkeypatch.chdir(tmp_path)
    assert post_instagram.load_env_var("IG_USER_ID") is None


def test_load_env_var_empty_value_returns_none(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("IG_USER_ID=\n")
    monkeypatch.chdir(tmp_path)
    assert post_instagram.load_env_var("IG_USER_ID") is None


@patch("post_instagram.requests.post")
def test_post_to_instagram_two_step_flow(mock_post):
    # Schritt 1: /media -> creation_id, Schritt 2: /media_publish -> media_id
    mock_post.side_effect = [
        MagicMock(status_code=200, json=lambda: {"id": "creation-123"}),
        MagicMock(status_code=200, json=lambda: {"id": "media-456"}),
    ]

    media_id = post_to_instagram(
        image_url="https://raw.githubusercontent.com/phismith91/ig-tagesgeschichte/master/output/2026-07/20/01.png",
        caption="Testcaption",
        ig_user_id="28194940543437064",
        access_token="dummy-token",
    )

    assert media_id == "media-456"
    assert mock_post.call_count == 2

    first_call = mock_post.call_args_list[0]
    assert first_call.args[0] == "https://graph.instagram.com/v21.0/28194940543437064/media"
    assert first_call.kwargs["data"]["image_url"] == "https://raw.githubusercontent.com/phismith91/ig-tagesgeschichte/master/output/2026-07/20/01.png"
    assert first_call.kwargs["data"]["caption"] == "Testcaption"
    assert first_call.kwargs["data"]["access_token"] == "dummy-token"

    second_call = mock_post.call_args_list[1]
    assert second_call.args[0] == "https://graph.instagram.com/v21.0/28194940543437064/media_publish"
    assert second_call.kwargs["data"]["creation_id"] == "creation-123"
    assert second_call.kwargs["data"]["access_token"] == "dummy-token"


@patch("post_instagram.requests.post")
def test_post_to_instagram_raises_on_api_error(mock_post):
    mock_post.return_value = MagicMock(
        status_code=400,
        json=lambda: {"error": {"message": "Invalid token"}},
    )

    try:
        post_to_instagram(
            image_url="https://raw.githubusercontent.com/phismith91/ig-tagesgeschichte/master/output/2026-07/20/01.png",
            caption="Testcaption",
            ig_user_id="28194940543437064",
            access_token="dummy-token",
        )
        assert False, "sollte RuntimeError werfen"
    except RuntimeError as e:
        assert "Invalid token" in str(e)


@patch("post_instagram.requests.post")
def test_post_to_instagram_raises_on_publish_error(mock_post):
    # Schritt 1 (/media) klappt, Schritt 2 (/media_publish) schlägt fehl.
    mock_post.side_effect = [
        MagicMock(status_code=200, json=lambda: {"id": "creation-123"}),
        MagicMock(status_code=400, json=lambda: {"error": {"message": "Publish failed"}}),
    ]

    try:
        post_to_instagram(
            image_url="https://raw.githubusercontent.com/phismith91/ig-tagesgeschichte/master/output/2026-07/20/01.png",
            caption="Testcaption",
            ig_user_id="28194940543437064",
            access_token="dummy-token",
        )
        assert False, "sollte RuntimeError werfen"
    except RuntimeError as e:
        assert "Publish failed" in str(e)


@patch("post_instagram.requests.post")
def test_post_to_instagram_raises_with_raw_text_on_non_json_error_body(mock_post):
    # Manche Fehlerantworten (z.B. Gateway-Timeout, HTML-Error-Page) sind kein JSON.
    def _raise_value_error():
        raise ValueError("not JSON")

    mock_post.return_value = MagicMock(
        status_code=502,
        json=_raise_value_error,
        text="<html>Bad Gateway</html>",
    )

    try:
        post_to_instagram(
            image_url="https://raw.githubusercontent.com/phismith91/ig-tagesgeschichte/master/output/2026-07/20/01.png",
            caption="Testcaption",
            ig_user_id="28194940543437064",
            access_token="dummy-token",
        )
        assert False, "sollte RuntimeError werfen"
    except RuntimeError as e:
        assert "Bad Gateway" in str(e)


@patch("post_instagram.requests.post")
def test_post_to_instagram_passes_timeout(mock_post):
    mock_post.side_effect = [
        MagicMock(status_code=200, json=lambda: {"id": "creation-123"}),
        MagicMock(status_code=200, json=lambda: {"id": "media-456"}),
    ]

    post_to_instagram(
        image_url="https://raw.githubusercontent.com/phismith91/ig-tagesgeschichte/master/output/2026-07/20/01.png",
        caption="Testcaption",
        ig_user_id="28194940543437064",
        access_token="dummy-token",
    )

    for call in mock_post.call_args_list:
        assert call.kwargs["timeout"] == 15


from post_instagram import post_carousel_to_instagram


@patch("post_instagram.requests.post")
def test_post_carousel_with_multiple_slides(mock_post):
    # 3 Kind-Container, dann Carousel-Container, dann Publish
    mock_post.side_effect = [
        MagicMock(status_code=200, json=lambda: {"id": "child-1"}),
        MagicMock(status_code=200, json=lambda: {"id": "child-2"}),
        MagicMock(status_code=200, json=lambda: {"id": "child-3"}),
        MagicMock(status_code=200, json=lambda: {"id": "carousel-container"}),
        MagicMock(status_code=200, json=lambda: {"id": "media-final"}),
    ]

    media_id = post_carousel_to_instagram(
        image_urls=["https://example.com/1.png", "https://example.com/2.png", "https://example.com/3.png"],
        caption="Testcaption",
        ig_user_id="28194940543437064",
        access_token="dummy-token",
    )

    assert media_id == "media-final"
    assert mock_post.call_count == 5

    for i, call in enumerate(mock_post.call_args_list[:3]):
        assert call.args[0] == "https://graph.instagram.com/v21.0/28194940543437064/media"
        assert call.kwargs["data"]["image_url"] == f"https://example.com/{i + 1}.png"
        assert call.kwargs["data"]["is_carousel_item"] == "true"
        assert "caption" not in call.kwargs["data"]

    carousel_call = mock_post.call_args_list[3]
    assert carousel_call.args[0] == "https://graph.instagram.com/v21.0/28194940543437064/media"
    assert carousel_call.kwargs["data"]["media_type"] == "CAROUSEL"
    assert carousel_call.kwargs["data"]["children"] == "child-1,child-2,child-3"
    assert carousel_call.kwargs["data"]["caption"] == "Testcaption"

    publish_call = mock_post.call_args_list[4]
    assert publish_call.args[0] == "https://graph.instagram.com/v21.0/28194940543437064/media_publish"
    assert publish_call.kwargs["data"]["creation_id"] == "carousel-container"


@patch("post_instagram.requests.post")
def test_post_carousel_skips_failed_slide_but_continues(mock_post):
    # Slide 2 schlägt fehl (Kind-Container-Erstellung), Rest läuft normal weiter.
    mock_post.side_effect = [
        MagicMock(status_code=200, json=lambda: {"id": "child-1"}),
        MagicMock(status_code=400, json=lambda: {"error": {"message": "slide 2 broken"}}),
        MagicMock(status_code=200, json=lambda: {"id": "child-3"}),
        MagicMock(status_code=200, json=lambda: {"id": "carousel-container"}),
        MagicMock(status_code=200, json=lambda: {"id": "media-final"}),
    ]

    media_id = post_carousel_to_instagram(
        image_urls=["https://example.com/1.png", "https://example.com/2.png", "https://example.com/3.png"],
        caption="Testcaption",
        ig_user_id="28194940543437064",
        access_token="dummy-token",
    )

    assert media_id == "media-final"
    carousel_call = mock_post.call_args_list[3]
    assert carousel_call.kwargs["data"]["children"] == "child-1,child-3"


@patch("post_instagram.requests.post")
def test_post_carousel_falls_back_to_single_image_when_only_one_slide_succeeds(mock_post):
    # 2 von 3 Kind-Containern schlagen fehl -> nur 1 Slide übrig -> normaler Einzelbild-Post
    # (NICHT der schon erstellte Kind-Container, da der ohne caption erstellt wurde).
    mock_post.side_effect = [
        MagicMock(status_code=200, json=lambda: {"id": "child-1"}),
        MagicMock(status_code=400, json=lambda: {"error": {"message": "broken"}}),
        MagicMock(status_code=400, json=lambda: {"error": {"message": "broken"}}),
        MagicMock(status_code=200, json=lambda: {"id": "single-container"}),
        MagicMock(status_code=200, json=lambda: {"id": "media-final"}),
    ]

    media_id = post_carousel_to_instagram(
        image_urls=["https://example.com/1.png", "https://example.com/2.png", "https://example.com/3.png"],
        caption="Testcaption",
        ig_user_id="28194940543437064",
        access_token="dummy-token",
    )

    assert media_id == "media-final"
    assert mock_post.call_count == 5

    fallback_call = mock_post.call_args_list[3]
    assert fallback_call.kwargs["data"]["image_url"] == "https://example.com/1.png"
    assert fallback_call.kwargs["data"]["caption"] == "Testcaption"
    assert "is_carousel_item" not in fallback_call.kwargs["data"]
    assert "media_type" not in fallback_call.kwargs["data"]


@patch("post_instagram.requests.post")
def test_post_carousel_fallback_uses_actual_survivor_not_first_url(mock_post):
    # Slide 1 und 3 schlagen fehl, nur Slide 2 überlebt -> Fallback MUSS die URL von
    # Slide 2 benutzen, nicht image_urls[0] (Regressionstest für den Bug, bei dem
    # hartkodiert immer die erste URL gepostet wurde, egal welcher Slide überlebte).
    mock_post.side_effect = [
        MagicMock(status_code=400, json=lambda: {"error": {"message": "broken"}}),
        MagicMock(status_code=200, json=lambda: {"id": "child-2"}),
        MagicMock(status_code=400, json=lambda: {"error": {"message": "broken"}}),
        MagicMock(status_code=200, json=lambda: {"id": "single-container"}),
        MagicMock(status_code=200, json=lambda: {"id": "media-final"}),
    ]

    media_id = post_carousel_to_instagram(
        image_urls=["https://example.com/1.png", "https://example.com/2.png", "https://example.com/3.png"],
        caption="Testcaption",
        ig_user_id="28194940543437064",
        access_token="dummy-token",
    )

    assert media_id == "media-final"
    assert mock_post.call_count == 5

    fallback_call = mock_post.call_args_list[3]
    assert fallback_call.kwargs["data"]["image_url"] == "https://example.com/2.png"
    assert fallback_call.kwargs["data"]["caption"] == "Testcaption"


@patch("post_instagram.requests.post")
def test_post_carousel_raises_when_all_slides_fail(mock_post):
    mock_post.side_effect = [
        MagicMock(status_code=400, json=lambda: {"error": {"message": "broken"}}),
        MagicMock(status_code=400, json=lambda: {"error": {"message": "broken"}}),
    ]

    try:
        post_carousel_to_instagram(
            image_urls=["https://example.com/1.png", "https://example.com/2.png"],
            caption="Testcaption",
            ig_user_id="28194940543437064",
            access_token="dummy-token",
        )
        assert False, "sollte RuntimeError werfen"
    except RuntimeError as e:
        assert "kein Slide" in str(e) or "0 von" in str(e)
