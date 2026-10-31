import obsidian_postit_kde.autostart as autostart


def test_autostart_enable_disable(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert autostart.is_enabled() is False
    path = autostart.enable()
    assert path.is_file()
    assert autostart.is_enabled() is True
    text = path.read_text(encoding="utf-8")
    assert "[Desktop Entry]" in text
    assert "Exec=" in text
    autostart.disable()
    assert autostart.is_enabled() is False


def test_set_enabled_toggles(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    autostart.set_enabled(True)
    assert autostart.is_enabled() is True
    autostart.set_enabled(False)
    assert autostart.is_enabled() is False
