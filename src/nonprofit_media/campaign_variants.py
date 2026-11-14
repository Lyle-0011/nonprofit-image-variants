from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any, get_args, get_origin, get_type_hints

try:
    from pydantic import BaseModel, Field
except ModuleNotFoundError:  # Keep the domain module usable in the lightweight test environment.
    class BaseModel:
        def __init__(self, **values: Any) -> None:
            hints = get_type_hints(type(self))
            unknown = set(values) - set(hints)
            if unknown:
                raise TypeError(f"Unexpected fields: {', '.join(sorted(unknown))}")
            for name, annotation in hints.items():
                if name not in values:
                    raise TypeError(f"Missing field: {name}")
                value = values[name]
                if get_origin(annotation) is list and not isinstance(value, list):
                    raise TypeError(f"{name} must be a list")
                if get_origin(annotation) is list:
                    item_type = get_args(annotation)[0]
                    value = [item_type(item) if not isinstance(item, item_type) else item for item in value]
                setattr(self, name, value)

    def Field(**_: Any) -> Any:
        return None

if TYPE_CHECKING:
    from .infrai_client import InfraiClient


class AssetUse(StrEnum):
    DONOR_RECEIPT = "donor_receipt"
    VOLUNTEER_REMINDER = "volunteer_reminder"
    CAMPAIGN_REPORT = "campaign_report"


class VariantRequest(BaseModel):
    campaign_id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    uses: list[AssetUse] = Field(min_length=1)


class VariantResult(BaseModel):
    use: AssetUse
    aspect: str
    object_key: str
    crop: dict[str, Any]
    upload: dict[str, Any]


@dataclass(frozen=True)
class CropTransformation:
    aspects: dict[AssetUse, str]

    @classmethod
    def nonprofit_defaults(cls) -> "CropTransformation":
        return cls(
            aspects={
                AssetUse.DONOR_RECEIPT: "4:3",
                AssetUse.VOLUNTEER_REMINDER: "1:1",
                AssetUse.CAMPAIGN_REPORT: "16:9",
            }
        )

    def aspect_for(self, use: AssetUse) -> str:
        return self.aspects[use]


class CampaignVariantService:
    def __init__(self, client: "InfraiClient", bucket: str, transform: CropTransformation) -> None:
        self.client = client
        self.bucket = bucket
        self.transform = transform
        self.created_bucket: str | None = None

    async def prepare(
        self,
        request: VariantRequest,
        image: bytes,
        filename: str,
    ) -> list[VariantResult]:
        bucket = await self.client.create_bucket(self.bucket)
        self.created_bucket = str(bucket.get("name") or self.bucket)
        digest = hashlib.sha256(image).hexdigest()[:16]
        results: list[VariantResult] = []

        for use in dict.fromkeys(request.uses):
            aspect = self.transform.aspect_for(use)
            object_key = f"{request.campaign_id}/{use.value}-{digest}.jpg"
            crop = await self.client.smart_crop(image, filename, aspect)
            upload = await self.client.presign_variant_upload(
                self.bucket,
                object_key,
                "image/jpeg",
                f"{request.campaign_id}:{use.value}:{digest}",
            )
            results.append(
                VariantResult(
                    use=use,
                    aspect=aspect,
                    object_key=object_key,
                    crop=crop,
                    upload=upload,
                )
            )
        return results
