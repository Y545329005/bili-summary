"""HTTPX client for Bilibili API with retry logic and cookie injection."""

import time

import httpx

from bili_summary.config import (
    BACKOFF_FACTOR,
    BILI_API_BASE,
    BILI_REFERER,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    RETRYABLE_STATUSES,
    USER_AGENT,
)


class BiliAPIError(Exception):
    """Bilibili API returned an error code."""

    def __init__(self, code: int, message: str, endpoint: str = ""):
        self.code = code
        self.message = message
        self.endpoint = endpoint
        super().__init__(f"[{code}] {message}" + (f" ({endpoint})" if endpoint else ""))


def _is_retryable(exception: Exception) -> bool:
    """Determine if an exception should trigger a retry."""
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in RETRYABLE_STATUSES
    if isinstance(exception, (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError)):
        return True
    return False


def _check_response(resp: httpx.Response) -> dict:
    """Check a Bilibili API response and return the parsed JSON data.

    Raises:
        BiliAPIError: If the response code is non-zero.
    """
    try:
        data = resp.json()
    except Exception as e:
        raise BiliAPIError(-1, f"无法解析 API 响应: {e}") from e

    code = data.get("code", -1)
    message = data.get("message", "未知错误")

    if code != 0:
        url = str(resp.url)
        raise BiliAPIError(code, message, url)

    return data


class BiliClient:
    """Synchronous HTTPX client for Bilibili API.

    Handles:
    - Base URL and default headers
    - Cookie injection
    - Automatic retry with exponential backoff
    - Response validation
    """

    def __init__(self, cookie_header: str = ""):
        headers = {
            "User-Agent": USER_AGENT,
            "Referer": BILI_REFERER,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        if cookie_header:
            headers["Cookie"] = cookie_header

        self._client = httpx.Client(
            base_url=BILI_API_BASE,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,
        )

    @property
    def headers(self) -> httpx.Headers:
        return self._client.headers

    def update_cookie(self, cookie_header: str) -> None:
        """Update the Cookie header on the client."""
        if cookie_header:
            self._client.headers["Cookie"] = cookie_header
        else:
            self._client.headers.pop("Cookie", None)

    def get(self, path: str, **kwargs) -> httpx.Response:
        """GET request with retry logic."""
        return self._request_with_retry("GET", path, **kwargs)

    def _request_with_retry(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Make a request with automatic retry on transient failures."""
        last_exception = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = self._client.request(method, path, **kwargs)
                resp.raise_for_status()
                return resp
            except Exception as e:
                last_exception = e
                if attempt < MAX_RETRIES and _is_retryable(e):
                    wait = BACKOFF_FACTOR ** attempt
                    time.sleep(wait)
                    continue
                raise
        raise last_exception  # type: ignore[misc]

    def get_json(self, path: str, **kwargs) -> dict:
        """GET request, validate Bilibili response, return data dict."""
        resp = self.get(path, **kwargs)
        return _check_response(resp)

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
