from unittest.mock import patch, MagicMock

from post_instagram import post_to_instagram


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
