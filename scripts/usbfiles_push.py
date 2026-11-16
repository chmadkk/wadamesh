#!/usr/bin/env python3
"""Push files to a Wadamesh device over the USB Files serial protocol.

The device must have the USB Files app open (Apps > USB Files). Protocol:
src/helpers/esp32/UsbFilesProtocol.h.

  python3 scripts/usbfiles_push.py /dev/cu.usbmodem101 LOCAL:/sd/meshcomod/apps/name.lua [...]

Waits up to --wait seconds for the app to be opened, so it can be started first.
"""
import argparse, glob, json, struct, sys, time, zlib

import serial  # pyserial (bundled with PlatformIO's Python)

MAGIC = b"\xE7\x5A"
T_HELLO, T_LIST, T_WRITE_BEGIN, T_WRITE_DATA, T_WRITE_END, T_ABORT = 0x01, 0x02, 0x05, 0x06, 0x07, 0x0C
T_REPLY = 0x80
CHUNK = 2048


class Link:
    def __init__(self, port):
        self.s = serial.Serial(port, 115200, timeout=0.2)
        self.buf = b""
        self.seq = 1

    def _frame(self, t, payload):
        head = bytes([t]) + struct.pack("<HH", self.seq, len(payload))
        return MAGIC + head + payload + struct.pack("<I", zlib.crc32(head + payload) & 0xFFFFFFFF)

    def _read_frame(self, timeout):
        end = time.time() + timeout
        while time.time() < end:
            self.buf += self.s.read(4096)
            while True:
                i = self.buf.find(MAGIC)
                if i < 0:
                    self.buf = self.buf[-1:] if self.buf.endswith(b"\xE7") else b""
                    break
                self.buf = self.buf[i:]
                if len(self.buf) < 7:
                    break
                t, seq, ln = self.buf[2], *struct.unpack("<HH", self.buf[3:7])
                total = 7 + ln + 4
                if ln > 4096 + 256:
                    self.buf = self.buf[1:]; continue
                if len(self.buf) < total:
                    break
                body = self.buf[2:7 + ln]
                crc = struct.unpack("<I", self.buf[7 + ln:total])[0]
                if zlib.crc32(body) & 0xFFFFFFFF != crc:
                    self.buf = self.buf[1:]; continue
                self.buf = self.buf[total:]
                return t, seq, self.buf[:0] + body[5:]
        return None

    def request(self, t, payload=b"", timeout=5.0, tries=3):
        for _ in range(tries):
            self.s.write(self._frame(t, payload))
            end = time.time() + timeout
            while time.time() < end:
                f = self._read_frame(end - time.time())
                if not f:
                    break
                rt, rseq, body = f
                if rt == (t | T_REPLY) and rseq == self.seq:
                    self.seq = (self.seq + 1) & 0xFFFF or 1
                    return body
        raise TimeoutError("no reply to request 0x%02x" % t)


def push(link, local, remote):
    data = open(local, "rb").read()
    r = link.request(T_WRITE_BEGIN, struct.pack("<IB", len(data), 0x01) + remote.encode())
    if r[0] != 0:
        raise RuntimeError("%s: WRITE_BEGIN status %d %s" % (remote, r[0], r[1:].decode(errors="replace")))
    off = 0
    while off < len(data):
        part = data[off:off + CHUNK]
        r = link.request(T_WRITE_DATA, struct.pack("<I", off) + part)
        if r[0] != 0:
            link.request(T_ABORT)
            raise RuntimeError("%s: WRITE_DATA status %d %s" % (remote, r[0], r[1:].decode(errors="replace")))
        off += len(part)
    r = link.request(T_WRITE_END, struct.pack("<I", zlib.crc32(data) & 0xFFFFFFFF), timeout=10)
    if r[0] != 0:
        raise RuntimeError("%s: WRITE_END status %d %s" % (remote, r[0], r[1:].decode(errors="replace")))
    print("wrote %s (%d bytes)" % (remote, len(data)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("port")
    ap.add_argument("files", nargs="+", help="local_path:/sd/... or local_path:/internal/...")
    ap.add_argument("--wait", type=float, default=180)
    a = ap.parse_args()
    port = a.port if a.port != "auto" else (glob.glob("/dev/cu.usbmodem*") or [None])[0]
    link = Link(port)
    t0 = time.time()
    hello = None
    while time.time() - t0 < a.wait:
        try:
            hello = link.request(T_HELLO, b"", timeout=1.5, tries=1)
            break
        except TimeoutError:
            pass
    if hello is None:
        sys.exit("USB Files did not answer -- open Apps > USB Files on the device")
    print("device:", hello[1:].decode(errors="replace"))
    for spec in a.files:
        local, remote = spec.split(":", 1)
        push(link, local, remote)


if __name__ == "__main__":
    main()
