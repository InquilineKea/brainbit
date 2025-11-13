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
class StatsViewer:
    def __init__(self, args):
        self.args = args
        self.parser = FrameParser(args.format, getattr(args, 'i16_unsigned', False))
        self.addr = None
        self.client = None
        self.stop_event = threading.Event()
        
        # Stats history
        self.history_size = args.history
        self.time_points = deque(maxlen=self.history_size)
        self.sr_history = deque(maxlen=self.history_size)
        self.nr_history = deque(maxlen=self.history_size)
        self.red_mean_history = deque(maxlen=self.history_size)
        self.red_std_history = deque(maxlen=self.history_size)
        self.ir_mean_history = deque(maxlen=self.history_size)
        self.ir_std_history = deque(maxlen=self.history_size)
        
        # Counters for stats
        self.total_samples = 0
        self.total_notifs = 0
        self.last_sample_count = 0
        self.last_notif_count = 0
        self.last_stats_time = time.time()
        
        # Data buffers
        self.ts = deque(maxlen=50000)
        self.red = deque(maxlen=50000)
        self.ir = deque(maxlen=50000)
        self.lock = threading.Lock()
        self.t0 = None
        
        # Stats logging
        self.stats_fh = None
        if args.stats_log:
            try:
                self.stats_fh = open(args.stats_log, 'w')
                self.stats_fh.write(f"# FNIRS session start {datetime.utcnow().isoformat()}Z\n")
                self.stats_fh.write("# columns: t_rel, sr, nr, red_mean, red_std, red_min, red_max, ir_mean, ir_std, ir_min, ir_max\n")
                self.stats_fh.flush()
            except Exception as e:
                print(f"Error opening stats log: {e}")
                self.stats_fh = None
    
    def init_plot(self):
        # Setup plot
        plt.style.use('dark_background')
        self.fig, self.axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True)
        plt.subplots_adjust(hspace=0.3)
        
        # Configure axes
        self.ax_sr = self.axes[0]
        self.ax_red = self.axes[1]  
        self.ax_ir = self.axes[2]
        self.ax_status = self.axes[3]
        
        # Setup lines
        empty_x = np.array([0])
        empty_y = np.array([0])
        
        self.ax_sr.set_title("Sample Rate (sps) & Notification Rate (nps)")
        self.l_sr, = self.ax_sr.plot(empty_x, empty_y, 'g-', linewidth=2, label='Sample Rate')
        self.l_nr, = self.ax_sr.plot(empty_x, empty_y, 'c--', linewidth=2, label='Notification Rate')
        self.ax_sr.legend(loc='upper right')
        
        self.ax_red.set_title("Red Channel Stats")
        self.l_red_mean, = self.ax_red.plot(empty_x, empty_y, 'r-', linewidth=2, label='Mean')
        self.l_red_std_up, = self.ax_red.plot(empty_x, empty_y, 'r:', linewidth=1, alpha=0.5, label='Mean + Std')
        self.l_red_std_down, = self.ax_red.plot(empty_x, empty_y, 'r:', linewidth=1, alpha=0.5, label='Mean - Std')
        self.ax_red.legend(loc='upper right')
        
        self.ax_ir.set_title("IR Channel Stats")
        self.l_ir_mean, = self.ax_ir.plot(empty_x, empty_y, 'y-', linewidth=2, label='Mean')
        self.l_ir_std_up, = self.ax_ir.plot(empty_x, empty_y, 'y:', linewidth=1, alpha=0.5, label='Mean + Std')
        self.l_ir_std_down, = self.ax_ir.plot(empty_x, empty_y, 'y:', linewidth=1, alpha=0.5, label='Mean - Std')
        self.ax_ir.legend(loc='upper right')
        
        # Status/connection indicator
        self.ax_status.set_title("Connection Status")
        self.status_t = deque(maxlen=50)
        self.status_v = deque(maxlen=50)
        self.l_status, = self.ax_status.plot(empty_x, empty_y, 'w-', linewidth=1)
        
        # Add a reset zoom button
        self.reset_btn_ax = plt.axes([0.81, 0.02, 0.1, 0.04])
        self.reset_btn = Button(self.reset_btn_ax, 'Reset Zoom')
        self.reset_btn.on_clicked(lambda event: self.reset_zoom())
        
        # Set axis properties
        for ax in self.axes:
            ax.grid(True, linestyle='--', alpha=0.7)
        
        plt.xlabel('Time (s)')
        self.ax_sr.set_ylim(0, 1000)  # Reasonable for sample rate
        
        # Enable zooming
        self.fig.canvas.toolbar.pan()  # Start in pan/zoom mode
        plt.tight_layout()
    
    def reset_zoom(self):
        for ax in self.axes:
            ax.relim()
            ax.autoscale_view()
        plt.draw()
    
    def update_plot(self):
        # Get stat history data
        x_data = list(self.time_points)
        if not x_data:
            return
        
        # Update sample rate/notification rate plot
        self.l_sr.set_data(x_data, list(self.sr_history))
        self.l_nr.set_data(x_data, list(self.nr_history))
        
        # Update Red channel stats
        red_mean = list(self.red_mean_history)
        red_std = list(self.red_std_history)
        self.l_red_mean.set_data(x_data, red_mean)
        self.l_red_std_up.set_data(x_data, [m + s for m, s in zip(red_mean, red_std)])
        self.l_red_std_down.set_data(x_data, [m - s for m, s in zip(red_mean, red_std)])
        
        # Update IR channel stats
        ir_mean = list(self.ir_mean_history)
        ir_std = list(self.ir_std_history)
        self.l_ir_mean.set_data(x_data, ir_mean)
        self.l_ir_std_up.set_data(x_data, [m + s for m, s in zip(ir_mean, ir_std)])
        self.l_ir_std_down.set_data(x_data, [m - s for m, s in zip(ir_mean, ir_std)])
        
        # Print buffer stats for debug
        with self.lock:
            red_size = len(self.red)
            ir_size = len(self.ir)
        print(f"Buffer sizes: Red={red_size}, IR={ir_size}")
        
        # Auto-scale with some padding
        for ax in self.axes:
            ax.relim()
            ax.autoscale_view()
        
        # Status trace: show heartbeat
        with self.lock:
            st = np.asarray(self.status_t)
            sv = np.asarray(self.status_v)
        if st.size:
            # Window to last N seconds
            stmax = st[-1] if st.size else 0
            win_sec = 10  # Show last 10 seconds of status
            smask = st > (stmax - win_sec)
            stw = st[smask]
            svw = sv[smask]
            self.l_status.set_data(stw, svw)
            self.ax_status.relim()
            self.ax_status.autoscale_view()
        
        # Set all axes to same x range (based on specified window)
        if x_data:
            latest = x_data[-1]
            for ax in self.axes:
                ax.set_xlim(latest - self.args.window, latest)
    
    def handle_notification(self, sender, data):
        now = time.time()
        if self.t0 is None:
            self.t0 = now
        
        t_rel = now - self.t0
        
        if sender == self.args.status_uuid:
            # Status/heartbeat notification - just record timing
            with self.lock:
                self.status_t.append(t_rel)
                self.status_v.append(1.0)  # Just a presence indicator
            return
        
        if sender == self.args.rx_uuid:
            # Debug raw notification
            print(f"RAW notif len={len(data)} hex={data[:20].hex()}...")
            
            # Process fNIRS data
            r, i = self.parser.parse_notification(data)
            n_samples = len(r)
            
            if n_samples:
                self.total_notifs += 1
                self.total_samples += n_samples
                
                # Print first few samples for debug
                if n_samples > 0:
                    print(f"Data received: {n_samples} samples. First: Red={r[0]}, IR={i[0]}")
                
                # Store in buffers
                with self.lock:
                    for j in range(n_samples):
                        self.ts.append(t_rel)
                        self.red.append(r[j])
                        self.ir.append(i[j])
    
    def run(self):
        # BLE thread
        def ble_thread():
            async def run_ble():
                # Scan for device if needed
                if not self.args.mac:
                    print("Scanning for Mendi device (up to 45s)...")
                    for attempt in range(9):
                        if self.stop_event.is_set():
                            return
                        devs = await BleakScanner.discover(timeout=5.0)
                        for d in devs:
                            name = (d.name or "").lower()
                            if "mendi" in name:
                                self.addr = d.address
                                print(f"Found: {d.name} [{self.addr}]")
                                break
                        if self.addr:
                            break
                        print("...still scanning")
                else:
                    self.addr = self.args.mac
                
                if not self.addr:
                    print("No Mendi device found. Please specify --mac directly.")
                    return
                
                print(f"Connecting to {self.addr}...")
                try:
                    async with BleakClient(self.addr) as client:
                        self.client = client
                        print("Connected.")
                        
                        # Subscribe to notifications
                        if self.args.status_uuid:
                            await client.start_notify(
                                self.args.status_uuid,
                                self.handle_notification
                            )
                            print(f"Subscribed status {self.args.status_uuid}")
                        
                        await client.start_notify(
                            self.args.rx_uuid,
                            self.handle_notification
                        )
                        print("Subscribed; receiving... Press Ctrl+C to quit.")
                        
                        # Keep connection alive until stopped
                        while not self.stop_event.is_set():
                            await asyncio.sleep(0.1)
                except Exception as e:
                    print(f"BLE error: {e}")
            
            # Create event loop for async BLE operations
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                loop.run_until_complete(run_ble())
            except Exception as e:
                print("BLE error:", e)
            finally:
                try:
                    if loop.is_running():
                        loop.stop()
                except Exception:
                    pass
                loop.close()
        
        # Start BLE thread
        th = threading.Thread(target=ble_thread, daemon=True)
        th.start()
        
        # Plot loop
        self.init_plot()
        try:
            while th.is_alive():
                # Update stats every second
                now = time.time()
                if now - self.last_stats_time >= 1.0:
                    self.last_stats_time = now
                    t_rel = now - self.t0 if self.t0 else 0
                    
                    # Calculate per-second stats
                    sr = (self.total_samples - self.last_sample_count) / 1.0
                    nr = (self.total_notifs - self.last_notif_count) / 1.0
                    self.last_sample_count = self.total_samples
                    self.last_notif_count = self.total_notifs
                    
                    # Get latest signal stats from buffer
                    with self.lock:
                        r = np.array(self.red)
                        i = np.array(self.ir)
                    
                    r_mean, r_std = float(np.mean(r)) if r.size else 0.0, float(np.std(r)) if r.size else 0.0
                    i_mean, i_std = float(np.mean(i)) if i.size else 0.0, float(np.std(i)) if i.size else 0.0
                    r_min, r_max = (float(np.min(r)) if r.size else 0.0, float(np.max(r)) if r.size else 0.0)
                    i_min, i_max = (float(np.min(i)) if i.size else 0.0, float(np.max(i)) if i.size else 0.0)
                    
                    # Store in history
                    self.time_points.append(t_rel)
                    self.sr_history.append(sr)
                    self.nr_history.append(nr)
                    self.red_mean_history.append(r_mean)
                    self.red_std_history.append(r_std)
                    self.ir_mean_history.append(i_mean)
                    self.ir_std_history.append(i_std)
                    
                    # Print to console (matching original format)
                    msg = f"SR ~ {sr:.1f} sps | NR ~ {nr:.1f} nps | Red μ={r_mean:.2f} σ={r_std:.2f} | IR μ={i_mean:.2f} σ={i_std:.2f}"
                    print(msg)
                    
                    # Log stats
                    if self.stats_fh:
                        try:
                            self.stats_fh.write(f"{t_rel:.3f},{sr:.3f},{nr:.3f},{r_mean:.6f},{r_std:.6f},{r_min:.6f},{r_max:.6f},{i_mean:.6f},{i_std:.6f},{i_min:.6f},{i_max:.6f}\n")
                            self.stats_fh.flush()
                        except Exception as e:
                            print(f"Error writing stats: {e}")
                
                # Update plot
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
            if self.stats_fh:
                try:
                    self.stats_fh.close()
                except Exception:
                    pass


def parse_args():
    p = argparse.ArgumentParser(description="Mendi fNIRS Stats Viewer")
    p.add_argument('--mac', help='Device MAC/UUID (macOS UUID acceptable)')
    p.add_argument('--service-uuid', default=DEFAULT_SERVICE)
    p.add_argument('--rx-uuid', default=DEFAULT_RX)
    p.add_argument('--status-uuid', default=DEFAULT_STATUS, help='Optional status/heartbeat characteristic to visualize')
    p.add_argument('--format', choices=['f32','i16'], default='f32', help='Payload format per sample pair')
    p.add_argument('--window', type=float, default=60.0, help='Plot window (s)')
    p.add_argument('--history', type=int, default=300, help='Number of data points to keep in history')
    p.add_argument('--stats-log', default='fnirs_stats.txt', help='Write per-second stats to this text file')
    p.add_argument('--i16-unsigned', action='store_true', help='When using --format i16, treat values as unsigned')
    return p.parse_args()


if __name__ == '__main__':
    args = parse_args()
    StatsViewer(args).run()
