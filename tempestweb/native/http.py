"""Typed HTTP client capability with retry, idempotency, upload and poll (N0).

The pythonic mirror of the React SDK's ``createApiClient`` / ``retry`` /
``generateIdempotencyKey`` / ``uploadWithProgress`` / ``usePoll``. It is the base
of the offline replay in Track T9 (P2): a request carries an idempotency key so a
replayed request never duplicates its server-side effect.

**The retry / backoff / poll *policy* lives here, in pure Python** — it is fully
unit-testable with a fake bridge and never touches a browser. The single HTTP
*round-trip* is the native capability ``http.request`` dispatched through the
installed :class:`~tempestweb.native.dispatch.NativeBridge`:

* **Mode A (WASM).** ``client/native/http.js`` calls the browser ``fetch`` API.
* **Mode B (server).** The ``native_call`` is proxied to the client, which runs
  the same ``fetch`` — so requests carry the user's cookies/origin, not the
  server's. (A server-side ``httpx`` backend can later be swapped in by installing
  a different bridge; the Python API is unchanged.)

The retry rule is conservative by design: a request is only retried when it is
**safe** — an idempotent method (``GET``/``HEAD``/``PUT``/``DELETE``/``OPTIONS``)
or any method carrying an explicit ``idempotency_key``. A bare ``POST`` is never
retried automatically, matching the "retry só em métodos idempotentes ou com
idempotency key" rule in ``docs/plan.md``.
"""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import Awaitable, Callable
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field

from tempestweb.native.dispatch import NativeError, send_native_call

__all__ = [
    "IDEMPOTENT_METHODS",
    "HttpResponse",
    "RetryOptions",
    "generate_idempotency_key",
    "poll",
    "request",
    "upload",
]

#: HTTP methods that are safe to retry without an explicit idempotency key.
IDEMPOTENT_METHODS: Final[frozenset[str]] = frozenset(
    {"GET", "HEAD", "PUT", "DELETE", "OPTIONS"}
)

#: Default HTTP status codes that warrant a retry (transient server / rate-limit).
_DEFAULT_RETRY_STATUSES: Final[frozenset[int]] = frozenset(
    {408, 425, 429, 500, 502, 503, 504}
)


class RetryOptions(BaseModel):
    """Retry / exponential-backoff policy for :func:`request`.

    Attributes:
        attempts: Total attempts including the first try. ``1`` disables retry.
        base_delay: Seconds to wait before the first retry.
        factor: Multiplier applied to the delay after each failed attempt.
        max_delay: Upper bound on any single backoff delay, in seconds.
        retry_statuses: HTTP status codes that should trigger a retry.
    """

    model_config = ConfigDict(frozen=True)

    attempts: int = Field(default=3, ge=1)
    base_delay: float = Field(default=0.2, ge=0.0)
    factor: float = Field(default=2.0, ge=1.0)
    max_delay: float = Field(default=10.0, ge=0.0)
    retry_statuses: frozenset[int] = Field(default=_DEFAULT_RETRY_STATUSES)

    def delay_for(self, attempt_index: int) -> float:
        """Compute the backoff delay before the retry numbered ``attempt_index``.

        Args:
            attempt_index: Zero-based index of the *upcoming* retry (``0`` is the
                wait before the first retry, i.e. after attempt 1 failed).

        Returns:
            The capped exponential delay in seconds.
        """
        delay = self.base_delay * (self.factor**attempt_index)
        return min(delay, self.max_delay)


class HttpResponse(BaseModel):
    """A typed HTTP response returned by the browser ``fetch`` call.

    Attributes:
        status: The HTTP status code.
        ok: Whether ``status`` is in the 2xx range (mirrors ``Response.ok``).
        headers: Response headers, lower-cased keys.
        text: The response body decoded as text (empty string when absent).
        json_body: The parsed JSON body when the response was JSON, else ``None``.
            Carried on the wire under the key ``"json"`` (the field is named
            ``json_body`` to avoid shadowing :meth:`pydantic.BaseModel.json`).
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    status: int
    ok: bool
    headers: dict[str, str] = Field(default_factory=dict)
    text: str = ""
    json_body: Any = Field(default=None, alias="json")


def generate_idempotency_key() -> str:
    """Generate a fresh, URL-safe idempotency key.

    Mirrors the React SDK's ``generateIdempotencyKey``. The key lets a retried (or
    offline-replayed) request be deduplicated server-side so its effect happens at
    most once.

    Returns:
        A random URL-safe token (32 hex-ish characters).
    """
    return secrets.token_urlsafe(24)


async def _dispatch_request(
    method: str,
    url: str,
    *,
    json_body: Any,  # noqa: ANN401 — a JSON request body is any JSON-able value
    headers: dict[str, str],
) -> HttpResponse:
    """Dispatch a single ``http.request`` round-trip and parse the response.

    Args:
        method: The HTTP method (already upper-cased).
        url: The request URL.
        json_body: A JSON-able body to send, or ``None``.
        headers: Request headers.

    Returns:
        The parsed :class:`HttpResponse`.

    Raises:
        NativeError: If the browser ``fetch`` rejects (network error, CORS, ...).
        BrowserUnavailableError: If no native bridge is installed.
    """
    value = await send_native_call(
        "http.request",
        {"method": method, "url": url, "json": json_body, "headers": headers},
    )
    return HttpResponse.model_validate(value)


async def request(
    method: str,
    url: str,
    *,
    json: Any = None,  # noqa: ANN401 — a JSON request body is any JSON-able value
    headers: dict[str, str] | None = None,
    retry: RetryOptions | None = None,
    idempotency_key: str | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> HttpResponse:
    """Perform an HTTP request with optional retry and idempotency.

    The request is retried with exponential backoff when it fails transiently
    (a retryable status code, or a network-level :class:`NativeError`) **and** the
    request is safe to retry — an idempotent method, or any method carrying an
    ``idempotency_key``. The key is sent as the ``Idempotency-Key`` header so the
    server deduplicates the effect across retries and offline replays.

    Args:
        method: The HTTP method (case-insensitive).
        url: The request URL.
        json: A JSON-able request body, or ``None``.
        headers: Extra request headers.
        retry: The retry policy. ``None`` means no retry (a single attempt).
        idempotency_key: An explicit idempotency key; also makes a non-idempotent
            method (e.g. ``POST``) eligible for retry.
        sleep: Awaitable sleep, injected so tests can run without real delays.

    Returns:
        The final :class:`HttpResponse` — the first success, or the last response
        after exhausting retries.

    Raises:
        NativeError: If every attempt fails at the network level.
        BrowserUnavailableError: If no native bridge is installed.
    """
    method_upper = method.upper()
    merged_headers: dict[str, str] = dict(headers or {})
    if idempotency_key is not None:
        merged_headers.setdefault("Idempotency-Key", idempotency_key)

    policy = retry or RetryOptions(attempts=1)
    retryable = method_upper in IDEMPOTENT_METHODS or idempotency_key is not None

    last_error: NativeError | None = None
    last_response: HttpResponse | None = None
    for attempt in range(policy.attempts):
        try:
            response = await _dispatch_request(
                method_upper, url, json_body=json, headers=merged_headers
            )
        except NativeError as exc:
            last_error = exc
            last_response = None
            if not retryable or attempt == policy.attempts - 1:
                raise
        else:
            last_response = response
            last_error = None
            if response.ok or response.status not in policy.retry_statuses:
                return response
            if not retryable or attempt == policy.attempts - 1:
                return response
        await sleep(policy.delay_for(attempt))

    # Unreachable in practice (the loop always returns or raises on the last
    # attempt); kept for type-completeness.
    if last_error is not None:
        raise last_error
    assert last_response is not None
    return last_response


async def upload(
    url: str,
    file: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
    on_progress: Callable[[float], None] | None = None,
) -> HttpResponse:
    """Upload a file, reporting progress via a callback.

    The browser performs a streaming upload (``XMLHttpRequest``/``fetch`` with an
    upload progress listener); each progress tick is proxied back and forwarded to
    ``on_progress`` as a fraction in ``[0.0, 1.0]``.

    Args:
        url: The upload endpoint.
        file: A JSON-able descriptor of the file to upload, e.g.
            ``{"name": "a.png", "type": "image/png", "data": "<base64>"}`` or a
            client-side blob reference ``{"name": ..., "blob_id": ...}``.
        headers: Extra request headers.
        on_progress: Optional callback receiving the upload fraction. The final
            tick is always ``1.0`` on success.

    Returns:
        The :class:`HttpResponse` for the completed upload.

    Raises:
        NativeError: If the upload fails.
        BrowserUnavailableError: If no native bridge is installed.
    """
    value = await send_native_call(
        "http.upload",
        {"url": url, "file": file, "headers": dict(headers or {})},
    )
    if on_progress is not None:
        ticks = value.get("progress", [])
        if isinstance(ticks, list):
            for tick in ticks:
                on_progress(float(tick))
        on_progress(1.0)
    return HttpResponse.model_validate(value.get("response", value))


async def poll(
    url: str,
    *,
    until: Callable[[HttpResponse], bool],
    interval: float = 1.0,
    max_attempts: int = 30,
    headers: dict[str, str] | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> HttpResponse:
    """Poll a URL until a predicate is satisfied or attempts run out.

    Args:
        url: The URL to poll (always fetched with ``GET``).
        until: Predicate deciding when polling is done, given the latest response.
        interval: Seconds to wait between polls.
        max_attempts: Maximum number of polls before giving up.
        headers: Extra request headers.
        sleep: Awaitable sleep, injected so tests can run without real delays.

    Returns:
        The :class:`HttpResponse` that first satisfied ``until``.

    Raises:
        NativeError: If a poll fails at the network level, or the predicate is
            never satisfied within ``max_attempts`` (``code="poll_exhausted"``).
        BrowserUnavailableError: If no native bridge is installed.
    """
    response: HttpResponse | None = None
    for attempt in range(max_attempts):
        response = await request("GET", url, headers=headers)
        if until(response):
            return response
        if attempt < max_attempts - 1:
            await sleep(interval)
    raise NativeError(
        "poll_exhausted",
        f"predicate not satisfied after {max_attempts} attempts polling {url}",
    )
