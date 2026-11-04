"""Run the documented Protoface MiniMax H3 example from GitHub Actions."""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from jsonschema import Draft202012Validator, ValidationError

API = "https://api.protoface.com"
MODEL = "minimax/minimax-h3"
TERMINAL = {"completed", "failed", "canceled"}
OUTPUT = Path("protoface-output")


class RunError(Exception):
    pass


def request(client, method, path, **kwargs):
    """Send once: a failed submit must never silently generate another video."""
    try:
        response = client.request(method, path, **kwargs)
    except httpx.RequestError as exc:
        raise RunError(
            "Network request failed. A submitted run may still be processing. "
            "Re-run this same workflow attempt or use check_run if you have its ID."
        ) from exc
    if not response.is_success:
        try:
            error = response.json().get("error", {})
            code = error.get("code", "request_failed") if isinstance(error, dict) else "request_failed"
        except (ValueError, AttributeError):
            code = "request_failed"
        raise RunError(f"Protoface HTTP {response.status_code}: {code}")
    try:
        return response.json()
    except ValueError as exc:
        raise RunError("Protoface returned an invalid JSON response.") from exc


def save(name, body):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / name).write_text(json.dumps(body, indent=2, ensure_ascii=False) + "\n")


def summary(text):
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if target:
        with open(target, "a", encoding="utf-8") as stream:
            stream.write(text + "\n\n")


def run_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"run_[A-Za-z0-9_-]+", value):
        raise RunError("Provide a valid Protoface run ID beginning with run_.")
    return value


def idempotency_key(payload):
    # GITHUB_RUN_ID stays the same on Re-run jobs; RUN_ATTEMPT deliberately isn't used.
    identity = os.environ.get("GITHUB_RUN_ID")
    if not identity:
        raise RunError("Generation requires GITHUB_RUN_ID to prevent duplicate submissions.")
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:20]
    return f"github-{identity}-{digest}"


def video_links(body):
    candidates = []
    if isinstance(body.get("video"), dict):
        candidates.append(body["video"].get("url"))
    for item in body.get("outputs", []):
        if item.get("modality") == "video" and isinstance(item.get("file"), dict):
            candidates.append(item["file"].get("url"))
    result = []
    for value in candidates:
        if not isinstance(value, str):
            continue
        parsed = urlsplit(value)
        if parsed.scheme == "https" and parsed.hostname and not parsed.username and value not in result:
            result.append(value)
    return result


def wait_for_run(client, identifier, timeout=1500, interval=5):
    identifier = run_id(identifier)
    save("run-id.json", {"id": identifier})
    print(f"Protoface run ID: {identifier}", flush=True)
    summary(f"Run ID: `{identifier}`. To resume later, choose **check_run** with this ID.")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = request(client, "GET", f"/v1/runs/{identifier}/status")
        save("status.json", state)
        status = state.get("status")
        print(f"Status: {status}", flush=True)
        if status in TERMINAL:
            body = request(client, "GET", f"/v1/runs/{identifier}")
            save("result.json", body)
            if status != "completed" or body.get("status") != "completed":
                error = body.get("error") or state.get("error") or {}
                code = error.get("code", status) if isinstance(error, dict) else status
                raise RunError(f"Run ended without a completed video: {code}. See the result artifact.")
            links = video_links(body)
            if not links:
                raise RunError("Run completed but has no HTTPS video link. See result.json in the artifact.")
            (OUTPUT / "video-links.txt").write_text("\n".join(links) + "\n")
            summary("### Your video is ready")
            for index, link in enumerate(links, 1):
                summary(f'<a href="{html.escape(link, quote=True)}">Open / download video {index}</a>')
            summary("Save the video to your phone; the provider's download link may expire.")
            return
        if status not in {"queued", "running"}:
            raise RunError(f"Unexpected run status: {status}. See status.json in the artifact.")
        time.sleep(min(interval, max(0, deadline - time.monotonic())))
    raise RunError(
        f"Stopped waiting after {timeout} seconds. The run was not canceled. "
        f"Choose check_run with {identifier}; do not start a new generation."
    )


def execute(client):
    action = os.environ.get("PROTOFACE_ACTION", "check_connection")
    if action == "check_connection":
        catalog = request(client, "GET", "/v1/models")
        count = len(catalog.get("data", []))
        print(f"Connection successful. {count} models returned.")
        summary(f"### Protoface connection successful\n\n{count} models returned. No video was submitted.")
        return
    if action == "check_run":
        wait_for_run(client, os.environ.get("PROTOFACE_RUN_ID", "").strip())
        return
    if action != "generate_video":
        raise RunError("Unknown action. Choose check_connection, generate_video, or check_run.")
    if os.environ.get("PROTOFACE_CONFIRM_SPEND", "").lower() != "true":
        raise RunError("To generate a paid video, tick confirm_spend. Otherwise use check_connection.")
    prompt = os.environ.get("PROTOFACE_PROMPT", "").strip()
    if not prompt:
        raise RunError("Enter a video prompt.")
    try:
        duration = int(os.environ.get("PROTOFACE_DURATION", "8"))
    except ValueError as exc:
        raise RunError("Duration must be a whole number of seconds.") from exc
    payload = {
        "prompt": prompt,
        "duration_seconds": duration,
        "quality": os.environ.get("PROTOFACE_QUALITY", "768p"),
        "aspect_ratio": os.environ.get("PROTOFACE_ASPECT_RATIO", "16:9"),
    }
    model = request(client, "GET", f"/v1/models/{MODEL}")
    if model.get("available") is False:
        raise RunError("MiniMax H3 is not accepting runs right now.")
    schemas = model.get("request_schemas", {})
    schema = schemas.get("video.general")
    if not isinstance(schema, dict) or not schema:
        raise RunError("The model has no video.general schema. No generation was submitted.")
    if len(model.get("operations", {})) > 1:
        payload["operation"] = "video.general"
    try:
        Draft202012Validator(schema).validate(payload)
    except ValidationError as exc:
        field = ".".join(str(item) for item in exc.path) or "request"
        raise RunError(f"Invalid {field}: {exc.message}") from exc
    save("model.json", model)
    quota = request(client, "GET", "/v1/billing/quota")
    if quota.get("balance_credits", 1) <= 0:
        raise RunError("Your Protoface credit balance is empty. No generation was submitted.")
    key = idempotency_key(payload)
    summary("### Generating one MiniMax H3 video")
    created = request(
        client, "POST", f"/v1/run/{MODEL}",
        headers={"Idempotency-Key": key}, json=payload,
    )
    save("submitted.json", created)
    estimate = created.get("credit_estimate")
    if estimate:
        summary("Credit estimate reported by Protoface after acceptance:\n\n```json\n"
                + json.dumps(estimate, indent=2) + "\n```")
    wait_for_run(client, run_id(created.get("id")))


def main():
    key = os.environ.get("PROTOFACE_API_KEY", "").strip()
    if not key:
        summary("### Add your Protoface key first\n\nIn repository Settings → Secrets and variables → "
                "Actions, add a repository secret named `PROTOFACE_API_KEY`.")
        print("Missing repository secret PROTOFACE_API_KEY.", file=sys.stderr)
        return 1
    try:
        with httpx.Client(
            base_url=API, headers={"Authorization": f"Bearer {key}"},
            timeout=60, follow_redirects=False,
        ) as client:
            execute(client)
    except (RunError, ValueError) as exc:
        message = str(exc).replace(key, "[REDACTED]")
        print(message, file=sys.stderr)
        summary("### Workflow stopped\n\n" + html.escape(message))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
