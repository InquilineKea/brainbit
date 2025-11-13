#!/usr/bin/env python3
"""
Mendi BLE Scanner & Raw Stream Logger

Features:
- Scans for Mendi device (by name substring or direct address) and connects via Nordic UART service.
- Subscribes to RX characteristic (Mendi -> client) and streams notifications (~10 Hz typical).
- Parses payload as configurable frame formats:
  * --format f32: little-endian float32 pairs [red, ir] (default)
  * --format i16: little-endian int16 pairs [red, ir]
  * --frame-size: number of values per frame (2 for red+ir, 3 if includes timestamp)
- Logs to CSV with timestamps and prints per-second stats.
- Optional real-time plot of Red/IR channels.
- Optional MBLL conversion (experimental) to oxy/deoxy Hb changes.

Requirements:
  pip install bleak matplotlib numpy

Usage examples:
  python3 mendi_ble_scanner.py --name Mendi --csv mendi_log.csv
  python3 mendi_ble_scanner.py --mac AA:BB:CC:DD:EE:FF --format f32 --frame-size 2 --plot
  python3 mendi_ble_scanner.py --name Mendi --format i16 --mbll --plot

Notes:
- The exact payload layout may vary by firmware. If unsure, run with --hexdump 10 to inspect raw bytes.
- If frames contain timestamps, set --frame-size 3 and --ts-pos to the index of timestamp (0-based). Default assumes [red, ir] only.
- MBLL output uses assumed pathlength factor and differential processing; treat as qualitative unless calibrated.
"""

import argparse
import asyncio
import csv
import math
import signal
import struct
import sys
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, List, Optional, Tuple

import numpy as np

try:
    from bleak import BleakClient, BleakScanner
except ImportError as e:
    print("Error: bleak not installed. Install with: pip install bleak")
    sys.exit(1)

try:
    import matplotlib.pyplot as plt
    HAS_MPL = True
except Exception:
    HAS_MPL = False

# Nordic UART Service UUIDs (commonly used by Mendi)
NUS_SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
NUS_RX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"  # Notify: Peripheral -> Client


@dataclass
class ParseConfig:
    fmt: str  # 'f32' or 'i16'
    frame_vals: int  # number of values per frame (2 for red+ir, 3 if includes timestamp)
    endian: str  # '<' little-endian or '>' big-endian
    ts_pos: int  # index of timestamp value inside frame if present; -1 if none

    @property
    def bytes_per_value(self) -> int:
        return 4 if self.fmt == 'f32' else 2

    @property
    def struct_code(self) -> str:
        if self.fmt == 'f32':
            return self.endian + ('f' * self.frame_vals)
        elif self.fmt == 'i16':
            return self.endian + ('h' * self.frame_vals)
        raise ValueError("Unsupported format")


def mbll_convert(red: np.ndarray, ir: np.ndarray,
                 wavelengths_nm: Tuple[float, float] = (660.0, 850.0),
                 dpf: float = 5.5,
                 optode_distance_cm: float = 3.0) -> Tuple[np.ndarray, np.ndarray]:
    """
    Very simplified MBLL to estimate relative changes in oxy/deoxy-Hb.
    This is illustrative only and uses assumed extinction coefficients.

    Returns: (dHbO, dHbR), arrays same shape as inputs.
    """
    # Avoid log of zero; normalize by initial mean
    r0 = max(np.mean(red[:max(1, len(red)//10)]), 1e-9)
    i0 = max(np.mean(ir[:max(1, len(ir)//10)]), 1e-9)
    dr = -np.log(np.clip(red / r0, 1e-9, None))
    di = -np.log(np.clip(ir / i0, 1e-9, None))

    # Approximate extinction coefficients (arbitrary units)
    # In practice, use literature values; here we use a made-up matrix for demonstration.
    #   [eR_HbO  eR_HbR]
    #   [eI_HbO  eI_HbR]
    e = np.array([[0.8, 1.2],  # at 660 nm
                  [1.1, 0.9]]) # at 850 nm

    # Pathlength = DPF * distance
    L = dpf * (optode_distance_cm / 10.0)  # convert cm to meters scale; relative

    # Solve for concentrations via least squares: [dr, di] = e * [HbO, HbR] * L
    A = e * L
    pinv = np.linalg.pinv(A)
    out = np.vstack([dr, di])
    dHbO, dHbR = pinv @ out
    return dHbO, dHbR


class MendiStream:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.client: Optional[BleakClient] = None
        self.csv_file: Optional[csv.writer] = None
        self.csv_fh = None
        self.buffer: Deque[Tuple[float, float, float]] = deque(maxlen=10000)  # (t_sec, red, ir)
        self.parse_cfg = ParseConfig(
            fmt=args.format,
            frame_vals=args.frame_size,
            endian='<' if args.little_endian else '>',
            ts_pos=args.ts_pos,
        )
        self.hex_left = args.hexdump
        self.start_time = time.time()
        self.plot_initialized = False
        self.fig = None
        self.ax = None           # top axes: red/IR
        self.ax_mbll = None      # bottom axes: dHbO/dHbR (optional)
        self.lines = None        # (red, IR)
        self.lines_mbll = None   # (dHbO, dHbR)
        self.last_stats_ts = 0.0

    async def scan_and_connect(self) -> None:
        target = self.args.mac or self.args.name
        print(f"Scanning for device ({'MAC ' + self.args.mac if self.args.mac else 'name contains ' + repr(self.args.name)})…")
        devices = await BleakScanner.discover(timeout=self.args.scan_timeout)
        dev = None
        for d in devices:
            name = (d.name or '').strip()
            if self.args.mac and d.address.lower() == self.args.mac.lower():
                dev = d
                break
            if (not self.args.mac) and self.args.name and self.args.name.lower() in name.lower():
                dev = d
                break
        if dev is None:
            raise RuntimeError("Mendi device not found. Try --name 'Mendi' or --mac AA:BB:CC:DD:EE:FF, or increase --scan-timeout.")
        print(f"Found: {dev.name} [{dev.address}] RSSI={getattr(dev, 'rssi', '?')}")

        self.client = BleakClient(dev.address)
        await self.client.connect(timeout=20.0)
        print("Connected. Discovering services…")
        svcs = self.client.services  # Bleak 1.0 API
        svc = svcs.get_service(self.args.service_uuid or NUS_SERVICE_UUID)
        if svc is None:
            raise RuntimeError(f"Service {self.args.service_uuid or NUS_SERVICE_UUID} not found on device")
        rx_char = svc.get_characteristic(self.args.rx_uuid or NUS_RX_CHAR_UUID)
        if rx_char is None:
            raise RuntimeError(f"RX characteristic {self.args.rx_uuid or NUS_RX_CHAR_UUID} not found")
        print(f"Subscribing to RX notifications: {rx_char.uuid}")

        await self.client.start_notify(rx_char.uuid, self.on_notification)

    def _open_csv(self):
        if self.args.csv:
            self.csv_fh = open(self.args.csv, 'w', newline='')
            self.csv_file = csv.writer(self.csv_fh)
            header = ['timestamp_iso', 't_rel_s', 'red', 'ir']
            if self.args.mbll:
                header += ['dHbO', 'dHbR']
            self.csv_file.writerow(header)
            self.csv_fh.flush()
            print(f"Logging to {self.args.csv}")

    def close(self):
        try:
            if self.client and self.client.is_connected:
                asyncio.create_task(self.client.disconnect())
        except Exception:
            pass
        try:
            if self.csv_fh:
                self.csv_fh.close()
        except Exception:
            pass

    def parse_frames(self, data: bytes) -> List[Tuple[float, float]]:
        """
        Parse byte payload into a list of (red, ir) pairs.
        Assumes a fixed-size frame with frame_vals values per frame.
        If ts_pos >= 0, timestamp value is ignored (we use local time).
        """
        bpv = self.parse_cfg.bytes_per_value
        frame_bytes = self.parse_cfg.frame_vals * bpv
        nframes = len(data) // frame_bytes
        out: List[Tuple[float, float]] = []
        if nframes <= 0:
            return out
        try:
            s = struct.Struct(self.parse_cfg.struct_code)
            for i in range(nframes):
                chunk = data[i*frame_bytes:(i+1)*frame_bytes]
                vals = s.unpack(chunk)
                # pick red/ir positions
                if self.parse_cfg.ts_pos == 0:
                    red, ir = vals[1], vals[2] if self.parse_cfg.frame_vals > 2 else (vals[1], float('nan'))
                elif self.parse_cfg.ts_pos == 1:
                    red, ir = vals[0], vals[2] if self.parse_cfg.frame_vals > 2 else (vals[0], float('nan'))
                elif self.parse_cfg.ts_pos == 2:
                    red, ir = vals[0], vals[1]
                else:
                    # assume [red, ir, (ts?)]
                    red, ir = vals[0], vals[1]
                out.append((float(red), float(ir)))
        except Exception as e:
            # Fallback: try two-value frames even if sizes mismatch
            try:
                s2 = struct.Struct(self.parse_cfg.endian + ('f' if self.parse_cfg.fmt=='f32' else 'h')*2)
                frame_bytes2 = 2 * self.parse_cfg.bytes_per_value
                n2 = len(data) // frame_bytes2
                for i in range(n2):
                    vals = s2.unpack(data[i*frame_bytes2:(i+1)*frame_bytes2])
                    out.append((float(vals[0]), float(vals[1])))
            except Exception:
                if self.hex_left > 0:
                    self.hex_left -= 1
                    print(f"Unparsed payload ({len(data)} B): "+data.hex())
        return out

    def on_notification(self, _handle: int, data: bytes):
        now = time.time()
        if self.hex_left > 0:
            self.hex_left -= 1
            print(f"RX[{len(data)}]: {data.hex()}")
        frames = self.parse_frames(data)
        if not frames:
            return
        for red, ir in frames:
            t_rel = now - self.start_time
            self.buffer.append((t_rel, red, ir))
            if self.csv_file:
                row = [time.strftime('%Y-%m-%d %H:%M:%S'), f"{t_rel:.3f}", f"{red:.6f}", f"{ir:.6f}"]
                if self.args.mbll:
                    try:
                        # Use last ~3s for normalization context
                        arr = np.array(list(self.buffer))
                        red_series = arr[-min(3*10, len(arr)):, 1]  # approximate 10 Hz
                        ir_series  = arr[-min(3*10, len(arr)):, 2]
                        dHbO, dHbR = mbll_convert(red_series, ir_series)
                        row += [f"{dHbO[-1]:.6f}", f"{dHbR[-1]:.6f}"]
                    except Exception:
                        row += ["", ""]
                self.csv_file.writerow(row)
                if self.csv_fh:
                    self.csv_fh.flush()

        # Stats once per second
        if now - self.last_stats_ts >= 1.0:
            self.last_stats_ts = now
            arr = np.array(list(self.buffer))
            if arr.size > 0:
                red_uv = arr[:,1]
                ir_uv  = arr[:,2]
                print(f"t={arr[-1,0]:.1f}s | red mean={np.mean(red_uv):.3f} std={np.std(red_uv):.3f} | ir mean={np.mean(ir_uv):.3f} std={np.std(ir_uv):.3f} | n={len(arr)}")
            if self.args.plot and HAS_MPL:
                self._update_plot()

    def _init_plot(self):
        if not HAS_MPL:
            print("matplotlib not available; plotting disabled")
            return
        if self.args.mbll:
            self.fig, (self.ax, self.ax_mbll) = plt.subplots(2, 1, figsize=(9,6), sharex=True)
        else:
            self.fig, self.ax = plt.subplots(figsize=(9,4))

        self.ax.set_title("Mendi raw (red/IR)")
        self.ax.set_xlabel("t (s)")
        self.ax.set_ylabel("a.u.")
        (l1,) = self.ax.plot([], [], label='red')
        (l2,) = self.ax.plot([], [], label='IR')
        self.ax.legend(loc='upper right')
        self.lines = (l1, l2)

        if self.args.mbll:
            self.ax_mbll.set_title("MBLL (relative) dHbO/dHbR")
            self.ax_mbll.set_xlabel("t (s)")
            self.ax_mbll.set_ylabel("arb.")
            (m1,) = self.ax_mbll.plot([], [], label='dHbO')
            (m2,) = self.ax_mbll.plot([], [], label='dHbR')
            self.ax_mbll.legend(loc='upper right')
            self.lines_mbll = (m1, m2)
        self.plot_initialized = True

    def _update_plot(self):
        if not self.plot_initialized:
            self._init_plot()
        if not self.plot_initialized:
            return
        arr = np.array(list(self.buffer))
        if arr.size == 0:
            return
        t = arr[:,0]
        red = arr[:,1]
        ir = arr[:,2]
        # Keep last N seconds
        mask = t > (t[-1] - self.args.plot_window)
        t = t[mask]; red = red[mask]; ir = ir[mask]
        self.lines[0].set_data(t, red)
        self.lines[1].set_data(t, ir)
        self.ax.relim(); self.ax.autoscale_view()

        # Update MBLL subplot if enabled
        if self.args.mbll and self.lines_mbll is not None and len(t) > 10:
            try:
                dHbO, dHbR = mbll_convert(red, ir)
                tt = t
                self.lines_mbll[0].set_data(tt, dHbO)
                self.lines_mbll[1].set_data(tt, dHbR)
                self.ax_mbll.relim(); self.ax_mbll.autoscale_view()
            except Exception:
                pass
        self.fig.canvas.draw_idle()
        plt.pause(0.001)


async def run(args: argparse.Namespace):
    stream = MendiStream(args)
    stream._open_csv()

    def handle_sigint(*_):
        print("\nStopping…")
        stream.close()
        try:
            loop = asyncio.get_event_loop()
            loop.stop()
        except Exception:
            pass

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, handle_sigint)
        except Exception:
            pass

    try:
        await stream.scan_and_connect()
        print("Streaming; press Ctrl+C to stop.")
        # Keep alive
        while True:
            await asyncio.sleep(1.0)
    finally:
        stream.close()


def main():
    p = argparse.ArgumentParser(description="Mendi BLE scanner and raw logger (Nordic UART)")
    p.add_argument('--name', default='Mendi', help="Device name substring to match (default: 'Mendi')")
    p.add_argument('--mac', default='', help='Device MAC/address to connect (overrides --name)')
    p.add_argument('--service-uuid', default=NUS_SERVICE_UUID, help='Service UUID (default: Nordic UART)')
    p.add_argument('--rx-uuid', default=NUS_RX_CHAR_UUID, help='RX characteristic UUID (notify)')
    p.add_argument('--scan-timeout', type=int, default=8, help='BLE scan timeout seconds')
    p.add_argument('--format', choices=['f32', 'i16'], default='f32', help='Payload data format per value')
    p.add_argument('--frame-size', type=int, default=2, help='Values per frame (2 for [red,ir], 3 if timestamp included)')
    p.add_argument('--ts-pos', type=int, default=-1, help='Index of timestamp value in frame (0-based), -1 if none')
    p.add_argument('--little-endian', action='store_true', default=True, help='Assume little-endian values (default)')
    p.add_argument('--csv', default='mendi_log.csv', help='CSV output file')
    p.add_argument('--hexdump', type=int, default=5, help='Print hex of the first N notifications to inspect payload')
    p.add_argument('--plot', action='store_true', help='Enable real-time plot (matplotlib)')
    p.add_argument('--plot-window', type=float, default=60.0, help='Seconds of data to show when plotting')
    p.add_argument('--mbll', action='store_true', help='Compute MBLL oxy/deoxy estimates (experimental)')
    args = p.parse_args()

    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
