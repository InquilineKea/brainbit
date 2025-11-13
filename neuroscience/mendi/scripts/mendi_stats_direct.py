#!/usr/bin/env python3
import asyncio
import argparse
import time
import threading
from collections import deque
from datetime import datetime

import numpy as np
from bleak import BleakScanner, BleakClient
import matplotlib.pyplot as plt
from matplotlib.widgets import Button

DEFAULT_SERVICE = "fc3eabb0-c6c4-49e6-922a-6e551c455af5"
DEFAULT_RX = "fc3eabb1-c6c4-49e6-922a-6e551c455af5"
DEFAULT_STATUS = "fc3eabb4-c6c4-49e6-922a-6e551c455af5"

# Direct adaptation from original Mendi viewer
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


class StatsViewer:
    def __init__(self, args):
        self.args = args
        self.parser = FrameParser(args.format, getattr(args, 'i16_unsigned', False))
        self.addr = args.mac
        self.client = None
        self.stop_event = threading.Event()
        
        # Buffers for data storage
        self.ts = deque(maxlen=50000)
        self.red = deque(maxlen=50000)
        self.ir = deque(maxlen=50000)
        self.lock = threading.Lock()
        self.t0 = None
        
        # Stats buffers
        self.history_size = args.history
        self.time_points = deque(maxlen=self.history_size)
        self.sr_history = deque(maxlen=self.history_size)
        self.nr_history = deque(maxlen=self.history_size)
        self.red_mean_history = deque(maxlen=self.history_size)
        self.red_std_history = deque(maxlen=self.history_size)
        self.ir_mean_history = deque(maxlen=self.history_size)
        self.ir_std_history = deque(maxlen=self.history_size)
        
        # Status buffers
        self.status_t = deque(maxlen=50)
        self.status_v = deque(maxlen=50)
        
        # Counters
        self.last_stats_time = time.time()
        self.last_sample_count = 0
        self.total_samples = 0
        self.total_notifs = 0
        self.last_notif_count = 0
        
        # Stats logging
        self.stats_fh = None
        if args.stats_log:
            try:
                self.stats_fh = open(args.stats_log, 'w')
                self.stats_fh.write(f"# FNIRS session start {datetime.now().isoformat()}\n")
                self.stats_fh.write("# columns: t_rel, sr, nr, red_mean, red_std, red_min, red_max, ir_mean, ir_std, ir_min, ir_max\n")
                self.stats_fh.flush()
            except Exception as e:
                print(f"Error opening stats log: {e}")
                self.stats_fh = None

    # Scan for Mendi device if address not provided
    async def discover_address(self):
        if self.addr:
            return
        
        print("Scanning for Mendi device...")
        max_retries = 3
        for attempt in range(max_retries):
            if self.stop_event.is_set():
                return
            
            try:
                devices = await BleakScanner.discover(timeout=5.0)
                for d in devices:
                    name = (d.name or "").lower()
                    if "mendi" in name:
                        self.addr = d.address
                        print(f"Found: {d.name} [{self.addr}]")
                        return
            except Exception as e:
                print(f"Scan error: {e}")
            
            if attempt < max_retries - 1:
                print(f"No Mendi device found, retrying ({attempt+1}/{max_retries})...")
        
        print("No Mendi device found. Please specify --mac directly.")
        raise RuntimeError("Device not found")

    # Main BLE connection and notification handling
    async def ble_task(self):
        await self.discover_address()
        print(f"Connecting to {self.addr}...")
        async with BleakClient(self.addr, timeout=20.0) as client:
            self.client = client
            print("Connected.")
            
            # Verify service exists
            svcs = client.services
            if not svcs.get_service(self.args.service_uuid):
                print("Warning: specified service not in service list.")
            
            # Data notification callback - DIRECT COPY from working viewer
            def cb(_h, data: bytes):
                r, i = self.parser.parse_notification(data)
                # Debug: print first few raw packets
                if self.total_notifs < 5:
                    print(f"RAW notif[{self.total_notifs+1}] len={len(data)} hex={data[:50].hex()}...")
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
            
            # Start notification for data characteristic
            await client.start_notify(self.args.rx_uuid, cb)
            
            # Status/heartbeat notification callback
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
            
            # Start notification for status characteristic (if specified)
            try:
                if self.args.status_uuid:
                    await client.start_notify(self.args.status_uuid, cb_status)
                    print(f"Subscribed status {self.args.status_uuid}")
            except Exception as e:
                print(f"Status subscribe failed: {e}")
            
            print("Subscribed; receiving... Press Ctrl+C to quit.")
            
            # Keep connection alive until stopped
            while not self.stop_event.is_set():
                await asyncio.sleep(0.1)
            
            # Clean up notifications on exit
            try:
                await client.stop_notify(self.args.rx_uuid)
            except Exception:
                pass
            try:
                if self.args.status_uuid:
                    await client.stop_notify(self.args.status_uuid)
            except Exception:
                pass

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
        
        # Setup lines with empty data initially
        empty_x = np.array([0])
        empty_y = np.array([0])
        
        # Sample rate and notification rate plot
        self.ax_sr.set_title("Sample Rate (sps) & Notification Rate (nps)")
        self.l_sr, = self.ax_sr.plot(empty_x, empty_y, 'g-', linewidth=2, label='Sample Rate')
        self.l_nr, = self.ax_sr.plot(empty_x, empty_y, 'c--', linewidth=2, label='Notification Rate')
        self.ax_sr.legend(loc='upper right')
        
        # Red channel stats
        self.ax_red.set_title("Red Channel Stats")
        self.l_red_mean, = self.ax_red.plot(empty_x, empty_y, 'r-', linewidth=2, label='Mean')
        self.l_red_std_up, = self.ax_red.plot(empty_x, empty_y, 'r:', linewidth=1, alpha=0.5, label='Mean + Std')
        self.l_red_std_down, = self.ax_red.plot(empty_x, empty_y, 'r:', linewidth=1, alpha=0.5, label='Mean - Std')
        self.ax_red.legend(loc='upper right')
        
        # IR channel stats
        self.ax_ir.set_title("IR Channel Stats")
        self.l_ir_mean, = self.ax_ir.plot(empty_x, empty_y, 'y-', linewidth=2, label='Mean')
        self.l_ir_std_up, = self.ax_ir.plot(empty_x, empty_y, 'y:', linewidth=1, alpha=0.5, label='Mean + Std')
        self.l_ir_std_down, = self.ax_ir.plot(empty_x, empty_y, 'y:', linewidth=1, alpha=0.5, label='Mean - Std')
        self.ax_ir.legend(loc='upper right')
        
        # Status/heartbeat plot
        self.ax_status.set_title("Connection Status")
        self.l_status, = self.ax_status.plot(empty_x, empty_y, 'w-', linewidth=1)
        
        # Add reset zoom button
        reset_btn_ax = plt.axes([0.81, 0.02, 0.1, 0.04])
        self.reset_btn = Button(reset_btn_ax, 'Reset Zoom')
        self.reset_btn.on_clicked(lambda event: self.reset_zoom())
        
        # Set up grids and labels
        for ax in self.axes:
            ax.grid(True, linestyle='--', alpha=0.7)
        
        plt.xlabel('Time (s)')
        self.ax_sr.set_ylim(0, 1000)  # Reasonable for sample rate
        
        # Enable pan/zoom mode by default
        self.fig.canvas.toolbar.pan()
        plt.tight_layout()
    
    def reset_zoom(self):
        for ax in self.axes:
            ax.relim()
            ax.autoscale_view()
        plt.draw()
    
    def update_plot(self):
        # Get data for plotting
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
        
        # Status trace
        with self.lock:
            st = list(self.status_t)
            sv = list(self.status_v)
        if st:
            # Window to last N seconds
            stmax = st[-1] if st else 0
            win_sec = 10  # Show last 10 seconds
            smask = [t > (stmax - win_sec) for t in st]
            stw = [st[i] for i in range(len(st)) if smask[i]]
            svw = [sv[i] for i in range(len(sv)) if smask[i]]
            self.l_status.set_data(stw, svw)
            self.ax_status.relim()
            self.ax_status.autoscale_view()
        
        # Auto-scale plots with some padding
        for ax in [self.ax_sr, self.ax_red, self.ax_ir]:
            ax.relim()
            ax.autoscale_view()
        
        # Set x-axis range based on window size
        if x_data:
            latest = x_data[-1]
            for ax in self.axes:
                ax.set_xlim(latest - self.args.window, latest)
    
    def run(self):
        # BLE thread
        def ble_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.ble_task())
            except Exception as e:
                print(f"BLE error: {e}")
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
        
        # Initialize plot
        self.init_plot()
        
        # Main loop for UI updates and stats calculation
        try:
            while th.is_alive():
                # Calculate stats every second
                now = time.time()
                if now - self.last_stats_time >= 1.0:
                    dt = now - self.last_stats_time
                    self.last_stats_time = now
                    t_rel = now - self.t0 if self.t0 else 0
                    
                    # Calculate rates
                    sr = (self.total_samples - self.last_sample_count) / dt
                    nr = (self.total_notifs - self.last_notif_count) / dt
                    self.last_sample_count = self.total_samples
                    self.last_notif_count = self.total_notifs
                    
                    # Get current data for statistics
                    with self.lock:
                        r = list(self.red)
                        i = list(self.ir)
                    
                    # Calculate statistics
                    if r:
                        r_mean = np.mean(r)
                        r_std = np.std(r)
                        r_min = np.min(r)
                        r_max = np.max(r)
                    else:
                        r_mean = r_std = r_min = r_max = 0.0
                    
                    if i:
                        i_mean = np.mean(i)
                        i_std = np.std(i)
                        i_min = np.min(i)
                        i_max = np.max(i)
                    else:
                        i_mean = i_std = i_min = i_max = 0.0
                    
                    # Store in history for plotting
                    self.time_points.append(t_rel)
                    self.sr_history.append(sr)
                    self.nr_history.append(nr)
                    self.red_mean_history.append(r_mean)
                    self.red_std_history.append(r_std)
                    self.ir_mean_history.append(i_mean)
                    self.ir_std_history.append(i_std)
                    
                    # Print to console
                    msg = f"SR ~ {sr:.1f} sps | NR ~ {nr:.1f} nps | Red μ={r_mean:.2f} σ={r_std:.2f} | IR μ={i_mean:.2f} σ={i_std:.2f}"
                    print(msg)
                    
                    # Log stats if enabled
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
            print("\nStopping viewer...")
        finally:
            # Clean up
            self.stop_event.set()
            try:
                plt.close(self.fig)
            except Exception:
                pass
            if self.stats_fh:
                try:
                    self.stats_fh.close()
                except Exception:
                    pass


def parse_args():
    parser = argparse.ArgumentParser(description="Mendi fNIRS Stats Viewer")
    parser.add_argument('--mac', help='Device MAC/UUID (macOS UUID acceptable)')
    parser.add_argument('--service-uuid', default=DEFAULT_SERVICE, help='BLE service UUID')
    parser.add_argument('--rx-uuid', default=DEFAULT_RX, help='BLE data characteristic UUID')
    parser.add_argument('--status-uuid', default=DEFAULT_STATUS, help='Status/heartbeat characteristic UUID')
    parser.add_argument('--format', choices=['f32', 'i16'], default='i16', help='Data format')
    parser.add_argument('--i16-unsigned', action='store_true', help='Treat i16 as unsigned')
    parser.add_argument('--window', type=float, default=60.0, help='Plot window size in seconds')
    parser.add_argument('--history', type=int, default=300, help='Number of stats points to keep in history')
    parser.add_argument('--stats-log', default='fnirs_stats_direct.txt', help='Stats log file')
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    StatsViewer(args).run()
