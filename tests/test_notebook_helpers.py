import io
import sys
from pathlib import Path
from urllib.error import HTTPError

import pytest

import notebook_helpers
from notebook_helpers import (
    ContentMismatchError,
    FetchError,
    InterstitialError,
    _resolve_source,
    fetch,
)


class FakeResponse:
    def __init__(self, data: bytes):
        self._data = data
        self.stream = io.BytesIO(data)

    def read(self, size=-1):
        return self.stream.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class FakeGdown:
    def __init__(self):
        self.fail = False
        self.return_none = False

    def download(self, id, output, quiet):
        if self.return_none:
            return None
        if self.fail:
            raise RuntimeError("gdown failed")
        Path(output).write_bytes(b"gdown content")
        return str(output)


@pytest.fixture
def fake_urlopen(monkeypatch):
    class MockUrlopen:
        def __init__(self):
            self.call_count = 0
            self.urls = []
            self.data = b"default content"
            self.error = None

        def __call__(self, req):
            self.call_count += 1
            self.urls.append(req.full_url)
            if isinstance(self.error, Exception):
                raise self.error
            if self.error == "interrupt":

                class InterruptingResponse:
                    def __enter__(self):
                        return self

                    def __exit__(self, *args):
                        pass

                    def read(self, size=-1):
                        raise RuntimeError("interrupted mid-stream")

                return InterruptingResponse()
            return FakeResponse(self.data)

    mock = MockUrlopen()
    monkeypatch.setattr("notebook_helpers.urllib.request.urlopen", mock)
    return mock


@pytest.fixture
def fake_gdown(monkeypatch):
    stub = FakeGdown()

    # Need to mock sys.modules
    class MockModule:
        download = stub.download

    monkeypatch.setitem(sys.modules, "gdown", MockModule())
    return stub


@pytest.fixture
def no_gdown(monkeypatch):
    monkeypatch.setitem(sys.modules, "gdown", None)


@pytest.fixture(autouse=True)
def setup_tmpdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_1_happy_path_ordinary_url(fake_urlopen):
    fake_urlopen.data = b"hello world\nline 2"
    res = fetch("https://example.com/data.csv", "out.csv")
    assert res == Path("out.csv")
    assert res.read_bytes() == b"hello world\nline 2"
    assert fake_urlopen.call_count == 1
    assert not Path("out.csv.part").exists()


def test_2_cache_hit(fake_urlopen):
    fake_urlopen.data = b"first run"
    fetch("https://example.com/data.csv", "cache.csv")
    assert fake_urlopen.call_count == 1

    # second call should hit cache, failing urlopen if called
    fake_urlopen.error = RuntimeError("should not be called")
    fetch("https://example.com/data.csv", "cache.csv")
    assert fake_urlopen.call_count == 1


def test_3_expects_mismatch_fresh_download(fake_urlopen):
    fake_urlopen.data = b"bad data"
    with pytest.raises(ContentMismatchError):
        fetch("https://example.com/data.csv", "out.csv", expects=b"good")
    assert not Path("out.csv").exists()
    assert not Path("out.csv.part").exists()


def test_4_expects_mismatch_cached_file(fake_urlopen):
    Path("cache.csv").write_bytes(b"bad cache")
    with pytest.raises(ContentMismatchError, match="bad cache") as exc:
        fetch("https://example.com/data.csv", "cache.csv", expects=b"good")
    assert not Path("cache.csv").exists()
    assert "re-run the cell" in str(exc.value)


def test_5_expects_match(fake_urlopen):
    fake_urlopen.data = b"good data\nmore"
    fetch("https://example.com/data.csv", "out.csv", expects=b"good")
    assert Path("out.csv").read_bytes() == b"good data\nmore"
    # coverage for cache hit with matching expects
    fake_urlopen.should_fail = True
    fetch("https://example.com/data.csv", "out.csv", expects=b"good")


def test_6_drive_source_html_interstitial(fake_urlopen, no_gdown):
    fake_urlopen.data = b"<!DOCTYPE html>\n<html>bad</html>"
    with pytest.raises(InterstitialError, match="pip install gdown"):
        fetch("1K4OvzpQUrJl--J7NN8d-rWkUXNugzYex", "out.csv")
    assert not Path("out.csv").exists()
    assert not Path("out.csv.part").exists()


def test_7_ordinary_url_serving_html(fake_urlopen):
    fake_urlopen.data = b"<!DOCTYPE html>\n<html>good</html>"
    fetch("https://example.com/index.html", "out.html")
    assert Path("out.html").read_bytes() == b"<!DOCTYPE html>\n<html>good</html>"


def test_8_interrupted_download(fake_urlopen):
    fake_urlopen.error = "interrupt"
    with pytest.raises(RuntimeError, match="interrupted"):
        fetch("https://example.com/data.csv", "out.csv")
    assert not Path("out.csv").exists()
    assert not Path("out.csv.part").exists()


def test_9_http_404(fake_urlopen):
    fake_urlopen.error = HTTPError("url", 404, "Not Found", {}, None)
    with pytest.raises(HTTPError):
        fetch("https://example.com/data.csv", "out.csv")
    assert not Path("out.csv").exists()
    assert not Path("out.csv.part").exists()


def test_10_drive_id_gdown_present(fake_urlopen, fake_gdown):
    fake_urlopen.error = RuntimeError("should not use urlopen")
    fetch("1K4OvzpQUrJl--J7NN8d-rWkUXNugzYex", "out.csv")
    assert Path("out.csv").read_bytes() == b"gdown content"


def test_11_drive_id_gdown_absent(fake_urlopen, no_gdown):
    fake_urlopen.data = b"urllib content"
    fetch("1K4OvzpQUrJl--J7NN8d-rWkUXNugzYex", "out.csv")
    assert Path("out.csv").read_bytes() == b"urllib content"
    assert fake_urlopen.urls[-1].startswith(
        "https://drive.google.com/uc?export=download&id="
    )


def test_12_ordinary_url_gdown_present(fake_urlopen, fake_gdown):
    fake_gdown.fail = True
    fake_urlopen.data = b"urllib content"
    fetch("https://example.com/data.csv", "out.csv")
    assert Path("out.csv").read_bytes() == b"urllib content"


def test_13_gdown_returns_none(fake_urlopen, fake_gdown):
    fake_gdown.return_none = True
    with pytest.raises(FetchError):
        fetch("1K4OvzpQUrJl--J7NN8d-rWkUXNugzYex", "out.csv")
    assert not Path("out.csv.part").exists()


def test_14_force_true_over_cache(fake_urlopen):
    Path("cache.csv").write_bytes(b"old")
    fake_urlopen.data = b"new"
    fetch("https://example.com/data.csv", "cache.csv", force=True)
    assert Path("cache.csv").read_bytes() == b"new"


def test_15_source_resolution():
    cases = [
        ("1K4OvzpQUrJl--J7NN8d-rWkUXNugzYex", "1K4OvzpQUrJl--J7NN8d-rWkUXNugzYex"),
        (
            "https://drive.google.com/file/d/1K4OvzpQUrJl--J7NN8d-rWkUXNugzYex/view",
            "1K4OvzpQUrJl--J7NN8d-rWkUXNugzYex",
        ),
        (
            "https://drive.google.com/uc?id=1K4OvzpQUrJl--J7NN8d-rWkUXNugzYex",
            "1K4OvzpQUrJl--J7NN8d-rWkUXNugzYex",
        ),
    ]
    for source, expected_id in cases:
        url, drive_id = _resolve_source(source)
        assert drive_id == expected_id
        assert url == f"https://drive.google.com/uc?export=download&id={expected_id}"

    url, drive_id = _resolve_source("https://example.com/x.csv")
    assert drive_id is None
    assert url == "https://example.com/x.csv"

    with pytest.raises(ValueError):
        _resolve_source("not a url")

    with pytest.raises(ValueError):
        _resolve_source("ftp://example.com/x.csv")


def test_16_nested_dest(fake_urlopen):
    fake_urlopen.data = b"nested"
    fetch("https://example.com/x.csv", "temp_data/x.csv")
    assert Path("temp_data/x.csv").read_bytes() == b"nested"


def test_17_release_consistency():
    assert notebook_helpers.__version__ == "0.1.0"

    root = Path(__file__).parent.parent

    pyproject = root / "pyproject.toml"
    assert pyproject.exists()
    assert 'version = "0.1.0"' in pyproject.read_text()

    changelog = root / "CHANGELOG.md"
    assert changelog.exists()
    assert "## [0.1.0]" in changelog.read_text()

    readme = root / "README.md"
    assert readme.exists()
    assert "notebook-helpers/v0.1.0/notebook_helpers.py" in readme.read_text()
