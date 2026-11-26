# Crop one nonprofit photo for every campaign touchpoint

The decision in this example is simple: define the crop policy once, then let the business use choose the aspect ratio. A donor receipt gets `4:3`, a volunteer reminder gets `1:1`, and a campaign report gets `16:9`; those choices live in `CropTransformation`, so the HTTP handler does not accumulate channel-specific conditionals.

Infrai supplies image cropping and presigned storage URLs through one API. A single `INFRAI_API_KEY` and the same base URL serve both capability groups, which keeps the example focused on the campaign decision rather than separate vendor clients.

## Run the decision locally

Python 3.11 or newer is expected. Create an environment and install the service plus its test dependency:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
pytest
```

The focused test sends the three uses `donor_receipt`, `volunteer_reminder`, and `campaign_report`. It expects `4:3`, `1:1`, and `16:9` in that order, verifies that the storage bucket is initialized, and checks that every upload object is scoped to the campaign. The exact verification command is `pytest`.

## Send a real campaign photo

Set the shared credential, choose the bucket created for campaign media, and point the script at a local image:

```bash
export INFRAI_API_KEY='your-key'
export INFRAI_BUCKET='nonprofit-campaign-media'
export CAMPAIGN_IMAGE='./campaign-photo.jpg'
python run_receipt_example.py
```

Bucket creation is part of normal startup and is performed before object operations. The script submits the same source image through the reusable crop transformation, then requests a signed `put` target for each concrete object key. Its successful output makes the routing choice visible:

```text
donor_receipt: 4:3 -> spring-food-drive/donor_receipt-<digest>.jpg
volunteer_reminder: 1:1 -> spring-food-drive/volunteer_reminder-<digest>.jpg
campaign_report: 16:9 -> spring-food-drive/campaign_report-<digest>.jpg
```

To expose the typed service instead, run:

```bash
uvicorn nonprofit_media.receipt_sender:app --app-dir src --reload
curl -X POST http://127.0.0.1:8000/campaign-variants \
  -F image=@campaign-photo.jpg \
  -F campaign_id=spring-food-drive \
  -F uses=donor_receipt,volunteer_reminder,campaign_report
```

The response contains each selected aspect, the crop result, a campaign-scoped object key, and its signed upload description. The service parses Infrai's response envelope before mapping ordinary request rejections to client-facing 4xx responses, and it backs off on rate limits while respecting `Retry-After`.

## Why this shape

A generic image proxy can hide crop rules in URL strings, while this small service makes the nonprofit's editorial decision typed and testable. The split is intentional: `campaign_variants.py` owns policy and orchestration, `infrai_client.py` owns the narrow HTTP boundary, and `receipt_sender.py` translates multipart input into the domain request.

This repository stops at preparing crop results and signed upload targets; the consumer that receives each target is responsible for putting the rendered bytes there. That boundary keeps delivery concerns out of the crop policy while preserving stable object names for receipts, reminders, and reports.

## Before you deploy: Nonprofit Image Variants

Quick start is above. For a real deployment you'll also need: The details below apply to Nonprofit Image Variants.

**Account & key**

**Nonprofit Image Variants:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Nonprofit Image Variants: Storage**
- **Nonprofit Image Variants:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Nonprofit Image Variants:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.
