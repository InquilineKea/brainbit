#!/usr/bin/env python3
import asyncio
import argparse
import time
import threading
from collections import deque
from datetime import datetime
import struct
import sys

import numpy as np
from bleak import BleakScanner, BleakClient
import matplotlib.pyplot as plt
from matplotlib.widgets import Button

# Default BLE UUIDs for Mendi
DEFAULT_SERVICE = "fc3eabb0-c6c4-49e6-922a-6e551c455af5"
DEFAULT_RX = "fc3eabb1-c6c4-49e6-922a-6e551c455af5"
DEFAULT_STATUS = "fc3eabb4-c6c4-49e6-922a-6e551c455af5"

# Stats viewer for Mendi data (focused on terminal-like output)
class StatsViewer:
    def __init__(self, args):
        self.args = args
        self.addr = args.mac
        self.client = None
        self.stop_event = threading.Event()
        self.notif_count = 0
        
        # Stats buffers
        self.history_size = args.history
        self.time_points = deque(maxlen=self.history_size)
        self.sr_history = deque(maxlen=self.history_size)
        self.nr_history = deque(maxlen=self.history_size)
        self.red_mean_history = deque(maxlen=self.history_size)
        self.red_std_history = deque(maxlen=self.history_size)
        self.ir_mean_history = deque(maxlen=self.history_size)
        self.ir_std_history = deque(maxlen=self.history_size)
        
        # Data buffers for processing
        self.ts = deque(maxlen=50000)
        self.red = deque(maxlen=50000)
        self.ir = deque(maxlen=50000)
        self.status_t = deque(maxlen=50)
        self.status_v = deque(maxlen=50)
        
        # Stats tracking
        self.lock = threading.Lock()
        self.t0 = None
        self.last_notif_time = None
        self.last_calc_time = time.time()
        self.sample_count = 0
        self.last_sample_count = 0
        self.notif_count = 0
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

    def init_plot(self):
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
        
        # Red channel stats plot
        self.ax_red.set_title("Red Channel Stats")
        self.l_red_mean, = self.ax_red.plot(empty_x, empty_y, 'r-', linewidth=2, label='Mean')
        self.l_red_std_up, = self.ax_red.plot(empty_x, empty_y, 'r:', linewidth=1, alpha=0.5, label='Mean + Std')
        self.l_red_std_down, = self.ax_red.plot(empty_x, empty_y, 'r:', linewidth=1, alpha=0.5, label='Mean - Std')
        self.ax_red.legend(loc='upper right')
        
        # IR channel stats plot
        self.ax_ir.set_title("IR Channel Stats")
        self.l_ir_mean, = self.ax_ir.plot(empty_x, empty_y, 'y-', linewidth=2, label='Mean')
        self.l_ir_std_up, = self.ax_ir.plot(empty_x, empty_y, 'y:', linewidth=1, alpha=0.5, label='Mean + Std')
        self.l_ir_std_down, = self.ax_ir.plot(empty_x, empty_y, 'y:', linewidth=1, alpha=0.5, label='Mean - Std')
        self.ax_ir.legend(loc='upper right')
        
        # Status/heartbeat plot
        self.ax_status.set_title("Connection Status")
        self.l_status, = self.ax_status.plot(empty_x, empty_y, 'w-', linewidth=1)
        
        # Add a reset zoom button
        reset_btn_ax = plt.axes([0.81, 0.02, 0.1, 0.04])
        self.reset_btn = Button(reset_btn_ax, 'Reset Zoom')
        self.reset_btn.on_clicked(lambda event: self.reset_zoom())
        
        # Grid and labels
        for ax in self.axes:
            ax.grid(True, linestyle='--', alpha=0.7)
        
        plt.xlabel('Time (s)')
        self.ax_sr.set_ylim(0, 1000)  # Reasonable initial range for sample rate
        
        # Enable pan/zoom mode by default
        self.fig.canvas.toolbar.pan()
        plt.tight_layout()
    
    def reset_zoom(self):
        for ax in self.axes:
            ax.relim()
            ax.autoscale_view()
        plt.draw()
    
    def update_plot(self):
        # Get history data for plotting
        x_data = list(self.time_points)
        if not x_data:
            return
        
        # Update sample rate and notification rate plot
        self.l_sr.set_data(x_data, list(self.sr_history))
        self.l_nr.set_data(x_data, list(self.nr_history))
        
        # Update Red channel stats plot
        red_mean = list(self.red_mean_history)
        red_std = list(self.red_std_history)
        self.l_red_mean.set_data(x_data, red_mean)
        self.l_red_std_up.set_data(x_data, [m + s for m, s in zip(red_mean, red_std)])
        self.l_red_std_down.set_data(x_data, [m - s for m, s in zip(red_mean, red_std)])
        
        # Update IR channel stats plot
        ir_mean = list(self.ir_mean_history)
        ir_std = list(self.ir_std_history)
        self.l_ir_mean.set_data(x_data, ir_mean)
        self.l_ir_std_up.set_data(x_data, [m + s for m, s in zip(ir_mean, ir_std)])
        self.l_ir_std_down.set_data(x_data, [m - s for m, s in zip(ir_mean, ir_std)])
        
        # Status/heartbeat trace
        with self.lock:
            st = np.array(self.status_t)
            sv = np.array(self.status_v)
        if len(st) > 0:
            # Window to last N seconds of status data
            stmax = st[-1] if len(st) else 0
            win_sec = 10  # Show last 10 seconds of status
            smask = st > (stmax - win_sec)
            stw = st[smask]
            svw = sv[smask]
            self.l_status.set_data(stw, svw)
            self.ax_status.relim()
            self.ax_status.autoscale_view()
        
        # Auto-scale the plots with some padding
        for ax in [self.ax_sr, self.ax_red, self.ax_ir]:
            ax.relim()
            ax.autoscale_view()
        
        # Set the x-axis range based on the window size
        if x_data:
            latest = x_data[-1]
            for ax in self.axes:
                ax.set_xlim(latest - self.args.window, latest)

    # Parse raw notification data
    def parse_notification(self, data):
        # Handle i16 data with optional unsigned flag
        if self.args.format == 'i16':
            if len(data) % 4 == 0:  # Expecting (red, ir) pairs as 16-bit integers
                dtype = '<u2' if self.args.i16_unsigned else '<i2'
                arr = np.frombuffer(data, dtype=dtype)
                if arr.size % 2 == 0:
                    arr = arr.reshape(-1, 2).astype(float)
                    return arr[:, 0], arr[:, 1]  # red, ir
        
        # Handle float32 data
        elif self.args.format == 'f32':
            if len(data) % 8 == 0:  # Expecting (red, ir) pairs as 32-bit floats
                arr = np.frombuffer(data, dtype='<f4')
                if arr.size % 2 == 0:
                    arr = arr.reshape(-1, 2)
                    return arr[:, 0], arr[:, 1]  # red, ir
        
        # Heuristic fallback: Try to strip a 1-byte header and retry
        if len(data) > 1:
            try:
                # Count notification for debug
                self.notif_count += 1
                
                # Try parsing with first byte as header
                if data[0] in [0x08, 0x18]:  # Common Mendi headers
                    r, i = self.parse_notification(data[1:])
                    return r, i
            except Exception as e:
                print(f"Parsing error: {e}")
        
        # If all parsing attempts fail, return empty arrays
        return np.array([]), np.array([])

    # Handle BLE notifications
    def handle_notification(self, sender, data):
        now = time.time()
        if self.t0 is None:
            self.t0 = now
        
        t_rel = now - self.t0
        
        # Track notification timing for rate calculation
        self.last_notif_time = now
        
        if sender == self.args.status_uuid:
            # Status/heartbeat notification
            with self.lock:
                self.status_t.append(t_rel)
                self.status_v.append(1.0)  # Just a heartbeat indicator
            return
        
        if sender == self.args.rx_uuid:
            self.notif_count += 1
            print(f"RAW notif[{self.notif_count}] len={len(data)} hex={data[:50].hex()}...")
            
            # Parse the notification data
            r, i = self.parse_notification(data)
            n_samples = len(r)
            
            if n_samples:
                self.sample_count += n_samples
                
                # Store in data buffers
                with self.lock:
                    for j in range(n_samples):
                        self.ts.append(t_rel)
                        self.red.append(r[j])
                        self.ir.append(i[j])

    # Run the viewer
    def run(self):
        # Thread for BLE operations
        def ble_thread():
            async def run_ble():
                # Scan for device if not specified
                if not self.addr:
                    print("Scanning for Mendi device...")
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
                        print(f"Subscribed to data notifications. Receiving... Press Ctrl+C to quit.")
                        
                        # Keep the connection alive until stopped
                        while not self.stop_event.is_set():
                            await asyncio.sleep(0.1)
                except Exception as e:
                    print(f"BLE error: {e}")
            
            # Create and run the async event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                loop.run_until_complete(run_ble())
            except Exception as e:
                print(f"BLE thread error: {e}")
            finally:
                try:
                    if loop.is_running():
                        loop.stop()
                except Exception:
                    pass
                loop.close()
        
        # Start the BLE thread
        th = threading.Thread(target=ble_thread, daemon=True)
        th.start()
        
        # Initialize the plot
        self.init_plot()
        
        # Main loop for UI updates and stats calculation
        try:
            while th.is_alive():
                # Calculate stats every second
                now = time.time()
                if now - self.last_calc_time >= 1.0:
                    dt = now - self.last_calc_time
                    self.last_calc_time = now
                    t_rel = now - self.t0 if self.t0 else 0
                    
                    # Calculate rates
                    sr = (self.sample_count - self.last_sample_count) / dt
                    nr = (self.notif_count - self.last_notif_count) / dt
                    self.last_sample_count = self.sample_count
                    self.last_notif_count = self.notif_count
                    
                    # Get latest signal data for statistics
                    with self.lock:
                        r = list(self.red)
                        i = list(self.ir)
                    
                    # Calculate statistics
                    r_arr = np.array(r)
                    i_arr = np.array(i)
                    
                    r_mean = float(np.mean(r_arr)) if len(r_arr) else 0.0
                    r_std = float(np.std(r_arr)) if len(r_arr) else 0.0
                    i_mean = float(np.mean(i_arr)) if len(i_arr) else 0.0
                    i_std = float(np.std(i_arr)) if len(i_arr) else 0.0
                    r_min = float(np.min(r_arr)) if len(r_arr) else 0.0
                    r_max = float(np.max(r_arr)) if len(r_arr) else 0.0
                    i_min = float(np.min(i_arr)) if len(i_arr) else 0.0
                    i_max = float(np.max(i_arr)) if len(i_arr) else 0.0
                    
                    # Store in history for plotting
                    self.time_points.append(t_rel)
                    self.sr_history.append(sr)
                    self.nr_history.append(nr)
                    self.red_mean_history.append(r_mean)
                    self.red_std_history.append(r_std)
                    self.ir_mean_history.append(i_mean)
                    self.ir_std_history.append(i_std)
                    
                    # Print to console - matches format of original viewer
                    msg = f"SR ~ {sr:.1f} sps | NR ~ {nr:.1f} nps | Red μ={r_mean:.2f} σ={r_std:.2f} | IR μ={i_mean:.2f} σ={i_std:.2f}"
                    print(msg)
                    
                    # Log stats if enabled
                    if self.stats_fh:
                        try:
                            self.stats_fh.write(f"{t_rel:.3f},{sr:.3f},{nr:.3f},{r_mean:.6f},{r_std:.6f},{r_min:.6f},{r_max:.6f},{i_mean:.6f},{i_std:.6f},{i_min:.6f},{i_max:.6f}\n")
                            self.stats_fh.flush()
                        except Exception as e:
                            print(f"Error writing stats: {e}")
                    
                    # Clear buffers for next interval
                    with self.lock:
                        self.red.clear()
                        self.ir.clear()
                
                # Update the plot
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
    parser.add_argument('--mac', help='Device MAC/UUID (macOS UUID format acceptable)')
    parser.add_argument('--service-uuid', default=DEFAULT_SERVICE, help='BLE service UUID')
    parser.add_argument('--rx-uuid', default=DEFAULT_RX, help='BLE data characteristic UUID')
    parser.add_argument('--status-uuid', default=DEFAULT_STATUS, help='Optional status/heartbeat characteristic')
    parser.add_argument('--format', choices=['f32', 'i16'], default='i16', help='Data format per sample pair')
    parser.add_argument('--i16-unsigned', action='store_true', help='When using i16 format, treat values as unsigned')
    parser.add_argument('--window', type=float, default=60.0, help='Plot window size in seconds')
    parser.add_argument('--history', type=int, default=300, help='Number of data points to keep in history')
    parser.add_argument('--stats-log', default='fnirs_stats_fixed.txt', help='Write per-second stats to this file')
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    StatsViewer(args).run()
