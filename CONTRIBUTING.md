# Contributing to Floodwatch

Floodwatch is a small project with one maintainer, and bug reports, corrections and pull requests are all welcome. A gauge in the wrong place, a storm overflow that belongs to the next catchment, a river drawn short or a warning that never showed up are as useful as code.

## Reporting a problem

Open an [issue](https://github.com/aallan/floodwatch/issues/new/choose) using the bug report or feature request template. For anything on the map, say which gauge, overflow or place it is, roughly when you saw it, and whether you were on a phone or a computer; a screenshot helps more than a description. Security problems go by email instead, as [SECURITY.md](.github/SECURITY.md) describes.

## Setting up

You'll need Python 3.10 or later, Node 22 or later, `make`, `curl` and `shasum`. There's nothing to install from PyPI or npm to run the site or its tests.

```bash
git clone https://github.com/aallan/floodwatch.git
cd floodwatch
make libs
make data
make serve
```

The site is then at http://localhost:8090. The [README](README.md#running-it) says what the first poll does, and how to rebuild the map overlays from the download cache.

[Ruff](https://docs.astral.sh/ruff/) checks the Python, in CI and, if you want it before each commit, through [pre-commit](https://pre-commit.com/):

```bash
pip install pre-commit
pre-commit install
```

## Conventions

- The server, the poller and the scripts use the Python standard library and nothing else. A change that needs a package from PyPI needs a very good reason.
- The page is plain HTML, CSS and JavaScript with no framework and no build step. Leaflet and Leaflet.markercluster are the only libraries; `make libs` downloads them and checks them against `libs.sha256`, so an upgrade changes the version in the `Makefile` and the checksums together.
- The page loads nothing from anywhere but its own server and Esri's tile servers, and the Content Security Policy in `serve.py` enforces that. New data from an outside service is fetched by the server and passed to the page through `/api/`.
- Each feed lives in its own module in `monitor/` and fails on its own, without stopping the rest of the poll.
- Whether something belongs to the catchment is decided by `monitor/region.py`, for every layer, rather than by a box or a radius of its own.
- `archive/` is written by the server every night. Don't edit it by hand, and keep code changes and archive changes in separate commits.
- Text on the page, in comments and in the documentation is British English, with headings in sentence case.

## Tests

```bash
make test       # both suites
make test-py    # the Python tests, with unittest
make test-js    # the JavaScript tests, with Node's test runner
```

The Python tests run against a temporary database, and every outside service is replaced by a fixed response, so they need no network. Fixtures in `tests/fixtures/` are trimmed copies of real responses; when a service changes the shape of what it sends, update the fixture from a real response rather than writing one by hand. The JavaScript tests load the page's scripts into a sandbox, through `tests/js/load.mjs`, and test their functions directly.

A change to behaviour comes with a test that fails without it.

## Pull requests

Branch from `main` and open the pull request against it. GitHub Actions runs Ruff and both test suites, and `main` won't accept a merge until the `python-tests` and `js-tests` checks pass. Keep each pull request to one change, say in its description what it changes and why, and include a screenshot of anything that looks different on the map. Add a line to the `Unreleased` section of the [changelog](CHANGELOG.md) for anything a visitor to the site or someone running it would notice.

By contributing you agree that your work is released under the project's [MIT licence](LICENSE), and that you'll follow the [code of conduct](CODE_OF_CONDUCT.md).
