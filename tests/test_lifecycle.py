"""Exercise the UI event handler without a display, and capture without hardware."""
from contextlib import contextmanager
import queue
from types import SimpleNamespace
import unittest

from evo_call.app import App
from evo_call.audio import AudioSession, Chunk
from evo_call.core import Conversation, Suggestion


class Value:
    def __init__(self, value=None):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class UIEvents(unittest.TestCase):
    def harness(self):
        displayed = []
        state = SimpleNamespace(
            closed=False, events=queue.Queue(), inflight=(1, 0, 3), epoch=1,
            conversation=Conversation(), request_id=3, active={}, shown_at=0,
            help_button=SimpleNamespace(configure=lambda **kwargs: None),
            show_suggestion=lambda *args: displayed.append(args), status=Value(), timing=Value(),
            auto=Value(False), after=lambda *args: None,
            _poll=lambda: None,
        )
        return state, displayed

    def test_current_result_shown(self):
        state, displayed = self.harness()
        state.events.put(("suggestion", (1, 0, 3), Suggestion("x", "y", "VALUTA", "local"), 1))
        App._poll(state)
        self.assertEqual(len(displayed), 1)
        self.assertIsNone(state.inflight)

    def test_result_after_new_turn_stop_or_mode_change_is_discarded(self):
        for reason in ("new_turn", "stop", "audio_started"):
            with self.subTest(reason=reason):
                state, displayed = self.harness()
                if reason == "new_turn":
                    state.conversation.add("Tu", "Argomento diverso")
                elif reason == "stop":
                    state.epoch += 1
                else:
                    state.request_id += 1
                state.events.put(("suggestion", (1, 0, 3), Suggestion("vecchio", "", "ASCOLTA", "local"), 1))
                App._poll(state)
                self.assertEqual(displayed, [])
                self.assertIsNone(state.inflight)

    def test_audio_event_from_old_session_is_ignored(self):
        state, displayed = self.harness()
        state.audio_epoch = 2
        state._audio_event = lambda *args: displayed.append(args)
        state.events.put(("audio", 1, "transcript", {"text": "old private context"}))
        App._poll(state)
        self.assertEqual(displayed, [])


class AudioLifecycle(unittest.TestCase):
    def test_stop_drops_pending_audio(self):
        session = AudioSession(lambda *args: None, 1, 2, "unused")
        session.jobs.put(Chunk("Tu", b"private", 16000, 1, 0, 0))
        session.stop()
        self.assertTrue(session.stop_event.is_set())
        self.assertTrue(session.jobs.empty())

    def test_hardware_failure_emits_one_error_and_stops_both_channels(self):
        emitted = []
        session = AudioSession(lambda *args: emitted.append(args), 1, 2, "unused")
        session.fail("Microfono non disponibile")
        session.fail("Secondo errore")
        self.assertTrue(session.stop_event.is_set())
        self.assertEqual(emitted, [("error", "Microfono non disponibile")])

    def test_silent_input_produces_no_chunks_and_releases_device(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy disponibile solo dopo l'installazione audio")
        emitted = []
        session = AudioSession(lambda *args: emitted.append(args), 1, 2, "unused")
        closed = []
        class FakePort:
            def get_device_info_by_index(self, _index):
                return {"defaultSampleRate": 16000, "maxInputChannels": 1, "isLoopbackDevice": False}

            @contextmanager
            def open(self, **kwargs):
                count = [0]
                def read(size, **_kw):
                    count[0] += 1
                    if count[0] > 30:
                        session.stop()
                    return bytes(size * 2)
                try:
                    yield SimpleNamespace(read=read)
                finally:
                    closed.append(True)

        @contextmanager
        def fake_context():
            yield FakePort()
        fake_pa = SimpleNamespace(PyAudio=fake_context, paInt16=8)
        session._capture("Tu", 2, fake_pa, np)
        self.assertTrue(session.jobs.empty())
        self.assertEqual(closed, [True])
        self.assertNotIn(("activity", {"speaker": "Tu", "active": True}), emitted)


if __name__ == "__main__":
    unittest.main()
