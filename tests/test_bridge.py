"""Offline protocol, encoder and lifecycle checks; never contact a camera."""
import argparse
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

BRIDGE = Path(__file__).parents[1] / "custom_components/aqara_talk/bridge.py"
spec = importlib.util.spec_from_file_location("aqara_bridge", BRIDGE)
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
FRAME = bytes.fromhex("fff16040011ffc00")


def options(**kwargs):
    values = dict(camera_ip="192.0.2.10", input_format="alaw", ffmpeg=FFMPEG,
                  probe=True, report=None, idle_timeout=2, max_duration=5)
    values.update(kwargs)
    return argparse.Namespace(**values)


def feed(fd, data, chunk=512, delay=0.064):
    try:
        for offset in range(0, len(data), chunk):
            os.write(fd, data[offset:offset + chunk])
            time.sleep(delay)
    except BrokenPipeError:
        pass
    finally:
        os.close(fd)


class BridgeTests(unittest.TestCase):
    def test_stop_drains_unread_response_and_releases_resources(self):
        client, server = socket.socketpair()
        session = b.Session("192.0.2.10")
        session.tcp, session.udp, session.lock = client, Mock(), Mock()
        udp, lock = session.udp, session.lock
        session.start_attempted = True
        errors = []

        def camera():
            try:
                server.settimeout(1)
                self.assertEqual(server.recv(15), b.packet(1, session.epoch))
                server.sendall(b.packet(2, 0))
                self.assertEqual(server.recv(1), b"")
            except Exception as error:
                errors.append(error)
            finally:
                server.close()

        worker = threading.Thread(target=camera)
        worker.start()
        session.close()
        worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(session.metrics["drain"], "eof")
        self.assertTrue(session.metrics["closed"])
        udp.close.assert_called_once()
        lock.close.assert_called_once()

    def test_stop_drain_deadline_releases_lock(self):
        client, server = socket.socketpair()
        session = b.Session("192.0.2.10")
        session.tcp, session.lock = client, Mock()
        lock = session.lock
        session.start_attempted = True
        try:
            before = time.monotonic()
            session.close()
            self.assertLess(time.monotonic() - before, 0.5)
            self.assertEqual(session.metrics["drain"], "TimeoutError")
            lock.close.assert_called_once()
            self.assertIsNone(session.tcp)
        finally:
            server.close()

    def test_cancellation_during_connect_never_sends_start(self):
        session = b.Session("192.0.2.241")
        cancelled = threading.Event()
        with patch.object(b.socket, "socket") as factory:
            factory.return_value.connect.side_effect = lambda _: cancelled.set()
            try:
                with self.assertRaises(InterruptedError):
                    session.start(cancelled.is_set)
            finally:
                session.close()
            factory.return_value.sendall.assert_not_called()
            self.assertIsNone(session.lock)

    def test_cancelled_input_never_starts_camera(self):
        read, write = os.pipe()
        os.write(write, b"\xd5" * 512)
        os.close(write)
        session = Mock()
        try:
            with patch("sys.stderr", new_callable=io.StringIO):
                with self.assertRaises(InterruptedError):
                    b.run(options(probe=False), read, session, cancelled=lambda: True)
            session.start.assert_not_called()
            session.close.assert_called_once()
        finally:
            os.close(read)

    def test_camera_closes_before_encoder_reap(self):
        read, write = os.pipe()
        os.write(write, b"\xd5" * 512)
        os.close(write)
        session, proc = Mock(), Mock()
        proc.poll.return_value = None
        proc.wait.side_effect = lambda **_: session.close.assert_called_once()
        try:
            with patch.object(b.subprocess, "Popen", return_value=proc), \
                    patch.object(b.os, "set_blocking", side_effect=RuntimeError("setup")), \
                    patch("sys.stderr", new_callable=io.StringIO):
                with self.assertRaisesRegex(RuntimeError, "setup"):
                    b.run(options(probe=False), read, session)
        finally:
            os.close(read)

    def test_signal_handler_only_sets_cancellation_flag(self):
        handlers = {}

        def run(args, *, cancelled):
            self.assertFalse(cancelled())
            handlers[signal.SIGTERM](signal.SIGTERM, None)
            handlers[signal.SIGINT](signal.SIGINT, None)
            self.assertTrue(cancelled())

        with patch.object(b.signal, "signal", side_effect=lambda key, value: handlers.update({key: value})), \
                patch.object(b, "run", side_effect=run), \
                patch.object(sys, "argv", [str(BRIDGE), "192.0.2.10"]):
            self.assertEqual(b.main(), 0)

    @unittest.skipUnless(Path(FFMPEG).exists(), "FFmpeg required")
    def test_main_holds_finished_call_until_eof_or_signal(self):
        for finish in ("eof", "signal"):
            with self.subTest(finish=finish):
                code = (
                    "import runpy,sys\n"
                    "m=runpy.run_path(" + repr(str(BRIDGE)) + ")\n"
                    "class Session:\n"
                    " def __init__(self, ip): self.metrics={}\n"
                    " def start(self, cancelled): print('fake_start',file=sys.stderr,flush=True)\n"
                    " def send(self, frame): pass\n"
                    " def heartbeat(self): pass\n"
                    " def close(self): print('fake_stop',file=sys.stderr,flush=True)\n"
                    "m['main'].__globals__['Session']=Session\n"
                    "sys.argv=['bridge','192.0.2.10','--max-duration','0.2','--ffmpeg',"
                    + repr(FFMPEG) + "]\n"
                    "sys.exit(m['main']())\n"
                )
                proc = subprocess.Popen([sys.executable, "-c", code], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                try:
                    for _ in range(32):
                        proc.stdin.write(b"\xd5" * 512)
                        proc.stdin.flush()
                        time.sleep(0.064)
                    self.assertIsNone(proc.poll(), "Call limit must not exit the consumer")
                    if finish == "signal":
                        proc.send_signal(signal.SIGTERM)
                        proc.wait(timeout=2)
                    out, err = proc.communicate(timeout=2)
                    self.assertEqual(out, b"")
                    self.assertEqual(err.count(b"fake_start"), 1)
                    self.assertEqual(err.count(b"fake_stop"), 1)
                    self.assertIn(b"Bridge ended (TimeoutError)", err)
                    self.assertIn(b"camera_closed waiting_for_disconnect", err)
                    self.assertLess(err.index(b"fake_stop"), err.index(b"waiting_for_disconnect"))
                finally:
                    if proc.poll() is None:
                        proc.kill()
                        proc.communicate()

    def test_unexpected_error_keeps_consumer_alive_and_redacts_exception(self):
        code = (
            "import runpy,sys\n"
            "m=runpy.run_path(" + repr(str(BRIDGE)) + ")\n"
            "def run(*args, **kwargs):\n"
            " print('single_run',file=sys.stderr,flush=True)\n"
            " raise TypeError('private credential')\n"
            "m['main'].__globals__['run']=run\n"
            "sys.argv=['bridge','192.0.2.10']\n"
            "sys.exit(m['main']())\n"
        )
        proc = subprocess.Popen([sys.executable, "-c", code], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            proc.stdin.write(b"\xd5" * 512)
            proc.stdin.flush()
            time.sleep(0.3)
            self.assertIsNone(proc.poll())
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=2)
            out, err = proc.communicate(timeout=2)
            self.assertEqual(out, b"")
            self.assertEqual(err.count(b"single_run"), 1)
            self.assertIn(b"camera_closed waiting_for_disconnect", err)
            self.assertIn(b"Bridge ended (TypeError)", err)
            self.assertNotIn(b"private credential", err)
            self.assertNotIn(b"Traceback", err)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()

    def test_ssrc_bounds(self):
        for random_value in (0, 2**31 - 2):
            with patch.object(b.secrets, "randbelow", return_value=random_value) as random:
                session = b.Session("192.0.2.10")
            random.assert_called_once_with(2**31 - 1)
            self.assertEqual(session.ssrc, random_value + 1)
            self.assertTrue(1 <= session.ssrc <= 0x7fffffff)

    def test_two_sessions_release_camera_and_lock(self):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        listener.settimeout(3)
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp.bind(("127.0.0.1", 0))
        udp.settimeout(3)
        errors, observed = [], []

        def receive(conn, size):
            data = bytearray()
            while len(data) < size:
                chunk = conn.recv(size - len(data))
                if not chunk:
                    raise AssertionError("Premature EOF")
                data.extend(chunk)
            return bytes(data)

        def camera():
            try:
                for _ in range(2):
                    conn, _ = listener.accept()
                    with conn:
                        conn.settimeout(3)
                        start = receive(conn, 15)
                        epoch = int.from_bytes(start[5:13], "big")
                        self.assertEqual(start, b.packet(0, epoch))
                        conn.sendall(b.packet(2, 0))
                        audio = [udp.recvfrom(8192)[0] for _ in range(2)]
                        self.assertEqual(receive(conn, 15), b.packet(1, epoch))
                        self.assertEqual(conn.recv(1), b"")
                        observed.append((epoch, audio))
            except Exception as error:
                errors.append(error)

        worker = threading.Thread(target=camera)
        worker.start()
        try:
            for index in range(2):
                with patch.object(b.time, "time", return_value=1000 + index), \
                        patch.object(b.secrets, "randbelow", return_value=100 + index):
                    session = b.Session("127.0.0.1", listener.getsockname()[1], udp.getsockname()[1])
                try:
                    session.start()
                    session.send(FRAME)
                    session.send(FRAME)
                finally:
                    session.close()
                self.assertEqual(session.metrics["stop"], "sent")
                self.assertTrue(session.metrics["closed"])
                self.assertIsNone(session.lock)
            worker.join(4)
            self.assertFalse(worker.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual([epoch for epoch, _ in observed], [1000000, 1001000])
            for index, (_, packets) in enumerate(observed):
                headers = [struct.unpack(">BBHII", packet[:12]) for packet in packets]
                self.assertEqual(headers, [(128, 97, 0, 0, 101 + index),
                                           (128, 97, 1, 1024, 101 + index)])
        finally:
            listener.close()
            udp.close()
            worker.join(4)

    @unittest.skipUnless(Path(FFMPEG).exists(), "FFmpeg required")
    def test_audio_survives_400ms_heartbeat_delay(self):
        read, write = os.pipe()
        worker = threading.Thread(target=feed, args=(write, b"\xd5" * 16000))
        worker.start()
        session = Mock()
        session.heartbeat.side_effect = lambda: time.sleep(0.4)
        try:
            with patch.object(b, "HEARTBEAT_SECONDS", 0.15), \
                    patch("sys.stderr", new_callable=io.StringIO):
                report = b.run(options(probe=False), read, session)
            self.assertEqual(report["status"], "eof")
            self.assertGreaterEqual(report["aac_frames"], 31)
            session.heartbeat.assert_called()
            session.close.assert_called_once()
        finally:
            os.close(read)
            worker.join()

    def test_heartbeat_latency_and_stop_error_metrics(self):
        session = b.Session("192.0.2.10")
        session.tcp = Mock()
        session.start_attempted = True
        with patch.object(b, "read_ack"), \
                patch.object(b.time, "monotonic", side_effect=[1, 1.4]):
            session.heartbeat()
        self.assertEqual(session.metrics["heartbeat_count"], 1)
        self.assertEqual(session.metrics["heartbeat_ack_max_ms"], 400)
        session.tcp.sendall.side_effect = ConnectionResetError("private detail")
        session.close()
        self.assertEqual(session.metrics["stop"], "ConnectionResetError")
        self.assertTrue(session.metrics["closed"])

    def test_real_call_report_is_stderr_only_and_redacted(self):
        read, write = os.pipe()
        os.write(write, b"\xd5" * 512)
        os.close(write)
        session = b.Session("192.0.2.10")
        try:
            with patch.object(session, "start", side_effect=TimeoutError("secret address")), \
                    patch.object(b, "emit_report") as report:
                with self.assertRaises(TimeoutError):
                    b.run(options(probe=False, report="/should-not-write"), read, session)
            value, destination = report.call_args.args
            self.assertIsNone(destination)
            self.assertEqual(value["stage"], "start")
            self.assertEqual(value["error_type"], "TimeoutError")
            self.assertEqual(value["ssrc"], session.ssrc)
            self.assertTrue(value["closed"])
            self.assertNotIn("192.0.2.10", json.dumps(value))
            self.assertNotIn("secret address", json.dumps(value))
        finally:
            os.close(read)

    def test_upstream_wire_vectors(self):
        self.assertEqual(b.crc16(b"123456789"), 0x906E)
        self.assertEqual(b.packet(2, 0).hex(), "feef02000100dc70")
        self.assertEqual(b.packet(0, 0).hex(), "feef0000080000000000000000701e")
        self.assertEqual(b.packet(1, 0).hex(), "feef0100080000000000000000258f")
        self.assertEqual(b.packet(3, 0).hex(), "feef03000800000000000000008ead")

    def test_ack_fragments_and_rejections(self):
        for data, valid in [(b.packet(2, 0), True), (b.packet(2, 1), False),
                            (b.packet(2, 0)[:-1] + b"x", False),
                            (b"\xfe\xef\x02\xff\xffxxx", False),
                            (b.packet(0, 0), False)]:
            sock = Mock()
            chunks = iter(bytes([n]) for n in data)
            sock.recv.side_effect = lambda _: next(chunks)
            if valid:
                b.read_ack(sock)
            else:
                with self.assertRaises(ValueError):
                    b.read_ack(sock)
        sock = Mock()
        sock.recv.return_value = b""
        with self.assertRaises(ConnectionError):
            b.read_ack(sock)

    def test_adts_and_rtp_wrap_no_bad_send(self):
        session = b.Session("192.0.2.10")
        session.udp = Mock()
        session.sequence, session.timestamp, session.ssrc = 65535, 0xFFFFFC00, 17
        session.send(FRAME)
        session.send(FRAME)
        packets = [call.args[0] for call in session.udp.sendto.call_args_list]
        self.assertEqual(struct.unpack(">BBHII", packets[0][:12]), (128, 97, 65535, 0xFFFFFC00, 17))
        self.assertEqual(struct.unpack(">BBHII", packets[1][:12]), (128, 97, 0, 0, 17))
        for invalid in [b"garbage!", FRAME[:-1], FRAME + b"x", FRAME[:2] + b"\x50" + FRAME[3:]]:
            with self.assertRaises(ValueError):
                session.send(invalid)
        self.assertEqual(session.udp.sendto.call_count, 2)

    def test_ip(self):
        for invalid in ["camera.local", "0.0.0.0", "127.0.0.1", "224.0.0.1", "255.255.255.255", "fe80::1"]:
            with self.assertRaises(ValueError):
                b.camera_ip(invalid)
        self.assertEqual(b.camera_ip("192.168.1.20"), "192.168.1.20")

    @unittest.skipUnless(Path(FFMPEG).exists(), "FFmpeg required")
    def test_real_probe_both_formats_zero_network(self):
        for fmt, chunk, data in [("alaw", 512, b"\xd5" * 4096),
                                 ("s16le", 2048, b"\0" * 16384)]:
            read, write = os.pipe()
            thread = threading.Thread(target=feed, args=(write, data, chunk))
            thread.start()
            try:
                with patch.object(b.socket, "socket", side_effect=AssertionError("Network in probe")), \
                        patch.object(b.Session, "start", side_effect=AssertionError("Lock in probe")), \
                        patch("sys.stderr", new_callable=io.StringIO):
                    report = b.run(options(input_format=fmt), read)
                self.assertEqual(report["status"], "eof")
                self.assertEqual(report["input_bytes"], len(data))
                self.assertGreaterEqual(report["aac_frames"], 8)
            finally:
                os.close(read)
                thread.join()

    @unittest.skipUnless(Path(FFMPEG).exists(), "FFmpeg required")
    def test_real_encoder_decodes(self):
        for fmt, data in [("alaw", b"\xd5" * 4096), ("s16le", b"\0" * 16384)]:
            encoded = subprocess.run(b.encoder_command(FFMPEG, fmt), input=data,
                                     capture_output=True, check=True).stdout
            buffer = bytearray(encoded)
            self.assertGreaterEqual(len(b.adts_frames(buffer)), 8)
            self.assertFalse(buffer)
            decoded = subprocess.run([FFMPEG, "-v", "error", "-f", "aac", "-i", "pipe:0",
                                      "-f", "s16le", "pipe:1"], input=encoded,
                                     capture_output=True, check=True).stdout
            self.assertGreaterEqual(len(decoded), 16384)

    @unittest.skipUnless(Path(FFMPEG).exists(), "FFmpeg required")
    def test_fake_camera_actual_sigterm_pending_and_accepted(self):
        for accept in [False, True]:
            listener = socket.socket()
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            listener.settimeout(3)
            udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp.bind(("127.0.0.1", 0))
            udp.settimeout(2)
            started = threading.Event()
            received = bytearray()

            def camera():
                conn, _ = listener.accept()
                with conn:
                    conn.settimeout(3)
                    while len(received) < 15:
                        received.extend(conn.recv(15 - len(received)))
                    if accept:
                        for byte in b.packet(2, 0):
                            conn.sendall(bytes([byte]))
                    started.set()
                    while True:
                        data = conn.recv(4096)
                        if not data:
                            break
                        received.extend(data)

            thread = threading.Thread(target=camera)
            thread.start()
            code = ("import runpy,argparse,signal; "
                    "m=runpy.run_path(" + repr(str(BRIDGE)) + "); "
                    "signal.signal(signal.SIGTERM,lambda *a: (_ for _ in ()).throw(InterruptedError())); "
                    "m['run'](argparse.Namespace(camera_ip='127.0.0.1',input_format='alaw',ffmpeg="
                    + repr(FFMPEG) + ",probe=False,report=None,idle_timeout=2,max_duration=5),session="
                    "m['Session']('127.0.0.1'," + str(listener.getsockname()[1]) + ","
                    + str(udp.getsockname()[1]) + "))")
            proc = subprocess.Popen([sys.executable, "-c", code], stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                proc.stdin.write(b"\xd5" * 512)
                proc.stdin.flush()
                self.assertTrue(started.wait(2))
                if accept:
                    for _ in range(5):
                        proc.stdin.write(b"\xd5" * 512)
                        proc.stdin.flush()
                        time.sleep(0.064)
                    audio, _ = udp.recvfrom(8192)
                    self.assertEqual(audio[:2], b"\x80\x61")
                proc.send_signal(signal.SIGTERM)
                out, _ = proc.communicate(timeout=4)
                self.assertEqual(out, b"")
                thread.join(timeout=3)
                self.assertFalse(thread.is_alive())
                self.assertEqual(len(received), 30)
                epoch = int.from_bytes(received[5:13], "big")
                self.assertEqual(bytes(received[:15]), b.packet(0, epoch))
                self.assertEqual(bytes(received[15:]), b.packet(1, epoch))
                # Kernel lock release is verified after a real process termination.
                lock = b.Session("127.0.0.1")
                with patch.object(b.socket, "socket"), patch.object(b, "read_ack"):
                    lock.start()
                    lock.close()
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.communicate()
                listener.close()
                udp.close()
                thread.join(timeout=3)

    @unittest.skipUnless(Path(FFMPEG).exists(), "FFmpeg required")
    def test_audio_resumes_after_empty_queue_gap(self):
        read, write = os.pipe()

        def microphone():
            try:
                for segment in range(2):
                    if segment:
                        time.sleep(0.8)
                    for _ in range(8):
                        os.write(write, b"\xd5" * 512)
                        time.sleep(0.064)
            except BrokenPipeError:
                pass
            finally:
                os.close(write)

        thread = threading.Thread(target=microphone)
        thread.start()
        try:
            with patch("sys.stderr", new_callable=io.StringIO):
                report = b.run(options(), read)
            self.assertEqual(report["status"], "eof")
            self.assertGreaterEqual(report["aac_frames"], 16)
        finally:
            os.close(read)
            thread.join()

    def test_report_error_does_not_mask_interruption(self):
        reports = []

        def report(value, _):
            reports.append(dict(value))
            if len(reports) > 1:
                raise OSError("report write failed")

        with patch.object(b, "emit_report", side_effect=report), \
                patch.object(b.select, "select", side_effect=InterruptedError("original signal")), \
                self.assertLogs(b.LOG, level="ERROR"):
            with self.assertRaisesRegex(InterruptedError, "original signal"):
                b.run(options())
        self.assertEqual(reports[-1]["status"], "interrupted")

    def test_cleanup_remembers_repeated_cancellation_signals(self):
        read, write = os.pipe()
        os.close(write)
        session = Mock()
        received = []
        old = {signum: signal.signal(signum, lambda signum, _: received.append(signum))
               for signum in (signal.SIGTERM, signal.SIGINT)}

        def close():
            os.kill(os.getpid(), signal.SIGTERM)
            os.kill(os.getpid(), signal.SIGINT)

        session.close.side_effect = close
        try:
            b.run(options(probe=False), read, session)
            self.assertEqual(received, [signal.SIGTERM, signal.SIGINT])
            session.close.assert_called_once()
        finally:
            os.close(read)
            for signum, handler in old.items():
                signal.signal(signum, handler)

    def test_eof_does_not_start(self):
        read, write = os.pipe()
        os.close(write)
        session = Mock()
        try:
            self.assertEqual(b.run(options(probe=False), read, session)["status"], "eof")
            session.start.assert_not_called()
            session.close.assert_called_once()
        finally:
            os.close(read)

    def test_encoder_failure_cleanup(self):
        read, write = os.pipe()
        os.write(write, b"\xd5" * 512)
        os.close(write)
        session = Mock()
        try:
            with self.assertRaises((RuntimeError, BrokenPipeError)):
                b.run(options(probe=False, ffmpeg="/usr/bin/false"), read, session)
            session.start.assert_called_once()
            session.close.assert_called_once()
        finally:
            os.close(read)

    @unittest.skipUnless(Path(FFMPEG).exists(), "FFmpeg required")
    def test_heartbeat_failure_terminates_pipeline(self):
        read, write = os.pipe()
        thread = threading.Thread(target=feed, args=(write, b"\xd5" * 8192))
        thread.start()
        session = Mock()
        session.heartbeat.side_effect = ConnectionResetError("heartbeat reset")
        try:
            with patch.object(b, "HEARTBEAT_SECONDS", 0.15):
                with self.assertRaises(ConnectionResetError):
                    b.run(options(probe=False), read, session)
            session.close.assert_called_once()
        finally:
            os.close(read)
            thread.join()

    @unittest.skipUnless(Path(FFMPEG).exists(), "FFmpeg required")
    def test_unpaced_input_fails_backlog_instead_of_dropping(self):
        with tempfile.TemporaryFile() as source, patch("sys.stderr", new_callable=io.StringIO):
            source.write(b"\xd5" * 64000)
            source.seek(0)
            with self.assertRaisesRegex(RuntimeError, "backlog exceeded 500 ms"):
                b.run(options(), source.fileno())

    def test_probe_start_marker_before_input_and_idle_limit(self):
        read, write = os.pipe()
        reports = []
        try:
            with patch.object(b, "emit_report", side_effect=lambda report, _: reports.append(dict(report))):
                with self.assertRaises(TimeoutError):
                    b.run(options(idle_timeout=0.02), read)
            self.assertEqual([r["status"] for r in reports], ["starting", "failed"])
            self.assertEqual(reports[0]["input_bytes"], 0)
            self.assertEqual(reports[0]["pid"], os.getpid())
        finally:
            os.close(read)
            os.close(write)

    def test_encoder_cleanup_failure_still_closes_session(self):
        for failure in ("wait", "pipe"):
            with self.subTest(failure=failure):
                read, write = os.pipe()
                os.write(write, b"\xd5" * 512)
                os.close(write)
                session, proc = Mock(), Mock()
                proc.poll.return_value = None
                if failure == "wait":
                    proc.wait.side_effect = subprocess.TimeoutExpired("ffmpeg", 1)
                    expected = subprocess.TimeoutExpired
                else:
                    proc.stdin.close.side_effect = OSError("pipe close failed")
                    expected = OSError
                try:
                    with patch.object(b.subprocess, "Popen", return_value=proc), \
                            patch.object(b.os, "set_blocking", side_effect=RuntimeError("setup failed")):
                        with self.assertRaises(expected):
                            b.run(options(probe=False), read, session)
                    session.close.assert_called_once()
                finally:
                    os.close(read)

    def test_lock_contention(self):
        first, second = b.Session("192.0.2.243"), b.Session("192.0.2.243")
        with patch.object(b.socket, "socket") as factory, patch.object(b, "read_ack"):
            try:
                first.start()
                count = factory.call_count
                with self.assertRaisesRegex(RuntimeError, "busy"):
                    second.start()
                self.assertEqual(factory.call_count, count)
            finally:
                second.close()
                first.close()
            third = b.Session("192.0.2.243")
            third.start()
            third.close()

    def test_missing_or_rejected_start_ack_still_sends_stop(self):
        for ack, error in [(None, TimeoutError), (b.packet(2, 1), ValueError)]:
            with self.subTest(ack=ack):
                listener = socket.socket()
                listener.bind(("127.0.0.1", 0))
                listener.listen()
                listener.settimeout(2)
                received, errors = bytearray(), []

                def camera():
                    try:
                        conn, _ = listener.accept()
                        with conn:
                            conn.settimeout(2)
                            while len(received) < 15:
                                chunk = conn.recv(15 - len(received))
                                if not chunk:
                                    raise AssertionError("Missing START")
                                received.extend(chunk)
                            if ack:
                                conn.sendall(ack)
                            while True:
                                chunk = conn.recv(4096)
                                if not chunk:
                                    break
                                received.extend(chunk)
                    except Exception as failure:
                        errors.append(failure)

                thread = threading.Thread(target=camera)
                thread.start()
                session = b.Session("127.0.0.1", listener.getsockname()[1])
                try:
                    with self.assertRaises(error):
                        session.start()
                    self.assertFalse(session.accepted)
                finally:
                    session.close()
                    thread.join(timeout=3)
                    listener.close()
                self.assertFalse(thread.is_alive())
                self.assertEqual(errors, [])
                self.assertEqual(bytes(received), b.packet(0, session.epoch) + b.packet(1, session.epoch))
                self.assertIsNone(session.lock)
                self.assertFalse(session.start_attempted)

    def test_connection_failure_does_not_send_stop(self):
        session = b.Session("192.0.2.242")
        with patch.object(b.socket, "socket") as factory:
            factory.return_value.connect.side_effect = ConnectionRefusedError()
            try:
                with self.assertRaises(ConnectionRefusedError):
                    session.start()
            finally:
                session.close()
            factory.return_value.sendall.assert_not_called()
            self.assertIsNone(session.lock)

    def test_pending_start_and_accepted_cleanup(self):
        for accepted in [False, True]:
            session = b.Session("192.0.2.242")
            with patch.object(b.socket, "socket") as factory, \
                    patch.object(b, "read_ack", side_effect=None if accepted else InterruptedError):
                if accepted:
                    session.start()
                else:
                    with self.assertRaises(InterruptedError):
                        session.start()
                tcp = factory.return_value
                session.close()
                sent = [call.args[0][2] for call in tcp.sendall.call_args_list]
                self.assertEqual(sent, [0, 1])
                self.assertIsNone(session.lock)

    def test_late_heartbeat_and_rst(self):
        for error in [socket.timeout(), ConnectionResetError()]:
            session = b.Session("192.0.2.10")
            session.tcp = Mock()
            session.tcp.recv.side_effect = error
            with self.assertRaises(OSError):
                session.heartbeat()
            session.close()
        a, c = socket.socketpair()
        try:
            before = time.monotonic()
            with self.assertRaises(TimeoutError):
                b.read_ack(a, timeout=0.03)
            self.assertLess(time.monotonic() - before, 0.2)
        finally:
            a.close()
            c.close()

    @unittest.skipUnless(Path(FFMPEG).exists(), "FFmpeg required")
    def test_sigterm_probe_and_private_report(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "probe.json"
            proc = subprocess.Popen([sys.executable, str(BRIDGE), "192.0.2.10", "--probe",
                                     "--ffmpeg", FFMPEG, "--probe-report", str(report)],
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            proc.stdin.write(b"\xd5" * 512)
            proc.stdin.flush()
            time.sleep(0.2)
            proc.send_signal(signal.SIGTERM)
            out, err = proc.communicate(timeout=4)
            self.assertEqual(out, b"")
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(json.loads(report.read_text())["status"], "interrupted")
            self.assertEqual(report.stat().st_mode & 0o777, 0o600)
            self.assertIn(b"Bridge ended (InterruptedError)", err)


if __name__ == "__main__":
    unittest.main()
