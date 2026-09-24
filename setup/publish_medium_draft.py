#!/usr/bin/env python3
"""Publish 07_medium_post.md to Medium as a draft.

Usage:
  export MEDIUM_TOKEN='...'
  python3 publish_medium_draft.py

Notes:
- Medium no longer issues new API integration tokens. This only works if your
  account already has a working token or Medium exposes one for your account.
- The script creates a draft, not a public post.
- It uploads local PNG/JPG/GIF/TIFF images referenced in Markdown and replaces
  local image links with Medium image URLs before creating the draft.
"""

from __future__ import annotations

import json
import mimetypes
import os
import re
import sys
from pathlib import Path
from urllib import request, error

ROOT = Path(__file__).resolve().parent
MARKDOWN_FILE = ROOT / "07_medium_post.md"
API = "https://api.medium.com/v1"
TOKEN = os.environ.get("MEDIUM_TOKEN")

if not TOKEN:
    raise SystemExit("Set MEDIUM_TOKEN in your shell first. Do not paste it into chat.")

headers_json = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/json",
    "Accept-Charset": "utf-8",
}


def api_json(method: str, url: str, payload: dict | None = None, headers: dict | None = None) -> dict:
    data = None
    req_headers = dict(headers_json)
    if headers:
        req_headers.update(headers)
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    req = request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Medium API error {exc.code} for {url}:\n{body}") from exc


def upload_image(path: Path) -> str:
    boundary = "----codexmediumboundary"
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    image_bytes = path.read_bytes()
    body = b"".join([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="image"; filename="{path.name}"\r\n'.encode(),
        f"Content-Type: {content_type}\r\n\r\n".encode(),
        image_bytes,
        f"\r\n--{boundary}--\r\n".encode(),
    ])
    req = request.Request(
        f"{API}/images",
        data=body,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/json",
            "Accept-Charset": "utf-8",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["data"]["url"]
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Medium image upload error {exc.code} for {path}:\n{body}") from exc


def replace_local_images(markdown: str) -> str:
    pattern = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
    uploaded: dict[str, str] = {}

    def repl(match: re.Match[str]) -> str:
        alt, target = match.group(1), match.group(2)
        if target.startswith(("http://", "https://")):
            return match.group(0)
        image_path = (ROOT / target).resolve()
        if not image_path.exists():
            raise SystemExit(f"Image referenced in Markdown does not exist: {target}")
        if str(image_path) not in uploaded:
            print(f"Uploading image: {image_path.name}", file=sys.stderr)
            uploaded[str(image_path)] = upload_image(image_path)
        return f"![{alt}]({uploaded[str(image_path)]})"

    return pattern.sub(repl, markdown)


markdown = MARKDOWN_FILE.read_text()
markdown = replace_local_images(markdown)

# Medium accepts markdown contentFormat for post creation. The title is also in
# the content because Medium uses the title field for metadata/listing behavior.
me = api_json("GET", f"{API}/me")
author_id = me["data"]["id"]

payload = {
    "title": "Connecting BigQuery Dataform to GitHub with Developer Connect, GitHub Apps, and Crossplane",
    "contentFormat": "markdown",
    "content": markdown,
    "tags": ["Google Cloud", "Dataform", "Crossplane", "GitHub", "DevOps"],
    "publishStatus": "draft",
}

post = api_json("POST", f"{API}/users/{author_id}/posts", payload)
print(json.dumps(post, indent=2))
