"""One-off: set Bernard's Matrix display name + avatar.

Reuses the same env vars as main_matrix.py (BERNARD_MATRIX_HOMESERVER / BERNARD_MATRIX_USER_ID /
BERNARD_MATRIX_ACCESS_TOKEN). Idempotent — safe to re-run after swapping the image.

    python harness/set_profile.py
    python harness/set_profile.py --avatar web/mothersands/bernard_front_mug.png \
        --name "Bernard"
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

from nio import AsyncClient, UploadResponse

DEFAULT_AVATAR = "web/mothersands/bernard_front_mug.png"
DEFAULT_NAME = "Bernard"


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--avatar", default=DEFAULT_AVATAR)
    ap.add_argument("--name", default=DEFAULT_NAME)
    args = ap.parse_args()

    homeserver = os.environ.get("BERNARD_MATRIX_HOMESERVER")
    user_id = os.environ.get("BERNARD_MATRIX_USER_ID")
    access_token = os.environ.get("BERNARD_MATRIX_ACCESS_TOKEN")
    if not (homeserver and user_id and access_token):
        print("BERNARD_MATRIX_HOMESERVER/BERNARD_MATRIX_USER_ID/BERNARD_MATRIX_ACCESS_TOKEN must be set", file=sys.stderr)
        return 1

    avatar = Path(args.avatar)
    if not avatar.is_file():
        print(f"avatar not found: {avatar}", file=sys.stderr)
        return 1

    client = AsyncClient(homeserver, user_id)
    client.access_token = access_token
    client.user_id = user_id

    try:
        await client.set_displayname(args.name)
        print(f"display name set: {args.name}")

        with avatar.open("rb") as f:
            resp, _ = await client.upload(
                f,
                content_type="image/png",
                filename=avatar.name,
                filesize=avatar.stat().st_size,
            )
        if not isinstance(resp, UploadResponse):
            print(f"upload failed: {resp}", file=sys.stderr)
            return 1
        await client.set_avatar(resp.content_uri)
        print(f"avatar set: {resp.content_uri}")
    finally:
        await client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
