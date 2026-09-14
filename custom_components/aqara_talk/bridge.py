"""Standalone go2rtc backchannel."""
from __future__ import annotations

import argparse
from collections import deque
import fcntl
import ipaddress
import json
import logging
import os
from pathlib import Path
import secrets
import select
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import time

LOG = logging.getLogger("aqara_talk")
CONTROL_PORT = 54324
AUDIO_PORT = 54323
FRAME_SECONDS = 1024 / 16000
HEARTBEAT_SECONDS = 5


def camera_ip(value):
    address = ipaddress.ip_address(value)
    if (address.version != 4 or address.is_multicast or address.is_unspecified or address.is_loopback
            or address.is_reserved or address.is_link_local):
        raise ValueError("Camera must be a numeric unicast IPv4 LAN address")
    return str(address)


def crc16(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0x8408 if crc & 1 else 0)
    return crc ^ 0xFFFF


def packet(kind, value):
    payload = struct.pack(">B" if kind == 2 else ">Q", value)
    body = struct.pack(">BH", kind, len(payload)) + payload
    return b"\xfe\xef" + body + struct.pack(">H", crc16(body))


def read_ack(sock, timeout=0.5):
    deadline = time.monotonic() + timeout
    data = bytearray()
    while len(data) < 8:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Control ACK deadline exceeded")
        sock.settimeout(remaining)
        part = sock.recv(8 - len(data))
        if not part:
            raise ConnectionError("Control channel closed before ACK")
        data.extend(part)
        if len(data) >= 5 and data[:5] != b"\xfe\xef\x02\x00\x01":
            raise ValueError("Invalid ACK header or length")
    if crc16(data[2:6]) != int.from_bytes(data[6:8], "big"):
        raise ValueError("Invalid ACK CRC")
    if data[5]:
        raise ValueError("Camera rejected control request")


def adts_frames(buffer):
    frames = []
    while len(buffer) >= 7:
        h = buffer
        if (h[0] != 255 or h[1] != 0xF1 or h[2] >> 6 != 1
                or (h[2] >> 2) & 15 != 8
                or ((h[2] & 1) << 2 | h[3] >> 6) != 1 or h[6] & 3):
            raise ValueError("Invalid AAC-LC/16kHz/mono ADTS header")
        length = (h[3] & 3) << 11 | h[4] << 3 | h[5] >> 5
        if not 7 < length <= 8191:
            raise ValueError("Invalid ADTS length")
        if len(buffer) < length:
            break
        frames.append(bytes(buffer[:length]))
        del buffer[:length]
    return frames


class Session:
    def __init__(self, ip, control_port=CONTROL_PORT, audio_port=AUDIO_PORT):
        self.ip, self.control_port, self.audio_port = ip, control_port, audio_port
        self.epoch = int(time.time() * 1000)
        self.tcp = self.udp = self.lock = None
        self.accepted = False
        self.start_attempted = False
        self.sequence = self.timestamp = 0
        self.ssrc = secrets.randbelow(2**31 - 1) + 1
        self.metrics = {"ssrc": self.ssrc, "start_ack_ms": None,
                        "heartbeat_count": 0, "heartbeat_ack_max_ms": None,
                        "stop": "not_attempted", "closed": False}

    def start(self, cancelled=lambda: False):
        lock_path = Path(tempfile.gettempdir()) / ("aqara-talk-" + self.ip.replace(":", "_") + ".lock")
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        self.lock = os.fdopen(fd, "rb")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Camera bridge already busy") from None
        family = socket.AF_INET6 if ":" in self.ip else socket.AF_INET
        self.tcp = socket.socket(family, socket.SOCK_STREAM)
        self.tcp.settimeout(2)
        self.tcp.connect((self.ip, self.control_port))
        if cancelled():
            raise InterruptedError("Bridge interrupted")
        self.start_attempted = True
        started = time.monotonic()
        self.tcp.sendall(packet(0, self.epoch))
        read_ack(self.tcp)
        self.metrics["start_ack_ms"] = round((time.monotonic() - started) * 1000, 3)
        self.accepted = True
        self.udp = socket.socket(family, socket.SOCK_DGRAM)
        self.udp.settimeout(0.2)

    def heartbeat(self):
        self.tcp.settimeout(0.5)
        started = time.monotonic()
        self.tcp.sendall(packet(3, self.epoch))
        read_ack(self.tcp)
        latency = round((time.monotonic() - started) * 1000, 3)
        self.metrics["heartbeat_count"] += 1
        self.metrics["heartbeat_ack_max_ms"] = max(self.metrics["heartbeat_ack_max_ms"] or 0, latency)

    def send(self, frame):
        check = bytearray(frame)
        if adts_frames(check) != [frame] or check:
            raise ValueError("Incomplete ADTS frame")
        header = struct.pack(">BBHII", 0x80, 97, self.sequence, self.timestamp, self.ssrc)
        self.udp.sendto(header + frame, (self.ip, self.audio_port))
        self.sequence = (self.sequence + 1) & 0xFFFF
        self.timestamp = (self.timestamp + 1024) & 0xFFFFFFFF

    def close(self):
        if self.tcp and self.start_attempted:
            try:
                self.tcp.settimeout(0.2)
                self.tcp.sendall(packet(1, self.epoch))
                self.metrics["stop"] = "sent"
            except OSError as error:
                self.metrics["stop"] = type(error).__name__
            try:
                self.tcp.shutdown(socket.SHUT_WR)
                deadline = time.monotonic() + 0.2
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError()
                    self.tcp.settimeout(remaining)
                    if not self.tcp.recv(4096):
                        self.metrics["drain"] = "eof"
                        break
            except OSError as error:
                self.metrics["drain"] = type(error).__name__
        for name in ("tcp", "udp", "lock"):
            resource = getattr(self, name)
            if resource:
                try:
                    resource.close()
                except OSError as error:
                    self.metrics["close_error"] = type(error).__name__
                finally:
                    setattr(self, name, None)
        self.accepted = False
        self.start_attempted = False
        self.metrics["closed"] = "close_error" not in self.metrics


def encoder_command(ffmpeg, input_format):
    return [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin",
            "-probesize", "32", "-analyzeduration", "0", "-f", input_format,
            "-ar", "8000" if input_format == "alaw" else "16000", "-ac", "1",
            "-i", "pipe:0", "-c:a", "aac", "-profile:a", "aac_low", "-b:a", "32k",
            "-ar", "16000", "-ac", "1", "-flush_packets", "1", "-f", "adts", "pipe:1"]


def run(args, input_fd=0, session=None, cancelled=lambda: False):
    report = {"probe": args.probe, "input_format": args.input_format,
              "input_bytes": 0, "aac_frames": 0, "aac_bytes": 0,
              "python": sys.version.split()[0], "executable": sys.executable, "pid": os.getpid(),
              "ffmpeg": args.ffmpeg, "status": "starting", "stage": "microphone"}
    proc = None
    started = last_input = time.monotonic()
    next_frame = None
    heartbeat = started + HEARTBEAT_SECONDS
    pending, encoded, frames = bytearray(), bytearray(), deque()
    eof = output_eof = False
    session = None if args.probe else (session or Session(args.camera_ip))
    try:
        if args.probe:
            emit_report(report, args.report)
        # Wait for actual microphone bytes before acquiring the speaker.
        while not select.select([input_fd], [], [], 0.1)[0]:
            if cancelled():
                raise InterruptedError("Bridge interrupted")
            if time.monotonic() - started > min(args.idle_timeout, args.max_duration):
                raise TimeoutError("Microphone idle timeout")
        first = os.read(input_fd, 512 if args.input_format == "alaw" else 2048)
        if not first:
            report["status"] = "eof"
            return report
        report["input_bytes"] += len(first)
        if cancelled():
            raise InterruptedError("Bridge interrupted")
        if session:
            report["stage"] = "start"
            session.start(cancelled)
        if cancelled():
            raise InterruptedError("Bridge interrupted")
        report["stage"] = "encoder"
        proc = subprocess.Popen(encoder_command(args.ffmpeg, args.input_format),
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, bufsize=0)
        os.set_blocking(proc.stdin.fileno(), False)
        os.set_blocking(proc.stdout.fileno(), False)
        pending.extend(first)
        last_input = time.monotonic()
        while True:
            if cancelled():
                raise InterruptedError("Bridge interrupted")
            now = time.monotonic()
            if now - started > args.max_duration:
                raise TimeoutError("Maximum call duration exceeded")
            if now - last_input > args.idle_timeout:
                raise TimeoutError("Microphone or encoder idle timeout")
            if session and now >= heartbeat:
                report["stage"] = "heartbeat"
                session.heartbeat()
                heartbeat = time.monotonic() + HEARTBEAT_SECONDS
                now = time.monotonic()
            report["stage"] = "audio"
            if frames and (len(frames) * FRAME_SECONDS > 0.5 or now - next_frame > 0.5):
                raise RuntimeError("Audio backlog exceeded 500 ms")
            if frames and now >= next_frame:
                frame = frames.popleft()
                if session:
                    session.send(frame)
                report["aac_frames"] += 1
                report["aac_bytes"] += len(frame)
                next_frame += FRAME_SECONDS
            if output_eof and not frames:
                if encoded:
                    raise ValueError("Truncated ADTS output")
                if proc.wait(timeout=1) != 0:
                    raise RuntimeError("FFmpeg encoder failed")
                if not eof:
                    raise RuntimeError("FFmpeg ended before microphone EOF")
                report["status"] = "eof"
                return report
            readers = ([] if eof else [input_fd]) + ([] if output_eof else [proc.stdout])
            writers = [proc.stdin] if pending else []
            ready, writable, _ = select.select(readers, writers, [], 0.01)
            if input_fd in ready:
                data = os.read(input_fd, 512 if args.input_format == "alaw" else 2048)
                if data:
                    pending.extend(data)
                    report["input_bytes"] += len(data)
                    last_input = time.monotonic()
                    if len(pending) > (4000 if args.input_format == "alaw" else 16000):
                        raise RuntimeError("Input backlog exceeded 500 ms")
                else:
                    eof = True
            if writable:
                try:
                    del pending[:os.write(proc.stdin.fileno(), pending)]
                except BlockingIOError:
                    pass
            if eof and not pending and not proc.stdin.closed:
                proc.stdin.close()
            if proc.stdout in ready:
                chunk = os.read(proc.stdout.fileno(), 8192)
                if not chunk:
                    output_eof = True
                else:
                    encoded.extend(chunk)
                    new_frames = adts_frames(encoded)
                    if new_frames and not frames:
                        next_frame = max(next_frame or 0, time.monotonic())
                    frames.extend(new_frames)
    except InterruptedError:
        report["status"] = "interrupted"
        raise
    except BaseException as error:
        report["status"] = "failed"
        report["error_type"] = type(error).__name__
        raise
    finally:
        try:
            if session:
                session.close()
        finally:
            try:
                if proc:
                    if proc.poll() is None:
                        proc.terminate()
                        try:
                            proc.wait(timeout=1)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                            proc.wait(timeout=1)
                    proc.stdin.close()
                    proc.stdout.close()
            finally:
                report["duration_seconds"] = round(time.monotonic() - started, 3)
                if isinstance(session, Session):
                    report.update(session.metrics)
                active_error = sys.exc_info()[0] is not None
                try:
                    emit_report(report, args.report if args.probe else None)
                except (OSError, ValueError) as error:
                    if not active_error:
                        raise
                    LOG.error("Diagnostic report write failed (%s)", type(error).__name__)



def emit_report(report, destination):
    text = json.dumps(report, sort_keys=True)
    print(text, file=sys.stderr, flush=True)
    if destination:
        target = Path(destination)
        if not target.is_absolute() or "custom_components" in target.parts:
            raise ValueError("Report requires an absolute path outside custom_components")
        fd, temporary = tempfile.mkstemp(prefix=".aqara-probe-", dir=target.parent)
        try:
            with os.fdopen(fd, "w") as stream:
                stream.write(text + "\n")
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def read_settings(destination):
    target = Path(destination)
    try:
        if not target.is_absolute():
            raise ValueError("path must be absolute")
        with target.open("rb") as stream:
            raw = stream.read(4097)
        if len(raw) > 4096:
            raise ValueError("file exceeds 4096 bytes")
        settings = json.loads(raw)
        if not isinstance(settings, dict) or set(settings) != {"max_duration"}:
            raise ValueError("expected only max_duration")
        duration = settings["max_duration"]
        if type(duration) is not int or not 1 <= duration <= 3600:
            raise ValueError("max_duration must be an integer from 1 to 3600")
        return duration
    except (OSError, ValueError) as err:
        raise ValueError(f"Invalid settings file {destination}: {err}") from err


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("camera_ip", type=camera_ip)
    parser.add_argument("--input-format", choices=("alaw", "s16le"), default="alaw")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--probe-report", "--report", dest="report")
    parser.add_argument("--idle-timeout", type=float, default=10)
    duration = parser.add_mutually_exclusive_group()
    duration.add_argument("--max-duration", type=float, default=180)
    duration.add_argument("--settings-file")
    args = parser.parse_args()
    if args.settings_file is not None:
        if args.probe:
            parser.error("--settings-file cannot be used with --probe")
        try:
            args.max_duration = read_settings(args.settings_file)
        except ValueError as err:
            parser.error(str(err))
    if not (0 < args.idle_timeout <= 60 and 0 < args.max_duration <= 3600):
        parser.error("Timeouts must be positive; idle <=60s, duration <=3600s")
    if args.report and (not args.probe or not Path(args.report).is_absolute()
                        or "custom_components" in Path(args.report).parts):
        parser.error("--report requires --probe and an absolute path outside custom_components")
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)

    cancelled = False

    def interrupted(signum, frame):
        nonlocal cancelled
        cancelled = True

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    result = 0
    try:
        run(args, cancelled=lambda: cancelled)
    except Exception as error:
        LOG.error("Bridge ended (%s)", type(error).__name__)
        result = 1
    if not args.probe and not cancelled:
        LOG.info("camera_closed waiting_for_disconnect")
        # ponytail: retain the consumer until hangup; exiting makes go2rtc reconnect.
        while not cancelled:
            if select.select([0], [], [], 0.1)[0] and not os.read(0, 8192):
                break
    return result


if __name__ == "__main__":
    sys.exit(main())
