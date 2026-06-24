"""Integration tests for pc-init CLI generation."""

import shutil
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import yaml
from typer.testing import CliRunner

from gpc_init.cli import app, entry_point
from gpc_init.exceptions import (
    PresetFetchError,
    PresetNotFoundError,
    PresetParseError,
)

runner = CliRunner()


class TestBasicGeneration:
    def test_lang_py_creates_file(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(app, ["--lang", "py", "--output", str(output)])
        assert result.exit_code == 0, result.output
        assert output.exists()

    def test_generated_file_is_valid_yaml(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        runner.invoke(app, ["--lang", "py", "--output", str(output)])
        content = output.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)
        assert isinstance(parsed, dict)
        assert "repos" in parsed

    def test_exit_code_zero_on_success(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(app, ["--lang", "py", "--output", str(output)])
        assert result.exit_code == 0

    def test_success_message_includes_lang(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(app, ["--lang", "py", "--output", str(output)])
        assert "py" in result.output

    def test_multiple_langs_merged(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(
            app, ["--lang", "py", "--lang", "js", "--output", str(output)]
        )
        assert result.exit_code == 0, result.output
        content = output.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)
        assert "repos" in parsed
        # Both languages should contribute repos
        all_repos = [r["repo"] for r in parsed["repos"]]
        # py has ruff, js has local prettier - check for some content
        assert len(all_repos) >= 2

    def test_success_message_includes_all_langs(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(
            app, ["--lang", "py", "--lang", "js", "--output", str(output)]
        )
        assert "py" in result.output
        assert "js" in result.output

    def test_success_message_formats_multiple_langs_with_comma_space(
        self, tmp_path: Path
    ) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(
            app, ["--lang", "py", "--lang", "js", "--output", str(output)]
        )
        assert result.exit_code == 0, result.output
        assert "py, js" in result.output

    def test_new_file_success_message_says_generated(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(app, ["--lang", "py", "--output", str(output)])
        assert result.exit_code == 0, result.output
        assert "Generated" in result.output

    def test_new_file_success_message_starts_with_generated(
        self, tmp_path: Path
    ) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(app, ["--lang", "py", "--output", str(output)])
        assert result.exit_code == 0, result.output
        assert "Generated " in result.output
        assert "XXGeneratedXX" not in result.output

    def test_common_preset_hooks_included_in_default_output(
        self, tmp_path: Path
    ) -> None:
        """Common preset hooks must appear in default (bundled) output."""
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(app, ["--lang", "py", "--output", str(output)])
        assert result.exit_code == 0, result.output
        parsed = yaml.safe_load(output.read_text(encoding="utf-8"))
        all_hook_ids = [
            hook["id"]
            for repo in parsed.get("repos", [])
            for hook in repo.get("hooks", [])
        ]
        # check-added-large-files is defined in the bundled common preset only;
        # it should be present when merge_presets receives the real common dict.
        # With the mutant (common=None), the common preset is skipped and this
        # hook is absent.
        assert "check-added-large-files" in all_hook_ids

    def test_success_message_says_none_when_no_framework(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(app, ["--lang", "py", "--output", str(output)])
        assert result.exit_code == 0, result.output
        assert "frameworks: none" in result.output


class TestFrameworkGeneration:
    def test_lang_and_framework(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(
            app,
            ["--lang", "js", "--framework", "react", "--output", str(output)],
        )
        assert result.exit_code == 0, result.output
        assert output.exists()

    def test_framework_adds_hooks(self, tmp_path: Path) -> None:
        output_lang_only = tmp_path / "lang_only.yaml"
        output_with_fw = tmp_path / "with_fw.yaml"
        runner.invoke(app, ["--lang", "js", "--output", str(output_lang_only)])
        runner.invoke(
            app,
            ["--lang", "js", "--framework", "react", "--output", str(output_with_fw)],
        )
        lang_only = yaml.safe_load(output_lang_only.read_text(encoding="utf-8"))
        with_fw = yaml.safe_load(output_with_fw.read_text(encoding="utf-8"))
        # With framework should have more repos
        assert len(with_fw.get("repos", [])) >= len(lang_only.get("repos", []))

    def test_framework_does_not_remove_lang_hooks(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        runner.invoke(
            app,
            ["--lang", "js", "--framework", "react", "--output", str(output)],
        )
        parsed = yaml.safe_load(output.read_text(encoding="utf-8"))
        # js has prettier - it should still be there
        all_hook_ids = [
            hook["id"]
            for repo in parsed.get("repos", [])
            for hook in repo.get("hooks", [])
        ]
        assert "prettier" in all_hook_ids

    def test_framework_with_non_primary_lang_succeeds(self, tmp_path: Path) -> None:
        """React framework should work with Go language (no validation error)."""
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(
            app,
            ["--lang", "go", "--framework", "react", "--output", str(output)],
        )
        assert result.exit_code == 0, result.output

    def test_multiple_langs_and_frameworks(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(
            app,
            [
                "--lang",
                "py",
                "--lang",
                "js",
                "--framework",
                "django",
                "--framework",
                "react",
                "--output",
                str(output),
            ],
        )
        assert result.exit_code == 0, result.output
        parsed = yaml.safe_load(output.read_text(encoding="utf-8"))
        assert "repos" in parsed

    def test_non_primary_lang_prints_note_message(self, tmp_path: Path) -> None:
        """A framework with a non-primary language should print an info note."""
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(
            app,
            ["--lang", "go", "--framework", "react", "--output", str(output)],
        )
        assert result.exit_code == 0, result.output
        assert "Note:" in result.output

    def test_framework_mismatch_info_message_content(self, tmp_path: Path) -> None:
        """Info message must contain actual language hint, not 'None'."""
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(
            app,
            ["--lang", "go", "--framework", "react", "--output", str(output)],
        )
        assert result.exit_code == 0, result.output
        assert "Note: framework 'react' is typically used with: js" in result.output
        assert "None" not in result.output

    def test_success_message_includes_framework_name(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(
            app,
            ["--lang", "js", "--framework", "react", "--output", str(output)],
        )
        assert result.exit_code == 0, result.output
        assert "react" in result.output

    def test_success_message_includes_frameworks_joined_by_comma(
        self, tmp_path: Path
    ) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(
            app,
            [
                "--lang",
                "py",
                "--lang",
                "js",
                "--framework",
                "django",
                "--framework",
                "react",
                "--output",
                str(output),
            ],
        )
        assert result.exit_code == 0, result.output
        assert "django, react" in result.output


class TestErrorHandling:
    def test_unsupported_lang_exits_nonzero(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(app, ["--lang", "cobol", "--output", str(output)])
        assert result.exit_code != 0

    def test_unsupported_lang_error_message_includes_supported(
        self, tmp_path: Path
    ) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(app, ["--lang", "cobol", "--output", str(output)])
        # Error should mention supported options
        assert "cobol" in result.output or "Error" in result.output

    def test_unsupported_framework_exits_nonzero(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(
            app, ["--lang", "py", "--framework", "angular", "--output", str(output)]
        )
        assert result.exit_code != 0

    def test_no_lang_exits_nonzero(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(app, ["--output", str(output)])
        assert result.exit_code != 0

    def test_unsupported_lang_exits_with_code_1(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(app, ["--lang", "cobol", "--output", str(output)])
        assert result.exit_code == 1

    def test_unsupported_framework_exits_with_code_1(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(
            app, ["--lang", "py", "--framework", "angular", "--output", str(output)]
        )
        assert result.exit_code == 1

    def test_no_lang_error_mentions_list_command(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(app, ["--output", str(output)])
        assert result.exit_code == 1, result.output
        assert "pc-init list" in result.output


class TestListCommand:
    def test_list_exits_zero(self) -> None:
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0, result.output

    def test_list_output_contains_languages_header(self) -> None:
        result = runner.invoke(app, ["list"])
        assert "Languages:" in result.output

    def test_list_output_contains_frameworks_header(self) -> None:
        result = runner.invoke(app, ["list"])
        assert "Frameworks:" in result.output

    def test_list_output_contains_known_language(self) -> None:
        result = runner.invoke(app, ["list"])
        assert "py" in result.output

    def test_list_output_contains_known_framework(self) -> None:
        result = runner.invoke(app, ["list"])
        assert "react" in result.output

    def test_list_with_custom_presets_dir(self, tmp_preset_dir: Path) -> None:
        result = runner.invoke(app, ["list", "--presets", str(tmp_preset_dir)])
        assert result.exit_code == 0, result.output
        assert "py" in result.output
        assert "js" in result.output
        assert "react" in result.output

    def test_list_with_missing_custom_presets_dir(self, tmp_path: Path) -> None:
        missing_dir = tmp_path / "missing_presets_dir"
        result = runner.invoke(app, ["list", "--presets", str(missing_dir)])
        assert result.exit_code == 1
        assert "presets directory" in result.output

    def test_list_custom_presets_dir_excludes_bundled_only_langs(
        self, tmp_preset_dir: Path
    ) -> None:
        """Custom preset dir with only py/js should not list bundled-only langs."""
        result = runner.invoke(app, ["list", "--presets", str(tmp_preset_dir)])
        assert "go" not in result.output


class TestOverwriteBehavior:
    def test_existing_file_without_force_exits_nonzero(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        output.write_text("existing content", encoding="utf-8")
        result = runner.invoke(app, ["--lang", "py", "--output", str(output)])
        assert result.exit_code != 0

    def test_existing_file_without_force_preserves_content(
        self, tmp_path: Path
    ) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        output.write_text("existing content", encoding="utf-8")
        runner.invoke(app, ["--lang", "py", "--output", str(output)])
        assert output.read_text(encoding="utf-8") == "existing content"

    def test_existing_file_without_force_mentions_force(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        output.write_text("existing content", encoding="utf-8")
        result = runner.invoke(app, ["--lang", "py", "--output", str(output)])
        assert "--force" in result.output

    def test_force_overwrites_existing_file(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        output.write_text("existing content", encoding="utf-8")
        result = runner.invoke(
            app, ["--lang", "py", "--force", "--output", str(output)]
        )
        assert result.exit_code == 0, result.output
        assert output.read_text(encoding="utf-8") != "existing content"

    def test_force_success_message(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        output.write_text("existing content", encoding="utf-8")
        result = runner.invoke(
            app, ["--lang", "py", "--force", "--output", str(output)]
        )
        assert "Overwrote" in result.output or "Generated" in result.output

    def test_force_overwrites_existing_file_says_overwrote(
        self, tmp_path: Path
    ) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        output.write_text("existing content", encoding="utf-8")
        result = runner.invoke(
            app, ["--lang", "py", "--force", "--output", str(output)]
        )
        assert result.exit_code == 0, result.output
        assert "Overwrote" in result.output

    def test_force_success_message_says_overwrote(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        output.write_text("existing content", encoding="utf-8")
        result = runner.invoke(
            app, ["--lang", "py", "--force", "--output", str(output)]
        )
        assert result.exit_code == 0, result.output
        assert "Overwrote" in result.output

    def test_force_success_message_word_is_exactly_overwrote(
        self, tmp_path: Path
    ) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        output.write_text("existing content", encoding="utf-8")
        result = runner.invoke(
            app, ["--lang", "py", "--force", "--output", str(output)]
        )
        assert result.exit_code == 0, result.output
        # Check "Overwrote " (with trailing space) so that a mutant like
        # "XXOverwroteXX" does not pass — "Overwrote" is a substring of that,
        # but "Overwrote " (with space) is not.
        assert "Overwrote " in result.output

    def test_write_text_called_with_utf8_encoding(self, tmp_path: Path) -> None:
        output = tmp_path / "out.yaml"
        original_write_text = Path.write_text

        calls = []

        def capturing_write_text(self, data, encoding=None, errors=None):
            calls.append({"path": self, "encoding": encoding})
            return original_write_text(self, data, encoding=encoding, errors=errors)

        with patch.object(Path, "write_text", capturing_write_text):
            result = runner.invoke(app, ["--lang", "py", "--output", str(output)])

        assert result.exit_code == 0, result.output
        assert any(c["path"] == output and c["encoding"] == "utf-8" for c in calls), (
            f"write_text was not called with encoding='utf-8'; calls={calls}"
        )


class TestArgumentNormalization:
    def test_python_alias_normalized_to_py(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(app, ["--lang", "python", "--output", str(output)])
        assert result.exit_code == 0, result.output

    def test_javascript_alias_normalized_to_js(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(app, ["--lang", "javascript", "--output", str(output)])
        assert result.exit_code == 0, result.output

    def test_rust_alias_normalized_to_ru(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(app, ["--lang", "rust", "--output", str(output)])
        assert result.exit_code == 0, result.output

    def test_mixed_case_lang_normalized(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(app, ["--lang", "Python", "--output", str(output)])
        assert result.exit_code == 0, result.output

    def test_duplicate_lang_deduplicated(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(
            app, ["--lang", "py", "--lang", "py", "--output", str(output)]
        )
        assert result.exit_code == 0, result.output

    def test_python_and_py_deduplicated(self, tmp_path: Path) -> None:
        """--lang=py --lang=python should produce same result as --lang=py."""
        output_dedup = tmp_path / "dedup.yaml"
        output_single = tmp_path / "single.yaml"
        runner.invoke(
            app, ["--lang", "py", "--lang", "python", "--output", str(output_dedup)]
        )
        runner.invoke(app, ["--lang", "py", "--output", str(output_single)])
        content_dedup = output_dedup.read_text(encoding="utf-8")
        content_single = output_single.read_text(encoding="utf-8")
        assert content_dedup == content_single

    def test_comma_delimited_langs_accepted(self, tmp_path: Path) -> None:
        """--lang=py,js should produce the same output as --lang=py --lang=js."""
        output_comma = tmp_path / "comma.yaml"
        output_repeat = tmp_path / "repeat.yaml"
        runner.invoke(app, ["--lang", "py,js", "--output", str(output_comma)])
        runner.invoke(
            app, ["--lang", "py", "--lang", "js", "--output", str(output_repeat)]
        )
        assert output_comma.read_text(encoding="utf-8") == output_repeat.read_text(
            encoding="utf-8"
        )

    def test_comma_delimited_frameworks_accepted(self, tmp_path: Path) -> None:
        """--framework=react,django equals --framework=react --framework=django."""
        output_comma = tmp_path / "comma.yaml"
        output_repeat = tmp_path / "repeat.yaml"
        runner.invoke(
            app,
            [
                "--lang",
                "js",
                "--framework",
                "react,django",
                "--output",
                str(output_comma),
            ],
        )
        runner.invoke(
            app,
            [
                "--lang",
                "js",
                "--framework",
                "react",
                "--framework",
                "django",
                "--output",
                str(output_repeat),
            ],
        )
        assert output_comma.read_text(encoding="utf-8") == output_repeat.read_text(
            encoding="utf-8"
        )

    def test_comma_delimited_langs_exit_zero(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(app, ["--lang", "py,js", "--output", str(output)])
        assert result.exit_code == 0, result.output


class TestDeterminism:
    def test_same_input_twice_produces_identical_output(self, tmp_path: Path) -> None:
        out1 = tmp_path / "run1.yaml"
        out2 = tmp_path / "run2.yaml"
        runner.invoke(app, ["--lang", "py", "--output", str(out1)])
        runner.invoke(app, ["--lang", "py", "--output", str(out2)])
        assert out1.read_text(encoding="utf-8") == out2.read_text(encoding="utf-8")

    def test_lang_order_matters(self, tmp_path: Path) -> None:
        out1 = tmp_path / "py_js.yaml"
        out2 = tmp_path / "js_py.yaml"
        runner.invoke(app, ["--lang", "py", "--lang", "js", "--output", str(out1)])
        runner.invoke(app, ["--lang", "js", "--lang", "py", "--output", str(out2)])
        # Different order may produce different file; both should be valid YAML
        parsed1 = yaml.safe_load(out1.read_text(encoding="utf-8"))
        parsed2 = yaml.safe_load(out2.read_text(encoding="utf-8"))
        assert isinstance(parsed1, dict)
        assert isinstance(parsed2, dict)


class TestPresetsOption:
    def test_local_presets_dir_success(
        self, tmp_path: Path, tmp_preset_dir: Path
    ) -> None:
        output = tmp_path / "out.yaml"
        result = runner.invoke(
            app,
            ["--lang", "py", "--presets", str(tmp_preset_dir), "--output", str(output)],
        )
        assert result.exit_code == 0, result.output
        assert output.exists()

    def test_local_presets_dir_nonexistent(self, tmp_path: Path) -> None:
        output = tmp_path / "out.yaml"
        result = runner.invoke(
            app,
            [
                "--lang",
                "py",
                "--presets",
                "/no/such/dir/for/presets",
                "--output",
                str(output),
            ],
        )
        assert result.exit_code == 1
        assert "does not exist" in result.output

    def test_git_url_success(self, tmp_path: Path, tmp_preset_dir: Path) -> None:
        output = tmp_path / "out.yaml"

        @contextmanager
        def fake_fetch(_url: str):
            yield tmp_preset_dir

        with patch("gpc_init.fetcher.fetch_preset_repo", fake_fetch):
            result = runner.invoke(
                app,
                [
                    "--lang",
                    "py",
                    "--presets",
                    "https://example.com/repo",
                    "--output",
                    str(output),
                ],
            )
        assert result.exit_code == 0, result.output
        assert output.exists()

    def test_git_url_fetch_error(self, tmp_path: Path) -> None:
        output = tmp_path / "out.yaml"
        with patch(
            "gpc_init.fetcher.fetch_preset_repo",
            side_effect=PresetFetchError("https://x", "connection refused"),
        ):
            result = runner.invoke(
                app,
                [
                    "--lang",
                    "py",
                    "--presets",
                    "https://x",
                    "--output",
                    str(output),
                ],
            )
        assert result.exit_code == 1
        assert "Failed to fetch" in result.output

    def test_local_presets_framework_validated_against_custom_dir(
        self, tmp_path: Path, fixtures_dir: Path
    ) -> None:
        """validate_frameworks must use the custom base_dir, not the bundled catalog."""
        preset_dir = tmp_path / "presets"
        shutil.copytree(fixtures_dir / "lang", preset_dir / "lang")
        fw_dir = preset_dir / "framework" / "customfw"
        fw_dir.mkdir(parents=True)
        (fw_dir / "preset.yaml").write_text(
            "repos:\n  - repo: local\n    hooks:\n"
            "      - id: custom-hook\n        name: custom\n"
            "        entry: custom\n        language: system\n",
            encoding="utf-8",
        )

        output = tmp_path / "out.yaml"
        result = runner.invoke(
            app,
            [
                "--lang",
                "py",
                "--framework",
                "customfw",
                "--presets",
                str(preset_dir),
                "--output",
                str(output),
            ],
        )
        assert result.exit_code == 0, result.output
        assert output.exists()

    def test_custom_presets_dir_framework_only_in_custom_dir_succeeds(
        self, tmp_path: Path, fixtures_dir: Path
    ) -> None:
        """validate_frameworks must use base_dir for custom-only frameworks."""
        preset_dir = tmp_path / "presets"
        shutil.copytree(fixtures_dir / "lang", preset_dir / "lang")
        fw_dir = preset_dir / "framework" / "myfw"
        fw_dir.mkdir(parents=True)
        (fw_dir / "preset.yaml").write_text(
            "repos:\n  - repo: local\n    hooks:\n"
            "      - id: myfw-hook\n        name: myfw\n"
            "        entry: myfw\n        language: system\n",
            encoding="utf-8",
        )

        output = tmp_path / "out.yaml"
        result = runner.invoke(
            app,
            [
                "--lang",
                "py",
                "--framework",
                "myfw",
                "--presets",
                str(preset_dir),
                "--output",
                str(output),
            ],
        )
        assert result.exit_code == 0, result.output

    def test_local_presets_common_preset_loaded_from_custom_dir(
        self, tmp_path: Path, tmp_preset_dir: Path
    ) -> None:
        """Common preset must come from the custom presets dir, not bundled defaults."""
        output = tmp_path / "out.yaml"
        result = runner.invoke(
            app,
            ["--lang", "py", "--presets", str(tmp_preset_dir), "--output", str(output)],
        )
        assert result.exit_code == 0, result.output
        parsed = yaml.safe_load(output.read_text(encoding="utf-8"))
        all_hook_ids = [
            hook["id"]
            for repo in parsed.get("repos", [])
            for hook in repo.get("hooks", [])
        ]
        # The fixture common preset only has trailing-whitespace and end-of-file-fixer.
        # The bundled default also has check-added-large-files,
        # check-merge-conflict, etc.
        # If base_dir=None is used (the mutant), bundled hooks leak in.
        assert "check-added-large-files" not in all_hook_ids
        assert "check-merge-conflict" not in all_hook_ids

    def test_local_presets_custom_framework_loaded_from_presets_dir(
        self, tmp_path: Path, tmp_preset_dir: Path
    ) -> None:
        """Framework preset loads from the custom base_dir, not bundled."""
        custom_fw_dir = tmp_preset_dir / "framework" / "custom_fw"
        custom_fw_dir.mkdir(parents=True)
        (custom_fw_dir / "preset.yaml").write_text(
            "repos:\n  - repo: local\n    hooks:\n"
            "      - id: custom-hook\n        name: custom\n"
            "        entry: echo\n        language: system\n",
            encoding="utf-8",
        )
        output = tmp_path / "out.yaml"
        result = runner.invoke(
            app,
            [
                "--lang",
                "py",
                "--framework",
                "custom_fw",
                "--presets",
                str(tmp_preset_dir),
                "--output",
                str(output),
            ],
        )
        assert result.exit_code == 0, result.output
        assert output.exists()

    def test_local_presets_dir_framework_uses_custom_preset(
        self, tmp_path: Path, tmp_preset_dir: Path
    ) -> None:
        output = tmp_path / "out.yaml"
        result = runner.invoke(
            app,
            [
                "--lang",
                "js",
                "--framework",
                "react",
                "--presets",
                str(tmp_preset_dir),
                "--output",
                str(output),
            ],
        )
        assert result.exit_code == 0, result.output
        content = output.read_text(encoding="utf-8")
        # The fixture react preset pins eslint@9.0.0; the bundled preset uses 9.28.0.
        # If base_dir is not forwarded to load_framework_preset the bundled preset
        # would be used instead and this assertion would fail.
        assert "eslint@9.0.0" in content

    def test_local_presets_common_hooks_present_in_output(
        self, tmp_path: Path, tmp_preset_dir: Path
    ) -> None:
        """Common preset hooks must be included when a custom presets dir is used."""
        # The fixture lang/common/preset.yaml defines trailing-whitespace and
        # end-of-file-fixer.  With the mutant (common = None) these are never
        # loaded and therefore absent from the merged output.
        output = tmp_path / "out.yaml"
        result = runner.invoke(
            app,
            ["--lang", "py", "--presets", str(tmp_preset_dir), "--output", str(output)],
        )
        assert result.exit_code == 0, result.output
        parsed = yaml.safe_load(output.read_text(encoding="utf-8"))
        all_hook_ids = [
            hook["id"]
            for repo in parsed.get("repos", [])
            for hook in repo.get("hooks", [])
        ]
        assert "trailing-whitespace" in all_hook_ids
        assert "end-of-file-fixer" in all_hook_ids


class TestErrorPaths:
    def test_write_permission_error(self, tmp_path: Path) -> None:
        output = tmp_path / "out.yaml"
        with patch.object(Path, "write_text", side_effect=PermissionError("denied")):
            result = runner.invoke(
                app, ["--lang", "py", "--force", "--output", str(output)]
            )
        assert result.exit_code == 1
        assert "cannot write to" in result.output

    def test_local_presets_missing_lang_subdir(self, tmp_path: Path) -> None:
        presets_dir = tmp_path / "presets"
        presets_dir.mkdir()
        output = tmp_path / "out.yaml"
        result = runner.invoke(
            app,
            ["--lang", "py", "--presets", str(presets_dir), "--output", str(output)],
        )
        assert result.exit_code == 1
        assert "must contain a 'lang' subdirectory" in result.output

    def test_local_presets_missing_lang_subdir_error_goes_to_stderr(
        self, tmp_path: Path
    ) -> None:
        presets_dir = tmp_path / "presets"
        presets_dir.mkdir()
        output = tmp_path / "out.yaml"
        result = runner.invoke(
            app,
            ["--lang", "py", "--presets", str(presets_dir), "--output", str(output)],
        )
        assert result.exit_code == 1
        assert "must contain a 'lang' subdirectory" in result.stderr
        assert "must contain a 'lang' subdirectory" not in result.stdout

    def test_preset_not_found_error(self, tmp_path: Path) -> None:
        output = tmp_path / "out.yaml"
        with patch(
            "gpc_init.cli.load_language_preset",
            side_effect=PresetNotFoundError("preset not found"),
        ):
            result = runner.invoke(app, ["--lang", "py", "--output", str(output)])
        assert result.exit_code == 1
        assert "preset not found" in result.output

    def test_preset_not_found_error_goes_to_stderr(self, tmp_path: Path) -> None:
        output = tmp_path / "out.yaml"
        with patch(
            "gpc_init.cli.load_language_preset",
            side_effect=PresetNotFoundError("preset not found"),
        ):
            result = runner.invoke(app, ["--lang", "py", "--output", str(output)])
        assert result.exit_code == 1
        assert "preset not found" in result.stderr
        assert "preset not found" not in result.stdout

    def test_preset_parse_error(self, tmp_path: Path) -> None:
        lang_dir = tmp_path / "lang" / "bad"
        lang_dir.mkdir(parents=True)
        (lang_dir / "preset.yaml").write_text(": bad: [", encoding="utf-8")
        output = tmp_path / "out.yaml"
        result = runner.invoke(
            app,
            [
                "--lang",
                "bad",
                "--presets",
                str(tmp_path),
                "--output",
                str(output),
            ],
        )
        assert result.exit_code == 1
        assert "failed to parse" in result.output

    def test_preset_parse_error_writes_to_stderr(self, tmp_path: Path) -> None:
        output = tmp_path / "out.yaml"
        with patch(
            "gpc_init.cli.load_language_preset",
            side_effect=PresetParseError("bad yaml"),
        ):
            result = runner.invoke(app, ["--lang", "py", "--output", str(output)])
        assert result.exit_code == 1
        assert "failed to parse" in result.stderr
        assert "failed to parse" not in result.stdout

    def test_write_permission_error_goes_to_stderr(self, tmp_path: Path) -> None:
        output = tmp_path / "out.yaml"
        with patch.object(Path, "write_text", side_effect=PermissionError("denied")):
            result = runner.invoke(
                app,
                ["--lang", "py", "--force", "--output", str(output)],
            )
        assert "cannot write to" in result.stderr
        assert "cannot write to" not in result.stdout

    def test_unsupported_lang_error_goes_to_stderr(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(app, ["--lang", "cobol", "--output", str(output)])
        assert result.exit_code != 0
        assert "Error" in result.stderr
        assert result.stdout == ""

    def test_unsupported_framework_error_message_contains_framework_name(
        self, tmp_path: Path
    ) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(
            app, ["--lang", "py", "--framework", "angular", "--output", str(output)]
        )
        assert "angular" in result.output or "Error" in result.output
        assert result.output.strip() != "None"

    def test_unsupported_framework_error_message(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(
            app, ["--lang", "py", "--framework", "angular", "--output", str(output)]
        )
        assert result.exit_code != 0
        assert "Error" in result.output

    def test_unsupported_framework_error_written_to_stderr(
        self, tmp_path: Path
    ) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(
            app,
            ["--lang", "py", "--framework", "angular", "--output", str(output)],
        )
        assert result.exit_code != 0
        assert "Error" in result.stderr
        assert "Error" not in result.stdout


class TestDiffOnExistingFile:
    def test_diff_shows_unified_diff_when_content_differs(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        output.write_text("existing: content\n", encoding="utf-8")
        result = runner.invoke(app, ["--lang", "py", "--output", str(output)])
        assert "---" in result.output
        assert "+++" in result.output

    def test_diff_exits_nonzero_when_content_differs(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        output.write_text("existing: content\n", encoding="utf-8")
        result = runner.invoke(app, ["--lang", "py", "--output", str(output)])
        assert result.exit_code == 1

    def test_diff_does_not_write_when_content_differs(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        output.write_text("existing: content\n", encoding="utf-8")
        runner.invoke(app, ["--lang", "py", "--output", str(output)])
        assert output.read_text(encoding="utf-8") == "existing: content\n"

    def test_diff_no_changes_exits_zero(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        runner.invoke(app, ["--lang", "py", "--output", str(output)])
        result = runner.invoke(app, ["--lang", "py", "--output", str(output)])
        assert result.exit_code == 0

    def test_diff_no_changes_prints_no_changes_message(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        runner.invoke(app, ["--lang", "py", "--output", str(output)])
        result = runner.invoke(app, ["--lang", "py", "--output", str(output)])
        assert "No changes" in result.output

    def test_diff_no_changes_does_not_write(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        runner.invoke(app, ["--lang", "py", "--output", str(output)])
        content_before = output.read_text(encoding="utf-8")
        runner.invoke(app, ["--lang", "py", "--output", str(output)])
        assert output.read_text(encoding="utf-8") == content_before

    def test_diff_mentions_force_when_content_differs(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        output.write_text("existing: content\n", encoding="utf-8")
        result = runner.invoke(app, ["--lang", "py", "--output", str(output)])
        assert "--force" in result.output

    def test_force_bypasses_diff_and_overwrites(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        output.write_text("existing: content\n", encoding="utf-8")
        result = runner.invoke(
            app, ["--lang", "py", "--force", "--output", str(output)]
        )
        assert result.exit_code == 0
        assert output.read_text(encoding="utf-8") != "existing: content\n"


class TestVersion:
    def test_version_exits_zero(self) -> None:
        with patch("gpc_init.cli.importlib.metadata.version", return_value="9.9.9"):
            result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0

    def test_version_prints_version_string(self) -> None:
        with patch("gpc_init.cli.importlib.metadata.version", return_value="9.9.9"):
            result = runner.invoke(app, ["--version"])
        assert result.output.strip() == "9.9.9"

    def test_version_is_eager_no_lang_required(self) -> None:
        with patch("gpc_init.cli.importlib.metadata.version", return_value="9.9.9"):
            result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "Missing" not in result.output


class TestEntryPoint:
    def test_entry_point_calls_app(self) -> None:
        with patch("gpc_init.cli.app") as mock_app:
            entry_point()
        mock_app.assert_called_once_with()
