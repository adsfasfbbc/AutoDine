"""CLI entry point for the front_vision edge service."""
from __future__ import annotations

import argparse
import logging
import sys

import uvicorn

from .config import FrontVisionConfig, is_port_free


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="front-vision", description="AutoDine M02 front_vision edge service")
    parser.add_argument("--source", default=None, help='"camera" or a path to a video file (looped)')
    parser.add_argument("--camera-index", type=int, default=None)
    parser.add_argument("--core-url", default=None)
    parser.add_argument("--store-id", default=None)
    parser.add_argument("--device-id", default=None)
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--backend", default=None, choices=["auto", "torch"], help="person-detection backend")
    parser.add_argument("--no-preview", action="store_true", help="disable the MJPEG debug preview (production)")
    parser.add_argument("--no-audio", action="store_true", help="disable the acoustic safety channel (vision-only; fusion never publishes)")
    parser.add_argument("--simulate-safety", action="store_true", help="inject synthetic dual-modality safety cues (demo without real people)")
    parser.add_argument("--no-fire", action="store_true", help="disable fire detection entirely")
    parser.add_argument("--no-fire-sensor", action="store_true", help="disable the Modbus flame-sensor channel (vision-only; fusion never publishes)")
    parser.add_argument("--fire-port", default=None, help="flame sensor serial port (default: COM3 on Windows, /dev/ttyUSB0 on Linux)")
    parser.add_argument("--fire-model", default=None, help="path to the flame detection model (fire.pt)")
    parser.add_argument("--simulate-fire", action="store_true", help="inject synthetic dual-channel fire cues (demo without a real fire)")
    parser.add_argument("--gui", action="store_true", help="run the PySide6 desktop debug window instead of the FastAPI service")
    parser.add_argument("--no-publish", action="store_true", help="skip ADP event publishing (local demo, GUI mode)")
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> FrontVisionConfig:
    config = FrontVisionConfig()
    if args.source is not None:
        config.source = args.source
    if args.camera_index is not None:
        config.camera_index = args.camera_index
    if args.core_url is not None:
        config.core_url = args.core_url
    if args.store_id is not None:
        config.store_id = args.store_id
    if args.device_id is not None:
        config.device_id = args.device_id
    if args.host is not None:
        config.host = args.host
    if args.port is not None:
        config.port = args.port
    if args.backend is not None:
        config.detector_backend = args.backend
    if args.no_preview:
        config.preview_enabled = False
    if args.no_audio:
        config.audio_enabled = False
    if args.simulate_safety:
        config.simulate_safety = True
    if args.no_fire:
        config.fire_enabled = False
    if args.no_fire_sensor:
        config.fire_sensor_enabled = False
    if args.fire_port is not None:
        config.fire_sensor_port = args.fire_port
    if args.fire_model is not None:
        config.fire_model_path = args.fire_model
    if args.simulate_fire:
        config.simulate_fire = True
    return config


def main(argv=None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    config = config_from_args(args)

    if args.gui:
        # GUI mode: no FastAPI/uvicorn; Qt must run on the main thread while
        # capture + inference stay on background threads.
        from .gui import run_gui

        return run_gui(config, publish=not args.no_publish)

    if not is_port_free(config.host, config.port):
        print(f"error: port {config.port} on {config.host} is already in use", file=sys.stderr)
        return 2

    from .service import create_app

    app = create_app(config)
    uvicorn.run(app, host=config.host, port=config.port, log_level=args.log_level.lower())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
