# notebook-helpers

[![CI](https://github.com/lightmotive/notebook-helpers/actions/workflows/ci.yml/badge.svg)](https://github.com/lightmotive/notebook-helpers/actions/workflows/ci.yml)

A zero-dependency helper to reliably fetch remote data files from Jupyter notebooks in Google Colab and local VS Code.

## Quickstart

Add this to a notebook cell to fetch a file:

```python
import pathlib, urllib.request

if not pathlib.Path("notebook_helpers.py").exists():
    urllib.request.urlretrieve(
        "https://raw.githubusercontent.com/lightmotive/notebook-helpers/v0.1.0/notebook_helpers.py",
        "notebook_helpers.py",
    )
from notebook_helpers import fetch

csv_path = fetch(
    "1K4OvzpQUrJl--J7NN8d-rWkUXNugzYex",
    "temp_data/pizza_sales.csv",
)
```

## Install

This package is designed to be bootstrapped directly via `urllib.request` as shown in the quickstart, requiring zero installation. 

However, you can also pip install it if you want to include it in a project environment:
```bash
pip install git+https://github.com/lightmotive/notebook-helpers.git@v0.1.0
```
For Google Drive virus-scan bypass on large files, install with the `drive` extra (which brings in `gdown`):
```bash
pip install "notebook-helpers[drive] @ git+https://github.com/lightmotive/notebook-helpers.git@v0.1.0"
```

## API

### `fetch(source: str, dest: str | os.PathLike, *, expects: str | bytes | None = None, force: bool = False, quiet: bool = False) -> pathlib.Path`

- `source`: Any public URL, or a bare Google Drive file ID.
- `dest`: Local file path to cache the download.
- `expects`: Optional string or bytes prefix the file's first line must start with.
- `force`: Set to `True` to force re-download over an existing cached file.
- `quiet`: Set to `True` to suppress output.

## Limitations

- When dealing with large Google Drive files, Google displays a virus-scan warning interstitial. For ordinary URLs, `fetch()` can handle the download with standard Python libraries. For Drive, `fetch()` requires the `gdown` backend to be installed in the environment to bypass this interstitial. If `gdown` is absent and an interstitial is encountered, it raises an `InterstitialError`.
