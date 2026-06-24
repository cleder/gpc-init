"""Unit tests for gpc_init/renderer.py."""

import yaml

from gpc_init.renderer import render_yaml


class TestRenderYaml:
    def test_renders_to_valid_yaml(self) -> None:
        data = {
            "repos": [
                {
                    "repo": "https://example.com",
                    "rev": "v1.0.0",
                    "hooks": [{"id": "my-hook"}],
                }
            ]
        }
        output = render_yaml(data)
        parsed = yaml.safe_load(output)
        assert parsed == data

    def test_deterministic_output(self) -> None:
        data = {
            "repos": [
                {"repo": "https://b.com", "rev": "v2", "hooks": [{"id": "hb"}]},
                {"repo": "https://a.com", "rev": "v1", "hooks": [{"id": "ha"}]},
            ]
        }
        out1 = render_yaml(data)
        out2 = render_yaml(data)
        assert out1 == out2

    def test_sort_keys_for_determinism(self) -> None:
        data_a = {"z_key": "last", "a_key": "first", "repos": []}
        data_b = {"a_key": "first", "z_key": "last", "repos": []}
        assert render_yaml(data_a) == render_yaml(data_b)

    def test_renders_hook_args_as_list(self) -> None:
        data = {
            "repos": [
                {
                    "repo": "local",
                    "hooks": [
                        {
                            "id": "my-hook",
                            "args": ["--strict", "--verbose"],
                        }
                    ],
                }
            ]
        }
        output = render_yaml(data)
        parsed = yaml.safe_load(output)
        assert parsed["repos"][0]["hooks"][0]["args"] == ["--strict", "--verbose"]

    def test_renders_additional_dependencies(self) -> None:
        data = {
            "repos": [
                {
                    "repo": "local",
                    "hooks": [
                        {
                            "id": "prettier",
                            "additional_dependencies": ["prettier@3.0.0"],
                        }
                    ],
                }
            ]
        }
        output = render_yaml(data)
        parsed = yaml.safe_load(output)
        assert (
            "prettier@3.0.0"
            in parsed["repos"][0]["hooks"][0]["additional_dependencies"]
        )

    def test_empty_dict_renders_to_yaml(self) -> None:
        output = render_yaml({})
        assert output.strip() == "{}"

    def test_round_trip_semantics(self) -> None:
        """Parsing the rendered output should yield the original data."""
        data = {
            "default_language_version": {"python": "python3.12"},
            "repos": [
                {
                    "repo": "https://github.com/pre-commit/pre-commit-hooks",
                    "rev": "v4.6.0",
                    "hooks": [
                        {"id": "trailing-whitespace"},
                        {"id": "end-of-file-fixer"},
                    ],
                }
            ],
        }
        output = render_yaml(data)
        round_tripped = yaml.safe_load(output)
        assert round_tripped == data

    def test_output_uses_block_style_not_flow_style(self) -> None:
        """Rendered YAML must use block style only — no inline flow-style dicts."""
        data = {
            "repos": [
                {
                    "repo": "https://example.com",
                    "rev": "v1.0.0",
                    "hooks": [{"id": "my-hook"}],
                }
            ]
        }
        output = render_yaml(data)
        assert "{" not in output, (
            "render_yaml must use default_flow_style=False to produce"
            " block-style YAML; "
            f"found flow-style braces in output:\n{output}"
        )

    def test_allow_unicode_renders_literal_non_ascii(self) -> None:
        """Non-ASCII characters must appear literally, not as escape sequences."""
        data = {"name": "café", "label": "こんにちは"}
        output = render_yaml(data)
        assert "café" in output
        assert "こんにちは" in output

    def test_long_string_value_is_not_line_wrapped(self) -> None:
        # A string with spaces longer than 80 chars; yaml.dump with width=None
        # (the default 80) wraps it, but width=4096 keeps it on a single line.
        long_value = (
            "word1 word2 word3 word4 word5 word6 word7 word8 "
            "word9 word10 word11 word12 word13 word14"
        )
        data = {"key": long_value}
        output = render_yaml(data)
        # The value must not be split across lines (no folded/wrapped scalar).
        assert "\n " not in output.rstrip("\n")

    def test_keys_are_sorted_in_output(self) -> None:
        data = {"z_key": "last", "a_key": "first", "m_key": "middle"}
        output = render_yaml(data)
        lines = [line for line in output.splitlines() if ":" in line]
        key_names = [line.split(":")[0].strip() for line in lines]
        assert key_names == sorted(key_names)

    def test_unicode_values_are_not_escaped(self) -> None:
        r"""Unicode characters must appear literally, not as \\xNN escape sequences."""
        data = {"name": "café"}
        output = render_yaml(data)
        assert "café" in output
        assert "\\x" not in output

    def test_values_within_width_are_not_folded(self) -> None:
        # 2046 single-char words → 'kk: ' (4) + 2046 'w' + 2045 spaces = 4095 chars,
        # which is within width=4096, so yaml.dump must not fold it.
        near_limit_value = " ".join(["w"] * 2046)
        output = render_yaml({"kk": near_limit_value})
        assert len(output.splitlines()) == 1, (
            "value within width=4096 must not be folded"
        )

    def test_width_4096_wraps_near_boundary(self) -> None:
        # 2048 single-char words → full YAML line is ~4099 chars ('kk: w w...w'),
        # which exceeds width=4096 so yaml.dump must fold it.  width=4097 keeps
        # it on a single line, so asserting > 1 lines detects that mutation.
        long_value = " ".join(["w"] * 2048)
        output = render_yaml({"kk": long_value})
        assert len(output.splitlines()) > 1, (
            "render_yaml must fold a value that exceeds width=4096"
        )
