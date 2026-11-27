"""A small client for the website's own JSON, served on the droplet's loopback."""

import http.client
import json
import urllib.error
import urllib.request

from stdmcp import ToolError

UNAVAILABLE = "Floodwatch is briefly unavailable; try again in a minute."
MAX_BYTES = 5 * 1024 * 1024


class NotFound(ToolError):
    """The site has no such resource; the message is the API's own."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Site:
    def __init__(self, base="http://127.0.0.1:8090", timeout=5):
        self.base = base.rstrip("/")
        self.timeout = timeout
        self._opener = urllib.request.build_opener(_NoRedirect)

    def json(self, path):
        """GET base + path and return the parsed JSON object."""
        assert path.startswith("/"), path
        try:
            with self._opener.open(self.base + path, timeout=self.timeout) as r:
                body = r.read(MAX_BYTES + 1)
        except urllib.error.HTTPError as e:
            try:
                if e.code == 404:
                    raise NotFound(_error_text(e)) from None
                raise ToolError(UNAVAILABLE) from None
            finally:
                e.close()
        except (OSError, ValueError, http.client.HTTPException):
            raise ToolError(UNAVAILABLE) from None
        if len(body) > MAX_BYTES:
            raise ToolError(UNAVAILABLE)
        try:
            data = json.loads(body)
        except ValueError:
            raise ToolError(UNAVAILABLE) from None
        if not isinstance(data, dict):
            raise ToolError(UNAVAILABLE)
        return data


def _error_text(e):
    try:
        text = json.loads(e.read(65536))["error"]
        if isinstance(text, str) and text:
            return text
    except (ValueError, KeyError, TypeError, OSError, http.client.HTTPException):
        pass
    return "not found"
