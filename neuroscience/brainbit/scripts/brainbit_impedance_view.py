#!/usr/bin/env python3
"""
BrainBit Impedance (Resistance) Live Viewer

Displays live electrode resistance values for BrainBit channels (T3, T4, O1, O2)
as a bar chart. Useful for checking contact quality. Values are read from the
board's resistance channels via BrainFlow.

Usage:
  python3 brainbit_impedance_view.py [--mac AA:BB:CC:DD:EE:FF]

Notes:
- Only one app can connect to BrainBit at once. Close other viewers first.
- Resistance channels are provided by BrainBit; units are device-defined (often kOhm).
- Press q or Esc to quit.
"""

import argparse
import sys
import time

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds, BrainFlowPresets


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--mac", default="", help="Optional MAC address to target a specific BrainBit device")
    p.add_argument("--interval", type=int, default=1000, help="Update interval in ms (default: 1000)")
    p.add_argument("--debug", action="store_true", help="Print latest resistance values each update")
    return p.parse_args()


def main():
    args = parse_args()

    BoardShim.enable_board_logger()

    params = BrainFlowInputParams()
    params.mac_address = args.mac

    board_id = BoardIds.BRAINBIT_BOARD.value
    board = BoardShim(board_id, params)

    board_descr = BoardShim.get_board_descr(board_id)
    eeg_names = board_descr.get("eeg_names", "T3,T4,O1,O2").split(",")
    res_idx = board_descr["resistance_channels"]  # e.g., [5,6,7,8]

    # Connect
    print("Connecting to BrainBit for impedance view...")
    board.prepare_session()
    board.start_stream(450000)
    print("Connected. Close this window or press q/Esc to exit.")

    # Matplotlib setup
    fig, ax = plt.subplots(figsize=(6, 4))
    plt.subplots_adjust(bottom=0.15)
    bars = ax.bar(eeg_names, [0] * len(res_idx), color=["#2ca02c"] * len(res_idx))
    ax.set_ylabel("Resistance (device units)")
    ax.set_ylim(0, 1000)  # initial; will auto-expand based on observed values
    txts = []
    for rect in bars:
        txt = ax.text(rect.get_x() + rect.get_width() / 2, rect.get_height(), "0",
                       ha="center", va="bottom", fontsize=10)
        txts.append(txt)

    ax.set_title("BrainBit Electrode Resistance")
    status_txt = ax.text(0.5, -0.18, "Waiting for resistance samples...",
                         transform=ax.transAxes, ha="center", va="top", fontsize=10)

    def quality_color(val):
        # Simple heuristic thresholds; adjust as appropriate
        if val <= 100:  # good
            return "#2ca02c"  # green
        if val <= 500:  # ok
            return "#ff7f0e"  # orange
        return "#d62728"  # red

    max_seen = [0]

    def update(_):
        # Get recent samples from default preset; BrainBit exposes resistance channels here
        data = board.get_current_board_data(250, BrainFlowPresets.DEFAULT_PRESET)
        if data.size == 0 or data.shape[1] == 0:
            status_txt.set_text("Waiting for resistance samples...")
            return bars
        last_vals = []
        for ch in res_idx:
            ch_data = data[ch, :]
            if ch_data.size:
                last_vals.append(ch_data[-1])
            else:
                last_vals.append(np.nan)

        # Replace NaNs with previous or zero
        for i, v in enumerate(last_vals):
            val = 0.0 if np.isnan(v) else float(v)
            bars[i].set_height(val)
            bars[i].set_color(quality_color(val))
            txts[i].set_text(f"{val:.0f}")
            txts[i].set_y(val)
        if args.debug:
            print("Resistance:", ", ".join(f"{n}:{(0.0 if np.isnan(v) else float(v)):.0f}" for n, v in zip(eeg_names, last_vals)))
        status_txt.set_text("")

        cur_max = np.nanmax(last_vals) if np.isfinite(last_vals).any() else 0
        if cur_max > max_seen[0]:
            max_seen[0] = cur_max
            top = max(1000, cur_max * 1.2)
            ax.set_ylim(0, top)
        return bars

    def on_key(event):
        if event.key in ("q", "escape"):
            plt.close(fig)

    fig.canvas.mpl_connect("key_press_event", on_key)
    ani = FuncAnimation(fig, update, interval=args.interval, blit=False)

    try:
        plt.show()
    finally:
        try:
            board.stop_stream()
        except Exception:
            pass
        try:
            board.release_session()
        except Exception:
            pass
        print("Impedance viewer closed.")


if __name__ == "__main__":
    sys.exit(main())
