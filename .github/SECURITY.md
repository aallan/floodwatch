# Security Policy

## Supported Versions

Only the latest version on the `main` branch is actively maintained.

## Reporting a Vulnerability

If you discover a security vulnerability in Floodwatch, please report it responsibly:

1. **Do not** open a public GitHub issue.
2. Email **alasdair@babilim.co.uk** with a description of the vulnerability and steps to reproduce it.
3. Allow reasonable time for the issue to be assessed and patched before disclosing publicly.

You will receive an acknowledgement within 48 hours and a follow-up once the issue has been triaged.

## Scope

Floodwatch is a client-side dashboard that reads from public government APIs. The main security surface areas are:

- **XSS prevention** — all user-visible data is escaped before rendering
- **Content-Security-Policy** — restricts script and resource origins
- **API proxy** — `serve.py` and `refresh.php` proxy EA API requests server-side
- **Rate limiting** — refresh endpoint is rate-limited to prevent misuse

## Out of Scope

- The EA Flood Monitoring API itself (report to the Environment Agency)
- The Open-Meteo API (report to Open-Meteo)
- Third-party CDN-hosted libraries (Leaflet, Chart.js, PapaParse)
