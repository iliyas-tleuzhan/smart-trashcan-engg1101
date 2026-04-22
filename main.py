"""Minimal entry point for the smart bin subsystem."""

from smart_bin.controller import SmartBinController


def main() -> None:
    controller = SmartBinController()
    try:
        controller.run()
    except KeyboardInterrupt:
        print("\n[INFO] Ctrl+C received. Stopping...")
    finally:
        controller.cleanup()


if __name__ == "__main__":
    main()
