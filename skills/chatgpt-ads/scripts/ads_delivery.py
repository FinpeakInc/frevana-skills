"""Campaign, ad group and ad proposals, execution, bulk targets and readbacks."""

from time import sleep, time

from ads_api import (
    RESOURCES,
    TRANSITION_STATUS,
    AdsError,
    account_info,
    identifier,
    native_matches,
    read_resource,
    resource_path,
)
from ads_operations import read_pages

# These configuration fields affect what an operator approves. Exclude counters,
# expiring preview URLs and diagnostic timestamps which change with each read.
ENTITY_FIELDS = (
    "id",
    "name",
    "status",
    "updated_at",
    "description",
    "budget",
    "targeting",
    "mode",
    "bidding_type",
    "start_time",
    "end_time",
    "bidding_config",
    "context_hints",
    "creative",
    "landing_page_configuration",
    "product_set",
    "feed_set",
    "feed_selection",
    "conversion_event_setting_ids",
    "product_feed_id",
    "campaign_id",
    "ad_group_id",
)


def entity_settings(obj):
    fields = {k: obj[k] for k in ENTITY_FIELDS if k in obj}
    if isinstance(fields.get("creative"), dict):
        creative = fields["creative"]
        fields["creative"] = {k: v for k, v in creative.items() if k not in ("image_url", "images")}
        if creative.get("images"):
            fields["creative"]["images"] = [
                {k: v for k, v in image.items() if k != "image_url"} for image in creative["images"]
            ]
    return fields


def hierarchy(api, kind, obj_id):
    children = []
    for parent, child, action in (("campaign", "ad_group", "list-ad-groups"), ("ad_group", "ad", "list-ads")):
        if kind != parent:
            continue
        spec = {"action": action, "params": {}, "query": {parent + "_id": obj_id, "limit": 500}}
        for page in read_pages(api, spec, {}, True):
            for item in page["data"]:
                children.append(entity_settings(item))
                children.extend(hierarchy(api, child, identifier(item["id"])))
    return sorted(children, key=lambda obj: obj["id"])


def snapshot(api, spec, body):
    name, params = spec["action"], spec["params"]
    before = {}

    def record(kind, rid, include_children=False):
        path = resource_path(kind, rid)
        if path not in before:
            before[path] = entity_settings(read_resource(api, kind, rid))
        if include_children:
            before[path + "/children"] = hierarchy(api, kind, rid)

    for kind in RESOURCES:
        field = kind + "_id"
        if field in params:
            record(kind, params[field], name.startswith("activate-") or body.get("status") == "active")
        if name in ("create-ad", "create-ad-group") and field in body:
            record(kind, body[field])
    if name == "create-bulk-job":
        for item in body["operations"]:
            kind, verb = item["type"].split(".")
            if verb == "update":
                record(kind, item["target_resource_id"], item["input"].get("status") == "active")
    return before


def response_target(name, spec, response):
    for kind in RESOURCES:
        suffix = kind.replace("_", "-")
        if name in [verb + "-" + suffix for verb in ("create", "update", "activate", "pause", "archive")]:
            rid = spec["params"].get(kind + "_id") or identifier(response.get("id"))
            return kind, rid
    return None


def field_matches(key, requested, observed):
    if (
        key == "creative"
        and isinstance(requested, dict)
        and "file_ids" in requested
        and isinstance(observed, dict)
        and "images" in observed
    ):
        # GET returns ordered collection items. Compare stable IDs and preserve the native response.
        images = observed["images"]
        if not isinstance(images, list) or not all(
            isinstance(item, dict) and item.get("file_id") for item in images
        ):
            return False
        observed = {**observed, "file_ids": [item["file_id"] for item in images]}
    return native_matches(requested, observed)


def verify_response(api, spec, response):
    name, body = spec["action"], spec["body"] or {}
    target = response_target(name, spec, response)
    if target is None:
        return None
    kind, rid = target
    live = read_resource(api, kind, rid)
    status = TRANSITION_STATUS.get(name.partition("-")[0])
    if status and live.get("status") != status:
        raise AdsError(f"Mutation submitted; {rid} has not confirmed {status}. Resume to read again.")
    # Upstream can normalize geography, dates and templates or omit parents.
    # Return canonical settings and identify differences rather than issuing a second write.
    different = [k for k, v in body.items() if not field_matches(k, v, live.get(k))]
    parent = {"create-ad": "ad_group_id", "create-ad-group": "campaign_id"}.get(name)
    if parent in different and parent not in live:
        action = "list-ads" if kind == "ad" else "list-ad-groups"
        listing = {"action": action, "params": {}, "query": {parent: body[parent], "limit": 500}}
        if any(item["id"] == rid for page in read_pages(api, listing, {}, True) for item in page["data"]):
            different.remove(parent)
    return {
        "state": "read_back" if not different else "review_readback",
        "resource": live,
        "fields_to_review": different,
    }


def pause_proposal(api, resource, resource_id):
    account = account_info(api)
    obj = read_resource(api, resource, resource_id)
    if obj["status"] not in ("active", "paused"):
        raise AdsError(f"Cannot pause a resource with status {obj['status']}.")
    return {
        "kind": "pause",
        "account": account,
        "resource": resource,
        "resource_id": resource_id,
        "name": obj["name"],
        "before": obj["status"],
        "updated_at": obj.get("updated_at"),
        "final_status": "paused",
    }


def create(execution, kind, body):
    step = "create_" + kind
    previous = execution.steps.get(step)
    if previous and previous != "pending":
        return identifier(previous)
    if kind == "upload" and previous and not execution.retry_uncertain:
        raise AdsError(
            "Upload outcome is unknown. Verify in Ads Manager before explicitly retrying the upload."
        )
    execution.checkpoint(step, "pending")
    if kind == "upload":
        obj = execution.api.request("POST", "/upload", body)
        value = identifier(obj.get("file_id"))
    else:
        key = execution.state["operation_id"] + "-" + kind
        obj = execution.api.request("POST", "/" + RESOURCES[kind], body, key=key)
        value = identifier(obj.get("id"))
    execution.checkpoint(step, value)
    return value


def transition(execution, kind, current, target):
    step = target + "_" + kind
    previous = execution.steps.get(step)
    if current["status"] == target:
        execution.checkpoint(step, target)
        return current
    if previous == target:
        raise AdsError(f"{kind} changed after the verified {target} transition. Inspect the resource.")
    if previous == "pending" and not execution.retry_uncertain:
        raise AdsError(f"Uncertain {kind} transition. Review its current state before explicitly retrying.")
    source = "paused" if target == "active" else "active"
    if current["status"] != source:
        raise AdsError(f"{kind} is {current['status']}; cannot apply this proposal.")
    execution.checkpoint(step, "pending")
    action = "activate" if target == "active" else "pause"
    execution.api.request("POST", resource_path(kind, current["id"]) + "/" + action)
    updated = read_resource(execution.api, kind, current["id"])
    if updated["status"] != target:
        raise AdsError(f"{kind} has not confirmed the requested state. Inspect before retrying.")
    execution.checkpoint(step, target)
    return updated


def pause(execution):
    plan = execution.plan
    current = read_resource(execution.api, plan["resource"], plan["resource_id"])
    if current["status"] != "paused" and (
        current["name"] != plan["name"]
        or current["status"] != plan["before"]
        or current.get("updated_at") != plan["updated_at"]
    ):
        raise AdsError("The resource changed since preview. Prepare and review a fresh pause proposal.")
    updated = transition(execution, plan["resource"], current, "paused")
    return {"resource": plan["resource"], "id": updated["id"], "status": updated["status"]}


def launch_ids(execution):
    p = execution.plan
    if p["kind"] == "activate_launch":
        return p["resource_ids"]
    asset = p["asset"]
    file_id = asset.get("file_id") or create(execution, "upload", asset)
    campaign_id = create(execution, "campaign", p["campaign"])
    group_body = {**p["ad_group"], "campaign_id": campaign_id}
    group_id = create(execution, "ad_group", group_body)
    ad_body = {
        **p["ad"],
        "ad_group_id": group_id,
        "creative": {**p["ad"]["creative"], "file_id": file_id},
    }
    ad_id = create(execution, "ad", ad_body)
    return {"file_id": file_id, "campaign": campaign_id, "ad_group": group_id, "ad": ad_id}


def launch(execution):
    p = execution.plan
    ids = launch_ids(execution)
    current = inspect_launch(execution.api, p, ids)
    for kind, obj in current.items():
        if obj["status"] != "paused" and not (
            obj["status"] == "active" and execution.steps.get("active_" + kind) in ("pending", "active")
        ):
            raise AdsError(f"Unexpected {kind} status {obj['status']}. Inspect before continuing.")
    if p["final_status"] == "active":
        # Activate children while the campaign is paused. A confirmed campaign
        # activation is the last change that can enable spend.
        for kind in ("ad", "ad_group"):
            current[kind] = transition(execution, kind, current[kind], "active")
        current = inspect_launch(execution.api, p, ids)
        if any(current[k]["status"] != "active" for k in ("ad", "ad_group")):
            raise AdsError("A child changed state before campaign activation.")
        if current["campaign"]["status"] != "paused" and not execution.steps.get("active_campaign"):
            raise AdsError("Campaign changed before final activation.")
        current["campaign"] = transition(execution, "campaign", current["campaign"], "active")
        current = inspect_launch(execution.api, p, ids)
        if any(obj["status"] != "active" for obj in current.values()):
            raise AdsError("Live state differs from the confirmed activation. Inspect the resources.")
    return launch_result(current, ids)


def launch_result(current, ids):
    crop = (current["ad"].get("creative") or {}).get("image_crop")
    return {
        **({"image_crop": crop} if crop else {}),
        "resources": {kind: {"id": obj["id"], "status": obj["status"]} for kind, obj in current.items()},
        "review_status": current["ad"].get("review_status"),
        "file_id": ids["file_id"],
    }


def read_launch_resources(api, plan, ids):
    group = {**plan["ad_group"], "campaign_id": ids["campaign"]}
    ad = {
        **plan["ad"],
        "ad_group_id": ids["ad_group"],
        "creative": {**plan["ad"]["creative"], "file_id": ids["file_id"]},
    }
    current = {}
    for kind, settings in (("campaign", plan["campaign"]), ("ad_group", group), ("ad", ad)):
        obj = read_resource(api, kind, ids[kind])
        # A paused save can record the platform crop for later review. Activation
        # requires a crop already frozen in its own new proposal.
        checked = obj
        if kind == "ad" and plan["final_status"] == "paused" and obj.get("status") == "paused":
            creative = obj.get("creative") or {}
            crop = creative.get("image_crop")
            if crop and valid_crop(crop):
                checked = {**obj, "creative": {k: v for k, v in creative.items() if k != "image_crop"}}
        verify_settings(kind, settings, checked)
        current[kind] = obj
    review = current["ad"].get("review_status")
    if review not in ("in_review", "rejected", "approved"):
        raise AdsError("Unknown ad review status. Inspect the submitted ad.")
    if plan["final_status"] == "active" and review == "rejected":
        raise AdsError("The ad was rejected. Review it in Ads Manager.")
    return current


def missing_launch_children(api, ids):
    """Return empty, complete lists. Any conflicting or incomplete scope stops activation."""
    missing = {}
    for kind, parent in (("ad_group", "campaign"), ("ad", "ad_group")):
        path = "/" + RESOURCES[kind]
        field = parent + "_id"
        listing = f"GET {path} ({field}={ids[parent]})"
        page = api.request("GET", path, query=[(field, ids[parent]), ("limit", "2")])
        rows = page.get("data")
        if not isinstance(rows, list) or not all(isinstance(row, dict) and row.get("id") for row in rows):
            raise AdsError(f"{listing} returned an invalid child list. Cannot verify the campaign hierarchy.")
        found = [identifier(row["id"]) for row in rows]
        if any(rid != ids[kind] for rid in found):
            raise AdsError(
                f"The campaign hierarchy differs from the approved scope. "
                f"{listing} returned {', '.join(found)}. Expected only {ids[kind]}."
            )
        if any(field in row and row[field] != ids[parent] for row in rows):
            raise AdsError(f"{listing} returned a conflicting {field}. Inspect the campaign hierarchy.")
        if page.get("has_more") is not False or len(found) > 1:
            raise AdsError(f"{listing} did not confirm a complete, unique child list. Inspect the hierarchy.")
        if not rows:
            missing[kind] = f"{kind} {ids[kind]} was found by ID, but {listing} returned an empty list."
    return missing


def inspect_launch(api, plan, ids):
    # Re-read both levels and the approved settings after a wait. An operator
    # could add a sibling or change the budget while a new child becomes visible.
    for delay in (1, 2, 4, None):
        current = read_launch_resources(api, plan, ids)
        if plan["final_status"] != "active":
            return current
        missing = missing_launch_children(api, ids)
        if not missing:
            return current
        now = time()
        created = [current[kind].get("created_at") for kind in missing]
        if delay is None or not all(type(ts) is int and 0 <= now - ts <= 60 for ts in created):
            raise AdsError(
                " ".join(missing.values())
                + f" Membership is unconfirmed. Campaign {ids['campaign']} was read as "
                f"{current['campaign']['status']}. Recheck using the original receipt."
            )
        sleep(delay)


def valid_crop(crop):
    if not isinstance(crop, dict) or set(crop) != {"x", "y", "width", "height"}:
        return False
    if not all(type(v) in (int, float) and 0 <= v <= 1 for v in crop.values()):
        return False
    return (crop["width"] > 0 and crop["height"] > 0
            and crop["x"] + crop["width"] <= 1.000001 and crop["y"] + crop["height"] <= 1.000001)


def has_value(value):
    if isinstance(value, dict):
        return any(has_value(child) for child in value.values())
    return value not in (None, "", [], {})


def activation_proposal(api, prior):
    p = prior["proposal"]
    if p["kind"] != "launch" or p["final_status"] != "paused" or not prior["result"]:
        raise AdsError("Activation requires the completed receipt of a launch created paused.")
    account = account_info(api)
    if any(account[k] != p["account"][k] for k in ("id", "currency_code", "timezone")):
        raise AdsError("The selected account differs from the original launch.")
    result = prior["result"]
    ids = {kind: identifier(result["resources"][kind]["id"]) for kind in RESOURCES}
    ids["file_id"] = identifier(result["file_id"])
    plan = {**p, "account": account, "kind": "activate_launch", "final_status": "active", "resource_ids": ids}
    crop = result.get("image_crop")
    if crop:
        if not valid_crop(crop):
            raise AdsError("Invalid saved image crop. Review the ad.")
        plan["ad"] = {**p["ad"], "creative": {**p["ad"]["creative"], "image_crop": crop}}
    current = inspect_launch(api, plan, ids)
    if any(obj["status"] != "paused" for obj in current.values()):
        raise AdsError("Activation preview requires all three original resources to be paused.")
    return plan


def verify_settings(kind, expected, obj):
    """Check approved fields, allowing documented enriched readback representations."""
    actual = dict(obj)
    expected = {k: v for k, v in expected.items() if k != "status"}
    if has_value(actual.get("landing_page_configuration")):
        raise AdsError(f"The {kind} has an unapproved landing-page override.")
    if kind == "ad":
        creative = actual.get("creative") or {}
        crop = creative.get("image_crop")
        if crop is not None and crop != {} and (
            not valid_crop(crop) or crop != expected.get("creative", {}).get("image_crop")
        ):
            raise AdsError("The ad has an unapproved image crop. Review the platform preview before enabling delivery.")
        if any(has_value(creative.get(k)) for k in ("price", "file_ids", "business_agent_id")):
            raise AdsError("The ad contains additional creative settings. Review the changed ad.")
    for parent in ("ad_group_id", "campaign_id"):
        if parent not in actual:  # Some GET representations omit the parent link.
            expected.pop(parent, None)
        elif parent in expected and actual[parent] != expected[parent]:
            raise AdsError(
                f"{kind} {obj['id']} returned {parent}={actual[parent]}. Expected {expected[parent]}."
            )
    if kind == "ad_group":
        actual["context_hints"] = actual.get("context_hints") or []
        config = dict(actual.get("bidding_config") or {})
        if not config.get("strategy") and config.get("max_bid_micros"):
            config["strategy"] = "fixed_bid"
        if (
            config.get("custom_audience_bid_multipliers")
            or actual.get("product_set")
            or ("max_bid_micros" not in expected["bidding_config"] and config.get("max_bid_micros"))
        ):
            raise AdsError("Ad group contains unapproved bid or product settings.")
        actual["bidding_config"] = config
    if kind == "campaign":
        targeting = dict(actual.get("targeting") or {})
        locations = targeting.pop("locations", None) or {}
        platforms = targeting.pop("platforms", None) or {}
        included_platforms = platforms.get("included") or []
        if (
            (included_platforms and set(included_platforms) != {"ios_app", "android_app", "web"})
            or has_value(targeting)
            or actual.get("budget", {}).get("lifetime_spend_limit_micros")
            or any(actual.get(k) is not None for k in ("start_time", "end_time") if k not in expected)
        ):
            raise AdsError("Unapproved campaign targeting, schedule or budget. Review the live campaign.")
        countries = locations.get("countries")
        included = locations.get("include") or []
        if included:
            if not all(isinstance(v, dict) and v.get("type") == "country" for v in included):
                raise AdsError("Campaign location targeting differs from the approved countries.")
            countries = list(countries or []) + [v.get("country_code") for v in included]
        if not countries or set(countries) != set(expected["targeting"]["locations"]["countries"]):
            raise AdsError("Campaign countries differ from the approved proposal.")
        expected.pop("targeting")

    if not native_matches(expected, actual):
        raise AdsError(f"{kind} readback differs from the approved proposal. Inspect its settings.")


def apply_delivery(execution):
    plan = execution.plan
    account = account_info(execution.api)
    if any(account[k] != plan["account"][k] for k in ("id", "currency_code", "timezone")):
        raise AdsError("Account, currency or timezone changed since preview.")
    if plan["kind"] in ("launch", "activate_launch"):
        if plan["final_status"] == "active" and account.get("status") != "active":
            raise AdsError("The API did not confirm an active advertiser account. Inspect it in Ads Manager.")
        return launch(execution)
    if plan["kind"] == "pause":
        return pause(execution)
    raise AdsError("Unknown proposal type.")
