from __future__ import annotations

import asyncio
import os
from pathlib import Path

from nonprofit_media.campaign_variants import AssetUse, CampaignVariantService, CropTransformation, VariantRequest
from nonprofit_media.infrai_client import InfraiClient, InfraiError


async def verify_bucket_deleted(client: InfraiClient, bucket: str) -> None:
    for attempt in range(5):
        try:
            await client.list_objects(bucket)
        except InfraiError as exc:
            if exc.status_code == 404:
                return
            raise
        if attempt < 4:
            await asyncio.sleep(1)
    raise AssertionError(f"bucket still exists after deletion: {bucket}")


async def main() -> None:
    source = Path(os.environ.get("CAMPAIGN_IMAGE", "campaign-photo.jpg"))
    client = InfraiClient(os.environ["INFRAI_API_KEY"])
    bucket_name = os.environ.get("INFRAI_BUCKET", "nonprofit-campaign-media")
    service = CampaignVariantService(
        client,
        bucket_name,
        CropTransformation.nonprofit_defaults(),
    )
    request = VariantRequest(
        campaign_id="spring-food-drive",
        uses=[AssetUse.DONOR_RECEIPT, AssetUse.VOLUNTEER_REMINDER, AssetUse.CAMPAIGN_REPORT],
    )
    created_bucket: str | None = None
    try:
        variants = await service.prepare(request, source.read_bytes(), source.name)
        created_bucket = service.created_bucket
        for variant in variants:
            print(f"{variant.use}: {variant.aspect} -> {variant.object_key}")
    finally:
        if created_bucket is not None:
            await client.delete_bucket(created_bucket)
            await verify_bucket_deleted(client, created_bucket)


if __name__ == "__main__":
    asyncio.run(main())
