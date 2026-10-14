#!/bin/sh
set -eu

cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
uv sync --locked --group dev --inexact
uv run --locked pre-commit install --install-hooks
