"""Native Tkinter UI; all widget operations stay on the main thread."""

from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from .core import Conversation, LocalModel, demo_suggestion, timing_hint

ROOT = Path(__file__).resolve().parents[1]
BG = "#F3F5F9"
INK = "#172A3A"
MUTED = "#526577"
TEAL = "#147D70"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("EvoCall · un pensiero alla volta")
        self.geometry(f"970x{max(620, min(850, self.winfo_screenheight() - 100))}")
        self.minsize(860, 620)
        self.configure(bg=BG)
        self.conversation = Conversation()
        self.events = queue.Queue()
        self.epoch = 0
        self.request_id = 0
        self.inflight = None
        self.shown_at = 0
        self.pending_auto = False
        self.last_activity = 0
        self.active = {"Tu": False, "Altra persona": False}
        self.audio = None
        self.audio_epoch = 0
        self.audio_ready = set()
        self.devices = {}
        self.device_request_id = 0
        self.model_request_id = 0
        self.demo_index = 0
        self.closed = False
        self.mode = tk.StringVar(value="Demo")
        self.goal = tk.StringVar(value="Ascoltare con attenzione e rispondere con naturalezza.")
        self.endpoint = tk.StringVar(value="http://127.0.0.1:1234/v1")
        self.model_name = tk.StringVar()
        self.token = tk.StringVar()
        self.language = tk.StringVar(value="it")
        self.auto = tk.BooleanVar(value=False)
        self.topmost = tk.BooleanVar(value=False)
        self.consent = tk.BooleanVar(value=False)
        self.threshold = tk.DoubleVar(value=0.012)
        self.source = tk.StringVar(value="DEMO · nessun audio attivo")
        self.timing = tk.StringVar(value="Ascolta · servono alcune parole di contesto.")
        self.reply = tk.StringVar(value="Un pensiero alla volta.")
        self.question = tk.StringVar(value="Prova un esempio oppure aggiungi una battuta qui sotto.")
        self.status = tk.StringVar(value="Pronto · demo senza modelli e senza connessioni.")
        self.audio_status = tk.StringVar(value="Audio spento")
        self._build()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Control-Return>", lambda event: self.suggest())
        self.bind("<Escape>", lambda event: self.stop_audio())
        self.after(100, self._poll)

    def _build(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=INK, font=("Segoe UI", 11))
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 7))
        style.configure("Primary.TButton", background=TEAL, foreground="white")
        style.map("Primary.TButton", background=[("active", "#10665C")])
        style.configure("TCheckbutton", background=BG, font=("Segoe UI", 10))
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", font=("Segoe UI", 11), padding=(18, 8))
        self.option_add("*TCombobox*Listbox.font", ("Segoe UI", 11))
        header = ttk.Frame(self, padding=(22, 18, 22, 10))
        header.pack(fill="x")
        ttk.Label(header, text="EvoCall", font=("Segoe UI", 23, "bold")).pack(side="left")
        ttk.Label(header, text="Conversazioni personali  /  0.1", foreground=MUTED).pack(side="left", padx=16)
        ttk.Checkbutton(header, text="Sempre in primo piano", variable=self.topmost,
                        command=lambda: self.attributes("-topmost", self.topmost.get())).pack(side="right")
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=22, pady=4)
        call = self._scroll_tab("Conversazione")
        setup = self._scroll_tab("Impostazioni")
        guide = ttk.Frame(self.tabs, padding=16)
        self.tabs.add(guide, text="Primi passi")
        self._call_tab(call)
        self._setup_tab(setup)
        text = scrolledtext.ScrolledText(guide, wrap="word", font=("Segoe UI", 12),
                                         borderwidth=0, padx=18, pady=14)
        text.pack(fill="both", expand=True)
        text.insert("1.0", GUIDE)
        text.configure(state="disabled")
        footer = ttk.Frame(self, padding=(22, 8))
        footer.pack(fill="x")
        ttk.Button(footer, text="STOP audio", command=self.stop_audio).pack(side="right", padx=(10, 0))
        ttk.Label(footer, textvariable=self.status, foreground=MUTED, wraplength=700,
                  font=("Segoe UI", 10)).pack(side="left", fill="x", expand=True)

    def _scroll_tab(self, title):
        outer = ttk.Frame(self.tabs)
        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        bar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = ttk.Frame(canvas, padding=(8, 12))
        window = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
        self.tabs.add(outer, text=title)
        return inner

    def _call_tab(self, parent):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(0, 10))
        ttk.Label(row, text="Modalità").pack(side="left")
        self.mode_picker = ttk.Combobox(row, textvariable=self.mode, values=("Demo", "LM Studio locale"),
                                         state="readonly", width=19)
        self.mode_picker.pack(side="left", padx=10)
        self.mode_picker.bind("<<ComboboxSelected>>", self.change_mode)
        self.example_button = ttk.Button(row, text="Prova un esempio", command=self.example)
        self.example_button.pack(side="left")
        ttk.Button(row, text="Nuova conversazione", command=self.clear).pack(side="right")
        ttk.Label(parent, text="Obiettivo della chiamata", foreground=MUTED).pack(anchor="w")
        goal_entry = ttk.Entry(parent, textvariable=self.goal, font=("Segoe UI", 11))
        goal_entry.pack(fill="x", pady=(3, 12))
        goal_entry.bind("<KeyRelease>", lambda _: self.invalidate())
        card = tk.Frame(parent, bg="white", highlightbackground="#DBE3EA", highlightthickness=1)
        card.pack(fill="x", pady=(0, 10))
        tk.Label(card, textvariable=self.source, bg="white", fg=TEAL, font=("Segoe UI", 10, "bold"),
                 anchor="w").pack(fill="x", padx=20, pady=(15, 8))
        reply_label = tk.Label(card, textvariable=self.reply, bg="white", fg=INK, font=("Segoe UI", 18, "bold"),
                              justify="left", anchor="w", wraplength=740)
        reply_label.pack(fill="x", padx=20, pady=(0, 9))
        reply_label.bind("<Configure>", lambda event: reply_label.configure(wraplength=max(320, event.width - 8)))
        question_label = tk.Label(card, textvariable=self.question, bg="white", fg=MUTED, font=("Segoe UI", 12),
                                 justify="left", anchor="w", wraplength=740)
        question_label.pack(fill="x", padx=20, pady=(0, 14))
        question_label.bind("<Configure>", lambda event: question_label.configure(wraplength=max(320, event.width - 8)))
        ttk.Label(parent, textvariable=self.timing, foreground=TEAL, wraplength=820).pack(anchor="w")
        controls = ttk.Frame(parent)
        controls.pack(fill="x", pady=10)
        self.help_button = ttk.Button(controls, text="Aiutami ora   Ctrl+Invio", style="Primary.TButton", command=self.suggest)
        self.help_button.pack(side="left")
        ttk.Checkbutton(controls, text="Suggerimenti automatici", variable=self.auto).pack(side="left", padx=14)
        ttk.Label(parent, text="Ultime battute · solo in memoria", foreground=MUTED).pack(anchor="w")
        self.transcript = scrolledtext.ScrolledText(parent, height=5, wrap="word", font=("Segoe UI", 11),
                                                   bg="white", fg=INK, relief="flat", padx=12, pady=8,
                                                   state="disabled")
        self.transcript.pack(fill="both", expand=True, pady=(4, 8))
        entry_row = ttk.Frame(parent)
        entry_row.pack(fill="x")
        self.speaker = tk.StringVar(value="Altra persona")
        ttk.Combobox(entry_row, textvariable=self.speaker, values=("Altra persona", "Tu"),
                     state="readonly", width=15).pack(side="left")
        self.manual = ttk.Entry(entry_row, font=("Segoe UI", 11))
        self.manual.pack(side="left", fill="x", expand=True, padx=8)
        self.manual.bind("<Return>", lambda _: self.add_manual())
        ttk.Button(entry_row, text="Aggiungi", command=self.add_manual).pack(side="right")
        bottom = ttk.Frame(parent)
        bottom.pack(fill="x", pady=(12, 0))
        ttk.Label(bottom, textvariable=self.audio_status, foreground=TEAL).pack(side="left")
        ttk.Button(bottom, text="STOP audio   Esc", command=self.stop_audio).pack(side="right")

    def _setup_tab(self, parent):
        parent.columnconfigure(1, weight=1)
        def label(text, row):
            ttk.Label(parent, text=text).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=6)
        label("Server locale", 0)
        ttk.Entry(parent, textvariable=self.endpoint).grid(row=0, column=1, sticky="ew")
        label("Modello", 1)
        self.model_picker = ttk.Combobox(parent, textvariable=self.model_name)
        self.model_picker.grid(row=1, column=1, sticky="ew")
        self.model_button = ttk.Button(parent, text="Rileva modelli", command=self.load_models)
        self.model_button.grid(row=1, column=2, padx=8)
        label("Token LM Studio", 2)
        ttk.Entry(parent, textvariable=self.token, show="•").grid(row=2, column=1, sticky="ew")
        ttk.Label(parent, text="Solo se il server locale lo richiede.", foreground=MUTED,
                  font=("Segoe UI", 9)).grid(row=2, column=2, sticky="w")
        label("Fatti che può usare", 3)
        self.facts = tk.Text(parent, height=3, wrap="word", font=("Segoe UI", 11), relief="solid", bd=1)
        self.facts.grid(row=3, column=1, columnspan=2, sticky="ew", pady=6)
        self.facts.bind("<KeyRelease>", lambda _: self.invalidate())
        ttk.Separator(parent).grid(row=4, column=0, columnspan=3, sticky="ew", pady=15)
        ttk.Label(parent, text="Audio live · Windows", font=("Segoe UI", 14, "bold")).grid(row=5, column=0, columnspan=2, sticky="w")
        self.devices_button = ttk.Button(parent, text="Rileva dispositivi", command=self.load_devices)
        self.devices_button.grid(row=5, column=2, padx=8)
        label("Uscita della chiamata", 6)
        self.output_picker = ttk.Combobox(parent, state="readonly")
        self.output_picker.grid(row=6, column=1, columnspan=2, sticky="ew", pady=4)
        label("Il tuo microfono", 7)
        self.mic_picker = ttk.Combobox(parent, state="readonly")
        self.mic_picker.grid(row=7, column=1, columnspan=2, sticky="ew", pady=4)
        label("Lingua parlata", 8)
        ttk.Combobox(parent, textvariable=self.language, values=("it", "en", "auto"), state="readonly",
                     width=12).grid(row=8, column=1, sticky="w")
        label("Soglia rumore", 9)
        ttk.Scale(parent, from_=0.003, to=0.05, variable=self.threshold).grid(row=9, column=1, sticky="ew")
        ttk.Label(parent, text="Aumenta se scatta nel silenzio", font=("Segoe UI", 9), foreground=MUTED).grid(row=9, column=2)
        ttk.Label(parent, text="Usa le cuffie. Viene acquisito tutto l'audio dell'uscita selezionata, anche notifiche e altre app.",
                  foreground=MUTED, wraplength=780).grid(row=10, column=0, columnspan=3, sticky="w", pady=(12, 6))
        self.consent_check = ttk.Checkbutton(parent, text="Ho informato l'altra persona e ha accettato la trascrizione.",
                                             variable=self.consent)
        self.consent_check.grid(row=11, column=0, columnspan=3, sticky="w", pady=8)
        self.start_button = ttk.Button(parent, text="Avvia audio locale", style="Primary.TButton", command=self.start_audio)
        self.start_button.grid(row=12, column=0, sticky="w", pady=8)
        ttk.Button(parent, text="STOP audio", command=self.stop_audio).grid(row=12, column=1, sticky="w")
        ttk.Label(parent, text="L'app non invia avvisi ai partecipanti. Il pannello può apparire se condividi l'intero schermo.",
                  foreground=MUTED, wraplength=780, font=("Segoe UI", 10)).grid(row=13, column=0, columnspan=3, sticky="w", pady=12)

    def invalidate(self):
        self.request_id += 1
        self.shown_at = 0
        self.reply.set("Ascolta il prossimo pensiero.")
        self.question.set("Premi «Aiutami ora» quando vuoi un suggerimento.")
        self.source.set("DEMO · regole fisse" if self.mode.get() == "Demo" else "LOCALE · in attesa")

    def change_mode(self, _event=None):
        self.epoch += 1
        self.invalidate()
        self.pending_auto = False
        self.example_button.configure(state="normal" if self.mode.get() == "Demo" else "disabled")
        if self.mode.get() == "Demo":
            self.stop_audio()
        self.status.set("Demo: risposte di esempio." if self.mode.get() == "Demo" else "Suggerimenti dal modello scelto in LM Studio.")

    def add_turn(self, speaker, text, at=None):
        if self.conversation.add(speaker, text, at):
            self.invalidate()
            self.pending_auto = self.conversation.turns[-1].speaker == "Altra persona"
            self.last_activity = time.monotonic()
            self.render_transcript()

    def render_transcript(self):
        self.transcript.configure(state="normal")
        self.transcript.delete("1.0", "end")
        for t in self.conversation.turns:
            self.transcript.insert("end", f"{t.speaker}  ·  {t.text}\n\n")
        self.transcript.configure(state="disabled")
        self.transcript.see("end")

    def add_manual(self):
        text = self.manual.get()
        self.manual.delete(0, "end")
        self.add_turn(self.speaker.get(), text)

    def example(self):
        examples = ["Oggi è stata una giornata pesante, sono molto stanco.",
                    "Ti andrebbe di fare qualcosa nel fine settimana?",
                    "Non ho capito bene cosa intendi, mi fai un esempio?"]
        self.add_turn("Altra persona", examples[self.demo_index % len(examples)])
        self.demo_index += 1
        self.suggest()

    def clear(self):
        self.stop_audio()
        self.epoch += 1
        self.conversation.clear()
        self.render_transcript()
        self.manual.delete(0, "end")
        self.facts.delete("1.0", "end")
        self.goal.set("Ascoltare con attenzione e rispondere con naturalezza.")
        self.pending_auto = False
        self.invalidate()
        self.status.set("Nuova conversazione · rimossi testo, fatti e suggerimenti dall'app.")

    def _client(self):
        return LocalModel(self.endpoint.get(), self.model_name.get(), self.token.get())

    def suggest(self):
        if not self.conversation.turns:
            self.status.set("Aggiungi una battuta o usa «Prova un esempio».")
            return
        if self.inflight is not None:
            self.status.set("Il modello sta ancora rispondendo. Puoi continuare ad ascoltare.")
            return
        if any(self.active.values()):
            self.status.set("Audio in corso · il suggerimento arriverà dopo una pausa.")
            self.pending_auto = self.auto.get()
            return
        self.pending_auto = False
        self.request_id += 1
        key = (self.epoch, self.conversation.revision, self.request_id)
        turns = self.conversation.snapshot()
        if self.mode.get() == "Demo":
            self.show_suggestion(demo_suggestion(turns), 0)
            return
        try:
            client = self._client()
        except ValueError as exc:
            self.status.set(str(exc))
            return
        goal, facts = self.goal.get(), self.facts.get("1.0", "end").strip()
        self.inflight = key
        self.help_button.configure(state="disabled")
        self.status.set("Il modello locale prepara una proposta…")
        def worker():
            start = time.monotonic()
            try:
                result = client.suggest(turns, goal, facts)
                self.events.put(("suggestion", key, result, time.monotonic() - start))
            except Exception as exc:
                self.events.put(("suggestion_error", key, str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def show_suggestion(self, suggestion, duration):
        self.source.set(f"{suggestion.source}  /  {suggestion.cue}")
        self.reply.set(suggestion.reply)
        self.question.set("Oppure: " + suggestion.question if suggestion.question else "")
        self.shown_at = time.monotonic()
        self.status.set("Esempio dimostrativo, senza AI." if duration == 0 else f"Proposta generata in {duration:.1f} s · adattala a ciò che pensi davvero.")

    def load_models(self):
        try:
            client = self._client()
        except ValueError as exc:
            self.status.set(str(exc))
            return
        self.model_request_id += 1
        key = self.model_request_id
        self.model_button.configure(state="disabled")
        def worker():
            try:
                self.events.put(("models", key, client.models()))
            except Exception as exc:
                self.events.put(("models_error", key, str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def load_devices(self):
        if self.audio and not self.audio.finished():
            self.status.set("Ferma l'audio prima di cambiare dispositivi.")
            return
        self.device_request_id += 1
        key = self.device_request_id
        self.devices_button.configure(state="disabled")
        def worker():
            try:
                from .audio import list_devices
                self.events.put(("devices", key, list_devices()))
            except Exception as exc:
                self.events.put(("devices_error", key, str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def start_audio(self):
        if self.audio and not self.audio.finished():
            self.status.set("Audio già avviato o in arresto. Attendi prima di riavviare.")
            return
        if self.mode.get() != "LM Studio locale":
            self.status.set("Scegli «LM Studio locale» nella scheda Conversazione per usare l'audio.")
            return
        if not self.consent.get():
            messagebox.showinfo("Prima della chiamata", "Informa l'altra persona, ottieni il suo accordo e seleziona la casella.")
            return
        output, mic = self.devices.get(self.output_picker.get()), self.devices.get(self.mic_picker.get())
        if output is None or mic is None:
            self.status.set("Rileva i dispositivi e seleziona uscita della chiamata e microfono.")
            return
        if not (ROOT / "models" / "whisper-base" / "model.bin").is_file():
            self.status.set("Manca il modello voce. Esegui PREPARA_VOCE.bat prima dell'audio live.")
            return
        from .audio import AudioSession
        self.audio_epoch += 1
        sid = self.audio_epoch
        self.audio_ready.clear()
        self.active = {"Tu": False, "Altra persona": False}
        self.invalidate()
        self.audio = AudioSession(lambda kind, data: self.events.put(("audio", sid, kind, data)),
                                  output, mic, str(ROOT / "models" / "whisper-base"),
                                  self.language.get(), self.threshold.get())
        self.start_button.configure(state="disabled")
        self.consent_check.configure(state="disabled")
        self.audio_status.set("Preparazione audio…")
        self.audio.start()
        self.tabs.select(0)

    def stop_audio(self):
        was_active = self.audio is not None and not self.audio.finished()
        if self.audio:
            self.audio.stop()
        self.audio_epoch += 1
        self.epoch += 1
        self.active = {"Tu": False, "Altra persona": False}
        self.audio_ready.clear()
        self.pending_auto = False
        self.consent.set(False)
        self.consent_check.configure(state="normal")
        self.start_button.configure(state="normal")
        self.audio_status.set("Audio spento")
        self.invalidate()
        if was_active:
            self.status.set("Stop richiesto · nuovi risultati scartati. Le ultime battute restano fino a «Nuova conversazione».")

    def _poll(self):
        if self.closed:
            return
        for _ in range(80):
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            kind = event[0]
            if kind in ("suggestion", "suggestion_error"):
                key = event[1]
                if self.inflight == key:
                    self.inflight = None
                    self.help_button.configure(state="normal")
                if key != (self.epoch, self.conversation.revision, self.request_id):
                    continue
                if kind == "suggestion":
                    self.show_suggestion(event[2], event[3])
                else:
                    self.status.set(event[2])
            elif kind in ("models", "models_error"):
                if event[1] != self.model_request_id:
                    continue
                self.model_button.configure(state="normal")
                if kind == "models_error":
                    self.status.set(event[2])
                else:
                    self.model_picker["values"] = event[2]
                    if event[2]:
                        self.model_name.set(event[2][0])
                    self.status.set("Scegli il modello caricato in LM Studio." if event[2] else "Nessun modello disponibile nel server.")
            elif kind in ("devices", "devices_error"):
                if event[1] != self.device_request_id:
                    continue
                self.devices_button.configure(state="normal")
                if kind == "devices_error":
                    self.status.set(event[2])
                else:
                    self.devices = {f"{int(d['index'])} · {d['name']}": int(d["index"]) for d in event[2]}
                    outputs = [f"{int(d['index'])} · {d['name']}" for d in event[2] if d.get("isLoopbackDevice")]
                    mics = [f"{int(d['index'])} · {d['name']}" for d in event[2] if not d.get("isLoopbackDevice")]
                    self.output_picker["values"], self.mic_picker["values"] = outputs, mics
                    self.output_picker.set(outputs[0] if outputs else "")
                    self.mic_picker.set(mics[0] if mics else "")
                    self.status.set("Seleziona gli stessi dispositivi usati nell'app della chiamata.")
            elif kind == "audio" and event[1] == self.audio_epoch:
                self._audio_event(event[2], event[3])
        now = time.monotonic()
        self.timing.set(timing_hint(self.conversation.turns, any(self.active.values())))
        if self.shown_at and now - self.shown_at > 18:
            self.invalidate()
        if (self.auto.get() and self.pending_auto and self.inflight is None
                and not any(self.active.values()) and now - self.last_activity > 1.2
                and (self.audio is None or self.audio.stop_event.is_set()
                     or (self.audio.jobs.empty() and not self.audio.transcribing))):
            self.suggest()
        self.after(100, self._poll)

    def _audio_event(self, kind, data):
        if kind == "ready":
            self.audio_ready.add(data)
            self.audio_status.set("AUDIO ATTIVO · cuffie + microfono" if len(self.audio_ready) == 2 else "Apertura dei due canali…")
        elif kind == "transcript":
            self.add_turn(data["speaker"], data["text"], data["at"])
            self.status.set(f"Voce trascritta in {data['stt_seconds']:.1f} s · testo da verificare.")
        elif kind == "activity":
            self.active[data["speaker"]] = data["active"]
            self.last_activity = time.monotonic()
            if data["active"]:
                self.pending_auto = False
                self.invalidate()
        elif kind == "error":
            self.stop_audio()
            self.status.set(data)
        elif kind == "status":
            self.status.set(data)

    def close(self):
        self.closed = True
        self.stop_audio()
        self.conversation.clear()
        self.token.set("")
        self.destroy()


GUIDE = """PRIMA PROVA · circa un minuto

1. Apri la scheda Conversazione e premi «Prova un esempio».
2. Leggi la frase grande e la domanda alternativa.
3. Aggiungi una battuta con il campo in basso. Scegli chi parla.
4. Premi «Aiutami ora». In Demo le risposte sono esempi a regole fisse.

CON IL MODELLO LOCALE

Avvia il server nella scheda Developer di LM Studio e carica un modello
instruction/chat. In Impostazioni premi «Rileva modelli» e scegli quello
caricato. Poi seleziona «LM Studio locale» in Conversazione.
Prova prima con testo digitato: separiamo così i problemi del modello
da quelli del microfono. Il client accetta solo indirizzi di questo PC.

CON L'AUDIO DELLA CHIAMATA

Esegui INSTALLA_AUDIO.bat e poi PREPARA_VOCE.bat. Il primo installa
i componenti Python; il secondo scarica il modello di riconoscimento
vocale. Queste preparazioni richiedono Internet.

Usa cuffie. In Impostazioni rileva i dispositivi e scegli l'uscita
utilizzata dalla chiamata e il tuo microfono. La cattura riguarda tutta
l'uscita selezionata: chiudi musica e altre sorgenti audio.
Informa l'altra persona e ottieni il suo accordo prima di avviare.

Le due sorgenti vengono etichettate Tu / Altra persona. Non riconosciamo
identità vocali e non distinguiamo più persone sullo stesso canale.
La soglia rumore influenza il rilevamento delle pause: se si attiva
nel silenzio, fermati, aumentala e riavvia; se perde parole, abbassala.

COME LEGGERE I SUGGERIMENTI

La pausa è solo un indizio. Guarda e ascolta se l'altra persona ha finito.
I suggerimenti possono sbagliare: scegli parole che corrispondono a ciò
che pensi. Nuove battute o nuovo audio fanno sparire la proposta vecchia.
Le proposte scadono dopo 18 secondi. L'automatico è disattivato all'avvio.
«Sempre in primo piano» non nasconde la finestra durante la condivisione.

DATI E STOP

EvoCall non scrive file audio, trascrizioni o token. Conserva al massimo
16 battute nella memoria dell'app. STOP ferma l'acquisizione, scarta nuovi
risultati e mantiene le battute già mostrate. «Nuova conversazione» le
elimina dall'app insieme ai fatti e all'obiettivo personalizzato.
Il modello locale riceve le battute: eventuali log di LM Studio dipendono
dalle sue impostazioni. Questa non è una garanzia di cancellazione forense.

LIMITI DEL PROTOTIPO

Audio Windows e velocità reale devono essere provati sul tuo PC.
Nessun avatar, risposta vocale automatica, traduzione simultanea o
riconoscimento affidabile del turno di parola in questa versione.
Non è un programma .exe autonomo: richiede Python 3.12 con Tkinter.
"""
