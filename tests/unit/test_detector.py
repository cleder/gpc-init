"""Unit tests for gpc_init/detector.py."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from gpc_init import detector as _detector
from gpc_init.detector import detect_frameworks, detect_languages

ALL_LANGS = [
    "docker",
    "go",
    "img",
    "js",
    "md",
    "nb",
    "py",
    "r",
    "ru",
    "sh",
    "sql",
    "tf",
    "toml",
    "ts",
    "yaml",
]
ALL_FRAMEWORKS = ["django", "git", "k8s", "react", "sphinx"]


class TestDetectLanguages:
    def test_detects_python_by_extension(self, tmp_path: Path) -> None:
        (tmp_path / "main.py").touch()
        assert "py" in detect_languages(tmp_path, ALL_LANGS)

    def test_detects_multiple_languages(self, tmp_path: Path) -> None:
        (tmp_path / "main.py").touch()
        (tmp_path / "index.ts").touch()
        (tmp_path / "main.go").touch()
        result = detect_languages(tmp_path, ALL_LANGS)
        assert "py" in result
        assert "ts" in result
        assert "go" in result

    def test_detects_dockerfile_by_filename(self, tmp_path: Path) -> None:
        (tmp_path / "Dockerfile").touch()
        assert "docker" in detect_languages(tmp_path, ALL_LANGS)

    def test_detects_dockerfile_case_insensitive(self, tmp_path: Path) -> None:
        (tmp_path / "dockerfile").touch()
        assert "docker" in detect_languages(tmp_path, ALL_LANGS)

    def test_detects_rust_by_rs_extension(self, tmp_path: Path) -> None:
        (tmp_path / "lib.rs").touch()
        assert "ru" in detect_languages(tmp_path, ALL_LANGS)

    def test_detects_markdown(self, tmp_path: Path) -> None:
        (tmp_path / "README.md").touch()
        assert "md" in detect_languages(tmp_path, ALL_LANGS)

    def test_detects_yaml(self, tmp_path: Path) -> None:
        (tmp_path / "config.yaml").touch()
        assert "yaml" in detect_languages(tmp_path, ALL_LANGS)

    def test_detects_yaml_yml_extension(self, tmp_path: Path) -> None:
        (tmp_path / "config.yml").touch()
        assert "yaml" in detect_languages(tmp_path, ALL_LANGS)

    def test_detects_notebook(self, tmp_path: Path) -> None:
        (tmp_path / "analysis.ipynb").touch()
        assert "nb" in detect_languages(tmp_path, ALL_LANGS)

    def test_detects_terraform(self, tmp_path: Path) -> None:
        (tmp_path / "main.tf").touch()
        assert "tf" in detect_languages(tmp_path, ALL_LANGS)

    def test_detects_image_files(self, tmp_path: Path) -> None:
        (tmp_path / "logo.png").touch()
        assert "img" in detect_languages(tmp_path, ALL_LANGS)

    def test_skips_node_modules(self, tmp_path: Path) -> None:
        nm = tmp_path / "node_modules"
        nm.mkdir()
        (nm / "index.js").touch()
        assert "js" not in detect_languages(tmp_path, ALL_LANGS)

    def test_skips_git_dir(self, tmp_path: Path) -> None:
        git = tmp_path / ".git"
        git.mkdir()
        (git / "COMMIT_EDITMSG").write_text("message")
        # No lang file there, but confirm dir is skipped (no crash, empty result)
        result = detect_languages(tmp_path, ALL_LANGS)
        assert isinstance(result, list)

    def test_skips_pycache(self, tmp_path: Path) -> None:
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "mod.pyc").touch()
        assert "py" not in detect_languages(tmp_path, ALL_LANGS)

    def test_skips_venv(self, tmp_path: Path) -> None:
        venv = tmp_path / ".venv"
        venv.mkdir()
        (venv / "script.py").touch()
        assert "py" not in detect_languages(tmp_path, ALL_LANGS)

    def test_only_returns_supported_langs(self, tmp_path: Path) -> None:
        (tmp_path / "main.py").touch()
        (tmp_path / "index.ts").touch()
        result = detect_languages(tmp_path, ["py"])
        assert result == ["py"]
        assert "ts" not in result

    def test_deduplicates_results(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").touch()
        (tmp_path / "b.py").touch()
        result = detect_languages(tmp_path, ALL_LANGS)
        assert result.count("py") == 1

    def test_empty_directory_returns_empty(self, tmp_path: Path) -> None:
        assert detect_languages(tmp_path, ALL_LANGS) == []

    def test_detects_in_subdirectory(self, tmp_path: Path) -> None:
        sub = tmp_path / "src"
        sub.mkdir()
        (sub / "app.py").touch()
        assert "py" in detect_languages(tmp_path, ALL_LANGS)

    def test_jsx_maps_to_js(self, tmp_path: Path) -> None:
        (tmp_path / "Component.jsx").touch()
        assert "js" in detect_languages(tmp_path, ALL_LANGS)

    def test_tsx_maps_to_ts(self, tmp_path: Path) -> None:
        (tmp_path / "Component.tsx").touch()
        assert "ts" in detect_languages(tmp_path, ALL_LANGS)

    def test_bash_extension_maps_to_sh(self, tmp_path: Path) -> None:
        (tmp_path / "deploy.bash").touch()
        assert "sh" in detect_languages(tmp_path, ALL_LANGS)


class TestDetectFrameworks:
    def test_detects_django_by_manage_py(self, tmp_path: Path) -> None:
        (tmp_path / "manage.py").touch()
        assert "django" in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    def test_no_django_without_manage_py(self, tmp_path: Path) -> None:
        assert "django" not in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    def test_detects_react_from_package_json(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text(
            json.dumps({"dependencies": {"react": "^18.0.0"}}),
            encoding="utf-8",
        )
        assert "react" in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    def test_detects_react_from_dev_dependencies(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text(
            json.dumps({"devDependencies": {"react": "^18.0.0"}}),
            encoding="utf-8",
        )
        assert "react" in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    def test_no_react_without_react_dep(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text(
            json.dumps({"dependencies": {"lodash": "^4.0.0"}}),
            encoding="utf-8",
        )
        assert "react" not in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    def test_no_react_without_package_json(self, tmp_path: Path) -> None:
        assert "react" not in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    def test_detects_sphinx_from_root_conf_py(self, tmp_path: Path) -> None:
        (tmp_path / "conf.py").write_text(
            "extensions = ['sphinx.ext.autodoc']", encoding="utf-8"
        )
        assert "sphinx" in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    def test_detects_sphinx_from_docs_conf_py(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "conf.py").write_text(
            "extensions = ['sphinx.ext.autodoc']", encoding="utf-8"
        )
        assert "sphinx" in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    def test_no_sphinx_from_conf_py_without_sphinx(self, tmp_path: Path) -> None:
        (tmp_path / "conf.py").write_text("# just a config file", encoding="utf-8")
        assert "sphinx" not in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    def test_detects_sphinx_from_conf_py_with_invalid_utf8_bytes(
        self, tmp_path: Path
    ) -> None:
        # Write raw bytes: valid ASCII content containing "sphinx" with an
        # embedded invalid UTF-8 byte (0xFF).  errors="ignore" silently drops
        # the bad byte; errors="IGNORE" (wrong case) would raise LookupError.
        (tmp_path / "conf.py").write_bytes(b"sphinx\xff extensions")
        assert "sphinx" in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    def test_detects_k8s_from_yaml_with_apiversion_and_kind(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "deployment.yaml").write_text(
            "apiVersion: apps/v1\nkind: Deployment\n", encoding="utf-8"
        )
        assert "k8s" in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    def test_no_k8s_from_yaml_without_apiversion(self, tmp_path: Path) -> None:
        (tmp_path / "config.yaml").write_text("key: value\n", encoding="utf-8")
        assert "k8s" not in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    def test_github_actions_yaml_does_not_trigger_k8s(self, tmp_path: Path) -> None:
        workflows = tmp_path / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "ci.yml").write_text(
            "apiVersion: v1\nkind: fake\n", encoding="utf-8"
        )
        assert "k8s" not in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    def test_detects_git_framework_from_github_workflows(self, tmp_path: Path) -> None:
        workflows = tmp_path / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "ci.yml").touch()
        assert "git" in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    def test_no_git_framework_without_workflows_dir(self, tmp_path: Path) -> None:
        (tmp_path / ".github").mkdir()
        assert "git" not in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    def test_no_git_framework_without_yml_files(self, tmp_path: Path) -> None:
        workflows = tmp_path / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "README.md").touch()
        assert "git" not in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    def test_only_returns_supported_frameworks(self, tmp_path: Path) -> None:
        (tmp_path / "manage.py").touch()
        workflows = tmp_path / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "ci.yml").touch()
        result = detect_frameworks(tmp_path, ["django"])
        assert result == ["django"]
        assert "git" not in result

    def test_empty_directory_returns_empty(self, tmp_path: Path) -> None:
        assert detect_frameworks(tmp_path, ALL_FRAMEWORKS) == []

    # --- Tests targeting surviving mutants ---

    # mutmut_9: encoding=None instead of encoding="utf-8" in _has_package_json_dep
    def test_reads_package_json_with_utf8_encoding(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").touch()

        recorded: dict = {}

        def _mock_read_text(_self: Path, **kwargs: Any) -> str:
            recorded.update(kwargs)
            return json.dumps({"dependencies": {"react": "^18.0.0"}})

        with patch.object(Path, "read_text", _mock_read_text):
            detect_frameworks(tmp_path, ["react"])

        assert recorded.get("encoding") == "utf-8"

    # mutmut_12: return True instead of return False in
    # _has_package_json_dep except block
    def test_no_react_when_package_json_is_invalid_json(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{ invalid json !!!", encoding="utf-8")
        assert "react" not in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    # mutmut_14: encoding=None instead of encoding="utf-8" in _has_sphinx_conf
    def test_sphinx_conf_reads_file_with_utf8_encoding(self, tmp_path: Path) -> None:
        conf = tmp_path / "conf.py"
        conf.write_text("extensions = ['sphinx.ext.autodoc']", encoding="utf-8")

        _original_read_text = Path.read_text
        read_text_encodings: list[str | None] = []

        def tracking_read_text(self: Path, *args: Any, **kwargs: Any) -> str:
            read_text_encodings.append(kwargs.get("encoding"))
            return _original_read_text(self, *args, **kwargs)  # type: ignore[arg-type]

        with patch.object(Path, "read_text", tracking_read_text):
            result = detect_frameworks(tmp_path, ALL_FRAMEWORKS)

        assert "sphinx" in result
        assert len(read_text_encodings) >= 1
        assert read_text_encodings[0] is not None
        assert read_text_encodings[0].casefold() == "utf-8"

    # mutmut_15 and mutmut_17: errors=None or errors removed in _has_sphinx_conf
    # (note: mutmut_21 test already exists above as
    # test_detects_sphinx_from_conf_py_with_invalid_utf8_bytes)
    def test_detects_sphinx_from_conf_py_with_invalid_utf8_bytes_15(
        self, tmp_path: Path
    ) -> None:
        # conf.py contains "sphinx" but also invalid UTF-8 bytes; errors="ignore"
        # must silently skip them rather than raising UnicodeDecodeError.
        conf = tmp_path / "conf.py"
        conf.write_bytes(b"extensions = ['sphinx.ext.autodoc']\n\xff\xfe")
        assert "sphinx" in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    def test_sphinx_conf_with_invalid_utf8_bytes_does_not_raise(
        self, tmp_path: Path
    ) -> None:
        # Write a conf.py that contains invalid UTF-8 bytes mixed with "sphinx"
        conf = tmp_path / "conf.py"
        conf.write_bytes(b"sphinx\xff\xfe extensions = []")
        assert "sphinx" in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    # mutmut_10: ".yml" replaced with "XX.ymlXX" in _has_kubernetes_files extension set
    def test_detects_k8s_from_yml_extension(self, tmp_path: Path) -> None:
        (tmp_path / "service.yml").write_text(
            "apiVersion: v1\nkind: Service\n", encoding="utf-8"
        )
        assert "k8s" in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    # mutmut_12: continue changed to break when non-YAML file encountered
    # in _has_kubernetes_files
    def test_detects_k8s_when_non_yaml_files_also_present(self, tmp_path: Path) -> None:
        # Place several non-YAML files alongside a Kubernetes manifest.
        # With 'break' instead of 'continue', iterating a non-YAML file first
        # would exit the loop prematurely and miss the k8s manifest.
        (tmp_path / "README.md").write_text("docs", encoding="utf-8")
        (tmp_path / "main.py").write_text("print('hello')", encoding="utf-8")
        (tmp_path / "Makefile").write_text("all:", encoding="utf-8")
        (tmp_path / "deployment.yaml").write_text(
            "apiVersion: apps/v1\nkind: Deployment\n", encoding="utf-8"
        )
        assert "k8s" in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    # mutmut_14: continue changed to break when .github file encountered
    # in _has_kubernetes_files
    def test_k8s_detected_alongside_github_actions_yaml(self, tmp_path: Path) -> None:
        # A GitHub Actions workflow that looks like k8s — must be skipped.
        workflows = tmp_path / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "ci.yml").write_text(
            "apiVersion: v1\nkind: fake\n", encoding="utf-8"
        )
        # A real Kubernetes manifest outside .github — must still be found.
        (tmp_path / "deployment.yaml").write_text(
            "apiVersion: apps/v1\nkind: Deployment\n", encoding="utf-8"
        )
        assert "k8s" in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    # mutmut_17, mutmut_19, mutmut_22, mutmut_23: errors="ignore" changed/removed
    # in _has_kubernetes_files file.read_text call
    def test_detects_k8s_from_yaml_with_invalid_utf8_bytes(
        self, tmp_path: Path
    ) -> None:
        # Write raw bytes: valid ASCII Kubernetes content with an embedded
        # invalid UTF-8 byte (0xFF). errors="ignore" silently drops the bad
        # byte; without it a UnicodeDecodeError or LookupError would propagate.
        (tmp_path / "deployment.yaml").write_bytes(
            b"apiVersion: apps/v1\nkind: Deployment\n\xff"
        )
        assert "k8s" in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    # mutmut_24: continue changed to break in OSError handler in _has_kubernetes_files
    def test_k8s_detected_when_oserror_yaml_precedes_valid_k8s_yaml(
        self, tmp_path: Path
    ) -> None:
        unreadable = tmp_path / "unreadable.yaml"
        unreadable.write_text("dummy", encoding="utf-8")

        valid_k8s = tmp_path / "k8s.yaml"
        valid_k8s.write_text(
            "apiVersion: apps/v1\nkind: Deployment\n", encoding="utf-8"
        )

        with patch.object(
            _detector,
            "_walk",
            return_value=iter([unreadable, valid_k8s]),
        ):
            # Simulate OSError for the first file by making it unreadable
            unreadable.chmod(0o000)
            try:
                assert "k8s" in detect_frameworks(tmp_path, ALL_FRAMEWORKS)
            finally:
                unreadable.chmod(0o644)

    # mutmut_25: "and" changed to "or" in apiVersion+kind check in _has_kubernetes_files
    def test_no_k8s_from_yaml_with_only_kind(self, tmp_path: Path) -> None:
        (tmp_path / "config.yaml").write_text("kind: SomeValue\n", encoding="utf-8")
        assert "k8s" not in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    # mutmut_13 and mutmut_14 (_has_github_workflows): ".yaml" replaced with
    # "XX.yamlXX" or ".YAML" in extension set
    def test_detects_git_framework_from_github_workflows_yaml_extension(
        self, tmp_path: Path
    ) -> None:
        workflows = tmp_path / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "ci.yaml").touch()
        assert "git" in detect_frameworks(tmp_path, ALL_FRAMEWORKS)
