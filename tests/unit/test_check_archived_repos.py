"""Tests for scripts/check_archived_repos.py."""

import importlib.util
import json
import urllib.error
import urllib.request
from email.message import Message
from pathlib import Path
from types import ModuleType
from typing import Any, Self

import pytest

SCRIPT = Path(__file__).parents[2] / "scripts" / "check_archived_repos.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_archived_repos", SCRIPT)
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


car = _load()


class _Response:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._data = json.dumps(payload).encode()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self, *_: object) -> bytes:
        return self._data


class _FakeUrlopen:
    """Stand-in for urlopen that records the request it received."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.request: urllib.request.Request | None = None

    def __call__(
        self,
        request: urllib.request.Request,
        timeout: int,  # noqa: ARG002
    ) -> _Response:
        self.request = request
        return _Response(self.payload)


def _fake_urlopen(payload: dict[str, Any]) -> _FakeUrlopen:
    return _FakeUrlopen(payload)


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("url", code, "err", Message(), None)


class TestGithubUrl:
    @pytest.mark.parametrize(
        "url",
        [
            "https://github.com/astral-sh/ruff-pre-commit",
            "https://github.com/astral-sh/ruff-pre-commit.git",
            "https://github.com/astral-sh/ruff-pre-commit/",
        ],
    )
    def test_matches_and_normalises(self, url: str) -> None:
        match = car.GITHUB_URL.match(url)
        assert match
        assert match.group(1) == "astral-sh/ruff-pre-commit"

    @pytest.mark.parametrize(
        "url",
        ["local", "meta", "https://gitlab.com/a/b", "https://github.com/a", ""],
    )
    def test_rejects_non_github(self, url: str) -> None:
        assert car.GITHUB_URL.match(url) is None


class TestPresetSlugs:
    def test_extracts_only_github_repos(self, tmp_path: Path) -> None:
        preset = tmp_path / "preset.yaml"
        preset.write_text(
            "repos:\n"
            "  - repo: https://github.com/a/one\n"
            "  - repo: local\n"
            "  - repo: https://gitlab.com/x/y\n"
            "  - repo: https://github.com/b/two.git\n",
            encoding="utf-8",
        )
        assert car.preset_slugs(preset) == ["a/one", "b/two"]

    def test_empty_and_repoless_files(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty.yaml"
        empty.write_text("", encoding="utf-8")
        recommended = tmp_path / "rec.yaml"
        recommended.write_text("recommended:\n  lang: [js]\n", encoding="utf-8")
        assert car.preset_slugs(empty) == []
        assert car.preset_slugs(recommended) == []


class TestInsecureUrls:
    def test_flags_non_https(self) -> None:
        urls = [
            "https://github.com/a/b",
            "local",
            "meta",
            "git@github.com:a/b.git",
            "http://github.com/a/b",
            "git://github.com/a/b",
            "ssh://git@github.com/a/b",
            "",
        ]
        assert car.insecure_urls(urls) == urls[3:]

    def test_collect_insecure_reports_preset(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "lang/py/preset.yaml"
        path.parent.mkdir(parents=True)
        path.write_text(
            "repos:\n  - repo: git@github.com:a/b.git\n  - repo: local\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(car, "PROJECT_ROOT", tmp_path)
        assert car.collect_insecure() == ["lang/py/preset.yaml: git@github.com:a/b.git"]

    def test_real_catalog_is_https_only(self) -> None:
        assert car.collect_insecure() == []


class TestCollectRepos:
    def test_groups_presets_by_repo(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for rel, repo in [
            ("lang/py/preset.yaml", "a/shared"),
            ("framework/django/preset.yaml", "a/shared"),
            ("lang/go/preset-extra.yaml", "b/only"),
        ]:
            path = tmp_path / rel
            path.parent.mkdir(parents=True)
            path.write_text(
                f"repos:\n  - repo: https://github.com/{repo}\n", encoding="utf-8"
            )
        monkeypatch.setattr(car, "PROJECT_ROOT", tmp_path)
        repos = car.collect_repos()
        assert sorted(repos["a/shared"]) == [
            Path("framework/django/preset.yaml"),
            Path("lang/py/preset.yaml"),
        ]
        assert repos["b/only"] == [Path("lang/go/preset-extra.yaml")]


class TestRepoStatus:
    def test_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            car.urllib.request, "urlopen", _fake_urlopen({"archived": False})
        )
        assert car.repo_status("a/b", None) == "ok"

    def test_archived(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            car.urllib.request, "urlopen", _fake_urlopen({"archived": True})
        )
        assert car.repo_status("a/b", None) == "archived"

    @pytest.mark.parametrize("code", [404, 410])
    def test_missing(self, monkeypatch: pytest.MonkeyPatch, code: int) -> None:
        def raiser(*_: object, **__: object) -> None:
            raise _http_error(code)

        monkeypatch.setattr(car.urllib.request, "urlopen", raiser)
        assert car.repo_status("a/b", None) == "missing"

    def test_other_http_errors_propagate(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def raiser(*_: object, **__: object) -> None:
            raise _http_error(403)

        monkeypatch.setattr(car.urllib.request, "urlopen", raiser)
        with pytest.raises(urllib.error.HTTPError):
            car.repo_status("a/b", None)

    def test_token_sets_authorization_header(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        opener = _fake_urlopen({"archived": False})
        monkeypatch.setattr(car.urllib.request, "urlopen", opener)
        car.repo_status("a/b", "secret")
        assert opener.request
        assert opener.request.get_header("Authorization") == "Bearer secret"
        assert opener.request.full_url == "https://api.github.com/repos/a/b"

    def test_no_token_no_authorization_header(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        opener = _fake_urlopen({"archived": False})
        monkeypatch.setattr(car.urllib.request, "urlopen", opener)
        car.repo_status("a/b", None)
        assert opener.request
        assert not opener.request.has_header("Authorization")


class TestMain:
    @staticmethod
    def _setup(monkeypatch: pytest.MonkeyPatch, statuses: dict[str, str]) -> None:
        repos = {slug: [Path(f"lang/{slug}/preset.yaml")] for slug in statuses}
        monkeypatch.setattr(car, "collect_repos", lambda: repos)
        monkeypatch.setattr(car, "collect_insecure", list)

        def fake_status(slug: str, _token: str | None) -> str:
            return statuses[slug]

        monkeypatch.setattr(car, "repo_status", fake_status)

    def test_all_ok_exits_cleanly(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._setup(monkeypatch, {"a/b": "ok", "c/d": "ok"})
        car.main()
        assert "Checked 2 hook repositories." in capsys.readouterr().out

    def test_insecure_url_fails(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._setup(monkeypatch, {"a/b": "ok"})
        monkeypatch.setattr(
            car, "collect_insecure", lambda: ["lang/x/preset.yaml: ssh"]
        )
        with pytest.raises(SystemExit) as exc:
            car.main()
        assert exc.value.code == 1
        assert "NOT HTTPS lang/x/preset.yaml: ssh" in capsys.readouterr().out

    def test_problems_exit_1_and_are_listed(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        self._setup(monkeypatch, {"a/b": "ok", "c/d": "archived", "e/f": "missing"})
        with pytest.raises(SystemExit) as exc:
            car.main()
        assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "ARCHIVED" in out
        assert "c/d" in out
        assert "MISSING" in out
        assert "e/f" in out
        assert "a/b  (" not in out

    def test_token_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen: list[str | None] = []
        monkeypatch.setattr(car, "collect_repos", lambda: {"a/b": [Path("p")]})

        def fake_status(_slug: str, token: str | None) -> str:
            seen.append(token)
            return "ok"

        monkeypatch.setattr(car, "repo_status", fake_status)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.setenv("GH_TOKEN", "gh")
        car.main()
        monkeypatch.setenv("GITHUB_TOKEN", "primary")
        car.main()
        assert seen == ["gh", "primary"]


def test_real_presets_reference_github_repos() -> None:
    """Smoke test against the real catalog (no network)."""
    repos = car.collect_repos()
    assert len(repos) > 50
    assert all("/" in slug for slug in repos)
