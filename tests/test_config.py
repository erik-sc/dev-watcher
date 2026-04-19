from pathlib import Path
from devwatcher.config import load_config, write_default_config, Config


def test_load_config_returns_defaults_when_no_file(tmp_config_path):
    config = load_config(config_path=tmp_config_path)
    assert config.general.idle_timeout_minutes == 5
    assert config.capture.git_commits is True
    assert config.ai.provider == "anthropic"
    assert config.ai.model == "claude-sonnet-4-6"


def test_load_config_reads_overrides_from_file(tmp_config_path):
    tmp_config_path.write_text(
        '[general]\nidle_timeout_minutes = 10\n', encoding="utf-8"
    )
    config = load_config(config_path=tmp_config_path)
    assert config.general.idle_timeout_minutes == 10
    assert config.capture.git_commits is True  # default preservado


def test_write_default_config_creates_parseable_file(tmp_config_path):
    write_default_config(config_path=tmp_config_path)
    assert tmp_config_path.exists()
    config = load_config(config_path=tmp_config_path)
    assert config.general.language == "pt-BR"
    assert config.capture.file_events is True


def test_watch_dirs_expanded_resolves_tilde(tmp_config_path):
    tmp_config_path.write_text(
        '[capture]\nwatch_dirs = ["~/Documents"]\n', encoding="utf-8"
    )
    config = load_config(config_path=tmp_config_path)
    expanded = config.watch_dirs_expanded
    assert len(expanded) == 1
    assert not str(expanded[0]).startswith("~")
