# mutmut Survivor Kill Report

**Date:** 2026-06-22

## Summary

| Metric | Count |
|---|---|
| Started with | 82 |
| Newly killed | 65 |
| Tests written | 71 |
| Still surviving | 9 |

## Equivalent Mutants (8)

These mutants cannot be killed by tests — no observable behavioral difference exists between the original and mutated code.

| Mutant | Reason |
|---|---|
| `gpc_init.merger.x_merge_presets__mutmut_21` | The `repos` key is filtered twice; `_deep_merge_top_level` already drops `repos` unconditionally (line 93-94 of merger.py), so removing the first filter in `merge_presets` produces no observable difference. |
| `gpc_init.merger.x_merge_presets__mutmut_22` | Changing the filter string from `"repos"` to `"REPOS"` allows `repos` to flow into `non_repo`, but `_deep_merge_top_level` still skips it. The final merged dict is identical. |
| `gpc_init.cli.x__run__mutmut_45` | The system's default locale encoding is UTF-8. Removing `encoding="utf-8"` from `write_text` causes Python to use the platform default, which is also UTF-8. The YAML content is ASCII-safe, so on-disk bytes are identical. |
| `gpc_init.cli.x__run__mutmut_47` | Python's `codecs` module normalizes encoding names, so `"utf-8"`, `"UTF-8"`, `"utf8"`, and `"UTF8"` all resolve to the same codec. `Path.write_text()` writes identical bytes either way. |
| `gpc_init.resolver.x_get_primary_languages_info__mutmut_11` | Both `[]` and `None` are falsy. The default is only used when `primary_languages` is absent from the preset dict, in which case `if primary` is `False` for both values. The `None` vs `[]` distinction never affects execution. |
| `gpc_init.resolver.x_get_primary_languages_info__mutmut_13` | Both `None` (returned by `dict.get(key)` when absent) and `[]` are falsy. All code using `primary` beyond the truthiness check is inside the `if primary` block and unreachable when the key is absent. |
| `gpc_init.renderer.x_render_yaml__mutmut_7` | PyYAML's `Dumper` class defaults `default_flow_style` to `False`. Passing `default_flow_style=False` explicitly is redundant — removing it produces the same YAML output for all inputs. |
| `gpc_init.loader.x__load_yaml_file__mutmut_5` | `open(path, encoding="UTF-8")` and `open(path, encoding="utf-8")` are completely equivalent — Python normalizes codec names internally. |

## Remaining Non-Equivalent Survivors (4)

These were not killed and not classified as equivalent — they may need further investigation:

- `gpc_init.cli.x__run__mutmut_70`
- `gpc_init.cli.x__run__mutmut_73`
- `gpc_init.renderer.x_render_yaml__mutmut_8`
- `gpc_init.loader.x__load_yaml_file__mutmut_13`
