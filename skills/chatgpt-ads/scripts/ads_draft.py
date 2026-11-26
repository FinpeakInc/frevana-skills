"""Prepare a standard chat card for a local preview or a confirmed launch."""

import re
from decimal import Decimal
from html import escape
from pathlib import Path
from string import Template
from urllib.parse import urlsplit

from ads_api import AdsError, identifier

LAUNCH_REQUIRED = {
    "title",
    "body",
    "landing_page_url",
    "campaign_name",
    "ad_group_name",
    "ad_name",
    "currency",
    "daily_budget",
    "countries",
    "objective",
    "bid_strategy",
    "final_status",
}
LAUNCH_FIELDS = LAUNCH_REQUIRED | {
    "context_hints",
    "max_cpc",
    "max_cpm",
    "image_url",
    "file_id",
    "start_time",
    "end_time",
}


def string(value, field, minimum=1, maximum=None):
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) < minimum
        or (maximum is not None and len(value) > maximum)
    ):
        raise AdsError(f"Invalid or missing {field}.")
    return value


def strings(value, field):
    if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
        raise AdsError(f"{field} must be an array of nonempty strings.")
    return value


def money(value, field, multiplier=1_000_000):
    # Limit precision before decimal arithmetic. JSON numbers with a fractional part
    # must be supplied as strings to preserve the amount from preview to wire.
    if type(value) not in (str, int) or not re.fullmatch(r"[0-9]{1,13}(?:\.[0-9]{1,6})?", str(value)):
        raise AdsError(f"{field} must be a positive decimal string or integer.")
    micros = Decimal(value) * multiplier
    if micros != int(micros) or not 0 < micros <= 2**63 - 1:
        raise AdsError(f"{field} cannot be represented as positive whole micros per billing event.")
    return int(micros)


def url(value, field, schemes):
    string(value, field, maximum=2048)
    parsed = urlsplit(value)
    if (
        parsed.scheme not in schemes
        or not parsed.hostname
        or parsed.username is not None
        or any(c.isspace() or ord(c) < 32 for c in value)
    ):
        raise AdsError(f"Invalid {field} URL.")
    return value


def chat_card(draft):
    creative = {
        "type": "chat_card",
        "title": string(draft.get("title"), "title", 3, 50),
        "body": string(draft.get("body"), "body", 1, 100),
        "target_url": url(draft.get("landing_page_url"), "landing_page_url", {"http", "https"}),
    }
    if ("image_url" in draft) == ("file_id" in draft):
        raise AdsError("Choose one image_url or existing file_id.")
    if "file_id" in draft:
        asset = {"file_id": identifier(draft["file_id"])}
    else:
        asset = {"image_url": url(draft["image_url"], "image_url", {"https", "http"})}
    return creative, asset


def write_card_preview(draft, output):
    if not isinstance(draft, dict) or draft.keys() - LAUNCH_FIELDS:
        raise AdsError("Supply a standard single-image draft using the fields in the draft reference.")
    creative, asset = chat_card(draft)
    if "image_url" in asset:
        media = f'<img src="{escape(asset["image_url"])}" alt="Ad creative">'
    else:
        media = (
            f'<p class="asset">Account image · {escape(asset["file_id"])}'
            "<br>Image unavailable before account selection.</p>"
        )
    template = Path(__file__).resolve().parents[1] / "assets" / "draft-card.html"
    html = Template(template.read_text(encoding="utf-8")).substitute(
        media=media,
        title=escape(creative["title"]),
        body=escape(creative["body"]),
        destination=escape(creative["target_url"]),
    )
    data = html.encode("utf-8")
    with output.open("xb") as out:
        out.write(data)
    return {"output": str(output), "kind": "draft_card"}


def launch_proposal(draft, account):
    if not isinstance(draft, dict) or LAUNCH_REQUIRED - draft.keys() or draft.keys() - LAUNCH_FIELDS:
        raise AdsError(
            f"Check the draft fields against the reference. Required: {', '.join(sorted(LAUNCH_REQUIRED))}."
        )
    if draft["currency"] != account["currency_code"]:
        raise AdsError("Draft currency does not match the ad account.")
    if draft["final_status"] not in ("active", "paused"):
        raise AdsError("Set final_status to active or paused.")
    objective, strategy = draft["objective"], draft["bid_strategy"]
    if objective not in ("clicks", "impressions") or strategy not in ("fixed_bid", "maximize_clicks"):
        raise AdsError("Unsupported objective or bid strategy.")
    countries = strings(draft["countries"], "countries")
    if not countries or not all(re.fullmatch("[A-Z]{2}", c) for c in countries):
        raise AdsError("Supply the intended two-letter uppercase country codes.")
    campaign = {
        "name": string(draft["campaign_name"], "campaign_name", 3, 1000),
        "status": "paused",
        "bidding_type": objective,
        "budget": {"daily_spend_limit_micros": money(draft["daily_budget"], "daily_budget")},
        "targeting": {"locations": {"countries": countries}},
    }
    for field in ("start_time", "end_time"):
        if field in draft:
            if type(draft[field]) is not int or not 946684800 <= draft[field] <= 4102444800:
                raise AdsError(f"{field} must be a supported Unix timestamp in seconds.")
            campaign[field] = draft[field]
    if campaign.get("end_time", 4102444801) <= campaign.get("start_time", 0):
        raise AdsError("end_time must follow start_time.")
    billing = "click" if objective == "clicks" else "impression"
    bidding = {"billing_event_type": billing, "strategy": strategy}
    bid_fields = {"max_cpc", "max_cpm"} & draft.keys()
    if strategy == "fixed_bid":
        field = "max_cpc" if billing == "click" else "max_cpm"
        if bid_fields != {field}:
            raise AdsError(f"Supply only {field} for this fixed bid.")
        bidding["max_bid_micros"] = money(draft[field], field, 1_000_000 if billing == "click" else 1000)
    elif objective != "clicks" or bid_fields:
        raise AdsError("maximize_clicks requires the clicks objective and omits a manual bid.")
    group = {
        "name": string(draft["ad_group_name"], "ad_group_name", 3, 1000),
        "status": "paused",
        "context_hints": strings(draft.get("context_hints", []), "context_hints"),
        "bidding_config": bidding,
    }
    creative, asset = chat_card(draft)
    ad = {"name": string(draft["ad_name"], "ad_name", 3, 1000), "status": "paused", "creative": creative}
    return {
        "kind": "launch",
        "account": account,
        "final_status": draft["final_status"],
        "daily_budget": str(draft["daily_budget"]),
        "asset": asset,
        "campaign": campaign,
        "ad_group": group,
        "ad": ad,
    }
