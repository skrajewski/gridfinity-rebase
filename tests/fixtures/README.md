# STL test fixtures

The regression tests use these models without external downloads or files in
the local `tmp/` directory. The files came from that directory and retain their
original contents and filenames.

| File | Purpose |
| --- | --- |
| `gf_bin_1x1_h6_bin_v01.stl` | Reference 1×1 standard bin for automatic base detection, interior preservation and rejection of donors with a lower floor. |
| `test.stl` | Custom 1×1 model for donor replacement, float32 export and explicit base-height override tests. |
| `test-rebased.stl` | The rebased model acts as a donor and as another input for float32 export regression tests. |

The tests read these fixtures and write outputs to pytest's temporary directories.
The tests fail if a fixture is missing. Other tests generate synthetic models
for specific geometry and validation cases.

Run the complete suite from the repository root:

```sh
uv run --locked pytest -q
```
