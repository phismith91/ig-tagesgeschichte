import logging
from unittest.mock import patch

import smtplib

import notify


def test_load_smtp_config_reads_env(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SMTP_HOST=smtp.example.com\n"
        "SMTP_PORT=587\n"
        "SMTP_USER=user@example.com\n"
        "SMTP_PASSWORD=secret\n"
        "SMTP_FROM=from@example.com\n"
        "NOTIFY_EMAIL_TO=to@example.com\n"
    )
    monkeypatch.chdir(tmp_path)
    config = notify.load_smtp_config()
    assert config["host"] == "smtp.example.com"
    assert config["port"] == 587
    assert config["to"] == "to@example.com"


def test_load_smtp_config_uses_default_recipient(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SMTP_HOST=smtp.example.com\n"
        "SMTP_PORT=587\n"
        "SMTP_USER=user@example.com\n"
        "SMTP_PASSWORD=secret\n"
        "SMTP_FROM=from@example.com\n"
    )
    monkeypatch.chdir(tmp_path)
    config = notify.load_smtp_config()
    assert config["to"] == "philippdschmidt@outlook.com"


def test_load_smtp_config_returns_none_when_missing():
    assert notify.load_smtp_config("nonexistent.env") is None


def test_load_smtp_config_returns_none_for_invalid_port(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SMTP_HOST=smtp.example.com\n"
        "SMTP_PORT=not-a-number\n"
        "SMTP_USER=user@example.com\n"
        "SMTP_PASSWORD=secret\n"
        "SMTP_FROM=from@example.com\n"
    )
    monkeypatch.chdir(tmp_path)
    assert notify.load_smtp_config() is None


@patch("notify.smtplib.SMTP")
def test_send_email_sends_correctly(mock_smtp):
    config = {
        "host": "smtp.example.com",
        "port": 587,
        "user": "user@example.com",
        "password": "secret",
        "from": "from@example.com",
        "to": "to@example.com",
    }
    notify.send_email("Test Subject", "Test Body", config)

    mock_smtp.assert_called_once_with("smtp.example.com", 587)
    server = mock_smtp.return_value.__enter__.return_value
    server.starttls.assert_called_once()
    server.login.assert_called_once_with("user@example.com", "secret")
    server.send_message.assert_called_once()
    mock_smtp.return_value.__exit__.assert_called_once()


def test_notify_post_success_builds_email():
    with patch("notify.send_email") as mock_send, patch("notify.load_smtp_config") as mock_load:
        mock_load.return_value = {"to": "to@example.com", "from": "from@example.com"}
        notify.notify_post_result("2026-07-25", success=True, media_id="media-123", image_count=5)
        mock_send.assert_called_once()
        subject, body, _ = mock_send.call_args[0]
        assert "erfolgreich" in subject.lower()
        assert "media-123" in body


def test_notify_post_failure_builds_email():
    with patch("notify.send_email") as mock_send, patch("notify.load_smtp_config") as mock_load:
        mock_load.return_value = {"to": "to@example.com", "from": "from@example.com"}
        notify.notify_post_result("2026-07-25", success=False, error="Token invalid", step="media_publish")
        mock_send.assert_called_once()
        subject, body, _ = mock_send.call_args[0]
        assert "fehlgeschlagen" in subject.lower()
        assert "Token invalid" in body


def test_notify_post_logs_warning_when_config_missing(caplog):
    with patch("notify.load_smtp_config", return_value=None):
        with caplog.at_level(logging.WARNING):
            notify.notify_post_result("2026-07-25", success=True)
    assert "SMTP nicht konfiguriert" in caplog.text


@patch("notify.smtplib.SMTP_SSL")
def test_send_email_uses_ssl_on_port_465(mock_smtp_ssl):
    config = {
        "host": "mail.your-server.de",
        "port": 465,
        "user": "software@withphil.de",
        "password": "secret",
        "from": "software@withphil.de",
        "to": "to@example.com",
    }
    notify.send_email("Test Subject", "Test Body", config)

    mock_smtp_ssl.assert_called_once_with("mail.your-server.de", 465)
    server = mock_smtp_ssl.return_value.__enter__.return_value
    server.login.assert_called_once_with("software@withphil.de", "secret")
    server.send_message.assert_called_once()
    server.starttls.assert_not_called()


def test_notify_post_catches_smtp_exception():
    with patch("notify.send_email", side_effect=smtplib.SMTPException("boom")), patch("notify.load_smtp_config") as mock_load:
        mock_load.return_value = {"to": "to@example.com", "from": "from@example.com"}
        notify.notify_post_result("2026-07-25", success=True)


def test_notify_post_catches_oserror():
    with patch("notify.send_email", side_effect=OSError("dns failure")), patch("notify.load_smtp_config") as mock_load:
        mock_load.return_value = {"to": "to@example.com", "from": "from@example.com"}
        notify.notify_post_result("2026-07-25", success=True)
