# EvoCall Assistant

A local conversation assistant for Windows. It offers a short reply, an alternative question, and a cautious listening cue. The current interface and suggestions are in Italian.

**Open source · Apache-2.0 · Prototype 0.1.0**

EvoCall combines a Python/Tkinter interface, an offline demonstration mode, and an optional connection to a model running in LM Studio on the same computer. Optional Windows audio capture feeds local Whisper transcription. This is an early source prototype; real audio devices, model performance, and the complete Windows interface still need hardware testing.

## Try the demonstration

1. Install 64-bit **Python 3.12**, including Tcl/Tk and Python Launcher, from [python.org](https://www.python.org/downloads/windows/).
2. Download this repository as a ZIP and extract it, or clone it.
3. Open `AVVIA.bat` and select **Prova un esempio**.

The demo uses clearly labeled fixed rules. It requires no model, microphone, cloud account, or extra Python packages. You can also run `python run.py` with a Python installation that includes Tkinter. The supplied Windows launchers specifically select Python 3.12.

## Use a local model

1. Load a chat/instruction model in LM Studio and start its local server.
2. In **Impostazioni → Rileva modelli**, select the loaded model. The default address is `http://127.0.0.1:1234/v1`.
3. Choose **LM Studio locale** in **Conversazione** and try a manually entered turn before enabling audio.

The model must support structured JSON output. A local LM Studio token can be entered when its server requires authentication. EvoCall accepts loopback HTTP endpoints, disables proxies, and refuses redirects. It does not connect conversation requests to a cloud API.

## Optional Windows audio

Run `INSTALLA_AUDIO.bat`, then `PREPARA_VOCE.bat`, and restart the app. These preparation steps download Python dependencies and the Whisper base model. Model files are not included in this repository.

Use headphones, choose the call's output device and your microphone, and obtain the other participant's agreement before starting transcription. WASAPI loopback captures all sound from the selected output, including other applications and notifications. The **Tu / Altra persona** labels come from the two selected audio channels. The panel can appear in screen sharing.

## Data handling

The app keeps the most recent 16 conversation turns in memory. It does not write audio recordings, transcripts, conversation logs, or personal configuration files. Text is sent only to the selected server on the same computer. LM Studio and other external software may keep their own logs.

**STOP audio** discards new results and retains turns already displayed. **Nuova conversazione** clears the app's conversation, explicit facts, and custom goal. This does not erase third-party logs or guarantee forensic removal from memory or the Windows page file.

## Source map

| File | Purpose |
| --- | --- |
| `evo_call/app.py` | Tkinter interface and session lifecycle |
| `evo_call/core.py` | Bounded conversation state, demo rules, local model client |
| `evo_call/audio.py` | Optional WASAPI capture and local transcription |
| `prepara_voce.py` | Explicit model download and preparation |
| `tests/` | HTTP contract, conversation state, and lifecycle tests |

Full Italian operating instructions are in [LEGGIMI.txt](LEGGIMI.txt).

## Development and verification

```sh
python -m unittest discover -s tests -v
```

The tests use a fake HTTP server bound to loopback and simulated audio devices. They do not call LM Studio, acquire microphone audio, or download models. The silent-input test needs NumPy and skips when it is unavailable. See [VERIFICHE.txt](VERIFICHE.txt) for the latest verification results and the remaining hardware checks.

Direct optional audio dependencies are pinned in `requirements-audio.txt`; transitive dependencies are not fully locked. There is no standalone executable or guaranteed real-time latency.

## Contribute

Contributions are welcome. Good first areas include Windows device testing, clearer accessibility and keyboard navigation, documentation, and reproducible latency measurements. Read [CONTRIBUTING.md](CONTRIBUTING.md), use synthetic examples, and keep changes focused. Please avoid sharing recordings, transcripts, credentials, or personal device identifiers in issues.

## License

Copyright 2026 Atlas DevLab contributors. EvoCall's source and documentation in this repository are licensed under the [Apache License 2.0](LICENSE). See [NOTICE](NOTICE) for attribution. External dependencies, models, and LM Studio retain their own licenses and are not bundled here.
