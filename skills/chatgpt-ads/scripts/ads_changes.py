"""Approval, drift checks, and recovery for individual advertiser operations."""

import hashlib
import json
import os
from pathlib import Path

import ads_accounts
import ads_delivery
from ads_api import (
    TRANSITION_STATUS,
    AdsError,
    AdsHTTPError,
    identifier,
    native_matches,
)
from ads_files import multipart_upload, sftp_upload
from ads_operations import (
    CATALOG,
    is_read,
    operation_path,
    query_pairs,
    read_ref,
    request_parts,
    webhook_origin,
)
from ads_workflow import new_preview, save_json


def snapshot(api, spec, body, actor, approved=None):
    name, params = spec["action"], spec["params"]
    before = {}

    if name in ("create-lead-sync-subscription", "delete-lead-sync-subscription"):
        page = api.request("GET", "/lead_sync_subscriptions", query=[("ad_account_id", actor["id"])])
        if not isinstance(page.get("data"), list) or page.get("has_more") is not False:
            raise AdsError("Cannot verify the complete Lead Sync subscription list for this account.")
        subscriptions = {}
        for item in page["data"]:
            if not isinstance(item, dict) or not all(
                isinstance(item.get(k), str) and item[k] for k in ("subscription_id", "status")
            ):
                raise AdsError("Incomplete Lead Sync subscription record.")
            subscriptions[item["subscription_id"]] = item["status"]
        if name == "delete-lead-sync-subscription":
            before["subscription_status"] = subscriptions.get(params["subscription_id"])
        else:
            before["subscriptions"] = subscriptions

    before.update(ads_delivery.snapshot(api, spec, body))
    before.update(ads_accounts.snapshot(api, name, body, approved))
    if "feed_id" in params and name in (
        "upload-feed-snapshot",
        "archive-product-feed",
        "patch-product-feed-settings",
    ):
        live = api.request("GET", f"/feeds/{params['feed_id']}/settings")
        before["feed_settings"] = {k: v for k, v in live.items() if k not in ("updated_at", "product_count")}
    if name == "upload-feed-snapshot" or "sftp-access" in name:
        try:
            access = api.request("GET", f"/feeds/{params['feed_id']}/sftp_access")
            before["access"] = {
                k: access.get(k) for k in ("enabled", "connection_uri", "authentication_method")
            }
        except AdsHTTPError as exc:
            if name != "post-product-feed-sftp-access" or exc.status != 404:
                raise
            before["access"] = None
    if "custom_audience_id" in params:
        obj = api.request("GET", f"/custom_audiences/{params['custom_audience_id']}")
        before["audience"] = {
            k: obj[k] for k in ("id", "name", "status", "updated_at", "membership_revision") if k in obj
        }
        if (
            "expected_revision" in body
            and "membership_revision" in obj
            and body["expected_revision"] != obj["membership_revision"]
        ):
            raise AdsError("Audience membership revision changed; use the current revision.")
    return before


def identity(api, spec):
    if spec["action"] == "create-partner-data-upload":
        # The upload API identifies the partner by API key. Its contract has no
        # account selector or identity endpoint that this key is required to access.
        return {"partner_key_fingerprint": hashlib.sha256(api.partner_data_key().encode()).hexdigest()}
    if spec["action"] == "send-conversion-events":
        return {"pixel_id": identifier(spec["query"]["pid"])}
    return ads_accounts.account_identity(api, spec["action"])


def active_identity(actor):
    return {
        k: actor[k]
        for k in ("id", "currency_code", "timezone", "pixel_id", "partner_user", "partner_key_fingerprint")
        if k in actor
    }


def plan_operation(api, args):
    op = CATALOG[args.action]
    if is_read(op):
        raise AdsError("Use read for this operation.")
    spec, body = request_parts(args)
    actor = identity(api, spec)
    if "ad_account_id" in body and body["ad_account_id"] != actor.get("id"):
        raise AdsError("Payload ad account differs from the authenticated selected account.")
    private_output = getattr(args, "secret_output", None)
    if bool(private_output) != bool(op.get("private_response")):
        raise AdsError("Use --secret-output only for and always with private-response operations.")
    if private_output:
        private_output = Path(private_output).expanduser().resolve()
        if private_output.exists() or private_output in (
            args.state.resolve(),
            Path(str(args.state.resolve()) + ".lock"),
        ):
            raise AdsError("Choose a new private output file separate from the receipt.")
        private_output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    proposal = {
        "kind": "operation",
        "account": actor,
        "request": spec,
        "before": snapshot(api, spec, body, actor),
        "secret_output": str(private_output) if private_output else None,
    }
    if args.action == "delete-lead-sync-subscription" and proposal["before"]["subscription_status"] is None:
        raise AdsError("This subscription is absent from the selected account.")
    if args.action == "create-lead-sync-subscription":
        proposal["private_summary"] = {
            "destination_origin": webhook_origin(body["destination_url"]),
            "signing_secret": "supplied" if "signing_secret" in body else "generated by OpenAI",
        }
    elif spec["private_body"]:
        events = body.get("events")
        proposal["private_summary"] = (
            {
                "count": len(events),
                "types": sorted({e["type"] for e in events}),
                "validate_only": body.get("validate_only", False),
                "integration_source": body.get("integration_source"),
            }
            if events is not None
            else {
                "fields": sorted(body),
                "rows": len(body.get("identifiers", [])),
                "file_id": body.get("file_id"),
                "expected_revision": body.get("expected_revision"),
            }
        )
    return new_preview(args.state, proposal)


def private_digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def private_receipt(spec, path, response):
    result = {"private_output": str(path)}
    if spec["action"] == "create-lead-sync-subscription":
        fields = ("subscription_id", "status")
        required = (*fields, "signing_secret")
    elif spec["action"] == "create-partner-data-upload":
        fields = ("upload_id", "status", "upload_url_expires_at")
        required = (*fields, "upload_url", "upload_method")
    else:
        return result
    result.update({k: response[k] for k in fields if isinstance(response.get(k), str)})
    issues = [k for k in required if not isinstance(response.get(k), str) or not response[k]]
    if spec["action"] == "create-partner-data-upload":
        if not isinstance(response.get("upload_headers"), dict):
            issues.append("upload_headers")
        issues.extend(k for k, v in spec["body"].items() if response.get(k) != v)
    if issues:
        result["fields_to_review"] = issues
    return result


def finish_private_output(execution, response):
    path = execution.plan["secret_output"]
    digest = private_digest(response)
    previous = execution.steps.get("private_digest")
    if previous is not None and previous != digest:
        raise AdsError("Private output differs from the saved response digest.")
    if previous is None:
        execution.checkpoint("private_digest", digest)
    save_json(path, response, create=False)
    return private_receipt(execution.plan["request"], path, response)


def recover_private_output(execution):
    path = execution.plan["secret_output"]
    if not path or execution.steps.get("dispatch") != "pending" or not Path(path).is_file():
        return None
    saved = json.loads(Path(path).read_bytes())
    if not isinstance(saved, dict):
        raise AdsError("Invalid private output. Inspect the original receipt.")
    if saved.get("reserved_for_ads_operation") == execution.state["operation_id"] and isinstance(
        saved.get("response"), dict
    ):
        return finish_private_output(execution, saved["response"])
    # Also recognizes native output written by earlier versions.
    if execution.steps.get("private_digest") == private_digest(saved):
        return private_receipt(execution.plan["request"], path, saved)
    return None


def verify_response(api, plan, response):
    spec = plan["request"]
    body = spec["body"] or {}
    name = spec["action"]
    if name in ("create-lead-sync-subscription", "create-partner-data-upload") and response.get(
        "fields_to_review"
    ):
        return {"state": "review_readback", "response": response}
    if name == "delete-lead-sync-subscription":
        if response.get("absent_in_account") is True:
            return {"state": "absent_in_account", "subscription_id": spec["params"]["subscription_id"]}
        if (
            response.get("subscription_id") != spec["params"]["subscription_id"]
            or response.get("deleted") is not True
        ):
            return {"state": "review_readback", "response": response}
        return {"state": "deleted", "response": response}
    delivery = ads_delivery.verify_response(api, spec, response)
    if delivery is not None:
        return delivery
    account = ads_accounts.verify_response(api, plan, response)
    if account is not None:
        return account
    if name == "patch-product-feed-settings":
        settings = api.request("GET", f"/feeds/{spec['params']['feed_id']}/settings")
        return {
            "state": "read_back" if native_matches(body, settings) else "review_readback",
            "response": response,
            "settings": settings,
        }
    return {"state": "submitted", "response": response}


def observed_transition(path, before, current):
    target, _, verb = path.rpartition("/")
    desired = TRANSITION_STATUS.get(verb)
    key = "account_settings" if target == "/ad_account" else target
    if not desired or key not in before or key not in current:
        return None
    resource = current[key]
    if resource["id"] != before[key]["id"] or resource["status"] != desired:
        return None
    if verb == "activate":
        # Allow the transition's own status and timestamp change. Keep the approved budget and scope checks.
        expected = {**before[key], "status": desired}
        if "updated_at" in resource:
            expected["updated_at"] = resource["updated_at"]
        if resource != expected or any(current.get(k) != v for k, v in before.items() if k != key):
            return None
    return {"observed_status": desired}


def apply_operation(execution):
    p, s = execution.plan, execution.state
    spec = p["request"]
    op = CATALOG[spec["action"]]
    if is_read(op):
        raise AdsError("Invalid mutation receipt.")
    if active_identity(identity(execution.api, spec)) != active_identity(p["account"]):
        raise AdsError("The selected account, partner user or pixel differs from the approved proposal.")
    accepted = execution.steps.get("accepted")
    # Once a response is saved, verification needs no source file, another POST, or unexpired upload URL.
    if accepted is not None:
        return verify_response(execution.api, p, accepted)
    accepted = recover_private_output(execution)
    if accepted is not None:
        execution.checkpoint("accepted", accepted)
        return verify_response(execution.api, p, accepted)
    body = json.loads(read_ref(spec["private_body"])) if spec["private_body"] else spec["body"]
    if spec["file"] and op["method"] != "SFTP" and spec["action"] not in ("upload-image", "upload-blob"):
        raise AdsError("Invalid file operation.")
    pending = execution.steps.get("dispatch") == "pending"
    path = operation_path(op, spec["params"])
    idempotent = op.get("idempotent") or (
        op.get("hotel_idempotency") and body.get("inventory_type") == "hotel"
    )
    # These data APIs can change their own revision or subscription list on
    # acceptance. Recover their keyed response under the original conditions.
    # For delivery operations a pending marker can predate the first remote
    # write, so the approved parent, budget and children must still match.
    replay_data_change = spec["action"] == "create-lead-sync-subscription" or (
        spec["action"]
        in (
            "add-custom-audience-members",
            "remove-custom-audience-members",
            "replace-custom-audience-members",
        )
        and "expected_revision" in body
    )
    if pending and idempotent and replay_data_change:
        current = p["before"]
    else:
        current = snapshot(execution.api, spec, body, p["account"], approved=p["before"])
        if (
            pending
            and spec["action"] == "delete-lead-sync-subscription"
            and current["subscription_status"] is None
        ):
            accepted = {"absent_in_account": True}
        elif pending:
            accepted = observed_transition(path, p["before"], current)
        if accepted is not None:
            execution.checkpoint("accepted", accepted)
            return verify_response(execution.api, p, accepted)
        if current != p["before"]:
            raise AdsError(
                "Live configuration changed since preview. Inspect the target and reconcile any pending request. "
                "Prepare a fresh preview before a new write."
            )
    if pending and not idempotent and not execution.retry_uncertain:
        raise AdsError(
            "Previous outcome is uncertain. Reconcile before explicitly authorizing another attempt."
        )
    api, name = execution.api, spec["action"]
    kwargs = {"query": query_pairs(op, spec["query"])}
    if idempotent:
        kwargs["key"] = s["operation_id"]
    if op.get("private_body") or op.get("private_response") or name == "upload-blob":
        kwargs["private"] = True
    if op.get("service"):
        kwargs["service"] = op["service"]
    if spec["file"] and op["method"] != "SFTP":
        kwargs["multipart"] = multipart_upload(spec["file"], body)
    if p["secret_output"]:
        dest = Path(p["secret_output"])
        reservation = {"reserved_for_ads_operation": s["operation_id"]}
        if dest.exists():
            if json.loads(dest.read_text()) != reservation:
                raise AdsError("Private output already exists. Inspect it before repeating this operation.")
        else:
            # Reserve an owner-only file on the actual destination filesystem.
            # A bad path or a competing receipt must fail before a key is issued.
            save_json(dest, reservation, create=True)
    if op["method"] == "SFTP":
        response = sftp_upload(
            spec["file"],
            body["remote_name"],
            current["access"],
            lambda: execution.checkpoint("dispatch", "pending"),
        )
    else:
        if op.get("service") == "events" and not os.getenv("OPENAI_ADS_CAPI_KEY"):
            raise AdsError("Set OPENAI_ADS_CAPI_KEY before submitting the confirmed events.")
        execution.checkpoint("dispatch", "pending")
        response = api.request(
            op["method"], path, body if "fields" in op and "multipart" not in kwargs else None, **kwargs
        )
    if p["secret_output"]:
        # Preserve the response on its reserved filesystem before touching the
        # receipt filesystem. Either this envelope or the final native file
        # survives a failed checkpoint without issuing a second credential.
        save_json(p["secret_output"], {**reservation, "response": response}, create=False)
        response = finish_private_output(execution, response)
    execution.checkpoint("accepted", response)
    return verify_response(api, p, response)
