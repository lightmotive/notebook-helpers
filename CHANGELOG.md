# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-08-28

### Added
- `fetch()` function to reliably pull remote data files.
- Support for ordinary URLs with `urllib` streaming download.
- Support for Google Drive IDs bypassing virus-scan interstitials (via optional `gdown`).
- Atomic downloads using `.part` extension.
- Caching to avoid re-downloads unless `force=True` is used.
- Optional content validation via the `expects=` parameter.
