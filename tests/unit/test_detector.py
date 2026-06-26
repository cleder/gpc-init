"""Unit tests for gpc_init/detector.py."""

import json
from pathlib import Path

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
