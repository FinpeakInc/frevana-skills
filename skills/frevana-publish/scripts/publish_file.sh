#!/usr/bin/env bash

set -euo pipefail

DEFAULT_API_BASE_URL="https://api.frevana.com"
API_BASE_URL="${FREVANA_API_BASE_URL:-$DEFAULT_API_BASE_URL}"
SUBSCRIPTION_PATH="/subscriptions/user"
UPLOAD_URL_PATH="/s3/custom-upload-url"
PUBLISH_PATH_PREFIX="/agents/workflow-result/content"
DOMAIN_SETUP_URL="https://www.frevana.com/dashboard/domain"
FIXED_CATEGORY="agent_app_result"
FIXED_SCENE_TYPE="content_html"
FIXED_PUBLISH_TYPE="custom_domain"
FALLBACK_AGENT_ID="frevana-publish"
CONNECT_TIMEOUT="10"
MAX_TIME="600"

usage() {
  cat <<'EOF'
Usage:
  publish_file.sh --file /path/to/result.html [options]

Options:
  --file        Local file to publish
  --title       Optional title. When omitted, extract it from the file content.
  --agent-id    Optional Frevana Agent ID
  --team-id     Optional desktop team ID
  --session-id  Optional current conversation/session ID used when team ID is unavailable
  --token       Optional Bearer token override for this run
  -h, --help    Show this help message

Environment:
  FREVANA_TOKEN          Frevana Bearer token
  FREVANA_AGENT_ID       Preferred Agent ID
  CODEX_AGENT_ID         Secondary Agent ID source
  FREVANA_TEAM_ID        Preferred team ID
  CODEX_TEAM_ID          Secondary team ID source
  FREVANA_SESSION_ID     Preferred session ID fallback
  CODEX_THREAD_ID        Codex task/thread ID fallback
  CODEX_SESSION_ID       Secondary Codex session ID fallback
  FREVANA_API_BASE_URL   API base URL override for local testing
EOF
}

fail() {
  echo "$1" >&2
  exit 1
}

FILE_PATH=""
FILE_TITLE=""
AGENT_ID="${FREVANA_AGENT_ID:-${CODEX_AGENT_ID:-}}"
TEAM_ID="${FREVANA_TEAM_ID:-${CODEX_TEAM_ID:-}}"
SESSION_ID_FALLBACK="${FREVANA_SESSION_ID:-${CODEX_THREAD_ID:-${CODEX_SESSION_ID:-}}}"
TOKEN_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  if [[ "$1" == --*=* ]]; then
    set -- "${1%%=*}" "${1#*=}" "${@:2}"
  fi

  case "$1" in
    --file)
      FILE_PATH="${2:-}"
      shift 2
      ;;
    --title)
      FILE_TITLE="${2:-}"
      shift 2
      ;;
    --agent-id)
      AGENT_ID="${2:-}"
      shift 2
      ;;
    --team-id)
      TEAM_ID="${2:-}"
      shift 2
      ;;
    --session-id)
      SESSION_ID_FALLBACK="${2:-}"
      shift 2
      ;;
    --token)
      TOKEN_OVERRIDE="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

[[ -n "$FILE_PATH" ]] || fail "Missing required argument: --file"
[[ -f "$FILE_PATH" ]] || fail "File not found or not a regular file: $FILE_PATH"
[[ -r "$FILE_PATH" ]] || fail "File is not readable: $FILE_PATH"
AGENT_ID="${AGENT_ID:-$FALLBACK_AGENT_ID}"
TEAM_ID="${TEAM_ID:-$SESSION_ID_FALLBACK}"
FILE_BASENAME="${FILE_PATH##*/}"
if [[ "$FILE_BASENAME" != *.* || -z "${FILE_BASENAME##*.}" ]]; then
  fail "The file must have an extension so file_extension can be sent to Frevana."
fi

command -v curl >/dev/null 2>&1 || fail "curl is required but was not found in PATH."
command -v python3 >/dev/null 2>&1 || fail "python3 is required but was not found in PATH."

TOKEN="${TOKEN_OVERRIDE:-${FREVANA_TOKEN:-}}"
if [[ -z "$TOKEN" && -t 0 ]]; then
  read -r -s -p "FREVANA_TOKEN not found. Please enter your Frevana Bearer token: " TOKEN
  echo >&2
fi
[[ -n "$TOKEN" ]] || fail "FREVANA_TOKEN is not set. In non-interactive runs, set FREVANA_TOKEN or pass --token explicitly."

SUBSCRIPTION_RESPONSE_FILE="$(mktemp)"
CUSTOM_DOMAIN_FILE="$(mktemp)"
PAYLOAD_FILE="$(mktemp)"
UPLOAD_URL_RESPONSE_FILE="$(mktemp)"
PRESIGNED_URL_FILE="$(mktemp)"
PUBLIC_URL_FILE="$(mktemp)"
CONTENT_ID_FILE="$(mktemp)"
UPLOAD_RESPONSE_FILE="$(mktemp)"
PUBLISH_PAYLOAD_FILE="$(mktemp)"
PUBLISH_RESPONSE_FILE="$(mktemp)"

cleanup() {
  rm -f \
    "$SUBSCRIPTION_RESPONSE_FILE" \
    "$CUSTOM_DOMAIN_FILE" \
    "$PAYLOAD_FILE" \
    "$UPLOAD_URL_RESPONSE_FILE" \
    "$PRESIGNED_URL_FILE" \
    "$PUBLIC_URL_FILE" \
    "$CONTENT_ID_FILE" \
    "$UPLOAD_RESPONSE_FILE" \
    "$PUBLISH_PAYLOAD_FILE" \
    "$PUBLISH_RESPONSE_FILE"
}
trap cleanup EXIT

SUBSCRIPTION_HTTP_CODE="$(
  curl -sS \
    --connect-timeout "$CONNECT_TIMEOUT" \
    --max-time "$MAX_TIME" \
    -o "$SUBSCRIPTION_RESPONSE_FILE" \
    -w "%{http_code}" \
    -X GET "$API_BASE_URL$SUBSCRIPTION_PATH" \
    -H "Accept: application/json" \
    -H "Authorization: Bearer $TOKEN"
)"

if [[ "$SUBSCRIPTION_HTTP_CODE" -lt 200 || "$SUBSCRIPTION_HTTP_CODE" -ge 300 ]]; then
  echo "Frevana subscription API request failed with HTTP $SUBSCRIPTION_HTTP_CODE" >&2
  cat "$SUBSCRIPTION_RESPONSE_FILE" >&2
  exit 1
fi
[[ -s "$SUBSCRIPTION_RESPONSE_FILE" ]] || fail "Frevana subscription API returned an empty response body."

python3 - "$SUBSCRIPTION_RESPONSE_FILE" "$CUSTOM_DOMAIN_FILE" "$DOMAIN_SETUP_URL" <<'PY'
import json
import sys
from pathlib import Path

response_path = Path(sys.argv[1])
domain_path = Path(sys.argv[2])
setup_url = sys.argv[3]
raw = response_path.read_text(encoding="utf-8")

try:
    payload = json.loads(raw)
except json.JSONDecodeError as exc:
    print(f"Frevana subscription API returned non-JSON response: {exc}", file=sys.stderr)
    print(raw, file=sys.stderr)
    sys.exit(1)

def find_custom_domain(value):
    if isinstance(value, dict):
        if "custom_domain" in value:
            return True, value["custom_domain"]
        for child in value.values():
            found, domain = find_custom_domain(child)
            if found:
                return found, domain
    elif isinstance(value, list):
        for child in value:
            found, domain = find_custom_domain(child)
            if found:
                return found, domain
    return False, None

found, custom_domain = find_custom_domain(payload)
if not found:
    print("Frevana subscription API response is missing the 'custom_domain' field.", file=sys.stderr)
    sys.exit(1)

if isinstance(custom_domain, dict):
    custom_domain = next(
        (
            custom_domain.get(key)
            for key in ("url", "domain", "host", "hostname")
            if isinstance(custom_domain.get(key), str) and custom_domain.get(key).strip()
        ),
        "",
    )

if not isinstance(custom_domain, str) or not custom_domain.strip():
    print(
        f"Custom domain is not configured. Configure it at {setup_url}, then run this command again.",
        file=sys.stderr,
    )
    sys.exit(3)

domain_path.write_text(custom_domain.strip(), encoding="utf-8")
PY

python3 - \
  "$FILE_PATH" \
  "$FILE_TITLE" \
  "$AGENT_ID" \
  "$TEAM_ID" \
  "$PAYLOAD_FILE" \
  "$FIXED_CATEGORY" \
  "$FIXED_SCENE_TYPE" \
  "$FIXED_PUBLISH_TYPE" <<'PY'
import json
import mimetypes
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

file_path = Path(sys.argv[1])
explicit_title = sys.argv[2].strip()
agent_id = sys.argv[3]
team_id = sys.argv[4]
payload_path = Path(sys.argv[5])
category = sys.argv[6]
scene_type = sys.argv[7]
publish_type = sys.argv[8]

def normalize_title(value):
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip()

class TitleParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.current_h1_parts = None
        self.current_title_parts = None
        self.h1_candidates = []
        self.title_candidates = []
        self.meta_titles = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attributes = {str(key).lower(): value for key, value in attrs}
        if tag == "h1" and self.current_h1_parts is None:
            self.current_h1_parts = []
        elif tag == "title" and self.current_title_parts is None:
            self.current_title_parts = []
        elif tag == "meta":
            marker = (attributes.get("property") or attributes.get("name") or "").lower()
            content = attributes.get("content")
            if marker in {"og:title", "twitter:title"} and content:
                self.meta_titles.append(content)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "h1" and self.current_h1_parts is not None:
            self.h1_candidates.append("".join(self.current_h1_parts))
            self.current_h1_parts = None
        elif tag == "title" and self.current_title_parts is not None:
            self.title_candidates.append("".join(self.current_title_parts))
            self.current_title_parts = None

    def handle_data(self, data):
        if self.current_h1_parts is not None:
            self.current_h1_parts.append(data)
        if self.current_title_parts is not None:
            self.current_title_parts.append(data)

    def close(self):
        super().close()
        if self.current_h1_parts is not None:
            self.h1_candidates.append("".join(self.current_h1_parts))
            self.current_h1_parts = None
        if self.current_title_parts is not None:
            self.title_candidates.append("".join(self.current_title_parts))
            self.current_title_parts = None

def extract_html_title(text):
    parser = TitleParser()
    try:
        parser.feed(text)
        parser.close()
    except Exception:
        return ""
    candidates = (
        *parser.h1_candidates,
        *parser.title_candidates,
        *parser.meta_titles,
    )
    return next((title for title in map(normalize_title, candidates) if title), "")

def extract_markdown_title(text):
    frontmatter = re.match(r"^\s*---\s*\n(.*?)\n---\s*(?:\n|$)", text, re.DOTALL)
    if frontmatter:
        title_match = re.search(
            r"(?mi)^\s*title\s*:\s*[\"']?(.*?)[\"']?\s*$",
            frontmatter.group(1),
        )
        if title_match:
            title = normalize_title(title_match.group(1))
            if title:
                return title
    heading = re.search(r"(?m)^\s*#\s+(.+?)\s*#*\s*$", text)
    return normalize_title(heading.group(1)) if heading else ""

def extract_json_title(text):
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return ""
    if not isinstance(value, dict):
        return ""
    for key in ("title", "headline", "name"):
        title = normalize_title(value.get(key))
        if title:
            return title
    return ""

def extract_text_title(text):
    for line in text.splitlines():
        title = normalize_title(re.sub(r"^\s*#+\s*", "", line))
        if title:
            return title
    return ""

def extract_title(path):
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    suffix = path.suffix.lower()
    content_type = mimetypes.guess_type(path.name)[0] or ""
    if suffix in {".html", ".htm"} or content_type == "text/html":
        return extract_html_title(text)
    if suffix in {".md", ".markdown", ".mdx"}:
        return extract_markdown_title(text)
    if suffix == ".json" or content_type == "application/json":
        return extract_json_title(text)
    if content_type.startswith("text/"):
        return extract_text_title(text)
    return ""

extension = file_path.suffix.lower().lstrip(".")
if not extension:
    print(
        "The file must have an extension so file_extension can be sent to Frevana.",
        file=sys.stderr,
    )
    sys.exit(1)

content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
file_title = explicit_title or extract_title(file_path) or file_path.stem
payload = {
    "file_extension": extension,
    "content_type": content_type,
    "agent_id": agent_id,
    "scene_type": scene_type,
    "publish_type": publish_type,
    "file_title": file_title,
    "category": category,
}
if team_id:
    payload["team_id"] = team_id
payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
PY

CONTENT_TYPE="$(
  python3 - "$PAYLOAD_FILE" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(payload["content_type"])
PY
)"

UPLOAD_URL_HTTP_CODE="$(
  curl -sS \
    --connect-timeout "$CONNECT_TIMEOUT" \
    --max-time "$MAX_TIME" \
    -o "$UPLOAD_URL_RESPONSE_FILE" \
    -w "%{http_code}" \
    -X POST "$API_BASE_URL$UPLOAD_URL_PATH" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    --data @"$PAYLOAD_FILE"
)"

if [[ "$UPLOAD_URL_HTTP_CODE" -lt 200 || "$UPLOAD_URL_HTTP_CODE" -ge 300 ]]; then
  echo "Frevana custom upload URL API request failed with HTTP $UPLOAD_URL_HTTP_CODE" >&2
  exit 1
fi
[[ -s "$UPLOAD_URL_RESPONSE_FILE" ]] || fail "Frevana custom upload URL API returned an empty response body."

python3 - \
  "$UPLOAD_URL_RESPONSE_FILE" \
  "$PRESIGNED_URL_FILE" \
  "$PUBLIC_URL_FILE" \
  "$CONTENT_ID_FILE" \
  "$CUSTOM_DOMAIN_FILE" <<'PY'
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

response_path = Path(sys.argv[1])
presigned_url_path = Path(sys.argv[2])
public_url_path = Path(sys.argv[3])
content_id_path = Path(sys.argv[4])
custom_domain_path = Path(sys.argv[5])
raw = response_path.read_text(encoding="utf-8")

try:
    payload = json.loads(raw)
except json.JSONDecodeError as exc:
    print(f"Frevana custom upload URL API returned non-JSON response: {exc}", file=sys.stderr)
    sys.exit(1)

if not isinstance(payload, dict):
    print("Frevana custom upload URL API returned JSON, but not an object.", file=sys.stderr)
    sys.exit(1)

presigned_url = payload.get("presigned_url")
public_url = payload.get("url")
content_id = payload.get("content_id")
file_key = payload.get("key") or payload.get("file_key")
if not isinstance(presigned_url, str) or not presigned_url.strip():
    print("Frevana custom upload URL API response is missing 'presigned_url'.", file=sys.stderr)
    sys.exit(1)
if not isinstance(content_id, str) or not content_id.strip():
    print("Frevana custom upload URL API response is missing 'content_id'.", file=sys.stderr)
    sys.exit(1)
if not re.fullmatch(r"[A-Za-z0-9_-]+", content_id.strip()):
    print("Frevana custom upload URL API returned an invalid 'content_id'.", file=sys.stderr)
    sys.exit(1)

custom_domain = custom_domain_path.read_text(encoding="utf-8").strip()
domain_url = custom_domain if "://" in custom_domain else f"https://{custom_domain}"
domain_parts = urlsplit(domain_url)
if domain_parts.scheme not in {"http", "https"} or not domain_parts.hostname:
    print("Frevana subscription API returned an invalid custom domain.", file=sys.stderr)
    sys.exit(1)

if isinstance(public_url, str) and public_url.strip():
    public_url = public_url.strip()
    if public_url.startswith("//"):
        public_url = f"{domain_parts.scheme}:{public_url}"
    elif public_url.startswith("/"):
        public_url = urlunsplit(
            (
                domain_parts.scheme,
                domain_parts.netloc,
                public_url,
                "",
                "",
            )
        )
    elif "://" not in public_url:
        public_url = f"{domain_parts.scheme}://{public_url}"
    public_parts = urlsplit(public_url)
    if (
        public_parts.scheme not in {"http", "https"}
        or not public_parts.hostname
        or public_parts.username is not None
        or public_parts.password is not None
    ):
        print(
            "Frevana custom upload URL API returned an invalid public URL.",
            file=sys.stderr,
        )
        sys.exit(1)
else:
    if not isinstance(file_key, str) or not file_key.strip():
        print(
            "Frevana custom upload URL API response is missing both public 'url' and file 'key'.",
            file=sys.stderr,
        )
        sys.exit(1)
    base_path = domain_parts.path.rstrip("/")
    encoded_key = quote(file_key.strip().lstrip("/"), safe="/%")
    public_url = urlunsplit(
        (
            domain_parts.scheme,
            domain_parts.netloc,
            f"{base_path}/{encoded_key}",
            "",
            "",
        )
    )

presigned_url_path.write_text(presigned_url.strip(), encoding="utf-8")
public_url_path.write_text(public_url, encoding="utf-8")
content_id_path.write_text(content_id.strip(), encoding="utf-8")
PY

PRESIGNED_URL="$(<"$PRESIGNED_URL_FILE")"
UPLOAD_HTTP_CODE="$(
  curl -sS \
    --connect-timeout "$CONNECT_TIMEOUT" \
    --max-time "$MAX_TIME" \
    -o "$UPLOAD_RESPONSE_FILE" \
    -w "%{http_code}" \
    -X PUT "$PRESIGNED_URL" \
    -H "Content-Type: $CONTENT_TYPE" \
    --upload-file "$FILE_PATH"
)"

if [[ "$UPLOAD_HTTP_CODE" -lt 200 || "$UPLOAD_HTTP_CODE" -ge 300 ]]; then
  echo "File upload failed with HTTP $UPLOAD_HTTP_CODE" >&2
  exit 1
fi

python3 - "$PAYLOAD_FILE" "$PUBLISH_PAYLOAD_FILE" <<'PY'
import json
import sys
from pathlib import Path

upload_payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
publish_payload = {
    "title": upload_payload["file_title"],
    "publish_type": upload_payload["publish_type"],
    "category": upload_payload["category"],
}
Path(sys.argv[2]).write_text(
    json.dumps(publish_payload, ensure_ascii=False),
    encoding="utf-8",
)
PY

CONTENT_ID="$(<"$CONTENT_ID_FILE")"
PUBLISH_HTTP_CODE="$(
  curl -sS \
    --connect-timeout "$CONNECT_TIMEOUT" \
    --max-time "$MAX_TIME" \
    -o "$PUBLISH_RESPONSE_FILE" \
    -w "%{http_code}" \
    -X PUT "$API_BASE_URL$PUBLISH_PATH_PREFIX/$CONTENT_ID/publish?op_type=publish" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    --data @"$PUBLISH_PAYLOAD_FILE"
)"

if [[ "$PUBLISH_HTTP_CODE" -lt 200 || "$PUBLISH_HTTP_CODE" -ge 300 ]]; then
  echo "File uploaded, but Frevana publish API request failed with HTTP $PUBLISH_HTTP_CODE" >&2
  cat "$PUBLISH_RESPONSE_FILE" >&2
  exit 1
fi

cat "$PUBLIC_URL_FILE"
printf '\n'
