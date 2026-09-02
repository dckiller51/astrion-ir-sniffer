# 📡 Astrion IR Sniffer User Guide

[![Ko-fi](https://img.shields.io/badge/Ko--fi-Buy_me_a_coffee-F16061?style=flat-square&logo=ko-fi&logoColor=white)](https://ko-fi.com/dckiller)

Astrion IR Sniffer captures Infrared (IR) codes using an ESPHome receiver
(ESP8285 or ESP32) and exports them as Pronto Hex, ready to drop into
Astrion's `ir-database/`. Two capture modes:

* **Harmony bulk export** — if your Logitech Harmony Hub already knows the
  device, this tool drives it through every command in turn and sniffs
  each IR transmission automatically.
* **Learning Mode** — for anything Harmony doesn't know about (its
  database is no longer maintained, so most recent devices are missing).
  Point the device's real remote at the ESP32 receiver yourself and
  capture button by button, no hub involved.

## 📋 Prerequisites

* Docker Desktop installed and running.
* An ESPHome device (ESP8285/ESP32) on the same local network (ESP8285 hardware also successfully tested once flashed with ESPHome `Tasmota MQTT IR remote ESP8285`). A Harmony Hub is only needed for the bulk-export mode — Learning Mode works without one.
* The local IP addresses of the devices you're using.
* This project's ESPHome config, `esphome/astrion-ir-sniffer.yaml`,
  flashed onto your ESP device AND present at that same path inside the
  project folder (Docker mounts the project folder as a volume, and
  `app.py` needs to find the file there to tail its logs).

## 🛠️ ESPHome Setup

1. Flash your ESP device with `esphome/astrion-ir-sniffer.yaml`.

2. Keep that file in `esphome/astrion-ir-sniffer.yaml` inside the project
   folder — Docker mounts the whole project folder as a volume, so the
   flashed config and the copy `app.py` reads logs from are the same file
   as long as the path matches.

   Renamed or moved it? No code to edit anymore — the app takes the path
   from the **"ESPHome config path"** field in step 1 of the web UI (it
   defaults to `esphome/astrion-ir-sniffer.yaml`, and you can also set it
   once via the `ASTRION_YAML_PATH` environment variable instead of
   typing it every time).

## 🛠️ ESPHome Configuration

`esphome/astrion-ir-sniffer.yaml` configures a `remote_receiver` restricted
to Pronto (`dump: pronto`) — Astrion only ever needs Pronto Hex, so nothing
else is decoded or logged — plus a `remote_transmitter` exposing one
`send_pronto` native-API service, used by Learning Mode's "Test / replay"
button to confirm a just-captured code actually works before you save it.

See the full file for the wifi/OTA/status boilerplate; the receiver/
transmitter section is what matters:

```yaml
remote_transmitter:
  pin:
    number: GPIO4
  carrier_duty_percent: 50%

remote_receiver:
  pin:
    number: GPIO5
    inverted: true
  dump: pronto
  on_pronto:
    then:
      - homeassistant.event:
          event: esphome.ir_pronto_code_received
          data:
            code: !lambda 'return x.data;'
```

## 🚀 Step 1: Launch the Application

Clone or download this repository to your local machine.

Open a terminal in the project directory.

Build the Docker image:

```Bash
docker build -t astrion-ir-sniffer .
```

Run the container:

```Bash
docker run --rm -it -p 5000:5000 -v ${PWD}:/app astrion-ir-sniffer
```

## 🌐 Step 2: Capture

Open your browser and navigate to <http://localhost:5000>.

**Connection & Setup** — enter your ESPHome device IP and confirm the
ESPHome config path (defaults to `esphome/astrion-ir-sniffer.yaml`).

**Option A — Harmony bulk export:**

* Also enter your Harmony Hub IP, click "Scan Hub Devices".
* Select the devices you want, click "Start Automatic Capture".
* The tool sequentially triggers each command on the Harmony Hub while the
  ESPHome receiver captures the emitted IR signals in real time. Track
  progress via the live progress bar.

**Option B — Learning Mode:**

* Click "Connect" in the Learning Mode card (no Harmony IP needed).
* Fill in category/brand/model, give the first command a key (e.g.
  `power`) and label, click "Capture next button press", then press that
  button on the device's real remote within 8 seconds.
* Optionally hit "Test / replay" to fire the captured code back at the
  device and confirm it reacts, then "Add command". Repeat per button.
* "Send this device to the editor below" hands the whole device over to
  the same editor/export flow the Harmony mode uses.

## 💾 Step 3: Edit & Export

Whichever mode you used, the result lands in the visual form/JSON editor
(section 4). Edit category/brand/model/commands if needed, then either
"Save JSON Locally" (downloads one file per category, matching Astrion's
`ir-database/<category>.json` shape) or "Submit to Astrion (GitHub)" to
open a pre-filled comment on the project's pinned IR-database issue.

## 🌐 Step 4: Online Database Selector (Web UI)

If you just want to select and download existing infrared device databases without running the full Docker capture tool, you can use the official online selector:

👉 **[Astrion IR Database Selector (Online)](https://dckiller51.github.io/astrion-ir-sniffer/)**

* **Browse & Filter:** Easily search through available brands and models across different categories.
* **Generate Files:** Check the devices you own and click **"Generate files"** to download the corresponding JSON files ready to copy into `/sdcard/astrion/ir-database/` on your remote.
* **⚠️ Direct Send Limitation on GitHub Pages:** Because the online web UI is hosted on GitHub Pages (`HTTPS`) and your remote operates on your local network (`HTTP`), modern browsers block direct requests (Mixed Content restriction). Therefore, the **"Send to my remote..."** button is automatically disabled on the online version.

### Running the Selector Locally (to enable direct send)

Since the standalone selector is located in the `docs/` folder, you can run it locally on your machine to bypass HTTPS restrictions and use the direct send feature:

1. Open a terminal and navigate into the `docs` directory:

   ```bash
   cd docs
   ```

2. Run a simple local HTTP server (requires [Node.js](https://nodejs.org/)):

   ```bash
   npx http-server . -p 8080
   ```

3. Open your browser and navigate to <http://localhost:8080>. Since it runs over HTTP, the browser will allow direct communication with your remote's local IP server, enabling the "Send to my remote..." button

## Useful links

* [Astrion IR Database Selector (Web UI)](https://dckiller51.github.io/astrion-ir-sniffer/)
* [Astrion Custom Dashboard (Android app / APK)](https://github.com/dckiller51/astrion-custom-dashboard)
* [HA Astrion Custom Dashboard (Custom component Home Assistant)](https://github.com/dckiller51/ha-astrion-custom-dashboard)

## ☕ Support

If you find **Astrion Custom Dashboard** useful and want to support its development, you can buy me a coffee!

[![Ko-fi](https://img.shields.io/badge/Buy_me_a_coffee-Ko--fi-F16061?style=for-the-badge&logo=ko-fi&logoColor=white)](https://ko-fi.com/dckiller)
