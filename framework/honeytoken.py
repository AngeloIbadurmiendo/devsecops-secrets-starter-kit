"""Synthetic, loopback-only canary. No Cloud credentials or useful privileges."""

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
from queue import Empty, Queue
import secrets
from threading import Event, Lock, Thread
import time


class Canary:
    def __init__(self, value, alert_sink=None):
        self._digest = hashlib.sha256(value.encode("ascii")).digest()
        self._lock = Lock()
        self._state = "armed"
        self._queue = Queue(maxsize=1)
        self.done = Event()
        self.events = []
        self._alert_sink = alert_sink
        self.alert_delivery_succeeded = False

    def _record(self, phase):
        self.events.append({"phase": phase, "monotonic_ns": time.perf_counter_ns(),
                            "at_utc": datetime.now(timezone.utc).isoformat()})

    def observe(self, candidate):
        if not isinstance(candidate, str) or len(candidate) > 128:
            return 404
        try:
            digest = hashlib.sha256(candidate.encode("ascii")).digest()
        except UnicodeError:
            return 404
        if not hmac.compare_digest(digest, self._digest):
            return 404
        with self._lock:
            if self._state == "contained":
                return 410
            if self._state == "pending":
                return 409
            self._state = "pending"
            self._record("detected")
            self._queue.put_nowait(True)
            return 204

    def monitor_once(self):
        try:
            self._queue.get(timeout=3)
        except Empty:
            return
        with self._lock:
            # Alert is an in-memory local event, not an email or Cloud alert.
            self._record("alerted")
            notification = {"phase": "alerted", "at_utc": self.events[-1]["at_utc"]}
        if self._alert_sink is not None:
            try:
                self.alert_delivery_succeeded = self._alert_sink(notification) is True
            except Exception:
                # A failed notification must not prevent containment or expose data.
                self.alert_delivery_succeeded = False
        with self._lock:
            if self.alert_delivery_succeeded:
                self._record("delivered")
            self._state = "contained"
            self._record("contained")
            self.done.set()


@contextmanager
def loopback_receiver(canary):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Never log paths, headers, clients or the canary value.

        def do_GET(self):
            status = (canary.observe(self.headers.get("X-Feria-Canary"))
                      if self.path == "/canary" and self.client_address[0] == "127.0.0.1"
                      else 404)
            self.send_response(status)
            self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()

    class Receiver(HTTPServer):
        def get_request(self):
            connection, address = super().get_request()
            connection.settimeout(2)
            return connection, address

        def handle_error(self, *args):
            pass  # Suppress untrusted request data and raw tracebacks.

    server = Receiver(("127.0.0.1", 0), Handler)
    worker = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02})
    monitor = Thread(target=canary.monitor_once)
    worker.start()
    monitor.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)
        monitor.join(timeout=4)
        if worker.is_alive() or monitor.is_alive():
            raise RuntimeError("local receiver cleanup failed")


def run_pilot(alert_sink=None, receiver_factory=loopback_receiver, request_path="/canary"):
    # HTTPConnection uses literal loopback directly: no DNS, proxies or redirects.
    from http.client import HTTPConnection
    value = "feria-canary." + secrets.token_urlsafe(32)
    canary = Canary(value, alert_sink=alert_sink)

    def request(port, candidate):
        connection = HTTPConnection("127.0.0.1", port, timeout=2)
        try:
            connection.request("GET", request_path, headers={"X-Feria-Canary": candidate})
            response = connection.getresponse()
            response.read(1)
            return response.status
        finally:
            connection.close()

    with receiver_factory(canary) as port:
        benign_status = request(port, "nonmatching-synthetic-canary")
        benign_alert_absent = not canary.events
        activation_ns = time.perf_counter_ns()
        activation_utc = datetime.now(timezone.utc).isoformat()
        activation_status = request(port, value)
        containment_observed = canary.done.wait(timeout=5 if alert_sink else 2)
        replay_status = request(port, value)
    events = [{"phase": event["phase"], "at_utc": event["at_utc"],
               "offset_from_activation_ns": event["monotonic_ns"] - activation_ns}
              for event in canary.events]
    offsets = {event["phase"]: event["offset_from_activation_ns"] for event in events}
    expected_phases = ["detected", "alerted", "contained"]
    if alert_sink is not None and canary.alert_delivery_succeeded:
        expected_phases.insert(2, "delivered")
    checks = {"benign_no_alert": benign_status == 404 and benign_alert_absent,
              "activation_detected": activation_status == 204,
              "local_alert_and_containment_observed": containment_observed,
              "exact_event_order": [event["phase"] for event in events]
                                   == expected_phases,
              "replay_blocked": replay_status == 410,
              "receiver_closed": True}
    report = {"schema_version": 1, "evidence_id": "HONEY-LOCAL-001",
              "observed_at_utc": activation_utc,
              "scope": "single synthetic loopback HTTP pilot; local in-memory alert",
              "clock": "perf_counter_ns within one process; UTC for traceability",
              "environment": {"cloud_changes_performed": False,
                              "useful_privileges": False, "loopback_only": True},
              "synthetic_value_retained": False, "identifiers_retained": False,
              "http_statuses": {"benign": benign_status, "activation": activation_status,
                                "replay": replay_status},
              "events": events, "checks": checks,
              "metrics_ns": {"activation_to_local_alert": offsets.get("alerted"),
                             "local_alert_to_containment":
                             (offsets["contained"] - offsets["alerted"]
                              if "contained" in offsets and "alerted" in offsets else None)},
              "real_provider_revocation_measured": False,
              "external_notification_delivered": False,
              "final_E4_dataset": False}
    if alert_sink is not None:
        report["schema_version"] = 2
        report["evidence_id"] = "HONEY-IPC-001"
        report["scope"] = "single synthetic loopback HTTP pilot; separate local alert process"
        report["independent_local_alert_delivered"] = canary.alert_delivery_succeeded
        report["metrics_ns"]["activation_to_delivery_ack"] = offsets.get("delivered")
        report["metrics_ns"]["delivery_ack_to_containment"] = (
            offsets["contained"] - offsets["delivered"] if "delivered" in offsets else None)
        checks["independent_local_alert_delivered"] = canary.alert_delivery_succeeded
    import json
    checks["synthetic_value_absent_from_report"] = value not in json.dumps(report)
    report["passed"] = all(checks.values())
    return report
