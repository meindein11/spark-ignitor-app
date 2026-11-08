import argparse
import sys
from pathlib import Path
from .config import Config


def main(argv=None):
    ap = argparse.ArgumentParser(prog="spark_ignitor", description="Spark ignitor test bench")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dashboard", help="start the one-page dashboard in your browser")
    d.add_argument("--config", default="config.json"); d.add_argument("--port", type=int, default=8080)
    sub.add_parser("selftest", help="run the checks that need no hardware")
    i = sub.add_parser("init-config", help="write a default config.json to edit"); i.add_argument("--config", default="config.json")
    sub.add_parser("ports", help="list serial ports and VISA instruments")
    sub.add_parser("scope-check", help="find out which PicoScope is connected")
    t = sub.add_parser("scope-test", help="capture one block from the real scope without any trigger")
    t.add_argument("--config", default="config.json")
    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        from .selftest import run_all
        return 0 if run_all() else 1
    if a.cmd == "init-config":
        Config().save(a.config); print(f"wrote {a.config}"); return 0
    if a.cmd == "ports":
        try:
            from serial.tools import list_ports
            print("Serial ports:", [f"{p.device} ({p.description})" for p in list_ports.comports()] or "none")
        except Exception as e:
            print("serial:", e)
        try:
            import pyvisa
            print("VISA instruments:", list(pyvisa.ResourceManager().list_resources()) or "none")
        except Exception as e:
            print("VISA:", e)
        return 0
    if a.cmd == "scope-check":
        from .scope import check_connected
        try:
            name, info = check_connected()
            print(f"Found a PicoScope. Driver series: {name}\n{info}\nSet scope_mode to '{name}' in config.json (supported here: ps2000a, ps3000a).")
        except Exception as e:
            print(f"No scope found or the PicoSDK is missing: {type(e).__name__}: {e}\nClose PicoScope 7 and check the USB cable.")
            return 1
        return 0
    cfg = Config.load(a.config)
    if a.cmd == "scope-test":
        from .scope import PicoScope
        if cfg.scope_mode == "sim":
            print("scope_mode is 'sim' in the config. Set it to ps2000a or ps3000a first."); return 1
        sc = PicoScope(cfg, cfg.scope_mode); sc.open()
        try:
            sc.start(auto_trigger_ms=500); d = sc.read(timeout=3.0)
        finally:
            sc.close()
        print(f"OK: {len(d['i_coil'])} samples, dt = {d['dt'] * 1e6:.2f} us\n coil current: min {d['i_coil'].min():.3f} A, max {d['i_coil'].max():.3f} A\n spark current: min {d['i_spark'].min() * 1e3:.2f} mA, max {d['i_spark'].max() * 1e3:.2f} mA")
        return 0
    from .app import run_dashboard
    run_dashboard(cfg, a.port, Path(cfg.data_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
