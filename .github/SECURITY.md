# Security policy

## Reporting a vulnerability

Please don't report a security problem in a public issue. Email **alasdair@babilim.co.uk** instead, with what you found, how to reproduce it and what you think it allows. You'll get an answer within 48 hours, and another once the problem has been looked at. Please allow time for a fix to be deployed before you say anything in public; you'll be credited in the changelog unless you'd rather not be.

Only the latest version, the one running at [tawriver.watch](https://tawriver.watch) and on `main`, is maintained.

## What's in scope

Floodwatch is one Python process serving a static page and a small read-only API, behind Caddy. Problems with any of these are in scope:

- `serve.py`: serving files from `site/` and nothing outside it, and the endpoints under `/api/`, which take a station or overflow ID checked against a fixed pattern and a number of days, and read the database without writing to it.
- The response headers: a Content Security Policy that lets the page load scripts, styles and data only from its own server and images only from its own server and Esri's tile servers, and refuses framing, along with `X-Content-Type-Options` and `Referrer-Policy`.
- The page: everything taken from an outside feed, a station name, a warning's message, a power cut's postcodes, is escaped before it goes into the page.
- The libraries: Leaflet and Leaflet.markercluster are served from the site itself, at versions pinned in the `Makefile` and checked against `libs.sha256` when they're downloaded.
- The poller's handling of what the feeds send, which is parsed as data and never run.
- The nightly archive: the server holds a deploy key with write access to this repository, which `main`'s ruleset lets push without a pull request, and which the server uses only to push `archive/`, from a separate worktree. The key sits in the checkout's `.ssh/`, which git ignores. A way to use the server to push anything else, or to read the key, is in scope.
- The GitHub Actions workflow, whose actions are pinned to commit SHAs and which runs with read-only permissions.

## What isn't

- The services Floodwatch reads: report problems with the Environment Agency's APIs to the Environment Agency, with the storm overflow feed to South West Water, and so on.
- The accuracy of the data itself. A gauge reading or warning that looks wrong is a bug report, not a vulnerability; open an issue.
- Denial of service by volume against the public site.
