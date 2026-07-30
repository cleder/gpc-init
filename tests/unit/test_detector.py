"""Unit tests for gpc_init/detector.py."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from gpc_init import detector as _detector
from gpc_init.detector import detect_frameworks, detect_languages

ALL_LANGS = [
    "cpp",
    "css",
    "docker",
    "env",
    "go",
    "groovy",
    "img",
    "js",
    "kt",
    "lua",
    "make",
    "md",
    "nb",
    "proto",
    "py",
    "r",
    "rb",
    "rs",
    "sh",
    "sql",
    "swift",
    "tf",
    "toml",
    "ts",
    "yaml",
]
ALL_FRAMEWORKS = [
    "ansible",
    "behave",
    "django",
    "git",
    "k8s",
    "nika",
    "react",
    "sphinx",
]


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

    def test_detects_makefile_by_filename(self, tmp_path: Path) -> None:
        (tmp_path / "Makefile").touch()
        assert "make" in detect_languages(tmp_path, ALL_LANGS)

    def test_detects_makefile_case_insensitive(self, tmp_path: Path) -> None:
        (tmp_path / "makefile").touch()
        assert "make" in detect_languages(tmp_path, ALL_LANGS)

    def test_detects_rust_by_rs_extension(self, tmp_path: Path) -> None:
        (tmp_path / "lib.rs").touch()
        assert "rs" in detect_languages(tmp_path, ALL_LANGS)

    def test_detects_ruby_by_rb_extension(self, tmp_path: Path) -> None:
        (tmp_path / "main.rb").touch()
        assert "rb" in detect_languages(tmp_path, ALL_LANGS)

    def test_detects_cpp_by_extension(self, tmp_path: Path) -> None:
        (tmp_path / "main.cpp").touch()
        assert "cpp" in detect_languages(tmp_path, ALL_LANGS)

    def test_detects_c_by_extension(self, tmp_path: Path) -> None:
        (tmp_path / "main.c").touch()
        assert "cpp" in detect_languages(tmp_path, ALL_LANGS)

    def test_detects_proto_by_extension(self, tmp_path: Path) -> None:
        (tmp_path / "service.proto").touch()
        assert "proto" in detect_languages(tmp_path, ALL_LANGS)

    def test_detects_swift_by_extension(self, tmp_path: Path) -> None:
        (tmp_path / "main.swift").touch()
        assert "swift" in detect_languages(tmp_path, ALL_LANGS)

    def test_detects_kotlin_by_extension(self, tmp_path: Path) -> None:
        (tmp_path / "Main.kt").touch()
        assert "kt" in detect_languages(tmp_path, ALL_LANGS)

    def test_detects_kotlin_script_by_extension(self, tmp_path: Path) -> None:
        (tmp_path / "build.gradle.kts").touch()
        assert "kt" in detect_languages(tmp_path, ALL_LANGS)

    def test_detects_css_by_extension(self, tmp_path: Path) -> None:
        (tmp_path / "styles.css").touch()
        assert "css" in detect_languages(tmp_path, ALL_LANGS)

    def test_detects_scss_by_extension(self, tmp_path: Path) -> None:
        (tmp_path / "styles.scss").touch()
        assert "css" in detect_languages(tmp_path, ALL_LANGS)

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

    def test_detects_lua_by_extension(self, tmp_path: Path) -> None:
        (tmp_path / "main.lua").touch()
        assert "lua" in detect_languages(tmp_path, ALL_LANGS)

    def test_detects_groovy_by_extension(self, tmp_path: Path) -> None:
        (tmp_path / "script.groovy").touch()
        assert "groovy" in detect_languages(tmp_path, ALL_LANGS)

    def test_detects_groovy_gvy_extension(self, tmp_path: Path) -> None:
        (tmp_path / "script.gvy").touch()
        assert "groovy" in detect_languages(tmp_path, ALL_LANGS)

    def test_detects_groovy_from_gradle_extension(self, tmp_path: Path) -> None:
        (tmp_path / "build.gradle").touch()
        assert "groovy" in detect_languages(tmp_path, ALL_LANGS)

    def test_detects_groovy_from_jenkinsfile(self, tmp_path: Path) -> None:
        (tmp_path / "Jenkinsfile").touch()
        assert "groovy" in detect_languages(tmp_path, ALL_LANGS)

    def test_detects_groovy_from_jenkinsfile_case_insensitive(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "jenkinsfile").touch()
        assert "groovy" in detect_languages(tmp_path, ALL_LANGS)

    def test_detects_env_file(self, tmp_path: Path) -> None:
        (tmp_path / ".env").touch()
        assert "env" in detect_languages(tmp_path, ALL_LANGS)

    def test_detects_env_local_file(self, tmp_path: Path) -> None:
        (tmp_path / ".env.local").touch()
        assert "env" in detect_languages(tmp_path, ALL_LANGS)

    def test_detects_env_production_file(self, tmp_path: Path) -> None:
        (tmp_path / ".env.production").touch()
        assert "env" in detect_languages(tmp_path, ALL_LANGS)

    def test_env_skip_dir_does_not_falsely_detect_env_lang(
        self, tmp_path: Path
    ) -> None:
        venv = tmp_path / "env"
        venv.mkdir()
        (venv / "pyvenv.cfg").touch()
        assert "env" not in detect_languages(tmp_path, ALL_LANGS)


class TestDetectFrameworks:
    def test_detects_django_by_manage_py(self, tmp_path: Path) -> None:
        (tmp_path / "manage.py").touch()
        assert "django" in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    def test_no_django_without_manage_py(self, tmp_path: Path) -> None:
        assert "django" not in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    def test_detects_ansible_by_ansible_cfg(self, tmp_path: Path) -> None:
        (tmp_path / "ansible.cfg").touch()
        assert "ansible" in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    def test_no_ansible_without_ansible_cfg(self, tmp_path: Path) -> None:
        assert "ansible" not in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    def test_detects_behave_by_features_steps_dir(self, tmp_path: Path) -> None:
        (tmp_path / "features" / "steps").mkdir(parents=True)
        assert "behave" in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    def test_detects_behave_by_behave_ini(self, tmp_path: Path) -> None:
        (tmp_path / "behave.ini").touch()
        assert "behave" in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    def test_detects_behave_by_dot_behaverc(self, tmp_path: Path) -> None:
        (tmp_path / ".behaverc").touch()
        assert "behave" in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    def test_no_behave_without_indicators(self, tmp_path: Path) -> None:
        assert "behave" not in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    def test_no_behave_from_features_dir_without_steps(self, tmp_path: Path) -> None:
        (tmp_path / "features").mkdir()
        assert "behave" not in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    def test_detects_nika_by_nika_yaml_file(self, tmp_path: Path) -> None:
        (tmp_path / "workflow.nika.yaml").touch()
        assert "nika" in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    def test_no_nika_without_nika_yaml_file(self, tmp_path: Path) -> None:
        assert "nika" not in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

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

    # mutmut_14: return True instead of return False in
    # _has_package_json_dep when parsed JSON is not a dict
    def test_no_react_when_package_json_is_not_a_dict(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text(json.dumps(["react"]), encoding="utf-8")
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

    def test_k8s_detected_when_non_yaml_file_precedes_manifest_in_walk(
        self, tmp_path: Path
    ) -> None:
        # Guarantee that a non-YAML file is yielded before the k8s manifest.
        # With 'break' instead of 'continue' the loop would stop at the first
        # non-YAML file and never inspect the manifest, returning False.
        non_yaml = tmp_path / "README.md"
        non_yaml.write_text("docs", encoding="utf-8")
        k8s_yaml = tmp_path / "deployment.yaml"
        k8s_yaml.write_text("apiVersion: apps/v1\nkind: Deployment\n", encoding="utf-8")

        with patch.object(_detector, "_walk", return_value=iter([non_yaml, k8s_yaml])):
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

    # mutmut_14 (has_kubernetes_files): continue changed to break when a
    # .github YAML file is encountered. With 'break' the loop exits as soon
    # as the .github file is seen, so a real k8s manifest that comes later in
    # the walk order is never inspected. Patch _walk to guarantee the .github
    # file is yielded first so the behaviour difference is deterministic.
    def test_k8s_detected_when_github_yaml_is_walked_before_k8s_manifest(
        self, tmp_path: Path
    ) -> None:
        github_workflow = tmp_path / ".github" / "workflows" / "ci.yml"
        github_workflow.parent.mkdir(parents=True)
        github_workflow.write_text("apiVersion: v1\nkind: fake\n", encoding="utf-8")

        k8s_manifest = tmp_path / "deployment.yaml"
        k8s_manifest.write_text(
            "apiVersion: apps/v1\nkind: Deployment\n", encoding="utf-8"
        )

        # Force the .github workflow to be visited BEFORE the k8s manifest.
        # With 'break', the loop exits on the github file and misses the manifest.
        # With 'continue', the github file is skipped and the manifest is found.
        with patch.object(
            _detector,
            "_walk",
            return_value=iter([github_workflow, k8s_manifest]),
        ):
            assert "k8s" in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    # mutmut_13 and mutmut_14 (_has_github_workflows): ".yaml" replaced with
    # "XX.yamlXX" or ".YAML" in extension set
    def test_detects_git_framework_from_github_workflows_yaml_extension(
        self, tmp_path: Path
    ) -> None:
        workflows = tmp_path / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "ci.yaml").touch()
        assert "git" in detect_frameworks(tmp_path, ALL_FRAMEWORKS)

    # mutmut_16: encoding=None instead of encoding="utf-8" in _has_kubernetes_files
    def test_k8s_reads_yaml_file_with_utf8_encoding(self, tmp_path: Path) -> None:
        (tmp_path / "deployment.yaml").write_text(
            "apiVersion: apps/v1\nkind: Deployment\n", encoding="utf-8"
        )

        recorded: dict = {}
        _original_read_text = Path.read_text

        def tracking_read_text(self: Path, *args: Any, **kwargs: Any) -> str:
            if self.suffix.lower() in {".yaml", ".yml"}:
                recorded.update(kwargs)
            return _original_read_text(self, *args, **kwargs)  # type: ignore[arg-type]

        with patch.object(Path, "read_text", tracking_read_text):
            result = detect_frameworks(tmp_path, ["k8s"])

        assert "k8s" in result
        assert recorded.get("encoding") == "utf-8"

    # mutmut_18:
    # encoding="utf-8" removed from file.read_text call in _has_kubernetes_files
    def test_k8s_yaml_read_uses_utf8_encoding(self, tmp_path: Path) -> None:
        (tmp_path / "deployment.yaml").write_text(
            "apiVersion: apps/v1\nkind: Deployment\n", encoding="utf-8"
        )

        _original_read_text = Path.read_text
        recorded: dict[str, Any] = {}

        def tracking_read_text(self: Path, *args: Any, **kwargs: Any) -> str:
            if self.suffix in (".yaml", ".yml"):
                recorded.update(kwargs)
            return _original_read_text(self, *args, **kwargs)  # type: ignore[arg-type]

        with patch.object(Path, "read_text", tracking_read_text):
            result = detect_frameworks(tmp_path, ALL_FRAMEWORKS)

        assert "k8s" in result
        assert recorded.get("encoding") == "utf-8"

    # mutmut_17 (_has_github_workflows): return True instead of return False
    # in the OSError except block
    def test_no_git_framework_when_workflows_dir_iterdir_raises_oserror(
        self, tmp_path: Path
    ) -> None:
        workflows = tmp_path / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "ci.yml").touch()

        _original_iterdir = Path.iterdir

        def _iterdir(self: Path) -> Any:
            if self == workflows:
                raise OSError
            return _original_iterdir(self)

        with patch.object(Path, "iterdir", _iterdir):
            assert "git" not in detect_frameworks(tmp_path, ALL_FRAMEWORKS)


class TestEvaluateDetectRule:
    def test_unknown_escape_hatch_name_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Unknown escape-hatch detector"):
            _detector._evaluate_detect_rule(tmp_path, "python:_does_not_exist")

    def test_unknown_rule_type_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Unknown detect rule type"):
            _detector._evaluate_detect_rule(tmp_path, {"bogus_rule": "x"})

    def test_multi_key_rule_dict_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="exactly one key"):
            _detector._evaluate_detect_rule(
                tmp_path, {"file_exists": "a", "dir_exists": "b"}
            )

    def test_non_str_non_dict_rule_raises(self, tmp_path: Path) -> None:
        with pytest.raises(TypeError, match="Invalid detect rule"):
            _detector._evaluate_detect_rule(tmp_path, 123)

    def test_glob_rule_matches_filename_pattern(self, tmp_path: Path) -> None:
        (tmp_path / "workflow.nika.yaml").touch()
        assert _detector._evaluate_detect_rule(tmp_path, {"glob": "*.nika.yaml"})

    def test_dir_exists_rule(self, tmp_path: Path) -> None:
        (tmp_path / "features" / "steps").mkdir(parents=True)
        rule = {"dir_exists": "features/steps"}
        assert _detector._evaluate_detect_rule(tmp_path, rule)
        assert not _detector._evaluate_detect_rule(tmp_path, {"dir_exists": "nope"})
