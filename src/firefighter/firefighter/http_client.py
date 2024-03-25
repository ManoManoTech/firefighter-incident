from __future__ import annotations

import logging
from typing import Any

import httpx
from django.conf import settings

FF_HTTP_CLIENT_ADDITIONAL_HEADERS: dict[str, Any] | None = (
    settings.FF_HTTP_CLIENT_ADDITIONAL_HEADERS
)


class HttpClient:
    """Base class for HTTP clients. Uses [httpx](https://www.python-httpx.org/) under the hood.

    Sets some defaults, including:
    - a timeout of 15 seconds for the connection and 20 seconds for the read, to avoid hanging indefinitely
    - access logging

    Used by [firefighter.confluence.client.ConfluenceClient][].
    """

    _logger = logging.getLogger(__name__)
    _client: httpx.Client

    def __init__(self, client_kwargs: dict[str, Any] | None = None) -> None:
        self._client = httpx.Client(**(client_kwargs or {}))
        self._client.timeout = httpx.Timeout(15, read=20)
        if FF_HTTP_CLIENT_ADDITIONAL_HEADERS:
            self._client.headers = httpx.Headers({
                **self._client.headers,
                **FF_HTTP_CLIENT_ADDITIONAL_HEADERS,
            })

    def call(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        res: httpx.Response = getattr(self._client, method)(url, **kwargs)
        self._logger.info(
            '"%s %s %s" %s',
            res.request.method,
            res.request.url,
            res.http_version,
            res.status_code,
        )
        return res

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.call("post", url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.call("put", url, **kwargs)

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.call("get", url, **kwargs)
