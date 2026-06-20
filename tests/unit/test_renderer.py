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
