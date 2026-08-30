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
* An ESPHome device (ESP8285/ESP32) on the same local network. A Harmony
  Hub is only needed for the bulk-export mode — Learning Mode works
  without one.
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

## Useful links

- [Astrion Custom Dashboard (Android app / APK)](https://github.com/dckiller51/astrion-custom-dashboard)
- [HA Astrion Custom Dashboard (Custom component Home Assistant)](https://github.com/dckiller51/ha-astrion-custom-dashboard)

## ☕ Support

If you find **Astrion Custom Dashboard** useful and want to support its development, you can buy me a coffee!

[![Ko-fi](https://img.shields.io/badge/Buy_me_a_coffee-Ko--fi-F16061?style=for-the-badge&logo=ko-fi&logoColor=white)](https://ko-fi.com/dckiller)
