from obsidian_postit_kde.config import Config


def test_defaults():
    cfg = Config()
    assert cfg.default_destination == "daily"
    assert cfg.subfolder == "PostIt"
    assert cfg.default_tags == ["postit"]
    assert cfg.vault_is_valid() is False
    assert cfg.speech_enabled is False


def test_save_load_roundtrip(tmp_path):
    path = tmp_path / "config.toml"
    cfg = Config(
        vault_path=str(tmp_path / "vault"),
        default_tags=["postit", "idea"],
        add_title_slug=False,
        autostart=True,
        speech_enabled=True,
        speech_model="small",
        speech_language="fr",
        speech_clean_with_openrouter=True,
    )
    cfg.save(path)
    assert path.is_file()
    loaded = Config.load(path)
    assert loaded.vault_path == str(tmp_path / "vault")
    assert loaded.default_tags == ["postit", "idea"]
    assert loaded.add_title_slug is False
    assert loaded.autostart is True
    assert (loaded.speech_enabled, loaded.speech_model, loaded.speech_language) == (
        True, "small", "fr"
    )
    assert loaded.speech_clean_with_openrouter is True


def test_load_missing_returns_defaults(tmp_path):
    loaded = Config.load(tmp_path / "nope.toml")
    assert loaded.subfolder == "PostIt"


def test_derived_paths(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    cfg = Config(vault_path=str(vault))
    assert cfg.vault_is_valid() is True
    assert cfg.postit_dir() == vault / "PostIt"
    daily = cfg.daily_file()
    assert daily.parent == vault / "Daily"
    assert daily.name.endswith("-daily-note.md")


def test_ignores_unknown_keys(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('vault_path = "/x"\nbogus_key = "y"\n', encoding="utf-8")
    loaded = Config.load(path)
    assert loaded.vault_path == "/x"
    assert not hasattr(loaded, "bogus_key")
