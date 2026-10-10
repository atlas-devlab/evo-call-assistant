"""Optional Windows capture. No audio or transcript files are written.

One capture thread per channel, bounded queue, one serial STT worker.
Energy segmentation is a prototype heuristic, not speaker diarization or turn detection.
"""

from collections import deque
from dataclasses import dataclass
from math import gcd
from pathlib import Path
import queue
import sys
import threading
import time


def dependencies():
    if sys.platform != "win32":
        raise RuntimeError("L'audio live di questo prototipo richiede Windows.")
    try:
        import pyaudiowpatch as pa
        import numpy as np
        from faster_whisper import WhisperModel
        from scipy.signal import resample_poly
    except ImportError:
        raise RuntimeError("Esegui prima INSTALLA_AUDIO.bat e PREPARA_VOCE.bat.") from None
    return pa, np, WhisperModel, resample_poly


def list_devices():
    pa, _, _, _ = dependencies()
    with pa.PyAudio() as p:
        host = p.get_host_api_info_by_type(pa.paWASAPI)["index"]
        devices = [p.get_device_info_by_index(i) for i in range(p.get_device_count())]
        return [d for d in devices if d["hostApi"] == host and d["maxInputChannels"] > 0]


@dataclass
class Chunk:
    speaker: str
    pcm: bytes
    rate: int
    channels: int
    at: float
    ended: float


class AudioSession:
    def __init__(self, emit, loopback, mic, model_dir, language="it", threshold=0.012):
        self.emit = emit
        self.loopback, self.mic = loopback, mic
        self.model_dir, self.language, self.threshold = model_dir, language, threshold
        self.stop_event = threading.Event()
        self.jobs = queue.Queue(maxsize=4)
        self.threads = []
        self.model = None
        self.loading = True
        self.transcribing = False
        self.fail_lock = threading.Lock()

    def start(self):
        thread = threading.Thread(target=self._run, daemon=True)
        self.threads = [thread]
        thread.start()

    def stop(self):
        self.stop_event.set()
        while True:
            try:
                self.jobs.get_nowait()
            except queue.Empty:
                break

    def finished(self):
        return not any(t.is_alive() for t in self.threads)

    def fail(self, message):
        with self.fail_lock:
            if not self.stop_event.is_set():
                self.emit("error", message)
                self.stop()

    def _run(self):
        try:
            pa, np, WhisperModel, resample_poly = dependencies()
            path = Path(self.model_dir)
            if not (path / "model.bin").is_file():
                raise RuntimeError("Modello voce assente. Chiudi e avvia PREPARA_VOCE.bat.")
            self.emit("status", "Caricamento del modello voce locale…")
            # Local path + local_files_only: a live session never downloads a model.
            self.model = WhisperModel(str(path), device="cpu", compute_type="int8",
                                      cpu_threads=4, num_workers=1, local_files_only=True)
            if self.stop_event.is_set():
                return
            for speaker, device in (("Altra persona", self.loopback), ("Tu", self.mic)):
                t = threading.Thread(target=self._capture, args=(speaker, device, pa, np), daemon=True)
                self.threads.append(t)
                t.start()
            self.loading = False
            while not self.stop_event.is_set():
                try:
                    chunk = self.jobs.get(timeout=0.15)
                except queue.Empty:
                    continue
                if time.monotonic() - chunk.ended > 20:
                    self.emit("status", "Trascrizione in ritardo: scartato un frammento vecchio.")
                    continue
                samples = np.frombuffer(chunk.pcm, dtype=np.int16).astype(np.float32) / 32768.0
                samples = samples.reshape(-1, chunk.channels).mean(axis=1)
                factor = gcd(chunk.rate, 16000)
                samples = resample_poly(samples, 16000 // factor, chunk.rate // factor).astype(np.float32)
                before = time.monotonic()
                self.transcribing = True
                segments, _ = self.model.transcribe(
                    samples, language=None if self.language == "auto" else self.language,
                    beam_size=1, vad_filter=True, condition_on_previous_text=False,
                    vad_parameters={"min_silence_duration_ms": 400},
                )
                text = " ".join(s.text.strip() for s in segments).strip()
                self.transcribing = False
                if self.stop_event.is_set():
                    break
                if text and time.monotonic() - chunk.ended <= 25:
                    self.emit("transcript", {"speaker": chunk.speaker, "text": text,
                                              "at": chunk.at, "stt_seconds": time.monotonic() - before})
                elif text:
                    self.emit("status", "Modello voce troppo lento: frammento scaduto.")
        except Exception as exc:
            self.fail(f"Audio: {type(exc).__name__}. {str(exc)[:220]}")
        finally:
            self.stop()
            self.model = None
            self.transcribing = False

    def _capture(self, speaker, device, pa, np):
        frames = []
        pre = deque(maxlen=3)
        speaking = False
        quiet = 0.0
        voiced = 0.0
        duration = 0.0
        started = 0.0
        try:
            with pa.PyAudio() as p:
                info = p.get_device_info_by_index(device)
                if bool(info.get("isLoopbackDevice")) != (speaker == "Altra persona"):
                    raise RuntimeError("Dispositivo cambiato: rileva di nuovo microfono e uscita.")
                rate, channels = int(info["defaultSampleRate"]), int(info["maxInputChannels"])
                size = max(128, int(rate * 0.04))
                with p.open(format=pa.paInt16, channels=channels, rate=rate, input=True,
                            input_device_index=device, frames_per_buffer=size) as stream:
                    self.emit("ready", speaker)
                    while not self.stop_event.is_set():
                        raw = stream.read(size, exception_on_overflow=False)
                        now = time.monotonic()
                        mono = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                        level = float(np.sqrt(np.mean(mono * mono)))
                        active = level >= self.threshold
                        step = size / rate
                        pre.append(raw)
                        if active and not speaking:
                            speaking = True
                            frames = list(pre)
                            started = now - len(pre) * step
                            duration = len(pre) * step
                            quiet = 0.0
                            voiced = step
                            self.emit("activity", {"speaker": speaker, "active": True})
                            continue
                        if not speaking:
                            continue
                        frames.append(raw)
                        duration += step
                        voiced += step if active else 0
                        quiet = 0 if active else quiet + step
                        if quiet >= 0.8 or duration >= 8:
                            if voiced >= 0.28:
                                chunk = Chunk(speaker, b"".join(frames), rate, channels, started, now)
                                try:
                                    self.jobs.put_nowait(chunk)
                                except queue.Full:
                                    try:
                                        self.jobs.get_nowait()
                                    except queue.Empty:
                                        pass
                                    try:
                                        self.jobs.put_nowait(chunk)
                                    except queue.Full:
                                        pass
                                    self.emit("status", "Voce in ritardo: alcuni frammenti vengono scartati.")
                            frames = []
                            pre.clear()
                            speaking = False
                            self.emit("activity", {"speaker": speaker, "active": False})
        except Exception as exc:
            self.fail(f"Dispositivo {speaker}: {str(exc)[:200]}")
        finally:
            self.emit("activity", {"speaker": speaker, "active": False})
