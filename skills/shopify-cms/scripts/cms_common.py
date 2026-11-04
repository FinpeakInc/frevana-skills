"""Small stdlib runtime bundled with each independently installable CMS skill."""
import argparse
import getpass
from http.client import HTTPException
import json
import os
from pathlib import Path
import sys
import tempfile
from urllib import error, request


class Failure(Exception):
    def __init__(self, message, **details):
        super().__init__(message)
        self.details = details


def require(condition, message):
    if not condition:
        raise Failure(message)


def read_json(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Failure("Cannot read JSON object from file", file=str(path)) from exc
    require(isinstance(value, dict), "Expected a JSON object")
    return value


def text_field(data, key, required=False):
    if required or key in data:
        require(isinstance(data.get(key), str) and (not required or data[key].strip()),
                f"{key} must be a string" + (" and nonempty" if required else ""))


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http(method, url, headers, data=None, form=False):
    body = data.encode("utf-8") if form else (
        json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None)
    req = request.Request(url, data=body, headers=headers, method=method)
    try:
        with request.build_opener(NoRedirect).open(req, timeout=30) as response:
            raw = response.read()
    except error.HTTPError as exc:
        try:
            native = json.loads(exc.read())
        except ValueError:
            native = None
        raise Failure("API request rejected; no automatic retry", http_status=exc.code,
                      response=native, retry_after=exc.headers.get("Retry-After")) from exc
    except (error.URLError, TimeoutError, OSError, HTTPException) as exc:
        raise Failure("Transport failed; reconcile remote state before repeating a write") from exc
    try:
        value = json.loads(raw)
    except ValueError as exc:
        raise Failure("API returned invalid JSON; reconcile remote state before repeating a write") from exc
    require(isinstance(value, dict), "API response must be a JSON object")
    return value


def parser_for(description, actions, fields):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("action", choices=["configure", *actions])
    parser.add_argument("--config")
    for field in fields:
        parser.add_argument("--" + field.replace("_", "-"))
    parser.add_argument("--id", help="Exact remote article/item ID")
    parser.add_argument("--data-file", help="UTF-8 JSON content payload")
    parser.add_argument("--execute", action="store_true", help="Execute a reviewed publication")
    parser.add_argument("--limit", type=int, default=50)
    return parser


class Config:
    def __init__(self, args, prefix, fields, defaults, secrets, setup_guide=None):
        self.args, self.prefix, self.fields, self.secrets = args, prefix, fields, secrets
        self.setup_guide = setup_guide
        root = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
        self.path = Path(args.config or os.environ.get(prefix + "_CONFIG_FILE") or
                         root / (prefix.lower() + "-content") / "config.json").expanduser()
        self.saved = read_json(self.path) if self.path.exists() else {}
        require(all(k in fields and isinstance(v, str) for k, v in self.saved.items()),
                "Config has unknown keys or non-string values")
        self.values = {key: getattr(args, key, None) or os.environ.get(prefix + "_" + key.upper()) or
                       self.saved.get(key) or defaults.get(key, "") for key in fields}

    def need(self, *keys):
        missing = [self.prefix + "_" + k.upper() for k in keys if not self.values.get(k, "").strip()]
        if missing:
            details = {"setupGuide": self.setup_guide} if self.setup_guide else {}
            raise Failure("Missing configuration: " + ", ".join(missing) +
                          ". Set environment variables or run configure.", **details)

    def configure(self, required, validate=None):
        if sys.stdin.isatty():
            for key in required:
                if not self.values[key]:
                    prompt = self.prefix + "_" + key.upper() + ": "
                    self.values[key] = getpass.getpass(prompt) if key in self.secrets else input(prompt)
        self.need(*required)
        if validate:
            validate(self.values)
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        # Do not change permissions of a user-selected existing parent directory.
        fd, tmp = tempfile.mkstemp(prefix=".cms-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(self.values, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        return {"configured": True, "configFile": str(self.path)}

    def redact(self, value):
        # Redact secrets even when a provider echoes them in an error string.
        if isinstance(value, dict):
            return {k: ("[REDACTED]" if k.lower() in {"access_token", "client_secret", "api_token"}
                        else self.redact(v)) for k, v in value.items()}
        if isinstance(value, list):
            return [self.redact(v) for v in value]
        if isinstance(value, str):
            for key in self.secrets:
                secret = self.values.get(key)
                if secret:
                    value = value.replace(secret, "[REDACTED]")
        return value


def cli_main(run, args, config):
    try:
        result = run(args, config)
        code = 1 if result.get("status") == "unverified" else 0
    except Failure as exc:
        result = {"error": str(exc), **exc.details}
        code = 1
    except (OSError, ValueError) as exc:
        result = {"error": "Local input/configuration failure", "type": type(exc).__name__}
        code = 1
    print(json.dumps(config.redact(result), ensure_ascii=False, indent=2))
    return code
