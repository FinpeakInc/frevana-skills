#!/usr/bin/env python3
"""Resumable Frevana Instagram profile integration (stdlib only)."""
import argparse
import contextlib
import fcntl
import http.client
import json
import math
import os
from pathlib import Path
import queue
import re
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ENDPOINT = "instagram/profile"
ROOT = "/socialcrawl/tasks"
ACTIVE = {"PENDING", "RUNNING", "POLLING", "SETTLING"}
STOP = {"FAILED", "REVIEW_REQUIRED"}
TRANSIENT = {429, 500, 502, 503, 504}


class Invalid(ValueError):
    pass


class StateError(Invalid):
    def __init__(self, message, metadata=None, code="INVALID_STATE"):
        super().__init__(message)
        self.metadata = metadata or {}
        self.code = code


def decode(raw):
    def reject_constant(value):
        raise ValueError("non-finite JSON number")
    return json.loads(raw, parse_constant=reject_constant)


def valid_client_id(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value) is not None


class TimedOut(Exception):
    pass


class TransportError(Exception):
    pass


class StateWriteError(Exception):
    pass


def validate_task_id(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-4[0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}", value
    ):
        raise Invalid("task_id must be a UUID v4")
    return str(uuid.UUID(value))


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def scrub(value, token):
    # Also protect against a server echoing request credentials in an error.
    if isinstance(value, str):
        return value.replace(token, "[REDACTED]") if token else value
    if isinstance(value, dict):
        return {scrub(k, token): scrub(v, token) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v, token) for v in value]
    return value


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(encode(value) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextlib.contextmanager
def locked(path):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(path) + ".lock", os.O_CREAT | os.O_RDWR, 0o600)
    except OSError:
        raise StateError("cannot access the operation state lock", code="STATE_ACCESS_FAILED") from None
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise StateError("state file is in use; serialize this operation", code="STATE_BUSY") from exc
        yield
    finally:
        os.close(fd)


def validate_input(value):
    if not isinstance(value, dict) or set(value) - {"handle", "trim", "async", "contact_email"}:
        raise Invalid("input must be an object containing only handle, trim, async, contact_email")
    if not isinstance(value.get("handle"), str) or not value["handle"] or value["handle"].startswith("@"):
        raise Invalid("handle must be a nonempty username string without @")
    if "trim" in value and type(value["trim"]) is not bool:
        raise Invalid("trim must be a JSON boolean")
    if "async" in value:
        item = value["async"]
        valid = (type(item) is bool or (type(item) is int and item in (0, 1))
                 or (type(item) is str and item in ("true", "false", "1", "0")))
        if not valid:
            raise Invalid("async must be boolean, integer 0/1, or string true/false/1/0")
    if "contact_email" in value and (type(value["contact_email"]) is not str or value["contact_email"] != "1"):
        raise Invalid('contact_email must be the string "1"')
    return value


def origin(value):
    url = urllib.parse.urlsplit(value)
    try:
        url.port
    except ValueError as exc:
        raise Invalid("invalid API origin port") from exc
    if (not url.hostname or url.username is not None or url.password is not None
            or url.query or url.fragment or url.path not in ("", "/")
            or any(c.isspace() for c in value)
            or (url.scheme != "https" and not (url.scheme == "http" and url.hostname in ("localhost", "127.0.0.1", "::1")))):
        raise Invalid("API base must be an HTTPS origin (HTTP allowed only for localhost)")
    return value.rstrip("/")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, base, token):
        self.base, self.token = base, token
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, method, suffix, payload, timeout):
        # A daemon bounds wall time even if a peer trickles response bytes.
        # On timeout the caller stops, without issuing overlapping retries.
        done = queue.Queue(maxsize=1)

        def perform():
            try:
                request = urllib.request.Request(
                    self.base + ROOT + suffix, method=method,
                    data=encode(payload).encode("utf-8") if payload is not None else None,
                    headers={"Authorization": "Bearer " + self.token,
                             "Content-Type": "application/json", "Accept": "application/json"})
                try:
                    response = self.opener.open(request, timeout=timeout)
                except urllib.error.HTTPError as error:
                    response = error
                with response:
                    status = response.code
                    raw = response.read()
                try:
                    body = json.loads(raw)
                except (ValueError, UnicodeError):
                    body = {"error_code": "INVALID_JSON_RESPONSE"}
                done.put(((status, scrub(body, self.token)), None))
            except (TimeoutError, urllib.error.URLError, OSError, http.client.HTTPException) as exc:
                timeout_error = isinstance(exc, TimeoutError) or isinstance(getattr(exc, "reason", None), TimeoutError)
                done.put((None, TimedOut() if timeout_error else TransportError()))
            except Exception:
                done.put((None, TransportError()))

        threading.Thread(target=perform, daemon=True).start()
        try:
            result, error = done.get(timeout=timeout)
        except queue.Empty as exc:
            raise TimedOut() from exc
        if error:
            raise error
        return result


def error_code(body):
    if isinstance(body, dict):
        for key in ("error_code", "code"):
            if isinstance(body.get(key), str):
                return body[key]
        if isinstance(body.get("error"), dict):
            found = error_code(body["error"])
            if found:
                return found
        if isinstance(body.get("message"), str):
            return body["message"]
    return None


class Operation:
    def __init__(self, state, path, client, args):
        self.state, self.path, self.client, self.args = state, path, client, args
        self.deadline = time.monotonic() + args.timeout
        self.final_outcome = None

    def persist(self):
        try:
            save(self.path, self.state)
        except OSError as exc:
            raise StateWriteError() from exc

    def finish(self, outcome, code=None, persist=True):
        self.final_outcome = outcome
        self.state["outcome"] = outcome
        if code:
            self.state["error_code"] = code
        if persist:
            self.persist()
        s = self.state
        return {**{key: s.get(key) for key in (
            "task_id", "client_task_id", "status", "error_code", "http_status",
            "server_error_code", "next_poll_after_ms", "request_payload", "api_response")},
            "outcome": outcome, "state_file": str(self.path),
            "endpoint_id": ENDPOINT,
            "error_source": ("server" if outcome in ("failed", "conflict", "http_error")
                             else "protocol" if outcome == "protocol_error"
                             else "client" if outcome in ("timeout", "transport_error") else None),
            "resumable": bool(s.get("task_id") or s.get("request_payload"))
                         and s.get("status") not in STOP and outcome != "completed"
                         and (s.get("http_status") != 409 or bool(s.get("task_id"))),
            **({"data": s["data"], "pagination": s.get("pagination")} if "data" in s else {})}

    def pause(self, seconds):
        remaining = self.deadline - time.monotonic()
        if seconds >= remaining:
            raise TimedOut()
        if seconds > 0:
            time.sleep(seconds)

    def request(self, method, suffix="", payload=None):
        for attempt in range(self.args.retries + 1):
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise TimedOut()
            try:
                status, body = self.client.request(method, suffix, payload, min(remaining, self.args.request_timeout))
            except TransportError:
                if attempt == self.args.retries:
                    raise
            else:
                if (status not in TRANSIENT or attempt == self.args.retries
                        or (isinstance(body, dict) and (body.get("task_id") or body.get("status") in STOP))):
                    return status, body
            self.pause(min(2 ** attempt, 8))
        raise AssertionError("unreachable")

    def accept(self, status, body, result=False, inline=False):
        s = self.state
        server_code = error_code(body)
        s.update(http_status=status, api_response=body, error_code=server_code, server_error_code=server_code)
        if isinstance(body, dict):
            task_id = None
            if "task_id" in body:
                try:
                    task_id = validate_task_id(body["task_id"])
                except Invalid:
                    return self.finish("protocol_error", "INVALID_TASK_ID")
                if s.get("task_id") and s["task_id"] != task_id:
                    return self.finish("protocol_error", "TASK_ID_MISMATCH")
            elif 200 <= status < 300 and body.get("error_code") != "INVALID_JSON_RESPONSE":
                return self.finish("protocol_error", "MISSING_TASK_ID")
            if body.get("endpoint_id") and body["endpoint_id"] != ENDPOINT:
                return self.finish("protocol_error", "ENDPOINT_ID_MISMATCH")
            if "client_task_id" in body:
                if not valid_client_id(body["client_task_id"]):
                    return self.finish("protocol_error", "INVALID_CLIENT_TASK_ID")
                if s.get("client_task_id") and s["client_task_id"] != body["client_task_id"]:
                    return self.finish("protocol_error", "CLIENT_TASK_ID_MISMATCH")
                s["client_task_id"] = body["client_task_id"]
            elif 200 <= status < 300 and not result and body.get("error_code") != "INVALID_JSON_RESPONSE":
                # The task was accepted, but its client identity was omitted.
                # Keep the verified server ID so recovery never POSTs again.
                if task_id:
                    s["task_id"] = task_id
                return self.finish("protocol_error", "MISSING_CLIENT_TASK_ID")
            if task_id:
                s["task_id"] = task_id
            if body.get("status"):
                if not isinstance(body["status"], str):
                    return self.finish("protocol_error", "INVALID_TASK_STATUS")
                s["status"] = body["status"]
            if result and s.get("status") not in ("READY", *STOP):
                return self.finish("protocol_error", "RESULT_NOT_READY")
            delay = body.get("next_poll_after_ms")
            if type(delay) not in (int, float) or not math.isfinite(delay) or delay < 0:
                delay = None
            s["next_poll_after_ms"] = delay
            s["next_poll_at"] = (time.time() + delay / 1000
                                 if type(delay) in (int, float) and math.isfinite(delay) and delay > 0 else None)
            # Fetching /result follows a READY status; inline data requires READY.
            if (200 <= status < 300 and s.get("status") == "READY" and "data" in body
                    and (result or (inline and status == 200))):
                s.update(data=body["data"], pagination=body.get("pagination"))
        if s.get("status") in STOP:
            return self.finish("failed", s.get("error_code") or s["status"])
        if not 200 <= status < 300:
            return self.finish("conflict" if status == 409 else "http_error",
                               s.get("error_code") or "HTTP_" + str(status))
        if not isinstance(body, dict) or body.get("error_code") == "INVALID_JSON_RESPONSE":
            return self.finish("protocol_error", "INVALID_JSON_RESPONSE")
        self.persist()  # task identity survives any subsequent interruption
        return None

    def run(self):
        try:
            return self._run()
        except StateWriteError:
            # Never continue polling/submitting after a failed checkpoint. Return
            # the identity already received even when it could not reach disk.
            s = self.state
            outcome = self.final_outcome or ("completed" if s.get("status") == "READY" and "data" in s
                                             else "failed" if s.get("status") in STOP else "pending")
            result = self.finish(outcome, persist=False)
            result["client_errors"] = [{"code": "STATE_SAVE_FAILED",
                                        "source": "state",
                                        "message": "State could not be saved; retain the returned task ID and original payload for recovery."}]
            return result

    def _run(self):
        s = self.state
        if s.get("status") in STOP:
            return self.finish("failed")
        if s.get("status") == "READY" and "data" in s:
            return self.finish("completed")
        if s.get("http_status") == 409 and not s.get("task_id"):
            return self.finish("conflict")
        if s.get("outcome") == "protocol_error" and not s.get("task_id"):
            return self.finish("protocol_error")
        try:
            if not s.get("task_id"):
                response = self.accept(*self.request("POST", payload=s["request_payload"]), inline=True)
                if response:
                    return response
            else:
                # Resume an ID with no creation; respect persisted scheduling first.
                self.pause(max(0, (s.get("next_poll_at") or 0) - time.time()))
                response = self.accept(*self.request("GET", "/" + urllib.parse.quote(s["task_id"], safe="")))
                if response:
                    return response
            while True:
                if s.get("status") == "READY":
                    if "data" not in s:
                        if not s.get("task_id"):
                            return self.finish("protocol_error", "MISSING_TASK_ID")
                        response = self.accept(*self.request("GET", "/" + urllib.parse.quote(s["task_id"], safe="") + "/result"), result=True)
                        if response:
                            return response
                        if "data" not in s:
                            return self.finish("protocol_error", "MISSING_RESULT_DATA")
                    return self.finish("completed")
                if not s.get("task_id"):
                    return self.finish("protocol_error", "MISSING_TASK_ID")
                if s.get("status") not in ACTIVE or not s.get("next_poll_at"):
                    return self.finish("pending")
                self.pause(max(0, s["next_poll_at"] - time.time()))
                response = self.accept(*self.request("GET", "/" + urllib.parse.quote(s["task_id"], safe="")))
                if response:
                    return response
        except TimedOut:
            return self.finish("timeout", "CLIENT_TIMEOUT")
        except TransportError:
            return self.finish("transport_error", "TRANSPORT_ERROR")


def parser():
    p = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    p.add_argument("action", choices=("run", "resume"))
    p.add_argument("--state-file", required=True, help="Durable path unique to this logical operation")
    p.add_argument("--task-id")
    p.add_argument("--client-task-id")
    p.add_argument("--handle")
    p.add_argument("--trim", choices=("true", "false"))
    p.add_argument("--async", dest="background", choices=("true", "false", "1", "0"))
    p.add_argument("--contact-email", choices=("1",))
    p.add_argument("--input-file")
    p.add_argument("--api-base-url", default=None)
    p.add_argument("--timeout", type=float, default=120)
    p.add_argument("--request-timeout", type=float, default=30)
    p.add_argument("--retries", type=int, default=2)
    p.add_argument("--output")
    return p


def recovery_metadata(state):
    """Return only usable identity fields; never trust arbitrary state as output."""
    result = {"endpoint_id": ENDPOINT, "task_id": None, "client_task_id": None, "request_payload": None,
              "resumable": False}
    if not isinstance(state, dict):
        return result
    try:
        result["task_id"] = validate_task_id(state.get("task_id"))
    except Invalid:
        pass
    if valid_client_id(state.get("client_task_id")):
        result["client_task_id"] = state["client_task_id"]
    payload = state.get("request_payload")
    if (isinstance(payload, dict) and set(payload) == {"endpoint_id", "client_task_id", "input", "response_mode"}
            and payload["endpoint_id"] == ENDPOINT and payload["response_mode"] == "json"
            and valid_client_id(payload["client_task_id"])):
        try:
            validate_input(payload["input"])
        except Invalid:
            pass
        else:
            result["request_payload"] = payload
    result["resumable"] = bool(result["task_id"] or result["request_payload"])
    return result


def validate_state(state):
    metadata = recovery_metadata(state)
    # Original version-1 states omitted endpoint_id; validate it when present.
    required = {"version", "api_base_url", "task_id", "client_task_id", "request_payload"}
    if not isinstance(state, dict) or not required <= state.keys():
        raise StateError("existing state must contain all operation identity fields", metadata)
    if type(state["version"]) is not int or state["version"] != 1 or state.get("endpoint_id", ENDPOINT) != ENDPOINT:
        raise StateError("state version or endpoint is incompatible", metadata)
    try:
        if origin(state["api_base_url"]) != state["api_base_url"]:
            raise Invalid("invalid saved API origin")
        if state["task_id"] is not None:
            state["task_id"] = validate_task_id(state["task_id"])
    except (Invalid, ValueError, TypeError, AttributeError):
        raise StateError("state has an invalid API origin or task_id", metadata) from None
    client_id = state["client_task_id"]
    if client_id is not None and not valid_client_id(client_id):
        raise StateError("state has an invalid client_task_id", metadata, "INVALID_CLIENT_TASK_ID")
    payload = state["request_payload"]
    if payload is not None:
        if metadata["request_payload"] is None:
            raise StateError("state has an invalid original request payload", metadata)
        if payload["client_task_id"] != client_id:
            raise StateError("state client identity differs from the original request", metadata, "CLIENT_TASK_ID_MISMATCH")
    if state["task_id"] is None and payload is None:
        raise StateError("state has neither task_id nor the original request", metadata)
    if state.get("status") is not None and not isinstance(state["status"], str):
        raise StateError("state has an invalid task status", metadata)
    if state.get("status") == "READY" and state["task_id"] is None:
        raise StateError("saved READY state requires a valid task_id", metadata)
    for key in ("next_poll_at", "next_poll_after_ms"):
        value = state.get(key)
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
            raise StateError("state has an invalid poll schedule", metadata)
    return state


def prepare(args, path):
    for value in (args.timeout, args.request_timeout):
        if not math.isfinite(value) or value <= 0:
            raise Invalid("timeouts must be finite positive seconds")
    if not 0 <= args.retries <= 10:
        raise Invalid("retries must be between 0 and 10")
    if args.task_id is not None:
        args.task_id = validate_task_id(args.task_id)
    supplied = {key: value for key, value in (
        ("handle", args.handle), ("trim", None if args.trim is None else args.trim == "true"),
        ("async", None if args.background is None else json.loads(args.background)),
        ("contact_email", args.contact_email)) if value is not None}
    if args.input_file:
        if supplied:
            raise Invalid("--input-file cannot be mixed with input flags")
        supplied = validate_input(json.loads(Path(args.input_file).read_text(encoding="utf-8")))
    try:
        raw_state = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        state = None
    except (OSError, UnicodeError):
        raise StateError("existing state is unreadable; no task was submitted") from None
    else:
        try:
            state = decode(raw_state)
        except (ValueError, UnicodeError):
            raise StateError("existing state contains invalid JSON; preserve it for recovery") from None
        state = validate_state(state)
    base = origin(args.api_base_url or os.environ.get("FREVANA_API_BASE_URL")
                  or (state or {}).get("api_base_url") or "https://api.frevana.com")
    if state is not None:
        metadata = recovery_metadata(state)
        if state["api_base_url"] != base:
            raise StateError("API origin differs from this operation's saved origin", metadata)
        payload = state["request_payload"]
        if supplied and (payload is None or any(encode(payload["input"].get(k)) != encode(v) for k, v in supplied.items())):
            raise StateError("input differs from the original profile operation; retain the original request", metadata)
        if args.client_task_id is not None and args.client_task_id != state["client_task_id"]:
            raise StateError("client_task_id differs from this operation", metadata, "CLIENT_TASK_ID_MISMATCH")
        if args.task_id is not None:
            if state["task_id"] is not None and args.task_id != state["task_id"]:
                raise StateError("task_id differs from this operation", metadata, "TASK_ID_MISMATCH")
            state["task_id"] = args.task_id
    elif args.task_id is not None:
        if supplied or args.client_task_id is not None:
            raise Invalid("known-task recovery accepts no creation input")
        state = {"version": 1, "endpoint_id": ENDPOINT, "api_base_url": base, "task_id": args.task_id,
                 "client_task_id": None, "request_payload": None}
    else:
        if args.action == "resume":
            raise StateError("resume requires saved state or --task-id")
        validate_input(supplied)
        client_id = args.client_task_id if args.client_task_id is not None else str(uuid.uuid4())
        if not valid_client_id(client_id):
            raise Invalid("client_task_id must be 1-128 letters, digits, or _.:-")
        state = {"version": 1, "endpoint_id": ENDPOINT, "api_base_url": base, "task_id": None,
                 "client_task_id": client_id, "request_payload": {
                     "endpoint_id": ENDPOINT, "client_task_id": client_id,
                     "input": supplied, "response_mode": "json"}}
    return state, base


def main(argv=None):
    args = parser().parse_args(argv)
    token = os.environ.get("FREVANA_TOKEN", "")
    path = Path(args.state_file).expanduser().resolve()
    state = None
    try:
        if not token or any(c.isspace() for c in token):
            raise Invalid("configure FREVANA_TOKEN in the runtime environment")
        if args.output and Path(args.output).expanduser().resolve() in (path, Path(str(path) + ".lock")):
            raise Invalid("output must differ from state and lock files")
        with locked(path):
            state, base = prepare(args, path)
            try:
                save(path, state)  # must happen before any network request
            except OSError:
                raise StateError("initial checkpoint failed; no request was sent", recovery_metadata(state), "INITIAL_STATE_SAVE_FAILED") from None
            result = scrub(Operation(state, path, Client(base, token), args).run(), token)
            if args.output:
                try:
                    save(Path(args.output).expanduser(), result)
                except OSError:
                    result.setdefault("client_errors", []).append({
                        "code": "OUTPUT_SAVE_FAILED", "source": "persistence",
                        "message": "Output file could not be saved; task outcome, data and recovery metadata are retained in stdout."})
            print(encode(result))
        if result.get("client_errors"):
            return 5
        return 0 if result["outcome"] == "completed" else (3 if result["outcome"] in ("timeout", "pending") else 4)
    except StateError as exc:
        print(encode(scrub({**exc.metadata, "outcome": "state_error", "error_source": "state",
                           "error_code": exc.code, "state_file": str(path), "requires_state_repair": True,
                           "message": str(exc)}, token)))
        return 5
    except (Invalid, OSError, ValueError, TypeError, KeyError) as exc:
        print(encode(scrub({**recovery_metadata(state), "outcome": "invalid_configuration", "error_source": "client",
                           "error_code": "INVALID_CONFIGURATION", "state_file": str(path),
                           "message": str(exc) if isinstance(exc, Invalid) else
                           "Check input JSON, runtime configuration and file permissions; see --help."}, token)))
        return 2


if __name__ == "__main__":
    sys.exit(main())
