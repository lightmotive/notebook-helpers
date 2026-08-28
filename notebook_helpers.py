from __future__ import annotations

import importlib
import os
import pathlib
import re
import shutil
import urllib.parse
import urllib.request
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

__version__ = "0.1.0"

__all__ = ["ContentMismatchError", "FetchError", "InterstitialError", "fetch"]


class FetchError(Exception):
    pass


class InterstitialError(FetchError):
    pass


class ContentMismatchError(FetchError):
    pass


def _load_gdown() -> ModuleType | None:
    try:
        return importlib.import_module("gdown")
    except ImportError:
        return None


def _resolve_source(source: str) -> tuple[str, str | None]:
    if source.startswith("http://") or source.startswith("https://"):
        parsed = urllib.parse.urlparse(source)
        netloc = parsed.netloc.lower()
        if netloc in ("drive.google.com", "drive.usercontent.google.com"):
            # Check for id in query params
            qs = urllib.parse.parse_qs(parsed.query)
            if "id" in qs:
                drive_id = qs["id"][0]
            else:
                # Check path /file/d/<id>/...
                m = re.match(r"^/file/d/([A-Za-z0-9_-]+)(?:/.*)?$", parsed.path)
                if m:
                    drive_id = m.group(1)
                else:
                    return source, None
            return (
                f"https://drive.google.com/uc?export=download&id={drive_id}",
                drive_id,
            )
        return source, None
    elif re.match(r"^[A-Za-z0-9_-]{20,}$", source):
        # bare Drive ID
        return f"https://drive.google.com/uc?export=download&id={source}", source
    else:
        raise ValueError(
            "Source must be a public http(s) URL or a bare Google Drive file ID"
        )


def fetch(
    source: str,
    dest: str | os.PathLike[str],
    *,
    expects: str | bytes | None = None,
    force: bool = False,
    quiet: bool = False,
) -> pathlib.Path:
    dest_path = pathlib.Path(dest)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    url, drive_id = _resolve_source(source)

    if dest_path.exists() and not force:
        if expects is None:
            return dest_path

        # Check expects
        first_line = dest_path.read_bytes().split(b"\n", 1)[0]
        exp_bytes = expects if isinstance(expects, bytes) else expects.encode("utf-8")
        if not first_line.startswith(exp_bytes):
            dest_path.unlink()
            msg_line = first_line.decode(errors="replace")
            raise ContentMismatchError(
                f"Cached file mismatch. Expected to start with {exp_bytes!r} "
                f"but got {msg_line!r}. "
                "The bad cache was removed. Please re-run the cell. "
                "Note the source may be private or serving an error page."
            )
        return dest_path

    part = dest_path.with_name(dest_path.name + ".part")
    try:
        if drive_id and (gdown := _load_gdown()) is not None:
            res = gdown.download(id=drive_id, output=str(part), quiet=quiet)
            if res is None:
                raise FetchError("gdown failed to download the file")
        else:
            req = urllib.request.Request(
                url, headers={"User-Agent": f"notebook-helpers/{__version__}"}
            )
            with urllib.request.urlopen(req) as resp, part.open("wb") as fh:
                shutil.copyfileobj(resp, fh, length=1024 * 1024)

        if expects is not None:
            first_line = part.read_bytes().split(b"\n", 1)[0]
            exp_bytes = (
                expects if isinstance(expects, bytes) else expects.encode("utf-8")
            )
            if not first_line.startswith(exp_bytes):
                msg_line = first_line.decode(errors="replace")
                raise ContentMismatchError(
                    f"Downloaded file mismatch. Expected to start with {exp_bytes!r} "
                    f"but got {msg_line!r}. "
                    "Please re-run the cell. "
                    "Note the source may be private or serving an error page."
                )
        elif drive_id:
            with part.open("rb") as f:
                head = f.read(1024)
            # strip BOM and leading whitespace, lowercase
            head_clean = head.lstrip(b"\xef\xbb\xbf \t\n\r").lower()
            if head_clean.startswith(b"<!doctype html") or head_clean.startswith(
                b"<html"
            ):
                raise InterstitialError(
                    "Drive served a virus-scan interstitial instead of the file. "
                    "pip install gdown to download this file."
                )

        part.replace(dest_path)

        if not quiet:
            size = dest_path.stat().st_size
            print(f"Loaded {dest_path} ({size:,} bytes)")

        return dest_path

    except Exception:
        part.unlink(missing_ok=True)
        raise
