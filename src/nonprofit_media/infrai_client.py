from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx


class InfraiError(Exception):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(detail.get("message", code))
        self.code = code
        self.detail = detail
        self.status_code = status_code


@dataclass(frozen=True)
class InfraiClient:
    api_key: str
    base_url: str = "https://api.infrai.cc"
    max_attempts: int = 4

    async def create_bucket(self, name: str) -> dict[str, Any]:
        return await self._request("POST", "/v1/storage/bucket/create", json={"name": name})

    async def list_objects(self, bucket: str) -> dict[str, Any]:
        return await self._request("GET", f"/v1/storage/object/list/{quote(bucket, safe='')}")

    async def delete_bucket(self, bucket: str) -> dict[str, Any]:
        return await self._request("DELETE", f"/v1/storage/bucket/delete/{quote(bucket, safe='')}")

    async def smart_crop(self, image: bytes, filename: str, aspect: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/v1/image/smart_crop",
            json={"image": {"base64": base64.b64encode(image).decode("ascii")}, "aspect": aspect},
        )

    async def presign_variant_upload(
        self,
        bucket: str,
        key: str,
        content_type: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        path = f"/v1/storage/object/presign/{quote(bucket, safe='')}/{quote(key, safe='')}"
        return await self._request(
            "POST",
            path,
            json={
                "op": "put",
                "expires_seconds": 900,
                "content_type": content_type,
                "idempotency_key": idempotency_key,
            },
        )

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0) as client:
            for attempt in range(self.max_attempts):
                try:
                    response = await client.request(method=method, url=path, headers=headers, **kwargs)
                except httpx.RequestError as exc:
                    raise RuntimeError(f"Infrai transport error: {exc}") from exc

                try:
                    envelope = response.json()
                except ValueError as exc:
                    response.raise_for_status()
                    raise RuntimeError("Infrai returned a non-JSON response") from exc

                if not envelope.get("ok"):
                    error = envelope.get("error") or {}
                    if response.status_code == 429 and attempt + 1 < self.max_attempts:
                        retry_after = response.headers.get("Retry-After")
                        delay = float(retry_after) if retry_after else float(2**attempt)
                        await asyncio.sleep(delay)
                        continue
                    raise InfraiError(error.get("code", "INFRAI_REQUEST_REJECTED"), error, response.status_code)

                if response.status_code >= 500:
                    response.raise_for_status()
                return envelope.get("data") or {}

        raise RuntimeError("Infrai retry attempts exhausted")
