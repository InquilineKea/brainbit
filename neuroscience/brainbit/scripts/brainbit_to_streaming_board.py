#!/usr/bin/env python3
"""
BrainBit -> BrainFlow Streaming Board bridge

This script connects to a BrainBit (Flex) headset via BrainFlow and re-streams
the data using BrainFlow's built-in Streaming Board protocol. You can then
select "BrainFlow" -> "Streaming Board" in the OpenBCI GUI and connect to the
same host/port specified here.

Usage examples:
  python3 brainbit_to_streaming_board.py
  python3 brainbit_to_streaming_board.py --host 0.0.0.0 --port 6677
  python3 brainbit_to_streaming_board.py --mac AA:BB:CC:DD:EE:FF

Notes:
- Only one application can hold the BrainBit connection at a time.
- If you encounter BOARD_NOT_READY_ERROR, power-cycle the headset and retry.
- On macOS, ensure Bluetooth is on and the device is paired.
"""

import argparse
import signal as _signal
import sys
import time

from brainflow.board_shim import BoardShim, BrainFlowInputParams, LogLevels, BoardIds


def parse_args():
    p = argparse.ArgumentParser(description="BrainBit to BrainFlow Streaming Board bridge")
    p.add_argument("--host", default="127.0.0.1", help="Host/interface to bind the streaming server (default: 127.0.0.1)")
    p.add_argument("--port", type=int, default=6677, help="Port for the streaming server (default: 6677)")
    p.add_argument("--mac", default="", help="Optional MAC address for the BrainBit device (speeds discovery)")
    p.add_argument("--log", default="warn", choices=["trace", "debug", "info", "warn", "error", "off"], help="BrainFlow log level")
    return p.parse_args()


def to_log_level(name: str) -> int:
    name = name.lower()
    # BrainFlow Python uses LEVEL_* constants for LogLevels
    return {
        "trace": LogLevels.LEVEL_TRACE.value,
        "debug": LogLevels.LEVEL_DEBUG.value,
        "info": LogLevels.LEVEL_INFO.value,
        "warn": LogLevels.LEVEL_WARN.value,
        "error": LogLevels.LEVEL_ERROR.value,
        "off": LogLevels.LEVEL_OFF.value,
    }[name]


def main():
    args = parse_args()

    # Configure BrainFlow logging (compat: no-arg variant)
    try:
        BoardShim.enable_board_logger()
    except TypeError:
        # Fallback if signature differs silently in future versions
        pass

    params = BrainFlowInputParams()
    # For BLE devices, BrainFlow uses mac_address for discovery on macOS/Linux.
    params.mac_address = args.mac

    board_id = BoardIds.BRAINBIT_BOARD.value

    print(f"Connecting to BrainBit (board_id={board_id})...")
    board = BoardShim(board_id, params)

    try:
        board.prepare_session()
        # Start internal acquisition and simultaneously expose a streaming server
        streamer = f"streaming_board://{args.host}:{args.port}"
        print(f"Starting stream and re-streaming via {streamer} ...")
        board.start_stream(450000, streamer)
        print("Bridge is running. Open OpenBCI GUI -> BrainFlow -> Streaming Board and connect to the same host/port.")
        print("Press Ctrl+C to stop.")

        # Keep process alive
        def _graceful_exit(signum, frame):
            raise KeyboardInterrupt

        _signal.signal(_signal.SIGINT, _graceful_exit)
        _signal.signal(_signal.SIGTERM, _graceful_exit)

        while True:
            time.sleep(1.0)

    except KeyboardInterrupt:
        print("\nStopping...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        try:
            board.stop_stream()
        except Exception:
            pass
        try:
            board.release_session()
        except Exception:
            pass
        print("Bridge stopped.")


if __name__ == "__main__":
    sys.exit(main())
