"""
Notification Service — abstract base + WaSender API implementation.

The alert pipeline calls ``NotificationService.send_alert()`` and never
knows which provider is behind it.  Swapping WhatsApp → SMS → email is
a one-class change.
"""

from __future__ import annotations

import asyncio
import logging
import mimetypes
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class NotificationResult:
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None


class NotificationService(ABC):
    """Abstract base for all notification providers."""

    @abstractmethod
    async def send_alert(
        self,
        phone: str,
        message: str,
        image_path: Optional[str] = None,
    ) -> NotificationResult:
        ...

    async def close(self) -> None:
        """Clean up resources. Override in subclasses that hold connections."""
        pass


class ConsoleNotificationService(NotificationService):
    """
    Demo / development implementation that logs alerts to the console.
    Used when no WhatsApp credentials are configured.
    """

    async def send_alert(
        self,
        phone: str,
        message: str,
        image_path: Optional[str] = None,
    ) -> NotificationResult:
        logger.warning(
            "[NOTIFY] ALERT NOTIFICATION (console) -> phone=%s  message=%s  image=%s",
            phone, message, image_path,
        )
        return NotificationResult(success=True, message_id="console-demo")


class WhatsAppCloudAPINotificationService(NotificationService):
    """
    WaSender API WhatsApp implementation.

    Requires:
    - WHATSAPP_API_BASE (e.g. https://www.wasenderapi.com/api)
    - WHATSAPP_API_KEY

    How images work
    ---------------
    ``/send-message`` only accepts a *complete public URL* in ``imageUrl``
    (data URIs and relative paths like ``/static/...`` are rejected with
    HTTP 422).  So for a local file we first push it to WaSender's own
    ``POST /upload`` endpoint, which returns a ``publicUrl`` (valid for 24h),
    and use that URL in the message.  No ngrok / public server needed.

    ``image_path`` must therefore be either:
      * a real filesystem path  (use ``MediaService.resolve_path(...)`` first), or
      * an ``http(s)://`` URL that is already public.

    If the image can't be read/uploaded, the alert is still sent as
    text-only — for a fire alert, a message without a photo beats no message.

    Rate limiting
    -------------
    * Sends are serialised through a lock, so two alerts can never race
      each other into a 429.
    * On HTTP 429 we sleep for the server's ``retry_after`` and retry.
    * Other 4xx errors (422, 401, ...) are not retried — they'd fail again.
    * ``min_interval`` (seconds) enforces a client-side gap between sends.
      Use 60 on the WaSender free trial (1 message / minute), 0 on a paid plan.
    """

    MAX_ATTEMPTS = 3
    MAX_RATE_LIMIT_WAIT = 120.0  # never sleep longer than this on a 429

    def __init__(self, api_base: str, api_key: str, min_interval: float = 0.0):
        self._api_base = api_base.rstrip("/")
        self._api_key = api_key
        self._min_interval = min_interval
        # Reuse a single client for connection pooling.
        self._client = httpx.AsyncClient(timeout=30.0)
        self._send_lock = asyncio.Lock()
        self._next_allowed = 0.0  # time.monotonic() value

    async def close(self) -> None:
        """Close the shared httpx client."""
        await self._client.aclose()

    # ------------------------------------------------------------------ #
    # Image handling
    # ------------------------------------------------------------------ #
    async def _get_public_image_url(self, image_path: str) -> str:
        """Return a public http(s) URL for the image, uploading if needed.

        Raises OSError / httpx.HTTPError / ValueError on failure.
        """
        if image_path.startswith(("http://", "https://")):
            return image_path

        path = Path(image_path)
        data = await asyncio.to_thread(path.read_bytes)  # OSError if missing
        mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"

        resp = await self._client.post(
            f"{self._api_base}/upload",
            content=data,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": mime_type,  # mandatory for raw-binary upload
            },
        )
        resp.raise_for_status()
        public_url = resp.json().get("publicUrl")
        if not public_url:
            raise ValueError(f"Upload response has no publicUrl: {resp.text}")
        return public_url

    # ------------------------------------------------------------------ #
    # Rate-limit helpers
    # ------------------------------------------------------------------ #
    async def _wait_for_slot(self) -> None:
        delay = self._next_allowed - time.monotonic()
        if delay > 0:
            logger.info("WhatsApp rate limit: waiting %.0fs before sending", delay)
            await asyncio.sleep(delay)

    def _retry_after(self, resp: httpx.Response) -> float:
        wait = 60.0
        try:
            wait = float(resp.json().get("retry_after", wait))
        except (ValueError, TypeError, AttributeError):
            pass
        return min(wait + 1.0, self.MAX_RATE_LIMIT_WAIT)

    @staticmethod
    def _extract_message_id(resp: httpx.Response) -> str:
        try:
            data = resp.json()
        except ValueError:
            return "unknown"
        inner = data.get("data")
        if isinstance(inner, dict) and inner.get("msgId") is not None:
            return str(inner["msgId"])
        msgs = data.get("messages")
        if isinstance(msgs, list) and msgs and isinstance(msgs[0], dict):
            return str(msgs[0].get("id", "unknown"))
        return "unknown"

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def send_alert(
        self,
        phone: str,
        message: str,
        image_path: Optional[str] = None,
    ) -> NotificationResult:
        url = f"{self._api_base}/send-message"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: dict = {"to": phone, "text": message}

        # One send at a time: keeps us inside the provider's rate limit.
        async with self._send_lock:
            if image_path:
                try:
                    payload["imageUrl"] = await self._get_public_image_url(image_path)
                except (OSError, httpx.HTTPError, ValueError) as exc:
                    logger.warning(
                        "Could not attach image %s (%s) - sending text only",
                        image_path, exc,
                    )

            return await self._post_message(url, headers, payload)

    async def _post_message(
        self, url: str, headers: dict, payload: dict
    ) -> NotificationResult:
        error_msg = "Unknown error"

        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            await self._wait_for_slot()

            try:
                resp = await self._client.post(url, json=payload, headers=headers)
            except httpx.HTTPError as exc:
                error_msg = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "WhatsApp send error (attempt %d): %s", attempt, error_msg
                )
                if attempt < self.MAX_ATTEMPTS:
                    await asyncio.sleep(2 ** attempt)
                continue

            if resp.status_code == 200:
                msg_id = self._extract_message_id(resp)
                self._next_allowed = time.monotonic() + self._min_interval
                logger.info("WhatsApp message sent: %s", msg_id)
                return NotificationResult(success=True, message_id=msg_id)

            error_msg = f"HTTP {resp.status_code}: {resp.text}"
            logger.warning(
                "WhatsApp API error (attempt %d): %s", attempt, error_msg
            )

            if resp.status_code == 429:
                # Sleep happens at the top of the next loop via _wait_for_slot.
                self._next_allowed = time.monotonic() + self._retry_after(resp)
                continue
            if resp.status_code >= 500:
                if attempt < self.MAX_ATTEMPTS:
                    await asyncio.sleep(2 ** attempt)
                continue
            break  # other 4xx: retrying can't help

        logger.error("WhatsApp notification failed: %s", error_msg)
        return NotificationResult(success=False, error=error_msg)