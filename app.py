import asyncio
import json
import os
import queue
import re
import subprocess
import threading
import time

from aioesphomeapi import APIClient
from aioharmony.harmonyapi import HarmonyAPI
from flask import Flask, jsonify, render_template, request, send_file

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Shared Pronto-only capture parsing
#
# Both capture modes (bulk export driven by the Harmony hub, and Learning
# Mode driven by a real remote) end up reading the same kind of ESPHome log
# line, now that harmony-2-esphome.yaml's `remote_receiver.dump` is
# restricted to `pronto` (see that file). This is the one place that turns
# raw log text into a clean {pronto, pronto_repeat} pair — nothing upstream
# or downstream needs to know about any other IR protocol.
# ---------------------------------------------------------------------------

PRONTO_TOKEN_RE = re.compile(r"\b[0-9A-Fa-f]{4}\b")

# Path to the ESPHome config, relative to the working directory app.py runs
# from. Was hardcoded as "harmony-2-esphome.yaml" at the repo root; now
# configurable (env var default, overridable per-request from the UI) so
# renaming the file or moving it into a folder — e.g. "esphome/astrion-ir-sniffer.yaml" —
# doesn't require touching this file again.
DEFAULT_YAML_PATH = os.environ.get("ASTRION_YAML_PATH", "esphome/astrion-ir-sniffer.yaml")


def parse_pronto_capture(raw_log):
    """Extracts {pronto, pronto_repeat} from raw ESPHome log text.

    Mirrors the heuristic already used client-side in templates/index.html's
    cleanEsphomePronto(): a Pronto dump can contain a "once" burst and a
    "repeat" burst back to back, each starting with a 0000 type code. We
    split on those boundaries and keep the longest sequence as `pronto`
    (the burst you actually want to replay) and the other as
    `pronto_repeat`, kept even when the sequence order from the log put the
    repeat burst first (which happens for some devices, e.g. a few Sony
    buttons that log only a repeat).
    """
    if not raw_log:
        return "", ""

    tokens = PRONTO_TOKEN_RE.findall(raw_log)
    if not tokens:
        return "", ""

    sequences = []
    current_seq = []
    for token in tokens:
        if token == "0000" and current_seq:
            sequences.append(" ".join(current_seq))
            current_seq = []
        current_seq.append(token)
    if current_seq:
        sequences.append(" ".join(current_seq))

    if not sequences:
        return "", ""
    if len(sequences[0]) > 20:
        main = sequences[0]
        repeat = sequences[1] if len(sequences) > 1 else ""
    elif len(sequences) > 1:
        main = sequences[1]
        repeat = sequences[0]
    else:
        main = sequences[0]
        repeat = ""
    return main, repeat


class EsphomeLogListener:
    """Tails `esphome logs` for one device and hands lines to callers via a
    thread-safe queue. Used by both capture modes so there's exactly one
    place that knows how to talk to the `esphome logs` CLI.
    """

    def __init__(self, esp_ip, yaml_file=None):
        self.esp_ip = esp_ip
        self.yaml_file = yaml_file or DEFAULT_YAML_PATH
        self.proc = None
        self.queue = queue.Queue()
        self._reader_thread = None

    def start(self):
        if self.proc is not None:
            return
        self.proc = subprocess.Popen(
            ["esphome", "logs", self.yaml_file, "--device", self.esp_ip],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        def _reader():
            for line in self.proc.stdout:
                self.queue.put(line.rstrip("\n"))

        self._reader_thread = threading.Thread(target=_reader, daemon=True)
        self._reader_thread.start()

    def drain(self):
        """Discards whatever's already queued, so the next capture window
        only sees fresh IR activity."""
        while not self.queue.empty():
            self.queue.get_nowait()

    def collect_pronto_for(self, seconds):
        """Blocks up to `seconds`, returns the raw text of every relevant
        log line seen in that window (possibly empty)."""
        deadline = time.time() + seconds
        lines = []
        while time.time() < deadline:
            remaining = deadline - time.time()
            try:
                line = self.queue.get(timeout=max(0, remaining))
            except queue.Empty:
                break
            if "pronto" in line.lower() or "Received" in line:
                lines.append(line)
        return " ".join(lines)

    def stop(self):
        if self.proc is not None:
            self.proc.terminate()
            self.proc = None


# ---------------------------------------------------------------------------
# Bulk capture (existing flow): Harmony hub fires every command in turn,
# ESPHome's receiver sniffs each one.
# ---------------------------------------------------------------------------

capture_status = {
    "running": False,
    "progress": 0,
    "total": 0,
    "current_command": "",
    "logs": [],
}

PROGRESS_FILE = "export_telecommandes_partial.json"
FINAL_FILE = "export_telecommandes.json"


def send_harmony_cmd(harmony_ip, device_id, command_name, retries=3):
    """Sends a command to Harmony Hub with auto-retry logic on failure."""
    for attempt in range(retries):
        try:
            res = subprocess.run(
                [
                    "python",
                    "-m",
                    "aioharmony",
                    "--harmony_ip",
                    harmony_ip,
                    "send_command",
                    "--device_id",
                    str(device_id),
                    "--command",
                    command_name,
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if res.returncode == 0:
                return True
        except subprocess.TimeoutExpired:
            pass
        time.sleep(2)
    return False


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/fetch-devices", methods=["POST"])
def fetch_devices():
    data = request.json
    harmony_ip = data.get("harmony_ip")

    async def _get_config():
        client = HarmonyAPI(ip_address=harmony_ip)
        if await client.connect():
            config = client.config
            await client.close()
            return config
        return None

    try:
        config = asyncio.run(_get_config())

        if config:
            with open("harmony_config.json", "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        else:
            with open("harmony_config.json", "r", encoding="utf-8") as f:
                config = json.load(f)

        devices = []
        for dev in config.get("device", []):
            devices.append(
                {
                    "id": dev.get("id"),
                    "label": dev.get("label"),
                    "manufacturer": dev.get("manufacturer"),
                    "model": dev.get("model"),
                    "commands_count": sum(
                        len(g.get("function", []))
                        for g in dev.get("controlGroup", [])
                    ),
                }
            )

        return jsonify({"devices": devices})

    except Exception as e:
        return jsonify({"error": f"Error fetching devices: {str(e)}"}), 500


@app.route("/api/start-capture", methods=["POST"])
def start_capture():
    global capture_status
    if capture_status["running"]:
        return jsonify({"error": "A capture process is already running"}), 400

    data = request.json
    harmony_ip = data.get("harmony_ip")
    esp_ip = data.get("esp_ip")
    yaml_path = data.get("yaml_path")
    selected_device_ids = data.get("device_ids", [])

    with open("harmony_config.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    targets = []
    for dev in config.get("device", []):
        if str(dev.get("id")) in selected_device_ids:
            for group in dev.get("controlGroup", []):
                for cmd in group.get("function", []):
                    targets.append(
                        {
                            "device_id": dev.get("id"),
                            "device_label": dev.get("label"),
                            "manufacturer": dev.get("manufacturer", ""),
                            "model": dev.get("model", ""),
                            "cmd_name": cmd.get("name"),
                            "cmd_label": cmd.get("label"),
                        }
                    )

    capture_status = {
        "running": True,
        "progress": 0,
        "total": len(targets),
        "current_command": "Starting...",
        "logs": [],
    }

    threading.Thread(
        target=run_capture_process,
        args=(harmony_ip, esp_ip, targets, yaml_path),
        daemon=True,
    ).start()

    return jsonify({"status": "started", "total": len(targets)})


def run_capture_process(harmony_ip, esp_ip, targets, yaml_path=None):
    global capture_status
    results = {}

    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                saved_data = json.load(f)
                for item in saved_data:
                    dev_key = f"{item['brand']}_{item['model']}".replace(" ", "_")
                    results[dev_key] = item
        except Exception:
            results = {}

    listener = EsphomeLogListener(esp_ip, yaml_path)
    listener.start()
    time.sleep(5)

    for i, target in enumerate(targets):
        capture_status["progress"] = i + 1
        capture_status["current_command"] = (
            f"{target['device_label']} - {target['cmd_label']}"
        )

        dev_key = f"{target['manufacturer']}_{target['model']}".replace(" ", "_")

        if dev_key in results and target["cmd_name"] in results[dev_key].get("commands", {}):
            if results[dev_key]["commands"][target["cmd_name"]].get("pronto"):
                continue

        listener.drain()
        send_harmony_cmd(harmony_ip, target["device_id"], target["cmd_name"])
        raw_text = listener.collect_pronto_for(2.5)

        pronto, pronto_repeat = parse_pronto_capture(raw_text)

        if dev_key not in results:
            results[dev_key] = {
                "category": target["device_label"],
                "brand": target["manufacturer"],
                "model": target["model"],
                "commands": {},
            }

        results[dev_key]["commands"][target["cmd_name"]] = {
            "label": target["cmd_label"],
            "pronto": pronto,
            "pronto_repeat": pronto_repeat,
            "meta": {"source": "ESPHome remote receiver capture (Harmony hub)"},
        }

        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(list(results.values()), f, indent=2, ensure_ascii=False)

    listener.stop()

    with open(FINAL_FILE, "w", encoding="utf-8") as f:
        json.dump(list(results.values()), f, indent=2, ensure_ascii=False)

    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)

    capture_status["running"] = False
    capture_status["current_command"] = "Completed successfully!"


@app.route("/api/status")
def status():
    return jsonify(capture_status)


@app.route("/api/get-latest-export", methods=["GET"])
def get_latest_export():
    file_path = FINAL_FILE if os.path.exists(FINAL_FILE) else PROGRESS_FILE
    if os.path.exists(file_path):
        return send_file(file_path, mimetype="application/json")
    return jsonify({"error": "Export file not found"}), 404


# ---------------------------------------------------------------------------
# Learning Mode: no Harmony hub involved. You point the *real* remote at the
# ESP32 receiver and press a button yourself — needed for anything not in
# Harmony's (unmaintained, increasingly outdated) device database, which is
# every recent TV/soundbar/etc. Astrion doesn't know about yet.
# ---------------------------------------------------------------------------

_learn_listener = None  # type: EsphomeLogListener | None


@app.route("/api/learn/connect", methods=["POST"])
def learn_connect():
    global _learn_listener
    data = request.json or {}
    esp_ip = data.get("esp_ip")
    yaml_path = data.get("yaml_path")
    if not esp_ip:
        return jsonify({"error": "esp_ip is required"}), 400

    if _learn_listener is not None and (
        _learn_listener.esp_ip != esp_ip
        or _learn_listener.yaml_file != (yaml_path or DEFAULT_YAML_PATH)
    ):
        _learn_listener.stop()
        _learn_listener = None

    if _learn_listener is None:
        _learn_listener = EsphomeLogListener(esp_ip, yaml_path)
        _learn_listener.start()
        time.sleep(3)  # let `esphome logs` finish attaching before we listen

    return jsonify({"status": "connected", "esp_ip": esp_ip, "yaml_path": _learn_listener.yaml_file})


@app.route("/api/learn/capture", methods=["POST"])
def learn_capture():
    """Arms the receiver, waits for the next button press (up to
    `timeout_s`, default 8s), and returns whatever Pronto code it saw. Does
    NOT save anything — the caller reviews/renames/retries via the existing
    visual form editor before committing it with /api/learn/commit."""
    if _learn_listener is None:
        return jsonify({"error": "Not connected — call /api/learn/connect first"}), 400

    data = request.json or {}
    timeout_s = float(data.get("timeout_s", 8))

    _learn_listener.drain()
    raw_text = _learn_listener.collect_pronto_for(timeout_s)
    pronto, pronto_repeat = parse_pronto_capture(raw_text)

    if not pronto:
        return jsonify({"error": "No IR signal detected in time — point the remote at the receiver and try again"}), 408

    return jsonify({"pronto": pronto, "pronto_repeat": pronto_repeat})


@app.route("/api/learn/test", methods=["POST"])
def learn_test():
    """Replays a captured Pronto code through the ESP32's own transmitter
    (harmony-2-esphome.yaml's `send_pronto` service), so you can point it at
    the device you just learned from and confirm it actually reacts before
    saving the command."""
    data = request.json or {}
    esp_ip = data.get("esp_ip")
    pronto = data.get("pronto")
    if not esp_ip or not pronto:
        return jsonify({"error": "esp_ip and pronto are required"}), 400

    async def _send():
        client = APIClient(esp_ip, 6053, None)
        await client.connect(login=True)
        try:
            services = (await client.list_entities_services())[1]
            svc = next((s for s in services if s.name == "send_pronto"), None)
            if svc is None:
                raise RuntimeError("Device has no 'send_pronto' service — flash the updated harmony-2-esphome.yaml")
            client.execute_service(svc, {"code": pronto})
        finally:
            await client.disconnect()

    try:
        asyncio.run(_send())
        return jsonify({"status": "sent"})
    except Exception as e:
        return jsonify({"error": f"Couldn't reach ESPHome device: {str(e)}"}), 500


@app.route("/api/learn/disconnect", methods=["POST"])
def learn_disconnect():
    global _learn_listener
    if _learn_listener is not None:
        _learn_listener.stop()
        _learn_listener = None
    return jsonify({"status": "disconnected"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)