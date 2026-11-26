"""Local pixel installation assets and file transports for the Ads API."""

import hashlib
import json
import mimetypes
import os
import subprocess
import tempfile
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from ads_api import AdsError, identifier
from ads_operations import read_ref


def multipart_upload(ref, fields):
    name = Path(ref["path"]).name
    if any(ord(c) < 32 for c in name):
        raise AdsError("Unsupported control character in upload filename.")
    name = name.replace("\\", "_").replace('"', "_")
    boundary = uuid.uuid4().hex
    sections = []
    for field, value in fields.items():
        if field != "purpose" or not isinstance(value, str):
            raise AdsError("Only the purpose text field accompanies a binary upload.")
        sections.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"\r\n\r\n{value}\r\n'.encode()
        )
    mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
    sections += [
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\nContent-Type: {mime}\r\n\r\n'.encode(),
        read_ref(ref),
        f"\r\n--{boundary}--\r\n".encode(),
    ]
    return b"".join(sections), "multipart/form-data; boundary=" + boundary


def sftp_upload(ref, remote_name, access, before_transfer):
    if not access.get("enabled"):
        raise AdsError("Feed SFTP access is disabled.")
    uri = access["connection_uri"]
    target = urlsplit(uri if "://" in uri else "sftp://" + uri)
    if (
        target.scheme != "sftp"
        or not target.hostname
        or not target.username
        or target.password is not None
        or any(c in (target.username + target.hostname) for c in "\r\n /@")
        or target.path not in ("", "/")
    ):
        raise AdsError("Unexpected SFTP connection URI returned by the feed.")
    if target.query or target.fragment:
        raise AdsError("Unexpected query or fragment in the SFTP connection URI.")
    with tempfile.TemporaryDirectory() as directory:
        local = Path(directory) / "snapshot"
        digest = hashlib.sha256()
        with open(ref["path"], "rb") as source, local.open("wb") as dest:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                dest.write(block)
                digest.update(block)
        if digest.hexdigest() != ref["sha256"]:
            raise AdsError("Feed changed after preview.")
        known_hosts = os.environ.get("OPENAI_ADS_SFTP_KNOWN_HOSTS")
        if access.get("authentication_method") == "password":
            try:
                import paramiko
            except ImportError:
                raise AdsError("Password SFTP requires paramiko in this Python environment.") from None
            password = os.getenv("OPENAI_ADS_SFTP_PASSWORD")
            if not password:
                raise AdsError("Set OPENAI_ADS_SFTP_PASSWORD for password-based SFTP.")
            with paramiko.SSHClient() as client:
                client.load_system_host_keys()
                if known_hosts:
                    client.load_host_keys(known_hosts)
                client.set_missing_host_key_policy(paramiko.RejectPolicy())
                client.connect(
                    hostname=target.hostname,
                    port=target.port or 22,
                    username=target.username,
                    password=password,
                    allow_agent=False,
                    look_for_keys=False,
                    timeout=30,
                )
                with client.open_sftp() as sftp:
                    before_transfer()
                    sftp.put(str(local), remote_name, confirm=True)
        elif access.get("authentication_method") == "ssh_key":
            cmd = [
                "sftp",
                "-b",
                "-",
                "-P",
                str(target.port or 22),
                "-oBatchMode=yes",
                "-oStrictHostKeyChecking=yes",
            ]
            if known_hosts:
                cmd.extend(["-o", "UserKnownHostsFile=" + str(Path(known_hosts).resolve())])
            if os.environ.get("OPENAI_ADS_SFTP_IDENTITY_FILE"):
                cmd.extend(["-i", str(Path(os.environ["OPENAI_ADS_SFTP_IDENTITY_FILE"]).resolve())])
            if target.username.startswith("-") or target.hostname.startswith("-"):
                raise AdsError("Invalid SFTP destination.")
            cmd.extend(["--", target.username + "@" + target.hostname])
            try:
                before_transfer()
                subprocess.run(
                    cmd,
                    cwd=directory,
                    input=f"put snapshot {remote_name}\n",
                    text=True,
                    capture_output=True,
                    check=True,
                )
            except subprocess.CalledProcessError as exc:
                raise AdsError(
                    f"SFTP exited with status {exc.returncode}. Check host trust, authentication and feed upload history."
                ) from None
        else:
            raise AdsError("Unsupported SFTP authentication method.")
    return {
        "remote_name": remote_name,
        "sha256": ref["sha256"],
        "transfer": "uploaded",
        "ingestion": "Check list-product-feed-uploads for the processing outcome.",
    }


def write_pixel(pixel_ids, path, consent_required):
    ids = [identifier(value) for value in pixel_ids]
    if len(set(ids)) != len(ids):
        raise AdsError("Supply each Pixel ID once.")
    # Site owner supplies the real conversion identity and value at purchase time.
    consent = '  oaiq("consent", false);\n' if consent_required else ""
    snippet = (
        """<script>
  (function(w,d) {
    if (w.oaiq) return;
    var q = function() { q.q.push(arguments); };
    q.q = []; w.oaiq = q;
    var js = d.createElement("script"); js.async = true;
    js.src = "https://bzrcdn.openai.com/sdk/oaiq.min.js";
    var first = d.getElementsByTagName("script")[0];
    first.parentNode.insertBefore(js, first);
  })(window, document);
"""
        + consent
        + "".join('  oaiq("init", {pixelId: ' + json.dumps(value) + "});\n" for value in ids)
        + "</script>\n"
    )
    path = Path(path)
    with path.open("x", encoding="utf-8") as out:
        out.write(snippet)
    result = {"output": str(path), "pixel_ids": ids, "consent_required": consent_required}
    if len(ids) == 1:
        result["pixel_id"] = ids[0]
    return result
