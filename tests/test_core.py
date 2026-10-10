import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import unittest

from evo_call.core import Conversation, LocalModel, demo_suggestion, local_base_url, timing_hint


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, payload):
        raw = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.server.redirect:
            self.send_response(302)
            self.send_header("Location", "http://example.invalid/private")
            self.end_headers()
        else:
            self.send({"data": [{"id": "test-local"}]})

    def do_POST(self):
        size = int(self.headers["Content-Length"])
        self.server.received = json.loads(self.rfile.read(size))
        self.send({"choices": [{"message": {"content": self.server.reply}}]})


class LocalAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.server.redirect = False
        self.server.reply = json.dumps({"reply": "Ti va di raccontarmelo?", "question": "Da dove vuoi partire?", "cue": "ASCOLTA"})
        self.client = LocalModel(f"http://127.0.0.1:{self.server.server_port}", "test-local")

    def test_real_http_contract_and_context(self):
        turns = [{"speaker": "Altra persona", "text": "Ho avuto una giornata pesante.", "at": 1}]
        self.assertEqual(self.client.models(), ["test-local"])
        result = self.client.suggest(turns, "Ascoltare", "Domani non sono disponibile.")
        self.assertEqual(result.cue, "ASCOLTA")
        body = self.server.received
        self.assertEqual(body["model"], "test-local")
        self.assertEqual(body["response_format"]["type"], "json_schema")
        context = json.loads(body["messages"][1]["content"])
        self.assertEqual(context["battute"], turns)
        self.assertIn("non sono disponibile", context["fatti_autorizzati"])

    def test_rejects_malformed_or_invented_cue(self):
        for bad in ("not json", "[]", '{"reply":"x","question":"x","cue":"PARLA ORA"}',
                    '{"reply":null,"question":"x","cue":"VALUTA"}'):
            with self.subTest(bad=bad):
                self.server.reply = bad
                with self.assertRaisesRegex(ValueError, "Risposta non utilizzabile"):
                    self.client.suggest([{"speaker": "Tu", "text": "ciao"}], "", "")

    def test_redirect_cannot_forward_context(self):
        self.server.redirect = True
        with self.assertRaisesRegex(ValueError, "HTTP 302"):
            self.client.models()


class ConversationTests(unittest.TestCase):
    def test_external_and_deceptive_urls_rejected(self):
        for url in ("https://api.example.com/v1", "http://127.0.0.1.example.com/v1",
                    "http://user@example.com/v1", "http://192.168.1.2:1234/v1",
                    "file:///tmp/file", "http://localhost/v1?next=evil", "http://localhost:99999/v1"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                local_base_url(url)
        self.assertEqual(local_base_url("http://localhost:1234/v1/"), "http://127.0.0.1:1234/v1")
        self.assertEqual(local_base_url("http://[::1]:1234"), "http://[::1]:1234/v1")

    def test_delayed_channel_keeps_capture_order_and_memory_is_bounded(self):
        state = Conversation()
        for i in range(20):
            state.add("Tu", str(i), at=i)
        state.add("Altra persona", "Delayed older audio", at=-1)
        self.assertEqual(len(state.turns), 16)
        self.assertEqual(state.turns[-1].text, "19")
        revision = state.revision
        state.clear()
        self.assertEqual(state.turns, [])
        self.assertGreater(state.revision, revision)

    def test_silence_is_not_definitive_turn_detection(self):
        state = Conversation()
        state.add("Altra persona", "Ci vediamo?")
        self.assertIn("se era rivolta a te", timing_hint(state.turns))
        self.assertIn("aspetta", timing_hint(state.turns, active=True))
        state.add("Tu", "Ci penso")
        self.assertIn("lascia spazio", timing_hint(state.turns))

    def test_demo_honestly_labelled_and_no_fabricated_availability(self):
        state = Conversation()
        state.add("Altra persona", "Usciamo domani?")
        result = demo_suggestion(state.snapshot())
        self.assertIn("regole fisse", result.source)
        self.assertIn("prima di decidere", result.reply)


if __name__ == "__main__":
    unittest.main()
