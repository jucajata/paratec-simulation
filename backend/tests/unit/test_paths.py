from pathlib import Path

import pytest

from sinsim.config import (
    INSTALLED_MODE,
    REPO_MODE,
    installed_paths,
    resolve_paths,
    user_data_dir,
)

REPO = Path(__file__).resolve().parents[3]


def test_sinsim_home_wins_over_the_platform_convention(tmp_path: Path):
    assert user_data_dir({"SINSIM_HOME": str(tmp_path)}, "darwin", Path("/u")) == tmp_path


@pytest.mark.parametrize(
    ("platform", "env", "expected"),
    [
        ("darwin", {}, Path("/u/Library/Application Support/sinsim")),
        ("linux", {}, Path("/u/.local/share/sinsim")),
        ("linux", {"XDG_DATA_HOME": "/x"}, Path("/x/sinsim")),
        ("win32", {"LOCALAPPDATA": "/l"}, Path("/l/sinsim")),
        ("win32", {}, Path("/u/AppData/Local/sinsim")),
    ],
)
def test_user_data_dir_follows_each_platform(platform: str, env: dict, expected: Path):
    assert user_data_dir(env, platform, Path("/u")) == expected


def bundled_tree(tmp_path: Path, *, demo: bool = True) -> Path:
    bundled = tmp_path / "_bundled"
    (bundled / "config").mkdir(parents=True)
    (bundled / "config" / "defaults.toml").write_text("", encoding="utf-8")
    if demo:
        (bundled / "paratec" / "2026-10-20").mkdir(parents=True)
    return bundled


def test_outside_the_repository_uses_the_package_and_the_user_folder(tmp_path: Path):
    bundled = bundled_tree(tmp_path)
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<html></html>", encoding="utf-8")
    home = tmp_path / "home"
    paths = resolve_paths(
        tmp_path, search_package=False, bundled=bundled, web=web, env={"SINSIM_HOME": str(home)}
    )
    assert paths.mode == INSTALLED_MODE
    assert paths.config_file == bundled / "config" / "defaults.toml"
    assert paths.equivalences == bundled / "equivalencias"
    assert paths.geo == bundled / "geo"
    assert paths.snapshots == home / "paratec"
    assert paths.cases == home / "cases"
    assert paths.bundled_snapshots == (bundled / "paratec",)
    assert paths.web == web


def test_installed_mode_without_interface_or_demo_snapshot(tmp_path: Path):
    paths = installed_paths(tmp_path / "home", bundled_tree(tmp_path, demo=False), tmp_path / "x")
    assert paths.web is None
    assert paths.bundled_snapshots == ()


def test_without_repository_or_package_resources_explains_what_to_do(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="reinstala sinsim"):
        resolve_paths(tmp_path, search_package=False, bundled=tmp_path / "nada")


def test_inside_the_repository_nothing_changes():
    paths = resolve_paths(REPO / "backend", search_package=False)
    assert paths.mode == REPO_MODE
    assert paths.root == REPO
    assert paths.snapshots == REPO / "data" / "paratec"
    assert paths.equivalences == REPO / "data" / "equivalencias"
    assert paths.cases == REPO / "cases"
    assert paths.bundled_snapshots == ()
