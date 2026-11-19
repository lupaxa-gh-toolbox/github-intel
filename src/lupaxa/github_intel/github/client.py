"""
Bounded asynchronous GitHub REST client.

The semaphore limits in-flight HTTP calls. Retries cover timeouts and
transient server errors. Permanent errors are returned to the caller.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import random
from typing import Any

import httpx

from lupaxa.github_intel.constants import API_VERSION, USER_AGENT
from lupaxa.github_intel.github.rate_limit import RateLimitController

__all__ = [
    "FetchResult",
    "GitHubClient",
]

_RETRYABLE = {500, 502, 503, 504}


@dataclass(frozen=True)
class FetchResult:
    """One completed GET, including a 304 that carries no new body."""

    status: int
    body: Any
    etag: str | None
    error: str | None
    not_modified: bool
    link: str | None = None


class GitHubClient:
    """httpx client with shared rate limiting and bounded concurrency."""

    def __init__(
        self,
        *,
        api_url: str,
        token: str | None,
        timeout: float,
        retries: int,
        concurrency: int,
        transport: httpx.AsyncBaseTransport | None = None,
        limits: RateLimitController | None = None,
    ) -> None:
        """
        Open a client. Call :meth:`aclose` when the sync run finishes.

        Args:
            api_url: GitHub API origin.
            token: Bearer token, or None for unauthenticated access.
            timeout: Per-request timeout in seconds.
            retries: Extra attempts after a transient failure.
            concurrency: Maximum in-flight HTTP calls.
            transport: Optional httpx transport for tests.
            limits: Shared rate-limit controller.

        """

        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": API_VERSION,
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._retries = retries
        self.concurrency = concurrency
        self._semaphore = asyncio.Semaphore(concurrency)
        self._limits = limits or RateLimitController()
        self._http = httpx.AsyncClient(
            base_url=api_url,
            headers=headers,
            timeout=timeout,
            transport=transport,
            follow_redirects=True,
        )
        self.token = token

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""

        await self._http.aclose()

    @property
    def rate_pauses(self) -> int:
        """
        Return how many times workers waited for a GitHub rate limit.

        Returns:
            Pause count for this client.

        """

        return self._limits.pauses

    def watch_rate_limit(self, listener: Callable[[float], None] | None) -> None:
        """
        Receive the remaining rate-limit wait while requests are paused.

        Args:
            listener: Called with seconds remaining, then 0 when the wait ends.
                It must not await.

        """

        self._limits.set_listener(listener)

    async def get(
        self,
        path: str,
        *,
        etag: str | None = None,
        params: dict[str, str] | None = None,
    ) -> FetchResult:
        """
        GET one API path.

        Args:
            path: Path under the API origin.
            etag: Previous ETag, sent as ``If-None-Match``.
            params: Query string.

        Returns:
            Status, parsed JSON when present, and the new ETag.

        """

        headers = {"If-None-Match": etag} if etag else {}
        response = await self._request(path, headers, params)
        if response is None:
            return FetchResult(0, None, etag, "Network request failed.", False)
        new_etag = response.headers.get("etag") or etag
        self._limits.observe(
            response.status_code,
            {k.lower(): v for k, v in response.headers.items()},
        )
        if response.status_code == 304:
            return FetchResult(304, None, new_etag, None, True)
        if response.status_code >= 400:
            return FetchResult(
                response.status_code,
                None,
                new_etag,
                _error_text(response),
                False,
            )
        return FetchResult(
            response.status_code,
            _json_body(response),
            new_etag,
            None,
            False,
            response.headers.get("link"),
        )

    async def _request(
        self,
        path: str,
        headers: dict[str, str],
        params: dict[str, str] | None,
    ) -> httpx.Response | None:
        attempt = 0
        while True:
            try:
                async with self._semaphore:
                    await self._limits.wait()
                    response = await self._http.get(
                        path,
                        headers=headers,
                        params=params,
                    )
            except httpx.HTTPError:
                if attempt >= self._retries:
                    return None
                await asyncio.sleep(_backoff(attempt))
                attempt += 1
                continue
            if response.status_code in _RETRYABLE and attempt < self._retries:
                await asyncio.sleep(_backoff(attempt))
                attempt += 1
                continue
            if _rate_limited(response) and attempt < self._retries:
                self._limits.observe(
                    response.status_code,
                    {key.lower(): value for key, value in response.headers.items()},
                )
                await self._limits.wait()
                attempt += 1
                continue
            return response


def _rate_limited(response: httpx.Response) -> bool:
    if response.status_code == 429:
        return True
    if response.status_code != 403:
        return False
    remaining = response.headers.get("x-ratelimit-remaining")
    if remaining == "0":
        return True
    return "rate limit" in response.text.casefold()


def _json_body(response: httpx.Response) -> object:
    try:
        return response.json()
    except ValueError:
        return None


def _error_text(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict) and isinstance(payload.get("message"), str):
        message = payload["message"]
    else:
        message = response.text[:300]
    if response.status_code == 404:
        return "GitHub returned 404. The repository may be missing or not visible."
    if response.status_code == 401:
        return "GitHub rejected the credentials."
    return f"GitHub returned {response.status_code}: {message}"


def _backoff(attempt: int) -> float:
    delay: float = 2.0**attempt
    return delay + random.uniform(0, 0.3)  # noqa: S311
