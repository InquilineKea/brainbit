#!/usr/bin/env python3
import asyncio
import argparse
import time
import threading
from collections import deque
from datetime import datetime
import struct

import numpy as np
from bleak import BleakScanner, BleakClient
import matplotlib.pyplot as plt
from matplotlib.widgets import Button

DEFAULT_SERVICE = "fc3eabb0-c6c4-49e6-922a-6e551c455af5"
DEFAULT_RX = "fc3eabb1-c6c4-49e6-922a-6e551c455af5"
DEFAULT_STATUS = "fc3eabb4-c6c4-49e6-922a-6e551c455af5"

# ---------- Simple MBLL (relative) ----------
def mbll(red, ir, eps=1e-9):
    red = np.asarray(red, dtype=float)
    ir = np.asarray(ir, dtype=float)
    if red.size < 5:
        return np.zeros_like(red), np.zeros_like(ir)
    # Ensure strictly positive signals for logarithm
    rmin = np.min(red)
    imin = np.min(ir)
    if not np.isfinite(rmin):
        rmin = 0.0
    if not np.isfinite(imin):
        imin = 0.0
    if rmin <= 0:
        red = red - rmin + eps
    if imin <= 0:
        ir = ir - imin + eps
    # Baseline as median of initial 3 s
    n = red.size
    base_n = max(10, min(n//5, 500))
    R0 = np.median(red[:base_n])
    I0 = np.median(ir[:base_n])
    dOD_r = -np.log((red+eps)/(R0+eps))
    dOD_i = -np.log((ir+eps)/(I0+eps))
    # Toy separation into dHbO/dHbR by simple mixing (no extinction coefficients used)
    dHbO = dOD_i - 0.5*dOD_r
    dHbR = dOD_r - 0.5*dOD_i
    return dHbO, dHbR

# ---------- Parser ----------
class FrameParser:
    def __init__(self, fmt: str = "f32", i16_unsigned: bool = False):
        self.fmt = fmt  # 'f32' or 'i16'
        self.i16_unsigned = i16_unsigned

    def parse_notification(self, data: bytes):
        # Try to parse as pairs of (red, ir)
        if self.fmt == 'f32':
            if len(data) % 8 == 0:
                arr = np.frombuffer(data, dtype='<f4')
                if arr.size % 2 == 0:
                    arr = arr.reshape(-1, 2)
                    return arr[:, 0], arr[:, 1]
        elif self.fmt == 'i16':
            if len(data) % 4 == 0:
                dtype = '<u2' if self.i16_unsigned else '<i2'
                arr = np.frombuffer(data, dtype=dtype)
                if arr.size % 2 == 0:
                    arr = arr.reshape(-1, 2).astype(float)
                    return arr[:, 0], arr[:, 1]
        # Heuristic fallback: try to strip a 1 byte header and retry
        if len(data) > 1:
            try:
                r, i = self.parse_notification(data[1:])
                return r, i
            except Exception:
                pass
        return np.array([]), np.array([])

# ---------- BLE + Plot ----------
class FNIRSViewer:
    def __init__(self, args):
        self.args = args
        self.parser = FrameParser(args.format, getattr(args, 'i16_unsigned', False))
        self.addr = None
        self.client: BleakClient | None = None
        self.stop_event = threading.Event()

        # Buffers (seconds window)
        self.win_sec = args.window
        self.ts = deque(maxlen=50000)
        self.red = deque(maxlen=50000)
        self.ir = deque(maxlen=50000)
        self.lock = threading.Lock()
        self.t0 = None

        # matplotlib
        self.fig = None
        self.ax_red = None
        self.ax_ir = None
        self.ax_mbll = None
        self.ax_status = None
        self.l_red = None
        self.l_ir = None
        self.l_hbo = None
        self.l_hbr = None
        self.l_status = None
        # Status buffers
        self.status_t = deque(maxlen=50000)
        self.status_v = deque(maxlen=50000)
        self.txt_raw = None
        self.txt_mbll = None
        self.last_stats_time = 0.0
        self.last_sample_count = 0
        self.total_samples = 0
        self.total_notifs = 0
        self.last_notif_count = 0
        # Stats logging
        self.stats_fh = None
        try:
            if self.args.stats_log:
                self.stats_fh = open(self.args.stats_log, 'a')
                self.stats_fh.write(f"# FNIRS session start {datetime.utcnow().isoformat()}Z\n")
                self.stats_fh.write("# columns: t_rel, sr, nr, red_mean, red_std, red_min, red_max, ir_mean, ir_std, ir_min, ir_max, red_slope, ir_slope, mbll_hbo_mean, mbll_hbo_std, mbll_hbr_mean, mbll_hbr_std, hbo_slope, hbr_slope, red_delta_mean, ir_delta_mean, hr_bpm\n")
                self.stats_fh.flush()
        except Exception:
            pass

        # HRV logging
        self.hrv_fh = None
        self.last_hr_peak_t = None  # absolute time relative to t0
        try:
            if getattr(self.args, 'hrv_log', None):
                if self.args.hrv_log:
                    self.hrv_fh = open(self.args.hrv_log, 'a')
                    self.hrv_fh.write(f"# HRV session start {datetime.utcnow().isoformat()}Z\n")
                    self.hrv_fh.write("# columns: t_peak, rr, bpm\n")
        except Exception:
            pass

    # ---- BLE ----
    async def discover_address(self):
        if self.args.mac:
            self.addr = self.args.mac
            return
        print("Scanning 8s for Mendi…")
        devices = await BleakScanner.discover(timeout=8.0)
        for d in devices:
            if (d.name or '').lower().startswith('mendi'):
                self.addr = d.address
                print(f"Found Mendi: {d.address}")
                return
        # fallback: just pick device advertising the service
        target = self.args.service_uuid.lower()
        for d in devices:
            adv = getattr(d, 'metadata', {}).get('uuids') or []
            if any((u or '').lower() == target for u in adv):
                self.addr = d.address
                print(f"Found by service: {d.address}")
                return
        raise RuntimeError("Mendi not found. Use --mac.")

    async def ble_task(self):
        await self.discover_address()
        print(f"Connecting to {self.addr}…")
        async with BleakClient(self.addr, timeout=20.0) as client:
            self.client = client
            print("Connected.")
            # Verify service exists
            svcs = client.services
            if not svcs.get_service(self.args.service_uuid):
                print("Warning: specified service not in service list.")
            # Start notify
            def cb(_h, data: bytes):
                r, i = self.parser.parse_notification(data)
                # Debug: print first few raw packets
                if self.total_notifs < 5:
                    print(f"RAW notif[{self.total_notifs}] len={len(data)} hex={data.hex()[:120]}…")
                self.total_notifs += 1
                if r.size == 0:
                    return
                now = time.time()
                with self.lock:
                    if self.t0 is None:
                        self.t0 = now
                    for rr, ii in zip(r, i):
                        t_rel = now - self.t0
                        self.ts.append(t_rel)
                        self.red.append(float(rr))
                        self.ir.append(float(ii))
                        self.total_samples += 1
            await client.start_notify(self.args.rx_uuid, cb)

            # Optional status notify (e.g., 3-byte heartbeat)
            def cb_status(_h, data: bytes):
                now = time.time()
                with self.lock:
                    if self.t0 is None:
                        self.t0 = now
                    t_rel = now - self.t0
                    # Interpret as little-endian 16-bit from last two bytes if length>=2
                    val = int.from_bytes(data[-2:], 'little', signed=False) if len(data)>=2 else data[0]
                    self.status_t.append(t_rel)
                    self.status_v.append(val)
            try:
                if self.args.status_uuid:
                    await client.start_notify(self.args.status_uuid, cb_status)
                    print(f"Subscribed status {self.args.status_uuid}")
            except Exception as e:
                print(f"Status subscribe failed: {e}")
            print("Subscribed; receiving… Press Ctrl+C to quit.")
            while not self.stop_event.is_set():
                await asyncio.sleep(0.1)
            try:
                await client.stop_notify(self.args.rx_uuid)
            except Exception:
                pass
            try:
                if self.args.status_uuid:
                    await client.stop_notify(self.args.status_uuid)
            except Exception:
                pass

    # ---- Plot ----
    def init_plot(self):
        self.fig, (self.ax_red, self.ax_ir, self.ax_mbll, self.ax_status) = plt.subplots(4, 1, figsize=(10, 9), sharex=True)
        # Red
        self.ax_red.set_title('Mendi fNIRS Raw - Red')
        self.ax_red.set_ylabel('a.u.')
        (self.l_red,) = self.ax_red.plot([], [], label='Red', color='tab:red')
        self.ax_red.legend(loc='upper right')
        # IR
        self.ax_ir.set_title('Mendi fNIRS Raw - IR')
        self.ax_ir.set_ylabel('a.u.')
        (self.l_ir,) = self.ax_ir.plot([], [], label='IR', color='tab:blue')
        self.ax_ir.legend(loc='upper right')

        self.ax_mbll.set_title('MBLL (relative) dHbO / dHbR')
        self.ax_mbll.set_xlabel('Time (s)')
        self.ax_mbll.set_ylabel('arb.')
        (self.l_hbo,) = self.ax_mbll.plot([], [], label='dHbO')
        (self.l_hbr,) = self.ax_mbll.plot([], [], label='dHbR')
        self.ax_mbll.legend(loc='upper right')

        # Status axis
        self.ax_status.set_title('Status/Heartbeat (from status UUID)')
        self.ax_status.set_xlabel('Time (s)')
        self.ax_status.set_ylabel('value')
        (self.l_status,) = self.ax_status.plot([], [], label='status')
        self.ax_status.legend(loc='upper right')

        # Overlay text placeholders
        self.txt_raw = self.ax_red.text(0.01, 0.95, '', transform=self.ax_red.transAxes,
                                        va='top', ha='left', fontsize=9,
                                        bbox=dict(boxstyle='round', facecolor='white', alpha=0.6))
        self.txt_mbll = self.ax_mbll.text(0.01, 0.95, '', transform=self.ax_mbll.transAxes,
                                          va='top', ha='left', fontsize=9,
                                          bbox=dict(boxstyle='round', facecolor='white', alpha=0.6))

        # Reset Zoom button
        ax_btn = self.fig.add_axes([0.82, 0.94, 0.15, 0.05])
        self.btn = Button(ax_btn, 'Reset Zoom')
        self.btn.on_clicked(lambda _evt: self.reset_zoom())

        # Scroll zoom
        self.fig.canvas.mpl_connect('scroll_event', self.on_scroll)

    def on_scroll(self, event):
        # Zoom all axes horizontally around cursor
        for ax in (self.ax_red, self.ax_ir, self.ax_mbll, self.ax_status):
            xlim = ax.get_xlim()
            xdata = event.xdata if event.xdata is not None else sum(xlim)/2
            scale = 0.9 if event.button == 'up' else 1.1
            new_w = (xlim[1]-xlim[0]) * scale
            cx = xdata
            ax.set_xlim(cx - new_w/2, cx + new_w/2)
        self.fig.canvas.draw_idle()

    def reset_zoom(self):
        # Auto-scale next update
        self.ax_red.relim(); self.ax_red.autoscale_view()
        self.ax_ir.relim(); self.ax_ir.autoscale_view()
        self.ax_mbll.relim(); self.ax_mbll.autoscale_view()
        self.ax_status.relim(); self.ax_status.autoscale_view()
        self.fig.canvas.draw_idle()

    def update_plot(self):
        with self.lock:
            if len(self.ts) == 0:
                return
            t = np.asarray(self.ts)
            r = np.asarray(self.red)
            i = np.asarray(self.ir)
        # Window last N seconds
        tmax = t[-1]
        mask = t > (tmax - self.win_sec)
        t = t[mask]; r = r[mask]; i = i[mask]
        # Estimate sampling rate over recent window
        dt = np.diff(t)
        fs = 1.0/np.median(dt[-int(min(50, dt.size)) :]) if dt.size else 0.0
        # Optional smoothing for display (moving average)
        def smooth_ma(y, fs, win_s):
            if win_s is None or win_s <= 0 or fs <= 0 or y.size < 3:
                return y
            k = max(1, int(round(win_s * fs)))
            k = min(k, y.size)
            if k <= 1:
                return y
            kernel = np.ones(k, dtype=float) / k
            return np.convolve(y, kernel, mode='same')
        # Optional exponential moving average (single-pole IIR)
        def smooth_ema(y, fs, tau_s):
            if tau_s is None or tau_s <= 0 or fs <= 0 or y.size < 3:
                return y
            alpha = 1.0 - np.exp(-1.0/(tau_s*fs))
            out = np.empty_like(y, dtype=float)
            out[0] = y[0]
            for n in range(1, y.size):
                out[n] = alpha*y[n] + (1.0-alpha)*out[n-1]
            return out
        # Optional display downsampling by block averaging
        def downsample(t, y, fs, target_fs):
            if target_fs is None or target_fs <= 0 or fs <= 0:
                return t, y
            step = max(1, int(round(fs/target_fs)))
            if step <= 1 or y.size < step*2:
                return t, y
            N = (y.size // step) * step
            yb = y[:N].reshape(-1, step).mean(axis=1)
            tb = t[:N].reshape(-1, step)[:, -1]
            return tb, yb
        r_disp = r
        i_disp = i
        try:
            if getattr(self.args, 'smooth_raw', 0.0) and fs > 0:
                r_disp = smooth_ma(r_disp, fs, float(self.args.smooth_raw))
                i_disp = smooth_ma(i_disp, fs, float(self.args.smooth_raw))
            if getattr(self.args, 'ema_raw', 0.0) and fs > 0:
                r_disp = smooth_ema(r_disp, fs, float(self.args.ema_raw))
                i_disp = smooth_ema(i_disp, fs, float(self.args.ema_raw))
            # Downsample for display
            t_ds, r_disp = downsample(t, r_disp, fs, float(getattr(self.args, 'display_fs', 0.0)))
            _,    i_disp = downsample(t, i_disp, fs, float(getattr(self.args, 'display_fs', 0.0)))
        except Exception:
            t_ds = t
            pass
        else:
            t_ds = t_ds
        if 't_ds' not in locals():
            t_ds = t
        # Optionally plot only per-interval means
        if getattr(self.args, 'means_only', False):
            try:
                bin_s = float(getattr(self.args, 'means_interval', 1.0)) or 1.0
                if getattr(self.args, 'means_rolling', False) and fs > 0:
                    # Rolling mean with window = means_interval seconds
                    k = max(1, int(round(bin_s * fs)))
                    k = min(k, max(3, r_disp.size))
                    kernel = np.ones(k, dtype=float) / k
                    r_mu = np.convolve(r_disp, kernel, mode='same')
                    i_mu = np.convolve(i_disp, kernel, mode='same')
                    self.l_red.set_data(t_ds, r_mu)
                    self.l_ir.set_data(t_ds, i_mu)
                else:
                    # Discrete bin means (e.g., every 1 s)
                    t0 = t_ds[0]
                    bins = np.floor((t_ds - t0) / bin_s).astype(int)
                    uniq = np.unique(bins)
                    tb = np.array([t0 + (b+1)*bin_s for b in uniq])
                    r_disp = np.array([np.nanmean(r_disp[bins==b]) for b in uniq])
                    i_disp = np.array([np.nanmean(i_disp[bins==b]) for b in uniq])
                    self.l_red.set_data(tb, r_disp)
                    self.l_ir.set_data(tb, i_disp)
            except Exception:
                self.l_red.set_data(t_ds, r_disp)
                self.l_ir.set_data(t_ds, i_disp)
        else:
            self.l_red.set_data(t_ds, r_disp)
            self.l_ir.set_data(t_ds, i_disp)
        if getattr(self.args, 'robust_scale', False):
            try:
                pr = np.nanpercentile(r_disp, [2, 98])
                pi = np.nanpercentile(i_disp, [2, 98])
                mr = (pr[1]-pr[0]) * 0.05
                mi = (pi[1]-pi[0]) * 0.05
                self.ax_red.set_ylim(pr[0]-mr, pr[1]+mr)
                self.ax_ir.set_ylim(pi[0]-mi, pi[1]+mi)
            except Exception:
                self.ax_red.relim(); self.ax_red.autoscale_view()
                self.ax_ir.relim(); self.ax_ir.autoscale_view()
        else:
            self.ax_red.relim(); self.ax_red.autoscale_view()
            self.ax_ir.relim(); self.ax_ir.autoscale_view()
        # MBLL
        if t.size >= 20:
            dHbO, dHbR = mbll(r, i)
            # Optional smoothing for MBLL display
            try:
                if getattr(self.args, 'smooth_mbll', 0.0) and fs > 0:
                    dHbO = smooth_ma(dHbO, fs, float(self.args.smooth_mbll))
                    dHbR = smooth_ma(dHbR, fs, float(self.args.smooth_mbll))
                if getattr(self.args, 'ema_mbll', 0.0) and fs > 0:
                    dHbO = smooth_ema(dHbO, fs, float(self.args.ema_mbll))
                    dHbR = smooth_ema(dHbR, fs, float(self.args.ema_mbll))
                # Downsample for display
                t_m, dHbO = downsample(t, dHbO, fs, float(getattr(self.args, 'display_fs', 0.0)))
                _,   dHbR = downsample(t, dHbR, fs, float(getattr(self.args, 'display_fs', 0.0)))
            except Exception:
                t_m = t
            if getattr(self.args, 'means_only', False):
                try:
                    bin_s = float(getattr(self.args, 'means_interval', 1.0)) or 1.0
                    if getattr(self.args, 'means_rolling', False) and fs > 0:
                        k = max(1, int(round(bin_s * fs)))
                        k = min(k, max(3, dHbO.size))
                        kernel = np.ones(k, dtype=float) / k
                        dHbO_mu = np.convolve(dHbO, kernel, mode='same')
                        dHbR_mu = np.convolve(dHbR, kernel, mode='same')
                        self.l_hbo.set_data(t_m, dHbO_mu)
                        self.l_hbr.set_data(t_m, dHbR_mu)
                    else:
                        t0m = t_m[0]
                        binsm = np.floor((t_m - t0m) / bin_s).astype(int)
                        uniqm = np.unique(binsm)
                        tm = np.array([t0m + (b+1)*bin_s for b in uniqm])
                        dHbO = np.array([np.nanmean(dHbO[binsm==b]) for b in uniqm])
                        dHbR = np.array([np.nanmean(dHbR[binsm==b]) for b in uniqm])
                        self.l_hbo.set_data(tm, dHbO)
                        self.l_hbr.set_data(tm, dHbR)
                except Exception:
                    self.l_hbo.set_data(t_m, dHbO)
                    self.l_hbr.set_data(t_m, dHbR)
            else:
                self.l_hbo.set_data(t_m, dHbO)
                self.l_hbr.set_data(t_m, dHbR)
            if getattr(self.args, 'robust_scale', False):
                try:
                    pm = np.nanpercentile(np.concatenate([dHbO, dHbR]), [2, 98])
                    mm = (pm[1]-pm[0]) * 0.05
                    self.ax_mbll.set_ylim(pm[0]-mm, pm[1]+mm)
                except Exception:
                    self.ax_mbll.relim(); self.ax_mbll.autoscale_view()
            else:
                self.ax_mbll.relim(); self.ax_mbll.autoscale_view()

        # Status trace: pull latest from buffers
        with self.lock:
            st = np.asarray(self.status_t)
            sv = np.asarray(self.status_v)
        if st.size:
            # Window to last N seconds
            stmax = st[-1]
            smask = st > (stmax - self.win_sec)
            stw = st[smask]
            svw = sv[smask]
            self.l_status.set_data(stw, svw)
            self.ax_status.relim(); self.ax_status.autoscale_view()

        # Console + file stats once per second and on-plot overlay
        now = time.time()
        if now - self.last_stats_time >= 1.0:
            self.last_stats_time = now
            sr = (self.total_samples - self.last_sample_count) / 1.0
            nr = (self.total_notifs - self.last_notif_count) / 1.0
            self.last_sample_count = self.total_samples
            self.last_notif_count = self.total_notifs
            r_mean, r_std = float(np.mean(r)) if r.size else 0.0, float(np.std(r)) if r.size else 0.0
            i_mean, i_std = float(np.mean(i)) if i.size else 0.0, float(np.std(i)) if i.size else 0.0
            r_min, r_max = (float(np.min(r)) if r.size else 0.0, float(np.max(r)) if r.size else 0.0)
            i_min, i_max = (float(np.min(i)) if i.size else 0.0, float(np.max(i)) if i.size else 0.0)
            msg = f"SR ~ {sr:.1f} sps | NR ~ {nr:.1f} nps | Red μ={r_mean:.2f} σ={r_std:.2f} | IR μ={i_mean:.2f} σ={i_std:.2f}"
            print(msg)
            if self.txt_raw:
                self.txt_raw.set_text(msg)
            # Compute 20 s slope (simple linear fit) and deltas
            def slope_of(x, y):
                if x.size < 5: return 0.0
                xw = x - x[0]
                try:
                    m, c = np.polyfit(xw, y, 1)
                except Exception:
                    m = 0.0
                return float(m)
            win = 20.0
            tmask = t > (t[-1] - win)
            red_slope = slope_of(t[tmask], r[tmask]) if tmask.any() else 0.0
            ir_slope = slope_of(t[tmask], i[tmask]) if tmask.any() else 0.0
            # Session baseline deltas relative to first values
            red_delta_mean = r_mean - float(r[0]) if r.size else 0.0
            ir_delta_mean = i_mean - float(i[0]) if i.size else 0.0

            if t.size >= 20:
                hbo_mean, hbo_std = float(np.mean(dHbO)), float(np.std(dHbO))
                hbr_mean, hbr_std = float(np.mean(dHbR)), float(np.std(dHbR))
                # Heart rate estimation from IR over last window
                hr_bpm = 0.0
                new_rr_rows = []
                try:
                    dt = np.diff(t)
                    fs = 1.0/np.median(dt[-int(min(50, dt.size)) :]) if dt.size else 0.0
                    win = float(self.args.hr_win)
                    mask = t > (t[-1] - win)
                    tw = t[mask]
                    iw = i[mask]
                    if tw.size > max(10, int(2*fs)) and fs > 0:
                        # Detrend: subtract 1 s moving average
                        n_ma = max(1, int(fs*1.0))
                        csum = np.cumsum(np.insert(iw, 0, 0.0))
                        ma = (csum[n_ma:] - csum[:-n_ma]) / n_ma
                        # Pad to original length
                        pad = np.full(n_ma-1, ma[0]) if ma.size else np.zeros(0)
                        ma_full = np.concatenate([pad, ma]) if ma.size else np.zeros_like(iw)
                        hp = iw - ma_full
                        # Smooth with 0.12 s moving average
                        n_sm = max(1, int(fs*0.12))
                        csum2 = np.cumsum(np.insert(hp, 0, 0.0))
                        sm = (csum2[n_sm:] - csum2[:-n_sm]) / n_sm
                        pad2 = np.full(n_sm-1, sm[0]) if sm.size else np.zeros(0)
                        sm_full = np.concatenate([pad2, sm]) if sm.size else hp
                        z = (sm_full - np.mean(sm_full)) / (np.std(sm_full) + 1e-9)
                        # Peak detection with refractory 0.4 s and threshold 0.8
                        min_dist = max(1, int(float(self.args.hr_refrac)*fs))
                        peaks = []
                        thresh = float(self.args.hr_thresh)
                        for k in range(1, z.size-1):
                            if z[k] > thresh and z[k] >= z[k-1] and z[k] >= z[k+1]:
                                if not peaks or (k - peaks[-1]) >= min_dist:
                                    peaks.append(k)
                        if len(peaks) >= 2:
                            ti = tw[peaks]
                            pv = z[peaks]
                            # SNR proxy: median peak z
                            snr_proxy = float(np.median(pv))
                            rr = np.diff(ti)
                            rr = rr[(rr > float(self.args.rr_min)) & (rr < float(self.args.rr_max))]
                            if rr.size and snr_proxy >= float(self.args.hr_snr_min):
                                hr_bpm = float(60.0 / np.median(rr))
                                # Prepare per-beat logs, avoiding duplicates
                                for idx in range(1, len(ti)):
                                    rr_i = float(ti[idx] - ti[idx-1])
                                    if rr_i <= 0: continue
                                    if rr_i < float(self.args.rr_min) or rr_i > float(self.args.rr_max):
                                        continue
                                    t_peak = float(ti[idx])
                                    if self.last_hr_peak_t is not None and t_peak <= self.last_hr_peak_t:
                                        continue
                                    bpm_i = 60.0/rr_i
                                    new_rr_rows.append((t_peak, rr_i, bpm_i))
                                if len(ti):
                                    self.last_hr_peak_t = float(ti[-1])
                except Exception:
                    hr_bpm = 0.0

                msg2 = f"dHbO μ={hbo_mean:.3f} σ={hbo_std:.3f} | dHbR μ={hbr_mean:.3f} σ={hbr_std:.3f} | HR ~ {hr_bpm:.1f} bpm"
                if self.txt_mbll:
                    self.txt_mbll.set_text(msg2)
                hbo_slope = slope_of(t[tmask], dHbO[tmask]) if tmask.any() else 0.0
                hbr_slope = slope_of(t[tmask], dHbR[tmask]) if tmask.any() else 0.0
            else:
                hbo_mean=hbo_std=hbr_mean=hbr_std=hbo_slope=hbr_slope=0.0
                hr_bpm = 0.0

            # Flat signal heuristic -> guidance
            if self.args.format == 'f32' and r_std < 1e-6 and i_std < 1e-6 and r.size > 50:
                print("Warning: signals look flat with f32 parsing. Try relaunching with --format i16.")

            # Write stats line to file
            if self.stats_fh:
                try:
                    line = [
                        f"{t[-1]:.3f}", f"{sr:.3f}", f"{nr:.3f}",
                        f"{r_mean:.6f}", f"{r_std:.6f}", f"{r_min:.6f}", f"{r_max:.6f}",
                        f"{i_mean:.6f}", f"{i_std:.6f}", f"{i_min:.6f}", f"{i_max:.6f}",
                        f"{red_slope:.6f}", f"{ir_slope:.6f}",
                        f"{hbo_mean:.6f}", f"{hbo_std:.6f}", f"{hbr_mean:.6f}", f"{hbr_std:.6f}",
                        f"{hbo_slope:.6f}", f"{hbr_slope:.6f}",
                        f"{red_delta_mean:.6f}", f"{ir_delta_mean:.6f}",
                        f"{hr_bpm:.3f}",
                    ]
                    self.stats_fh.write(",".join(line) + "\n")
                    self.stats_fh.flush()
                except Exception:
                    pass

            # Write HRV per-beat rows
            if self.hrv_fh and new_rr_rows:
                try:
                    for t_peak, rr_i, bpm_i in new_rr_rows:
                        self.hrv_fh.write(f"{t_peak:.3f},{rr_i:.3f},{bpm_i:.1f}\n")
                    self.hrv_fh.flush()
                except Exception:
                    pass
        self.fig.canvas.draw_idle()

    def run(self):
        # Start BLE in a thread
        loop = asyncio.new_event_loop()
        def ble_thread():
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.ble_task())
            except Exception as e:
                print("BLE error:", e)
            finally:
                try:
                    if loop.is_running():
                        loop.stop()
                except Exception:
                    pass
                loop.close()
        th = threading.Thread(target=ble_thread, daemon=True)
        th.start()

        # Plot loop
        self.init_plot()
        try:
            while th.is_alive():
                self.update_plot()
                plt.pause(0.05)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop_event.set()
            try:
                plt.close(self.fig)
            except Exception:
                pass
            # Close logs
            try:
                if self.stats_fh:
                    self.stats_fh.close()
            except Exception:
                pass
            try:
                if self.hrv_fh:
                    self.hrv_fh.close()
            except Exception:
                pass


def parse_args():
    p = argparse.ArgumentParser(description="Real-time Mendi fNIRS viewer (raw + MBLL)")
    p.add_argument('--mac', help='Device MAC/UUID (macOS UUID acceptable)')
    p.add_argument('--service-uuid', default=DEFAULT_SERVICE)
    p.add_argument('--rx-uuid', default=DEFAULT_RX)
    p.add_argument('--status-uuid', default=DEFAULT_STATUS, help='Optional status/heartbeat characteristic to visualize')
    p.add_argument('--format', choices=['f32','i16'], default='f32', help='Payload format per sample pair')
    p.add_argument('--window', type=float, default=30.0, help='Plot window (s)')
    p.add_argument('--stats-log', default='fnirs_stats.txt', help='Write per-second stats to this text file')
    p.add_argument('--i16-unsigned', action='store_true', help='When using --format i16, treat values as unsigned')
    # Display smoothing (seconds); 0 disables
    p.add_argument('--smooth-raw', type=float, default=0.0, help='Moving-average window (s) for raw Red/IR display')
    p.add_argument('--smooth-mbll', type=float, default=0.0, help='Moving-average window (s) for MBLL display')
    p.add_argument('--ema-raw', type=float, default=0.0, help='EMA time-constant (s) for raw Red/IR display')
    p.add_argument('--ema-mbll', type=float, default=0.0, help='EMA time-constant (s) for MBLL display')
    p.add_argument('--display-fs', type=float, default=0.0, help='Downsample display to this Hz (0 disables)')
    p.add_argument('--robust-scale', action='store_true', help='Use robust autoscale (2-98th percentile) for display')
    # Plot per-interval means instead of raw traces
    p.add_argument('--means-only', action='store_true', help='Plot only per-interval means (e.g., 1 s bins)')
    p.add_argument('--means-interval', type=float, default=1.0, help='Interval (s) for means-only plotting')
    p.add_argument('--means-rolling', action='store_true', help='Use rolling mean over means-interval for continuous real-time plotting')
    # Heart-rate estimation tuning
    p.add_argument('--hr-win', type=float, default=15.0, help='HR window (s) used for detection')
    p.add_argument('--hr-thresh', type=float, default=0.8, help='Z-threshold for peak detection')
    p.add_argument('--hr-refrac', type=float, default=0.4, help='Refractory period (s) between peaks')
    p.add_argument('--rr-min', type=float, default=0.35, help='Min RR interval (s) [~170 bpm]')
    p.add_argument('--rr-max', type=float, default=1.5, help='Max RR interval (s) [~40 bpm]')
    p.add_argument('--hr-snr-min', type=float, default=1.0, help='Minimum median peak z to accept HR')
    p.add_argument('--hrv-log', default='hrv_beats.txt', help='Write per-beat RR/BPM here (CSV)')
    return p.parse_args()

if __name__ == '__main__':
    args = parse_args()
    FNIRSViewer(args).run()
