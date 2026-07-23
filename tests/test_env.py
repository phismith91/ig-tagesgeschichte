import env


def test_load_env_var_reads_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("IG_USER_ID=28194940543437064\nMETA_ACCESS_TOKEN=dummy-token\n")
    monkeypatch.chdir(tmp_path)
    assert env.load_env_var("IG_USER_ID") == "28194940543437064"
    assert env.load_env_var("META_ACCESS_TOKEN") == "dummy-token"


def test_load_env_var_missing_file_returns_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert env.load_env_var("IG_USER_ID") is None


def test_load_env_var_missing_key_returns_none(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("SOME_OTHER_KEY=x\n")
    monkeypatch.chdir(tmp_path)
    assert env.load_env_var("IG_USER_ID") is None


def test_load_env_var_empty_value_returns_none(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("IG_USER_ID=\n")
    monkeypatch.chdir(tmp_path)
    assert env.load_env_var("IG_USER_ID") is None
