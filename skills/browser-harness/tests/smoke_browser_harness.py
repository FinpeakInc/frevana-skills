import argparse
import functools
import tempfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import threading
import time

parser = argparse.ArgumentParser(description="Opt-in smoke test using installed official CLI and an isolated headless Chrome. Never uses personal Chrome profiles.")
parser.add_argument("--harness-bin-dir", type=Path, required=True)
parser.add_argument("--chrome", type=Path, required=True)
args = parser.parse_args()
# macOS AF_UNIX socket paths are limited to 104 bytes. Its default temp root
# already consumes most of that budget, so keep this isolated profile root short.
ROOT = Path(tempfile.mkdtemp(prefix="bh-smoke-", dir="/tmp" if os.name != "nt" else None))
print(f"Smoke artifacts: {ROOT}", flush=True)
BIN = args.harness_bin_dir.expanduser().resolve()
CHROME = args.chrome.expanduser().resolve()
if not CHROME.is_file():
    raise SystemExit("Chrome binary not found")
SITE = ROOT / 'site'
SITE.mkdir(exist_ok=True)
(SITE / 'index.html').write_text('''<!doctype html><title>Frevana browser fixture</title>
<label>Name <input id="name" aria-label="Name"></label>
<button id="submit" onclick="document.querySelector('#result').textContent=document.querySelector('#name').value">Save name</button>
<p id="result"></p><input id="upload" type="file" aria-label="Upload file">
<a id="download" href="download.txt" download="download.txt">Download</a>''')
(SITE / 'download.txt').write_text('download fixture')
(ROOT / 'upload.txt').write_text('upload fixture')

class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(SITE)))
threading.Thread(target=server.serve_forever, daemon=True).start()
env = os.environ.copy()
env.update({'UV_TOOL_BIN_DIR': str(BIN), 'PATH': str(BIN) + os.pathsep + env.get('PATH', ''),
            'UV_CACHE_DIR': str(ROOT / 'cache'), 'BH_HOME': str(ROOT / 'smoke-state'),
            'BH_AGENT_WORKSPACE': str(ROOT / 'workspace'), 'BH_TELEMETRY': '0',
            'BH_UPDATE_CHECK': '0', 'BH_RECORD': '0', 'BH_TAB_MARKER': '0'})
for key in ('BU_NAME', 'BU_CDP_WS', 'BU_CDP_URL', 'BU_AUTOSPAWN', 'BH_REQUIRE_EXISTING_DAEMON',
            'BH_CONFIG_DIR', 'BH_RUNTIME_DIR', 'BH_TMP_DIR', 'BROWSER_USE_API_KEY'):
    env.pop(key, None)
workspace = ROOT / 'workspace'
workspace.mkdir(exist_ok=True)
(workspace / 'agent_helpers.py').write_text('def fixture_custom_helper():\n    return "custom helper loaded"\n')
profile = ROOT / 'chrome-profile'
chrome = subprocess.Popen([str(CHROME),
                           '--headless=new', '--remote-debugging-port=0', '--no-first-run',
                           '--no-default-browser-check', '--disable-background-networking',
                           '--user-data-dir=' + str(profile), 'about:blank'],
                          stdout=subprocess.DEVNULL, stderr=open(ROOT / 'chrome.log', 'w'))
wrapper = str(Path(__file__).resolve().parents[1] / 'scripts/browser_harness.sh')

def call(*args, code=None):
    result = subprocess.run(['bash', wrapper, *args], env=env, input=code,
                            text=True, capture_output=True, timeout=45)
    if result.returncode:
        raise RuntimeError(result.stdout + '\n' + result.stderr)
    print(result.stdout, end='')
    return result.stdout

try:
    for _ in range(100):
        active = profile / 'DevToolsActivePort'
        if active.exists():
            break
        if chrome.poll() is not None:
            raise RuntimeError('Isolated Chrome exited; see chrome.log')
        time.sleep(.1)
    port = int(active.read_text().splitlines()[0])
    env['BU_CDP_URL'] = f'http://127.0.0.1:{port}'
    call('register', '--skill-dir', str(ROOT / 'registered/browser-harness'))
    original = (ROOT / 'registered/browser-harness/references/upstream-skill.md').read_text()
    entry = (ROOT / 'registered/browser-harness/SKILL.md').read_text()
    assert entry.endswith(original.split('\n---\n', 1)[1])
    call('connect')
    url = f'http://127.0.0.1:{server.server_port}/index.html'
    download_dir = ROOT / 'downloads'
    download_dir.mkdir(exist_ok=True)
    code = f'''
import json
new_tab({url!r})
wait_for_load()
assert fixture_custom_helper() == "custom helper loaded"
fill_input("#name", "Frevana test")
nodes = cdp("Accessibility.getFullAXTree")["nodes"]
button = next(n for n in nodes if n.get("role", {{}}).get("value") == "button" and n.get("name", {{}}).get("value") == "Save name")
q = cdp("DOM.getBoxModel", backendNodeId=button["backendDOMNodeId"])["model"]["content"]
click_at_xy(sum(q[0::2])/4, sum(q[1::2])/4)
assert js("document.querySelector('#result').textContent") == "Frevana test"
upload_file("#upload", {str(ROOT / 'upload.txt')!r})
assert js("document.querySelector('#upload').files[0].name") == "upload.txt"
image = capture_screenshot(path={str(ROOT / 'screenshot.png')!r})
assert image
cdp("Browser.setDownloadBehavior", behavior="allow", downloadPath={str(download_dir)!r})
js("document.querySelector('#download').click()")
print(json.dumps({{"filled": True, "AX_click": True, "upload": True, "screenshot": image, "custom_helper": True}}))
'''
    call('run', code=code)
    call('run', code='assert js("document.querySelector(\'#result\').textContent") == "Frevana test"\nprint("Cross-process tab persistence passed")\n')
    for _ in range(50):
        if (download_dir / 'download.txt').exists():
            break
        time.sleep(.1)
    assert (download_dir / 'download.txt').read_text() == 'download fixture'
    call('recordings', '--choice', 'no')
    call('cli', '--', 'doctor', '--json', '--require-existing-daemon')
    print('REAL_CLI_BROWSER_SMOKE_PASSED', flush=True)
finally:
    subprocess.run(['bash', wrapper, 'cli', '--', '--reload'], env=env,
                   text=True, capture_output=True, timeout=15)
    chrome.terminate()
    try:
        chrome.wait(timeout=10)
    except subprocess.TimeoutExpired:
        chrome.kill()
        chrome.wait()
    server.shutdown()
