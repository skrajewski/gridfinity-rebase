# STL test fixtures

These models are included in the repository so the regression tests run without
external downloads or files in the local `tmp/` directory. They were moved from
that directory without changing their contents or filenames.

| File | Purpose |
| --- | --- |
| `gf_bin_1x1_h6_bin_v01.stl` | Reference 1×1 standard bin for automatic base detection, interior preservation and rejection of donors with a lower floor. |
| `test.stl` | Custom 1×1 model for donor replacement, float32 export and explicit base-height override tests. |
| `test-rebased.stl` | Rebased counterpart used as a donor and as another input for float32 export regression tests. |

The tests read these fixtures and write outputs to pytest's temporary directories.
Missing fixtures are test failures; these tests are not skipped when files are
absent. Other tests generate synthetic models for specific geometry and
validation cases.

Run the complete suite from the repository root:

```sh
uv run --locked pytest -q
```
