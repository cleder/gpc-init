"""Integration tests for pc-init CLI generation."""

import importlib.metadata
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Any
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
        assert "Note: preset 'react' recommends adding: --lang=js" in result.output
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


class TestAllRecommendations:
    def test_framework_only_expands_recommended_langs(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(
            app,
            [
                "--framework",
                "django",
                "--recommended",
                "--output",
                str(output),
            ],
        )
        assert result.exit_code == 0, result.output
        assert output.exists()

    def test_framework_only_success_message_includes_expanded_lang(
        self, tmp_path: Path
    ) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(
            app,
            [
                "--framework",
                "django",
                "--recommended",
                "--output",
                str(output),
            ],
        )
        assert result.exit_code == 0, result.output
        assert "py" in result.output

    def test_framework_only_no_note_printed(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(
            app,
            [
                "--framework",
                "django",
                "--recommended",
                "--output",
                str(output),
            ],
        )
        assert result.exit_code == 0, result.output
        assert "Note:" not in result.output

    def test_no_lang_no_framework_still_errors(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(
            app,
            ["--recommended", "--output", str(output)],
        )
        assert result.exit_code != 0

    def test_all_recommendations_without_flag_prints_note(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(
            app,
            ["--lang", "go", "--framework", "react", "--output", str(output)],
        )
        assert result.exit_code == 0, result.output
        assert "Note:" in result.output

    def test_all_recommendations_with_flag_suppresses_note(
        self, tmp_path: Path
    ) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(
            app,
            [
                "--lang",
                "go",
                "--framework",
                "react",
                "--recommended",
                "--output",
                str(output),
            ],
        )
        assert result.exit_code == 0, result.output
        assert "Note:" not in result.output

    def test_recommended_flag_expands_lang_hooks_into_generated_file(
        self, tmp_path: Path
    ) -> None:
        """
        --recommended must cause _run to pass recommended=True to _generate_content.

        The django preset recommends lang=py.  Without --recommended the py hooks
        (e.g. ruff-check) must not appear.  With --recommended they must appear
        because expand_recommendations is invoked inside _generate_content only
        when recommended=True.  If _run drops the recommended kwarg (the mutant)
        the flag is silently ignored and the py hooks are absent.
        """
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(
            app,
            ["--framework", "django", "--recommended", "--output", str(output)],
        )
        assert result.exit_code == 0, result.output
        parsed = yaml.safe_load(output.read_text(encoding="utf-8"))
        all_hook_ids = [
            hook["id"]
            for repo in parsed.get("repos", [])
            for hook in repo.get("hooks", [])
        ]
        assert "ruff-check" in all_hook_ids


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

    def test_framework_without_lang_hints_recommended_lowercase(
        self, tmp_path: Path
    ) -> None:
        """
        Error message hint for --recommended must use lowercase text.

        When a framework is provided without --lang and without --recommended,
        _require_lang_or_exit appends a hint about --recommended.  The mutant
        uppercases that hint string (' USE --RECOMMENDED TO APPLY...').  This
        test asserts the exact lowercase form is present so the mutant is killed.
        """
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(app, ["--framework", "django", "--output", str(output)])
        assert result.exit_code == 1, result.output
        assert (
            "Use --recommended to apply languages suggested by the frameworks."
            in result.output
        )

    def test_no_lang_error_message_starts_with_expected_prefix(
        self, tmp_path: Path
    ) -> None:
        """
        The no-lang error message must start with 'No --lang specified'.

        The mutant prepends 'XX' to the message, producing
        'XXNo --lang specified and none detected. XX...'.  Substring checks
        like '"No --lang specified" in output' still pass because that string
        is contained in the mutated version.  Asserting that the output *starts*
        with the expected prefix (and that 'XXNo' is absent) kills the mutant.
        """
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(app, ["--output", str(output)])
        assert result.exit_code == 1, result.output
        assert result.output.startswith("No --lang specified"), (
            f"Expected error output to start with 'No --lang specified', "
            f"got: {result.output!r}"
        )
        assert "XXNo" not in result.output

    def test_no_lang_error_message_starts_with_capital_no(self, tmp_path: Path) -> None:
        """
        Error message must begin with capital 'No', not lowercase 'no'.

        The mutant changes 'No --lang specified...' to 'no --lang specified...'
        in _require_lang_or_exit.  Checking the exact substring 'No --lang specified'
        (capital N, no 'or' fallback) kills the mutant.
        """
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(app, ["--output", str(output)])
        assert result.exit_code == 1, result.output
        assert "No --lang specified" in result.output

    def test_no_lang_error_message_starts_with_run(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(app, ["--output", str(output)])
        assert result.exit_code == 1, result.output
        # The error message must begin with "Run `pc-init list`", not "XXRun ...XX".
        assert "Run `pc-init list`" in result.output
        assert "XXRun" not in result.output

    def test_no_lang_error_message_run_is_capitalised(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(app, ["--output", str(output)])
        assert result.exit_code == 1, result.output
        # The sentence starts with a capital "R" in "Run" after the period.
        # The mutant changes this to lowercase "run", so checking for the
        # capital-R form kills the mutant.
        assert "Run `pc-init list`" in result.output

    def test_framework_without_lang_error_message_contains_list_command_hint(
        self, tmp_path: Path
    ) -> None:
        """
        Error message must retain the 'pc-init list' hint even when --framework is set.

        When --framework is provided without --lang and without --recommended,
        _require_lang_or_exit builds an error message starting with the
        'No --lang specified' base sentence and then *appends* a hint about
        --recommended.  The mutant replaces 'msg +=' with 'msg =', so the base
        sentence (including 'pc-init list') is discarded and only the
        --recommended hint is printed.  This test asserts that 'pc-init list'
        appears in the error output, killing that mutant.
        """
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(app, ["--framework", "django", "--output", str(output)])
        assert result.exit_code == 1
        assert "pc-init list" in result.output

    def test_framework_without_lang_error_mentions_recommended_flag(
        self, tmp_path: Path
    ) -> None:
        """
        Error message includes '--recommended' hint with framework.

        When --framework is supplied without --lang (and without --recommended),
        _require_lang_or_exit appends a hint about --recommended to the error
        message.  The mutant changes the appended string to start with 'XX' and
        end with 'XX', so checking for ' Use --recommended' (with the leading
        space that separates it from the preceding sentence) kills the mutant.
        """
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(app, ["--framework", "django", "--output", str(output)])
        assert result.exit_code == 1
        assert " Use --recommended" in result.output
        assert "XX" not in result.output

    def test_no_lang_with_framework_error_hints_recommended_with_capital_use(
        self, tmp_path: Path
    ) -> None:
        """
        Error message must start the --recommended hint with an uppercase 'U'.

        When --framework is given but --lang is omitted and --recommended is not
        set, _require_lang_or_exit appends a sentence beginning with 'Use'.
        The mutant changes 'Use' to 'use', altering the observable error message.
        """
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(app, ["--framework", "django", "--output", str(output)])
        assert result.exit_code == 1
        assert "Use --recommended" in result.output

    def test_detect_hint_not_corrupted_with_xx_markers(self, tmp_path: Path) -> None:
        """
        The --detect hint in the no-lang error message must not contain 'XX' markers.

        When no --lang is supplied and --detect is not set, _require_lang_or_exit
        appends ' Use --detect to auto-detect languages from the current directory.'
        (space-prefixed).  The mutant wraps this fragment with 'XX' tokens, producing
        'XX Use --detect ...XX'.  The existing test only checks for '--detect' as a
        substring, which passes for both the original and the mutant.  This test
        checks that the message starts with ' Use --detect' (space + 'Use') rather
        than 'XX Use --detect', killing the mutant.
        """
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(app, ["--output", str(output)])
        assert result.exit_code != 0
        # The hint must appear in its clean form -- no 'XX' decoration.
        assert "XX" not in result.output
        # Confirm the hint is present with the expected leading space.
        assert " Use --detect" in result.output

    def test_detect_hint_starts_with_capital_use(self, tmp_path: Path) -> None:
        """
        Detect hint in error message must start with capital 'Use'.

        _require_lang_or_exit appends ' Use --detect to auto-detect languages from the
        current directory.' when --detect is not passed.  The mutant changes 'Use' to
        'use', which this test catches by asserting the capitalised form is present.
        """
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(app, ["--output", str(output)])
        assert result.exit_code != 0
        assert "Use --detect" in result.output

    def test_no_lang_error_goes_to_stderr(self, tmp_path: Path) -> None:
        """
        Error message must go to stderr, not stdout.

        The mutant changes typer.echo(msg, err=True) to typer.echo(msg, err=False),
        routing the message to stdout instead.  This test asserts that the message
        appears in result.stderr and that result.stdout is empty, killing the mutant.
        """
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(app, ["--output", str(output)])
        assert result.exit_code == 1
        assert "No --lang specified" in result.stderr
        assert result.stdout == ""


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

    def test_recommended_expanded_lang_preset_loaded_from_custom_presets_dir(
        self, tmp_path: Path, tmp_preset_dir: Path
    ) -> None:
        """
        Expanded lang presets (via --recommended) must be loaded from base_dir.

        The react fixture recommends lang: [js].  When --recommended is used with
        a custom --presets directory the second load_language_preset call (for the
        newly-added 'js') must also receive base_dir, not None.

        The fixture js preset pins prettier@3.0.0 (local hook).
        The bundled js preset uses biome-check from a remote repo instead.
        If base_dir=None is passed to the second load_language_preset call (the
        mutant), the bundled js preset is loaded and 'prettier@3.0.0' is absent.
        """
        output = tmp_path / "out.yaml"
        result = runner.invoke(
            app,
            [
                "--lang",
                "py",
                "--framework",
                "react",
                "--recommended",
                "--presets",
                str(tmp_preset_dir),
                "--output",
                str(output),
            ],
        )
        assert result.exit_code == 0, result.output
        content = output.read_text(encoding="utf-8")
        # The fixture js preset (prettier@3.0.0) must be present.
        # With the mutant (base_dir=None), the bundled js preset (biome-check)
        # is loaded instead and this assertion fails.
        assert "prettier@3.0.0" in content

    def test_recommended_fw_preset_reloaded_from_custom_presets_dir(
        self, tmp_path: Path, tmp_preset_dir: Path
    ) -> None:
        """
        Framework presets reloaded after --recommended expansion use base_dir.

        When --recommended is used with a custom --presets directory, the second
        load_framework_preset call (line 84, inside the `if recommended:` block)
        must receive base_dir, not None.

        The fixture react preset pins eslint@9.0.0; the bundled preset uses 9.28.0.
        With the mutant (base_dir omitted, defaulting to None), the bundled react
        preset is loaded in the second pass and 'eslint@9.0.0' is absent from the
        output.
        """
        output = tmp_path / "out.yaml"
        result = runner.invoke(
            app,
            [
                "--lang",
                "js",
                "--framework",
                "react",
                "--recommended",
                "--presets",
                str(tmp_preset_dir),
                "--output",
                str(output),
            ],
        )
        assert result.exit_code == 0, result.output
        content = output.read_text(encoding="utf-8")
        # The fixture react preset pins eslint@9.0.0; the bundled preset uses 9.28.0.
        # If base_dir is not forwarded to load_framework_preset in the second pass
        # (the mutant), the bundled preset is used and this assertion fails.
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

    def test_recommended_with_custom_presets_expands_custom_only_framework(
        self, tmp_path: Path
    ) -> None:
        """
        --recommended must discover supported frameworks from the custom base_dir.

        The py preset in the custom dir recommends 'custom_only_fw', a framework
        that only exists in the custom dir (not in the bundled catalog).  With the
        original code get_supported_frameworks(base_dir) returns ['custom_only_fw'],
        so expand_recommendations includes it.  With the mutant
        get_supported_frameworks(None) returns only bundled frameworks, so
        'custom_only_fw' is silently dropped and the success message says
        'frameworks: none'.
        """
        preset_dir = tmp_path / "presets"
        # common preset (required by _generate_content)
        common_dir = preset_dir / "lang" / "common"
        common_dir.mkdir(parents=True)
        (common_dir / "preset.yaml").write_text("repos: []\n", encoding="utf-8")
        # py preset that recommends a framework only present in the custom dir
        py_dir = preset_dir / "lang" / "py"
        py_dir.mkdir(parents=True)
        (py_dir / "preset.yaml").write_text(
            "recommended:\n  framework:\n    - custom_only_fw\nrepos: []\n",
            encoding="utf-8",
        )
        # framework preset that only exists in the custom dir, not in bundled catalog
        fw_dir = preset_dir / "framework" / "custom_only_fw"
        fw_dir.mkdir(parents=True)
        (fw_dir / "preset.yaml").write_text("repos: []\n", encoding="utf-8")

        output = tmp_path / "out.yaml"
        result = runner.invoke(
            app,
            [
                "--lang",
                "py",
                "--recommended",
                "--presets",
                str(preset_dir),
                "--output",
                str(output),
            ],
        )
        assert result.exit_code == 0, result.output
        # The recommended framework from the custom dir must appear in the success
        # message.  The mutant passes None to get_supported_frameworks so it checks
        # the bundled catalog, which does not contain 'custom_only_fw', causing the
        # expansion to be silently skipped and the message to say 'frameworks: none'.
        assert "custom_only_fw" in result.output

    def test_recommended_expansion_loads_lang_preset_from_custom_presets_dir(
        self, tmp_path: Path, tmp_preset_dir: Path
    ) -> None:
        """
        Lang presets from --recommended must load from custom base_dir.

        The fixture react preset recommends lang=js.  When --recommended is set and
        --presets points at tmp_preset_dir, the js preset loaded after expansion must
        come from the fixture (prettier@3.0.0 as a local dep), not from the bundled
        catalog (which uses a mirrors-prettier repo).  The mutant drops base_dir from
        the load_language_preset call inside the recommended block, so it would load
        the bundled js preset instead.
        """
        output = tmp_path / "out.yaml"
        result = runner.invoke(
            app,
            [
                "--framework",
                "react",
                "--recommended",
                "--presets",
                str(tmp_preset_dir),
                "--output",
                str(output),
            ],
        )
        assert result.exit_code == 0, result.output
        content = output.read_text(encoding="utf-8")
        # The fixture lang/js/preset.yaml pins prettier@3.0.0 as a local dep.
        # The bundled lang/js/preset.yaml uses a remote mirrors-prettier repo instead.
        # If base_dir is not forwarded, the bundled preset is used and
        # this assertion fails.
        assert "prettier@3.0.0" in content

    def test_framework_preset_loaded_from_custom_base_dir(
        self, tmp_path: Path, tmp_preset_dir: Path
    ) -> None:
        """
        load_framework_preset must receive base_dir so custom presets are used.

        The fixture react preset pins eslint@9.0.0; the bundled preset uses 9.28.0.
        Without base_dir forwarded to load_framework_preset (the mutant), the
        bundled preset is silently used and the assertion fails.
        """
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
        assert "eslint@9.0.0" in content

    def test_recommended_with_custom_presets_uses_custom_lang_catalog(
        self, tmp_path: Path
    ) -> None:
        """
        expand_recommendations must use the custom base_dir's lang catalog.

        A language ('customlang') that only exists in the custom presets directory
        must be included in the expanded output when a framework preset in the same
        directory recommends it.  With the mutant (get_supported_languages(None))
        the bundled catalog is consulted instead: 'customlang' is absent from the
        bundled catalog, so the recommendation is silently dropped and the language
        never appears in the success message.
        """
        preset_dir = tmp_path / "presets"
        # Create a minimal custom language preset for 'customlang'
        lang_dir = preset_dir / "lang" / "customlang"
        lang_dir.mkdir(parents=True)
        (lang_dir / "preset.yaml").write_text(
            "repos:\n  - repo: local\n    hooks:\n"
            "      - id: custom-lang-hook\n        name: customlang\n"
            "        entry: echo\n        language: system\n",
            encoding="utf-8",
        )
        # Create a framework preset that recommends 'customlang'
        fw_dir = preset_dir / "framework" / "customfw"
        fw_dir.mkdir(parents=True)
        (fw_dir / "preset.yaml").write_text(
            "recommended:\n  lang:\n    - customlang\n"
            "repos:\n  - repo: local\n    hooks:\n"
            "      - id: customfw-hook\n        name: customfw\n"
            "        entry: echo\n        language: system\n",
            encoding="utf-8",
        )
        output = tmp_path / "out.yaml"
        result = runner.invoke(
            app,
            [
                "--framework",
                "customfw",
                "--recommended",
                "--presets",
                str(preset_dir),
                "--output",
                str(output),
            ],
        )
        assert result.exit_code == 0, result.output
        # 'customlang' was recommended by 'customfw' and only exists in the custom
        # catalog.  The success message lists all expanded languages; 'customlang'
        # must appear there.  The mutant passes None to get_supported_languages
        # instead of base_dir, so the bundled catalog is used and 'customlang' is
        # filtered out of the recommendations.
        assert "customlang" in result.output


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

    def test_diff_output_includes_generated_tofile_marker(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        output.write_text("existing: content\n", encoding="utf-8")
        result = runner.invoke(app, ["--lang", "py", "--output", str(output)])
        assert "<generated>" in result.output

    def test_diff_tofile_label_is_lowercase_generated(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        output.write_text("existing: content\n", encoding="utf-8")
        result = runner.invoke(app, ["--lang", "py", "--output", str(output)])
        plus_line = next(
            (line for line in result.output.splitlines() if line.startswith("+++")),
            None,
        )
        assert plus_line is not None, "No '+++' line found in diff output"
        assert "<generated>" in plus_line, (
            f"Expected '<generated>' (lowercase) in '+++' line, got: {plus_line!r}"
        )

    def test_diff_output_contains_actual_diff_lines_not_none(
        self, tmp_path: Path
    ) -> None:
        """
        Diff output must echo the joined diff lines, not None.

        The mutant replaces typer.echo("".join(diff_lines)) with
        typer.echo(None).  typer.echo(None) writes only a blank newline, so
        the unified diff header lines ('---', '+++') and changed lines are
        absent from stdout.  This test asserts both header markers are present,
        which fails when None is echoed instead of the diff text.
        """
        output = tmp_path / ".pre-commit-config.yaml"
        output.write_text("existing: content\n", encoding="utf-8")
        result = runner.invoke(app, ["--lang", "py", "--output", str(output)])
        assert result.exit_code == 1
        assert "---" in result.output
        assert "+++" in result.output

    def test_diff_output_contains_joined_diff_lines(self, tmp_path: Path) -> None:
        """
        The diff lines must be joined and echoed as a single string.

        The mutant replaces ''.join(diff_lines) with ''.join(None), which
        raises a TypeError and produces no output.  This test asserts that
        the unified-diff fromfile header (which always appears in the joined
        output) is present in stdout, ensuring the join call received the
        actual diff_lines list rather than None.
        """
        output = tmp_path / ".pre-commit-config.yaml"
        output.write_text("existing: content\n", encoding="utf-8")
        result = runner.invoke(app, ["--lang", "py", "--output", str(output)])
        assert not isinstance(result.exception, TypeError), (
            f"TypeError raised — likely from ''.join(None) mutant: {result.exception}"
        )
        assert str(output) in result.output, (
            "The unified diff fromfile header (target path) must appear in the "
            "echoed diff; with the mutant (''.join(None)) a TypeError is raised "
            "and nothing is printed"
        )

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

    def test_diff_existing_file_with_newlines_no_false_diff(
        self, tmp_path: Path
    ) -> None:
        r"""
        unified_diff must use keepends=True when reading the existing file.

        difflib.unified_diff compares the existing file's lines against the
        generated content's lines.  Both sides must use keepends=True so that
        line endings are included.  The mutant passes keepends=None (falsy) for
        the existing file, stripping all '\\n' from its lines.  Even when the
        file on disk is identical to the generated content, the stripped lines
        ('line1', 'line2', ...) differ from the kept-ends lines ('line1\\n',
        'line2\\n', ...), producing a spurious non-empty diff and an exit code
        of 1 instead of 0.

        This test writes the generated content directly to disk, then runs the
        CLI again without --force.  With the original code, the diff is empty
        and the command exits 0.  With the mutant (keepends=None), the diff is
        non-empty and the command exits 1.
        """
        output = tmp_path / ".pre-commit-config.yaml"
        # First run: generate and write the file.
        first = runner.invoke(app, ["--lang", "py", "--output", str(output)])
        assert first.exit_code == 0, first.output

        # The generated content is multi-line YAML, so every line ends with '\n'.
        generated_content = output.read_text(encoding="utf-8")
        assert "\n" in generated_content, "generated content must be multi-line"

        # Second run: the file on disk already matches; no diff expected.
        # With keepends=None (mutant), lines like 'repos:\n' become 'repos:'
        # while the generated side still has 'repos:\n', causing a false diff.
        result = runner.invoke(app, ["--lang", "py", "--output", str(output)])
        assert result.exit_code == 0, (
            "Expected exit 0 (no diff) but got non-zero; "
            "possibly keepends=True was changed to keepends=None on"
            " the existing-file side"
        )
        assert "No changes" in result.output

    def test_diff_no_changes_prints_no_changes_message(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        runner.invoke(app, ["--lang", "py", "--output", str(output)])
        result = runner.invoke(app, ["--lang", "py", "--output", str(output)])
        assert "No changes" in result.output

    def test_diff_no_changes_message_includes_target_path(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        runner.invoke(app, ["--lang", "py", "--output", str(output)])
        result = runner.invoke(app, ["--lang", "py", "--output", str(output)])
        assert result.exit_code == 0
        # The message must name the actual target file, not print "None"
        assert str(output) in result.output
        assert "already matches" in result.output

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

    def test_diff_force_hint_starts_with_pc_init(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        output.write_text("existing: content\n", encoding="utf-8")
        result = runner.invoke(app, ["--lang", "py", "--output", str(output)])
        assert result.exit_code == 1
        # The hint command must start with "pc-init", not a mutated placeholder.
        assert "Try: pc-init" in result.output

    def test_diff_force_suggestion_uses_lowercase_pc_init(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        output.write_text("existing: content\n", encoding="utf-8")
        result = runner.invoke(app, ["--lang", "py", "--output", str(output)])
        assert result.exit_code == 1
        # The force-command hint must use the lowercase tool name "pc-init",
        # not an upper-cased variant like "PC-INIT".
        assert "pc-init" in result.output

    def test_diff_force_command_uses_comma_to_join_langs(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        output.write_text("existing: content\n", encoding="utf-8")
        result = runner.invoke(
            app, ["--lang", "py", "--lang", "js", "--output", str(output)]
        )
        assert result.exit_code == 1
        # The suggested "Try:" command must join multiple langs with a plain comma,
        # not the mutant's "XX,XX" separator.
        assert "--lang=py,js" in result.output
        assert "XX,XX" not in result.output

    def test_force_command_hint_parts_joined_by_single_space(
        self, tmp_path: Path
    ) -> None:
        """
        _build_force_command must join parts with a single space.

        The mutant replaces ' '.join(parts) with 'XX XX'.join(parts), producing
        a garbled hint like 'pc-initXX XX--lang=pyXX XX--force'.  This test
        verifies that the 'Try:' hint is a properly space-separated shell command
        by checking that 'pc-init --lang=py --force' appears literally in the output.
        """
        output = tmp_path / ".pre-commit-config.yaml"
        output.write_text("existing: content\n", encoding="utf-8")
        result = runner.invoke(app, ["--lang", "py", "--output", str(output)])
        assert result.exit_code == 1
        assert "pc-init --lang=py --force" in result.output

    def test_force_command_hint_includes_lang_flag(self, tmp_path: Path) -> None:
        """
        The 'Try:' command hint must include the --lang flag used in the invocation.

        _handle_existing_file calls _build_force_command(langs, frameworks) to
        build the hint shown when a diff is detected.  The mutant passes None
        instead of langs, so _build_force_command omits '--lang=py' and the hint
        reads 'pc-init --force' rather than 'pc-init --lang=py --force'.
        """
        output = tmp_path / ".pre-commit-config.yaml"
        output.write_text("existing: content\n", encoding="utf-8")
        result = runner.invoke(app, ["--lang", "py", "--output", str(output)])
        assert result.exit_code == 1
        try_line = next(
            (line for line in result.output.splitlines() if "Try:" in line), None
        )
        assert try_line is not None, "'Try:' hint line not found in output"
        assert "--lang=py" in try_line, (
            f"Expected '--lang=py' in 'Try:' hint line, got: {try_line!r}"
        )

    def test_diff_try_command_hint_contains_force_flag(self, tmp_path: Path) -> None:
        """
        The 'Try:' command hint must include --force as a standalone flag.

        _build_force_command appends '--force' to the suggested command so the
        hint reads e.g. 'Try: pc-init --lang=py --force'.
        A mutant that replaces '--force' with a garbled token (e.g. 'XX--forceXX')
        keeps '--force' as a substring, so checking for '--force' anywhere in the
        output is not enough.  Checking for ' --force' (space + flag) fails for
        the mutant because 'XX--forceXX' is never preceded by a space.
        """
        output = tmp_path / ".pre-commit-config.yaml"
        output.write_text("existing: content\n", encoding="utf-8")
        result = runner.invoke(app, ["--lang", "py", "--output", str(output)])
        try_line = next(
            (line for line in result.output.splitlines() if "Try:" in line), None
        )
        assert try_line is not None, "'Try:' hint line not found in output"
        assert " --force" in try_line, (
            f"Expected ' --force' (space-prefixed) in 'Try:' line, got: {try_line!r}"
        )

    def test_force_bypasses_diff_and_overwrites(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        output.write_text("existing: content\n", encoding="utf-8")
        result = runner.invoke(
            app, ["--lang", "py", "--force", "--output", str(output)]
        )
        assert result.exit_code == 0
        assert output.read_text(encoding="utf-8") != "existing: content\n"

    def test_recommended_flag_forwarded_to_handle_existing_file(
        self, tmp_path: Path, tmp_preset_dir: Path
    ) -> None:
        """
        _dispatch must pass recommended=True to _handle_existing_file.

        When an existing file was generated *without* --recommended, a second
        invocation *with* --recommended should detect a diff (the expanded js
        preset adds hooks absent from the original file) and exit non-zero.
        With the mutant (recommended dropped from _handle_existing_file call),
        the diff is computed without expanding recommendations so the file looks
        identical and the command exits 0 instead of 1.
        """
        output = tmp_path / ".pre-commit-config.yaml"
        # First run: write a file without --recommended (react recommends js,
        # but js is not expanded here).
        runner.invoke(
            app,
            [
                "--lang",
                "py",
                "--framework",
                "react",
                "--presets",
                str(tmp_preset_dir),
                "--output",
                str(output),
            ],
        )
        # Second run: same args but with --recommended.  Because the existing
        # file lacks the js-recommended hooks, there IS a diff → exit code 1.
        result = runner.invoke(
            app,
            [
                "--lang",
                "py",
                "--framework",
                "react",
                "--recommended",
                "--presets",
                str(tmp_preset_dir),
                "--output",
                str(output),
            ],
        )
        assert result.exit_code == 1, (
            "Expected a diff (exit 1) because the existing file was generated "
            "without --recommended and is missing the js-preset hooks"
        )

    def test_diff_no_changes_with_custom_presets_uses_custom_presets_for_comparison(
        self, tmp_path: Path, tmp_preset_dir: Path
    ) -> None:
        """
        _handle_existing_file must receive base_dir, not None.

        When the target file was generated with a custom --presets directory and
        the same command is run again (no --force), _dispatch routes to
        _handle_existing_file.  That function must use base_dir (from --presets)
        to regenerate the content for comparison, not the bundled catalog.

        With the mutant (_handle_existing_file receives None instead of base_dir),
        the comparison is made against bundled presets which differ from the
        custom-preset output, causing a false diff and a non-zero exit code.
        """
        output = tmp_path / ".pre-commit-config.yaml"
        # First invocation: generate the file using the custom presets directory.
        first = runner.invoke(
            app,
            ["--lang", "py", "--presets", str(tmp_preset_dir), "--output", str(output)],
        )
        assert first.exit_code == 0, first.output

        # Second invocation: same custom presets, same output file, no --force.
        # The file content already matches what the custom presets produce, so
        # the diff must be empty and exit_code must be 0.
        # With the mutant (base_dir=None passed to _handle_existing_file), the
        # bundled catalog is used instead, finds differences, and exits 1.
        second = runner.invoke(
            app,
            ["--lang", "py", "--presets", str(tmp_preset_dir), "--output", str(output)],
        )
        assert second.exit_code == 0, second.output
        assert "No changes" in second.output

    def test_force_command_hint_uses_comma_separator_for_multiple_frameworks(
        self, tmp_path: Path
    ) -> None:
        """
        _build_force_command must join frameworks with ',' not 'XX,XX'.

        When a diff is detected on an existing file, _handle_existing_file prints
        a hint of the form 'Try: pc-init --lang=... --framework=a,b --force'.
        The mutant replaces ',' with 'XX,XX' as the join separator, producing
        '--framework=aXX,XXb' which is syntactically wrong.
        """
        output = tmp_path / ".pre-commit-config.yaml"
        output.write_text("existing: content\n", encoding="utf-8")
        result = runner.invoke(
            app,
            [
                "--lang",
                "py",
                "--framework",
                "django",
                "--framework",
                "react",
                "--output",
                str(output),
            ],
        )
        assert result.exit_code == 1
        # The hint must contain the two frameworks joined by a plain comma.
        assert "--framework=django,react" in result.output
        # Mutant produces 'XX,XX' as separator — must not appear.
        assert "XX,XX" not in result.output

    def test_read_permission_error_on_existing_file_shows_cannot_read_message(
        self, tmp_path: Path
    ) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        output.write_text("existing: content\n", encoding="utf-8")
        original_read_text = Path.read_text

        def raise_on_target(self, *args: Any, **kwargs: Any) -> str:
            if self == output:
                msg = "denied"
                raise PermissionError(msg)
            return original_read_text(self, *args, **kwargs)  # type: ignore[return-value]

        with patch.object(Path, "read_text", raise_on_target):
            result = runner.invoke(app, ["--lang", "py", "--output", str(output)])

        assert result.exit_code == 1
        assert "cannot read" in result.output

    def test_read_permission_error_on_existing_file_prints_cannot_read(
        self, tmp_path: Path
    ) -> None:
        """
        _handle_existing_file must print the 'cannot read' error message.

        When reading the existing file raises PermissionError, the error handler
        calls typer.echo with a formatted message that includes 'cannot read' and
        exits with code 1.  The mutant drops the message argument entirely
        (typer.echo(err=True)), so the error text never reaches stderr.
        """
        output = tmp_path / ".pre-commit-config.yaml"
        output.write_text("existing: content\n", encoding="utf-8")

        original_read_text = Path.read_text

        def failing_read_text(self, encoding=None, errors=None):
            if self == output:
                msg = "access denied"
                raise PermissionError(msg)
            return original_read_text(self, encoding=encoding, errors=errors)

        with patch.object(Path, "read_text", failing_read_text):
            result = runner.invoke(app, ["--lang", "py", "--output", str(output)])

        assert result.exit_code == 1
        assert "cannot read" in result.output

    def test_read_permission_error_on_existing_file_goes_to_stderr(
        self, tmp_path: Path
    ) -> None:
        """
        'cannot read' error must be written to stderr, not stdout.

        The mutant drops err=True from typer.echo, sending the message to stdout.
        This test verifies the message appears on stderr and not on stdout.
        """
        output = tmp_path / ".pre-commit-config.yaml"
        output.write_text("existing: content\n", encoding="utf-8")

        original_read_text = Path.read_text

        def failing_read_text(self, encoding=None, errors=None):
            if self == output:
                msg = "access denied"
                raise PermissionError(msg)
            return original_read_text(self, encoding=encoding, errors=errors)

        with patch.object(Path, "read_text", failing_read_text):
            result = runner.invoke(app, ["--lang", "py", "--output", str(output)])

        assert result.exit_code == 1
        assert "cannot read" in result.stderr
        assert "cannot read" not in result.stdout

    def test_read_text_called_with_utf8_encoding_on_existing_file(
        self, tmp_path: Path
    ) -> None:
        """
        _handle_existing_file must read the existing file with encoding='utf-8'.

        The mutant changes encoding='utf-8' to encoding=None in the read_text
        call inside _handle_existing_file.  This test patches Path.read_text to
        record every call, then asserts that the target file is read with the
        explicit 'utf-8' encoding rather than the platform default (None).
        """
        output = tmp_path / ".pre-commit-config.yaml"
        output.write_text("existing: content\n", encoding="utf-8")

        original_read_text = Path.read_text
        calls: list[dict] = []

        def capturing_read_text(self, encoding=None, errors=None):
            calls.append({"path": self, "encoding": encoding})
            return original_read_text(self, encoding=encoding, errors=errors)

        with patch.object(Path, "read_text", capturing_read_text):
            runner.invoke(app, ["--lang", "py", "--output", str(output)])

        assert any(c["path"] == output and c["encoding"] == "utf-8" for c in calls), (
            f"read_text was not called with encoding='utf-8' on the target file; "
            f"calls={calls}"
        )

    def test_recommended_forwarded_to_generate_content_in_handle_existing_file(
        self, tmp_path: Path
    ) -> None:
        """
        _handle_existing_file must pass recommended=True to _generate_content.

        When an existing file was generated without --recommended and the next
        invocation uses --recommended, _handle_existing_file must expand
        recommendations when regenerating content for comparison.  With the mutant
        (recommended keyword argument removed), _generate_content is called with
        the default recommended=False, so the expanded hooks (js/ts from the
        bundled react preset) are absent from the comparison content — the diff
        looks empty and the command exits 0 instead of 1.
        """
        output = tmp_path / ".pre-commit-config.yaml"
        # First run: generate without --recommended.  react recommends js and ts,
        # but those are not expanded here, so the file only contains go+react hooks.
        runner.invoke(
            app,
            ["--lang", "go", "--framework", "react", "--output", str(output)],
        )
        # Second run: same args but with --recommended.  _dispatch routes to
        # _handle_existing_file because the file exists and --force is absent.
        # _handle_existing_file must call _generate_content(recommended=True) so
        # that the comparison content includes the js/ts expansion.  The existing
        # file lacks those hooks, so there IS a diff → exit code 1.
        # With the mutant, recommended=True is dropped and the comparison content
        # matches the stored file → exit code 0.
        result = runner.invoke(
            app,
            [
                "--lang",
                "go",
                "--framework",
                "react",
                "--recommended",
                "--output",
                str(output),
            ],
        )
        assert result.exit_code == 1, (
            "Expected a diff (exit 1) because the existing file was generated "
            "without --recommended and is missing the js/ts preset hooks"
        )


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

    def test_version_queries_correct_package_name(self) -> None:
        with patch(
            "gpc_init.cli.importlib.metadata.version", return_value="1.2.3"
        ) as mock_ver:
            runner.invoke(app, ["--version"])
        mock_ver.assert_called_once_with("pc-init")

    def test_version_prints_unknown_when_package_not_found(self) -> None:
        with patch(
            "gpc_init.cli.importlib.metadata.version",
            side_effect=importlib.metadata.PackageNotFoundError("pc-init"),
        ):
            result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert result.output.strip() == "unknown"

    def test_version_package_not_found_prints_unknown(self) -> None:
        with patch(
            "gpc_init.cli.importlib.metadata.version",
            side_effect=importlib.metadata.PackageNotFoundError("pc-init"),
        ):
            result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert result.output.strip() == "unknown"


class TestEntryPoint:
    def test_entry_point_calls_app(self) -> None:
        with patch("gpc_init.cli.app") as mock_app:
            entry_point()
        mock_app.assert_called_once_with()


class TestDetect:
    def test_detect_flag_generates_valid_config(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        with (
            patch("gpc_init.cli.detect_languages", return_value=["py"]),
            patch("gpc_init.cli.detect_frameworks", return_value=[]),
        ):
            result = runner.invoke(app, ["--detect", "--output", str(output)])
        assert result.exit_code == 0, result.output
        assert output.exists()
        parsed = yaml.safe_load(output.read_text(encoding="utf-8"))
        assert isinstance(parsed, dict)
        assert "repos" in parsed

    def test_detect_flag_prints_detected_langs(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        with (
            patch("gpc_init.cli.detect_languages", return_value=["py"]),
            patch("gpc_init.cli.detect_frameworks", return_value=[]),
        ):
            result = runner.invoke(app, ["--detect", "--output", str(output)])
        assert result.exit_code == 0, result.output
        assert "Detected languages:" in result.output
        assert "py" in result.output

    def test_detect_flag_prints_detected_frameworks(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        with (
            patch("gpc_init.cli.detect_languages", return_value=["py"]),
            patch("gpc_init.cli.detect_frameworks", return_value=["django"]),
        ):
            result = runner.invoke(app, ["--detect", "--output", str(output)])
        assert result.exit_code == 0, result.output
        assert "Detected frameworks:" in result.output
        assert "django" in result.output

    def test_detect_flag_merges_with_explicit_lang(self, tmp_path: Path) -> None:
        """Detected languages and explicitly passed --lang are both included."""
        output = tmp_path / ".pre-commit-config.yaml"
        with (
            patch("gpc_init.cli.detect_languages", return_value=["py"]),
            patch("gpc_init.cli.detect_frameworks", return_value=[]),
        ):
            result = runner.invoke(
                app, ["--detect", "--lang", "md", "--output", str(output)]
            )
        assert result.exit_code == 0, result.output
        assert "py" in result.output
        assert "md" in result.output

    def test_detect_flag_deduplicates_langs(self, tmp_path: Path) -> None:
        """When detect returns a lang also passed via --lang, it appears once."""
        output = tmp_path / ".pre-commit-config.yaml"
        with (
            patch("gpc_init.cli.detect_languages", return_value=["py"]),
            patch("gpc_init.cli.detect_frameworks", return_value=[]),
        ):
            result = runner.invoke(
                app, ["--detect", "--lang", "py", "--output", str(output)]
            )
        assert result.exit_code == 0, result.output
        # "py" should appear in output but not duplicated as "py, py"
        assert "py, py" not in result.output

    def test_detect_no_files_and_no_lang_errors(self, tmp_path: Path) -> None:
        """--detect with nothing detected and no --lang must exit non-zero."""
        output = tmp_path / ".pre-commit-config.yaml"
        with (
            patch("gpc_init.cli.detect_languages", return_value=[]),
            patch("gpc_init.cli.detect_frameworks", return_value=[]),
        ):
            result = runner.invoke(app, ["--detect", "--output", str(output)])
        assert result.exit_code != 0

    def test_detect_no_files_error_message(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        with (
            patch("gpc_init.cli.detect_languages", return_value=[]),
            patch("gpc_init.cli.detect_frameworks", return_value=[]),
        ):
            result = runner.invoke(app, ["--detect", "--output", str(output)])
        assert (
            "No --lang specified" in result.output or "none detected" in result.output
        )

    def test_detect_without_flag_suggests_detect(self, tmp_path: Path) -> None:
        """The 'no --lang' error message should hint about --detect."""
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(app, ["--output", str(output)])
        assert result.exit_code != 0
        assert "--detect" in result.output

    def test_detect_only_with_framework_no_lang_detected_errors(
        self, tmp_path: Path
    ) -> None:
        """--detect + --framework but no lang detected and no --recommended → error."""
        output = tmp_path / ".pre-commit-config.yaml"
        with (
            patch("gpc_init.cli.detect_languages", return_value=[]),
            patch("gpc_init.cli.detect_frameworks", return_value=[]),
        ):
            result = runner.invoke(
                app, ["--detect", "--framework", "django", "--output", str(output)]
            )
        assert result.exit_code != 0

    def test_detect_passes_custom_presets_supported_langs_to_detector(
        self, tmp_path: Path, tmp_preset_dir: Path
    ) -> None:
        """
        _apply_detection calls detect_languages with get_supported_languages(base_dir).

        When --detect and --presets are combined, the supported-language list
        passed to detect_languages must come from the custom presets directory
        (base_dir), not from the bundled catalog (None).

        The fixture presets dir contains only 'js' and 'py'.  The bundled catalog
        contains many more (go, docker, ts, …).  With the mutant
        (get_supported_languages(None)), the bundled catalog is used and languages
        like 'go' appear in the supported list.  With the original code,
        get_supported_languages(base_dir) returns only ['js', 'py'] and 'go' is
        absent from the supported list.

        This test captures the supported list argument and asserts that it matches
        the custom catalog's contents exactly, killing the mutant.
        """
        output = tmp_path / ".pre-commit-config.yaml"
        captured_supported: list[list[str]] = []

        def capturing_detect_languages(
            _repo_dir: Path, supported: list[str]
        ) -> list[str]:
            captured_supported.append(list(supported))
            return ["py"]

        with (
            patch(
                "gpc_init.cli.detect_languages", side_effect=capturing_detect_languages
            ),
            patch("gpc_init.cli.detect_frameworks", return_value=[]),
        ):
            result = runner.invoke(
                app,
                ["--detect", "--presets", str(tmp_preset_dir), "--output", str(output)],
            )

        assert result.exit_code == 0, result.output
        assert captured_supported, "detect_languages was never called"
        supported_used = set(captured_supported[0])
        # The fixture presets dir has only 'js' and 'py'; the bundled catalog has
        # many more (e.g. 'go', 'docker', 'ts').  The mutant passes None and gets
        # the full bundled list, so 'go' would be present.
        assert "go" not in supported_used, (
            f"'go' must not be in the supported langs (bundled catalog leaked in): "
            f"{supported_used}"
        )
        assert "js" in supported_used
        assert "py" in supported_used

    def test_detect_with_custom_presets_uses_custom_framework_catalog(
        self, tmp_path: Path, tmp_preset_dir: Path
    ) -> None:
        """
        _apply_detection must pass base_dir to get_supported_frameworks, not None.

        The fixture custom presets dir contains only 'react' as a supported framework.
        The bundled catalog also contains 'django'.  When the mutant calls
        get_supported_frameworks(None), 'django' is included in the supported set and
        detect_frameworks detects it from the manage.py file in the fake project dir.
        validate_frameworks then raises UnsupportedFrameworkError ('django' is absent
        from the custom presets dir) and the command exits 1.

        With the original code, get_supported_frameworks(base_dir) returns only
        ['react'], so 'django' is not in the detection candidate set and is silently
        skipped -- the command exits 0.
        """
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        (repo_dir / "manage.py").write_text("# django manage.py\n", encoding="utf-8")
        output = tmp_path / "out.yaml"

        with patch.object(Path, "cwd", return_value=repo_dir):
            result = runner.invoke(
                app,
                [
                    "--detect",
                    "--lang",
                    "py",
                    "--presets",
                    str(tmp_preset_dir),
                    "--output",
                    str(output),
                ],
            )

        assert result.exit_code == 0, (
            "Expected exit 0: 'django' is not in the custom presets catalog so "
            "detect_frameworks should not surface it. "
            f"Got exit {result.exit_code}; output: {result.output}"
        )

    def test_detect_detected_langs_joined_by_comma_space(self, tmp_path: Path) -> None:
        """
        Detected languages in the output message must be joined by ', ' not 'XX, XX'.

        _apply_detection prints "Detected languages: {', '.join(detected_langs)}".
        The mutant replaces the separator with 'XX, XX'.  When two languages are
        detected the output reads "Detected languages: pyXX, XXjs" instead of
        "Detected languages: py, js".  This test asserts the exact separator.
        """
        output = tmp_path / ".pre-commit-config.yaml"
        with (
            patch("gpc_init.cli.detect_languages", return_value=["py", "js"]),
            patch("gpc_init.cli.detect_frameworks", return_value=[]),
        ):
            result = runner.invoke(app, ["--detect", "--output", str(output)])
        assert result.exit_code == 0, result.output
        assert "Detected languages: py, js" in result.output
        assert "XX" not in result.output

    def test_detect_flag_prints_multiple_frameworks_joined_by_comma_space(
        self, tmp_path: Path
    ) -> None:
        """
        Detected frameworks must be joined with ', ' not 'XX, XX'.

        _apply_detection uses ', '.join(detected_frameworks) to build the
        echo message.  The mutant replaces the separator with 'XX, XX', which
        produces 'djangoXX, XXreact' instead of 'django, react'.
        This test detects two frameworks so the separator is exercised.
        """
        output = tmp_path / ".pre-commit-config.yaml"
        with (
            patch("gpc_init.cli.detect_languages", return_value=["py"]),
            patch("gpc_init.cli.detect_frameworks", return_value=["django", "react"]),
        ):
            result = runner.invoke(app, ["--detect", "--output", str(output)])
        assert result.exit_code == 0, result.output
        assert "Detected frameworks: django, react" in result.output
        assert "XX, XX" not in result.output

    def test_detect_flag_merges_with_explicit_framework(self, tmp_path: Path) -> None:
        """
        Explicit --framework must be included even when --detect detects nothing.

        _apply_detection merges detected frameworks with the user-supplied
        --framework list via _expand_comma_separated(framework).  The mutant
        replaces 'framework' with 'None', so _expand_comma_separated(None) always
        returns [] and any explicit --framework value is silently dropped.
        With the original code, 'react' appears in the success message because it
        is merged in.  With the mutant, 'react' is absent and 'frameworks: none'
        is printed instead.
        """
        output = tmp_path / ".pre-commit-config.yaml"
        with (
            patch("gpc_init.cli.detect_languages", return_value=["py"]),
            patch("gpc_init.cli.detect_frameworks", return_value=[]),
        ):
            result = runner.invoke(
                app, ["--detect", "--framework", "react", "--output", str(output)]
            )
        assert result.exit_code == 0, result.output
        assert "react" in result.output, (
            "Expected 'react' in output -- explicit --framework must survive "
            "the _apply_detection merge (mutant drops it by passing None instead "
            "of 'framework' to _expand_comma_separated)"
        )

    def test_detect_passes_cwd_to_detectors(self, tmp_path: Path) -> None:
        """detect_languages and detect_frameworks are called with Path.cwd()."""
        output = tmp_path / ".pre-commit-config.yaml"
        cwd = Path("/some/project")
        captured: list[Path] = []

        def fake_detect_langs(repo_dir: Path, supported: list[str]) -> list[str]:  # noqa: ARG001
            captured.append(repo_dir)
            return ["py"]

        with (
            patch("gpc_init.cli.Path") as mock_path_cls,
            patch("gpc_init.cli.detect_languages", side_effect=fake_detect_langs),
            patch("gpc_init.cli.detect_frameworks", return_value=[]),
        ):
            mock_path_cls.cwd.return_value = cwd
            mock_path_cls.return_value = Path(str(output))
            runner.invoke(app, ["--detect", "--output", str(output)])

        assert cwd in captured
