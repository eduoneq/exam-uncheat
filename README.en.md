# exam-uncheat — open, hardware-agnostic RF sensor hub for exam integrity

**Plug in any receive-only RF hardware; get one dashboard, one tamper-evident evidence log and one incident report.**
It is a *decision-support* tool for human proctors. It never decides that someone cheated.

> ⚠️ v0.1 is validated with a simulator and replayed event streams only — **not yet field-tested or hardware-tested**.
> It is **receive-only**: no transmitting, jamming, connecting, injecting or decrypting. CI rejects such code.

## Why
After a wave of AI smart-glasses cheating cases in Korean exams in 2026, the Ministry of Education said it will
*consider* RF detectors for next year's CSAT. Reported catches so far were made by proctors' eyes, and metal/RF detectors
reportedly failed in a mock drill. So rather than "one more scanner", exam-uncheat publishes a **vendor-neutral structure**:

- **Adapter spec** (`exam-uncheat.event/v1`, serial NDJSON / WebSocket / HTTP / MQTT) — ESP32, Linux monitor-mode Wi-Fi,
  BLE sniffers, SDRs, commercial detectors with serial output, or manual proctor entries.
- **Sees what phone apps can't** (hardware-dependent): Wi-Fi probe requests, associated stations, Wi-Fi Direct groups,
  5 GHz, continuous BLE advertising.
- **Open signature DB** sourced from Bluetooth SIG assigned numbers and public literature.
- **Baseline-vs-exam diffing** → *clues* (info / check / urgent) → proctor decision → report.
- **Hash-chained ledger** + `exam-uncheat verify`.
- **Privacy by default**: addresses pseudonymised with a per-session HMAC key that is destroyed at close; SSIDs/names
  masked; no cloud; 30-day auto-deletion.

## Quick start (no hardware)
```bash
pip install -e ".[dev]"
exam-uncheat demo --scenario all --decide && exam-uncheat verify data/sessions/*
exam-uncheat hub                                   # console at http://127.0.0.1:8765
exam-uncheat replay scenarios/all.jsonl --speed 20 # after "start session" in the console
```
Real sensors: `exam-uncheat hub --serial /dev/ttyACM0:115200` (see `firmware/esp32-sniffer`).

Docs (Korean): [ARCHITECTURE](docs/ARCHITECTURE.md) · [ADAPTER_SPEC](docs/ADAPTER_SPEC.md) · [HARDWARE](docs/HARDWARE.md) ·
[LEGAL](docs/LEGAL.md) · [LIMITATIONS](docs/LIMITATIONS.md)

License: code Apache-2.0; signatures & docs CC BY 4.0. Maintained by **EDUONEQ**.
