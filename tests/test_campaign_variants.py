import asyncio

from nonprofit_media.campaign_variants import AssetUse, CampaignVariantService, CropTransformation, VariantRequest


class RecordingClient:
    def __init__(self) -> None:
        self.bucket_names: list[str] = []
        self.crop_aspects: list[str] = []
        self.object_keys: list[str] = []

    async def create_bucket(self, name: str) -> dict:
        self.bucket_names.append(name)
        return {"name": name}

    async def smart_crop(self, image: bytes, filename: str, aspect: str) -> dict:
        self.crop_aspects.append(aspect)
        return {"asset": f"crop-{aspect}"}

    async def presign_variant_upload(
        self, bucket: str, key: str, content_type: str, idempotency_key: str
    ) -> dict:
        self.object_keys.append(key)
        return {"url": f"https://uploads.example/{key}"}


def test_business_uses_choose_expected_crops_and_stable_keys() -> None:
    asyncio.run(_exercise_business_decision())


async def _exercise_business_decision() -> None:
    client = RecordingClient()
    service = CampaignVariantService(client, "campaign-media", CropTransformation.nonprofit_defaults())  # type: ignore[arg-type]
    request = VariantRequest(
        campaign_id="fall-drive",
        uses=[AssetUse.DONOR_RECEIPT, AssetUse.VOLUNTEER_REMINDER, AssetUse.CAMPAIGN_REPORT],
    )

    results = await service.prepare(request, b"same-photo", "food-drive.jpg")

    assert client.bucket_names == ["campaign-media"]
    assert [result.aspect for result in results] == ["4:3", "1:1", "16:9"]
    assert client.crop_aspects == ["4:3", "1:1", "16:9"]
    assert all(key.startswith("fall-drive/") and key.endswith(".jpg") for key in client.object_keys)
