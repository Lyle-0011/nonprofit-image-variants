from __future__ import annotations

import os

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from .campaign_variants import CampaignVariantService, CropTransformation, VariantRequest, VariantResult
from .infrai_client import InfraiClient, InfraiError

app = FastAPI(title="Nonprofit image variants")


def build_service() -> CampaignVariantService:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise RuntimeError("Set INFRAI_API_KEY before starting the service")
    bucket = os.environ.get("INFRAI_BUCKET", "nonprofit-campaign-media")
    return CampaignVariantService(InfraiClient(api_key), bucket, CropTransformation.nonprofit_defaults())


@app.post("/campaign-variants", response_model=list[VariantResult])
async def create_campaign_variants(
    image: UploadFile = File(),
    campaign_id: str = Form(),
    uses: str = Form("donor_receipt,volunteer_reminder,campaign_report"),
) -> list[VariantResult]:
    try:
        request = VariantRequest(campaign_id=campaign_id, uses=[item.strip() for item in uses.split(",")])
        return await build_service().prepare(request, await image.read(), image.filename or "campaign.jpg")
    except InfraiError as exc:
        client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=client_status, detail={"code": exc.code, "message": str(exc)}) from exc
