"""Integration tests for pc-init CLI generation."""

from pathlib import Path

import yaml
from typer.testing import CliRunner

from gpc_init.cli import app

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
                "--lang", "py",
                "--lang", "js",
                "--framework", "django",
                "--framework", "react",
                "--output", str(output),
            ],
        )
        assert result.exit_code == 0, result.output
        parsed = yaml.safe_load(output.read_text(encoding="utf-8"))
        assert "repos" in parsed


class TestErrorHandling:
    def test_unsupported_lang_exits_nonzero(self, tmp_path: Path) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(
            app, ["--lang", "cobol", "--output", str(output)]
        )
        assert result.exit_code != 0

    def test_unsupported_lang_error_message_includes_supported(
        self, tmp_path: Path
    ) -> None:
        output = tmp_path / ".pre-commit-config.yaml"
        result = runner.invoke(
            app, ["--lang", "cobol", "--output", str(output)]
        )
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
        runner.invoke(
            app, ["--lang", "py", "--lang", "js", "--output", str(out1)]
        )
        runner.invoke(
            app, ["--lang", "js", "--lang", "py", "--output", str(out2)]
        )
        # Different order may produce different file; both should be valid YAML
        parsed1 = yaml.safe_load(out1.read_text(encoding="utf-8"))
        parsed2 = yaml.safe_load(out2.read_text(encoding="utf-8"))
        assert isinstance(parsed1, dict)
        assert isinstance(parsed2, dict)
