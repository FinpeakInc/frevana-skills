"""CLI entry point for the chatgpt-ads skill."""

import argparse
import json
import os
import sys
from pathlib import Path

from ads_api import (
    RESOURCES,
    AdsAPI,
    AdsError,
    account_info,
    read_resource,
    report,
    resource_path,
)
from ads_changes import plan_operation
from ads_delivery import activation_proposal, pause_proposal
from ads_draft import launch_proposal, write_card_preview
from ads_files import write_pixel
from ads_operations import CATALOG, call_read, describe, is_read, request_parts
from ads_workflow import reconcile_paused, execute, load_state, new_preview, save_json


def parser():
    cli = argparse.ArgumentParser(description="Preview and operate ChatGPT advertising.")
    commands = cli.add_subparsers(dest="command", required=True)
    commands.add_parser("account", help="Check the account associated with the Ads API key")
    commands.add_parser("operations", help="List all named read and mutation operations")
    detail = commands.add_parser(
        "describe", help="Show one action's method, inputs, and confirmation requirements"
    )
    detail.add_argument("action", choices=CATALOG)
    read = commands.add_parser("read", help="Read one named operation, optionally fetching every page")
    plan = commands.add_parser("plan", help="Preview an advertiser operation without submitting it")
    for command in (read, plan):
        command.add_argument("action", choices=CATALOG)
        command.add_argument("--param", action="append", default=[], metavar="NAME=ID")
        command.add_argument("--query", type=Path, help="JSON file containing named query parameters")
        command.add_argument("--body", type=Path, help="JSON file containing native body fields")
    read.add_argument("--all-pages", action="store_true")
    read.add_argument("--output", type=Path)
    plan.add_argument("--state", type=Path, required=True)
    plan.add_argument("--file", type=Path, help="Local image, audience or feed snapshot")
    plan.add_argument(
        "--secret-output",
        type=Path,
        help="New owner-only file for issued credentials, webhook secrets or signed URLs",
    )
    pixel = commands.add_parser("pixel-snippet", help="Generate a browser Pixel installation snippet")
    pixel.add_argument("--pixel-id", required=True, action="append", help="Repeat for each intended Pixel")
    pixel.add_argument("--output", type=Path, required=True)
    pixel.add_argument("--consent-required", action="store_true")
    draft_card = commands.add_parser(
        "preview-card", help="Render a local draft ad card before choosing an account"
    )
    draft_card.add_argument(
        "--draft", type=Path, required=True, help="Creative fields or a full launch draft"
    )
    draft_card.add_argument("--output", type=Path, required=True, help="New HTML file for the draft card")
    preview = commands.add_parser("preview", help="Save a launch proposal; performs account reads only")
    preview.add_argument("--draft", type=Path, required=True)
    preview.add_argument("--state", type=Path, required=True)
    activate = commands.add_parser(
        "activate", help="Preview enabling the exact hierarchy from a paused launch"
    )
    activate.add_argument("--from-state", type=Path, required=True, help="Completed paused launch receipt")
    activate.add_argument("--state", type=Path, required=True, help="New activation proposal")
    pause = commands.add_parser("pause", help="Preview pausing one existing resource")
    status = commands.add_parser("status", help="Read current resource settings and status")
    for command in (pause, status):
        command.add_argument("--resource", choices=RESOURCES, required=True)
        command.add_argument("--id", required=True)
    pause.add_argument("--state", type=Path, required=True)
    show = commands.add_parser("show", help="Inspect a saved proposal, progress and result offline")
    show.add_argument("--state", type=Path, required=True)
    verify = commands.add_parser("verify-paused", help="Read back existing IDs without any advertiser mutation")
    verify.add_argument("--state", type=Path, required=True)
    verify.add_argument("--confirm", required=True)
    run = commands.add_parser("execute", help="Apply a specific human-approved proposal")
    run.add_argument("--state", type=Path, required=True)
    run.add_argument("--confirm", required=True, help="Confirmation fingerprint printed by preview or pause")
    run.add_argument(
        "--retry-uncertain",
        action="store_true",
        help="Allow retry of an unresolved upload or state change after checking Ads Manager",
    )
    card = commands.add_parser("ad-preview", help="Retrieve the official preview of an existing ad")
    card.add_argument("--id", required=True)
    card.add_argument("--output", type=Path, help="Save the native JSON including iframe HTML")
    insights = commands.add_parser("report", help="Get a complete delivery report as JSON")
    insights.add_argument("--scope", choices=["ad_account", *RESOURCES], default="ad_account")
    insights.add_argument("--id", help="Resource ID for a non-account scope")
    insights.add_argument("--level", choices=["ad_account", *RESOURCES], help="Entity for each row")
    insights.add_argument("--granularity", choices=["hourly", "daily", "monthly", "none"], default="daily")
    insights.add_argument(
        "--options",
        type=Path,
        help="JSON with native fields, filters, segments, sort and attribution settings",
    )
    insights.add_argument("--since", required=True, help="Inclusive first account-local date (YYYY-MM-DD)")
    insights.add_argument("--until", required=True, help="Inclusive last account-local date (YYYY-MM-DD)")
    insights.add_argument("--output", type=Path, help="Save complete rows to a new file")
    return cli


def handle(args, api=None):
    if args.command == "operations":
        return {n: "read" if is_read(op) else "plan" for n, op in CATALOG.items()}
    if args.command == "describe":
        return describe(args.action)
    if args.command == "pixel-snippet":
        return write_pixel(args.pixel_id, args.output, args.consent_required)
    if args.command == "show":
        return load_state(args.state)
    if args.command == "preview-card":
        return write_card_preview(json.loads(args.draft.read_text(encoding="utf-8")), args.output)
    if api is None:
        api = AdsAPI()
    if args.command == "plan":
        return plan_operation(api, args)
    if args.command == "read":
        if not is_read(CATALOG[args.action]):
            raise AdsError("A mutation requires plan and confirmed execute.")
        spec, body = request_parts(args)
        result = call_read(api, spec, body, args.all_pages)
        if args.output:
            save_json(args.output, result, create=True)
            return {"output": str(args.output)}
        return result
    if args.command == "account":
        return account_info(api)
    if args.command == "preview":
        draft = json.loads(args.draft.read_text(encoding="utf-8"))
        return new_preview(args.state, launch_proposal(draft, account_info(api)))
    if args.command == "activate":
        return new_preview(args.state, activation_proposal(api, load_state(args.from_state)))
    if args.command == "pause":
        return new_preview(args.state, pause_proposal(api, args.resource, args.id))
    if args.command == "verify-paused":
        return reconcile_paused(api, args.state, args.confirm)
    if args.command == "execute":
        return execute(api, args.state, args.confirm, args.retry_uncertain)
    if args.command == "status":
        return read_resource(api, args.resource, args.id)
    if args.command == "ad-preview":
        result = api.request("POST", resource_path("ad", args.id) + "/preview")
        rows = result.get("data")
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict) or not rows[0].get("body"):
            raise AdsError("Ad preview is missing the native preview body.")
    else:
        result = report(api, args)
    if args.output:
        save_json(args.output, result, create=True)
        return {"output": str(args.output), "rows": len(result["data"])}
    return result


def main():
    args = parser().parse_args()
    try:
        result = handle(args)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        message = str(exc)
        key = os.environ.get("OPENAI_ADS_API_KEY")
        if key:
            message = message.replace(key, "[redacted]")
        print(f"Error: {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
