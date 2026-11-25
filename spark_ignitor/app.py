"""The one-page dashboard (NiceGUI). It only shows `rig.state` and calls the Rig; all logic lives in rig.py."""
import math
from nicegui import app, run, ui
from .rig import Rig
from .storage import FIELDS

COLUMNS = [dict(name=f, label=l, field=f, align="right") for f, l in [
    ("shot", "#"), ("time", "time"), ("vset_V", "V set"), ("dwell_us", "dwell µs"), ("ipk_A", "I peak A"),
    ("E_mJ", "E mJ"), ("L_est_mH", "L est mH"), ("burn_ms", "burn ms"), ("ispark_max_mA", "spark mA"), ("misfire", "misfire")]]


def _num(x, nd=1):
    return "–" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{nd}f}"


def _heat(sw, key, title, pct):
    data, vals = [], []
    for di in range(len(sw["dwells"])):
        for vi in range(len(sw["volts"])):
            v = float(sw[key][di][vi])
            if not math.isnan(v):
                data.append([vi, di, round(100 * v if pct else v, 1)]); vals.append(data[-1][2])
    return {"animation": False, "title": {"text": title, "textStyle": {"fontSize": 14}},
            "grid": {"left": 80, "right": 30, "top": 50, "bottom": 55},
            "xAxis": {"type": "category", "data": [f"{v:g}" for v in sw["volts"]], "name": "supply voltage (V)", "nameLocation": "middle", "nameGap": 32},
            "yAxis": {"type": "category", "data": [f"{d:g}" for d in sw["dwells"]], "name": "dwell (µs)"},
            "visualMap": {"min": 0 if pct else (min(vals) if vals else 0), "max": 100 if pct else (max(vals) if vals else 1),
                          "calculable": True, "orient": "horizontal", "left": "center", "bottom": 0, "show": False,
                          "inRange": {"color": ["#fff5f0", "#cb181d"] if pct else ["#440154", "#21918c", "#fde725"]}},
            "series": [{"type": "heatmap", "data": data, "label": {"show": True, "formatter": "{@[2]}" + ("%" if pct else "")}}]}


def build(rig: Rig, config_path=None):
    cfg = rig.cfg

    def save_settings(*_):
        """Write the Devices panel settings back to config.json, so they survive a restart."""
        if config_path is None:
            return
        try:
            cfg.save(config_path)
        except OSError as e:
            ui.notify(f"Could not save settings to {config_path}: {e}", type="warning", multi_line=True)

    @ui.page("/")
    def index():
        ui.query("body").style("background:#eef1f5")
        seen = dict(shot=-1, log=0, sweep=None)

        def start(fn, *a):
            try:
                rig.start_job(fn, *a)
            except Exception as e:
                ui.notify(str(e), type="negative")

        async def do_connect():
            try:
                await run.io_bound(rig.connect)
                ui.notify("Connected", type="positive")
            except Exception as e:
                ui.notify(f"Could not connect: {e}", type="negative", multi_line=True)

        async def do_disconnect():
            await run.io_bound(rig.disconnect)

        # ------------------------------------------------------------------ header
        with ui.header(elevated=True).classes("bg-primary items-center justify-between q-px-md"):
            ui.label("Spark ignitor dashboard").classes("text-h6")
            with ui.row().classes("items-center q-gutter-sm"):
                b_rigol, b_ard, b_scope = ui.badge("Rigol", color="grey"), ui.badge("Arduino", color="grey"), ui.badge("Scope", color="grey")
                b_mode = ui.badge("SIMULATION", color="orange")
                b_armed = ui.badge("not armed", color="grey")
                b_trip = ui.badge("no trip", color="green")
                l_status = ui.label("Disconnected").classes("text-body1")
                ui.button("STOP", icon="stop", color="red", on_click=rig.stop).props("unelevated size=lg")

        with ui.row().classes("w-full no-wrap items-start q-pa-sm"):
            # ------------------------------------------------------------------ controls
            with ui.card().classes("w-80"):
                ui.label("Controls").classes("text-subtitle1 text-bold")
                with ui.row():
                    btn_connect = ui.button("Connect", icon="power", on_click=do_connect)
                    btn_disc = ui.button("Disconnect", on_click=do_disconnect).props("outline")
                volt = ui.number("Supply voltage (V)", value=12.0, min=6.0, max=cfg.max_voltage_V, step=0.5, format="%.1f").classes("w-full")
                ui.slider(min=6.0, max=cfg.max_voltage_V, step=0.5).bind_value(volt)
                dwell = ui.number("Dwell (µs)", value=2000, min=500, max=cfg.max_dwell_us, step=100, format="%.0f").classes("w-full")
                ui.slider(min=500, max=cfg.max_dwell_us, step=100).bind_value(dwell)
                nshots = ui.number("Shots in a batch", value=20, min=1, max=500, step=1, format="%.0f").classes("w-full")
                run_btns = []
                with ui.row():
                    run_btns.append(ui.button("Fire once", icon="bolt", color="positive", on_click=lambda: start(rig.run_batch, float(volt.value), float(dwell.value), 1)))
                    run_btns.append(ui.button("Run batch", icon="repeat", on_click=lambda: start(rig.run_batch, float(volt.value), float(dwell.value), int(nshots.value))))
                with ui.row():
                    run_btns.append(ui.button("Auto-fire", icon="all_inclusive", color="secondary", on_click=lambda: start(rig.run_auto, float(volt.value), float(dwell.value))))
                    btn_reset = ui.button("Reset trip", icon="restart_alt", color="warning", on_click=rig.reset_trip)
                ui.label("Every run arms the coil itself and switches everything off when it ends.").classes("text-caption text-grey")
                with ui.expansion("Devices", icon="usb").classes("w-full") as dev_box:
                    dev_inputs = [
                        ui.select({"sim": "Arduino: simulated", "real": "Arduino: real"}, value=cfg.arduino_mode).bind_value(cfg, "arduino_mode").classes("w-full").on_value_change(save_settings),
                        ui.input("Arduino port (for example COM3)").bind_value(cfg, "arduino_port").classes("w-full").on_value_change(save_settings),
                        ui.select({"sim": "Rigol: simulated", "real": "Rigol: real"}, value=cfg.rigol_mode).bind_value(cfg, "rigol_mode").classes("w-full").on_value_change(save_settings),
                        ui.input("Rigol VISA resource").bind_value(cfg, "rigol_resource").classes("w-full").on_value_change(save_settings),
                        ui.select({"sim": "Scope: simulated", "ps2000a": "PicoScope 2000A series", "ps3000a": "PicoScope 3000A series", "ps5000a": "PicoScope 5000A series"}, value=cfg.scope_mode).bind_value(cfg, "scope_mode").classes("w-full").on_value_change(save_settings)]

            # ------------------------------------------------------------------ live view
            with ui.column().classes("grow"):
                with ui.row().classes("w-full no-wrap"):
                    metric = {}
                    for key, title in [("ipk", "I peak (A)"), ("E", "Stored energy (mJ)"), ("L", "L estimate (mH)"),
                                       ("burn", "Burn time (ms)"), ("shot", "Shots"), ("mis", "Misfire rate")]:
                        with ui.card().classes("grow items-center q-pa-sm"):
                            ui.label(title).classes("text-caption text-grey")
                            metric[key] = ui.label("–").classes("text-h5 text-bold")
                l_stats = ui.label("Batch statistics will appear here.").classes("text-body2")
                wave = ui.echart({"animation": False, "grid": {"left": 60, "right": 60, "top": 40, "bottom": 45},
                                  "legend": {"data": ["coil current (A)", "spark current (mA)"]}, "tooltip": {"trigger": "axis"},
                                  "xAxis": {"type": "value", "name": "time (ms)", "nameLocation": "middle", "nameGap": 28},
                                  "yAxis": [{"type": "value", "name": "A"}, {"type": "value", "name": "mA"}],
                                  "series": [{"name": "coil current (A)", "type": "line", "showSymbol": False, "data": [], "yAxisIndex": 0, "color": "#1f77b4"},
                                             {"name": "spark current (mA)", "type": "line", "showSymbol": False, "data": [], "yAxisIndex": 1, "color": "#ff7f0e"}]}).classes("w-full h-80")

        # ------------------------------------------------------------------ tabs
        with ui.tabs().classes("w-full") as tabs:
            t1, t2, t3, t4 = ui.tab("Shots", icon="table_rows"), ui.tab("Sweep", icon="grid_on"), ui.tab("Export", icon="download"), ui.tab("Log", icon="list")
        with ui.tab_panels(tabs, value=t1).classes("w-full"):
            with ui.tab_panel(t1):
                with ui.row().classes("w-full no-wrap"):
                    table = ui.table(columns=COLUMNS, rows=[], row_key="shot", pagination=8).classes("w-1/2")
                    e_chart = ui.echart({"animation": False, "title": {"text": "Stored energy per shot (mJ)", "textStyle": {"fontSize": 14}},
                                         "grid": {"left": 55, "right": 20, "top": 45, "bottom": 40}, "xAxis": {"type": "value", "name": "shot"}, "yAxis": {"type": "value"},
                                         "series": [{"type": "line", "name": "sparked", "data": [], "symbolSize": 5, "color": "#2ca02c"},
                                                    {"type": "scatter", "name": "misfire", "data": [], "symbolSize": 10, "color": "#d62728"}]}).classes("w-1/2 h-72")
            with ui.tab_panel(t2):
                with ui.row().classes("items-end"):
                    sv = ui.input("Voltages (V), comma separated", value="8, 10, 12").classes("w-64")
                    sd = ui.input("Dwell times (µs), comma separated", value="1000, 2000, 3000").classes("w-72")
                    sn = ui.number("Shots per point", value=5, min=1, max=100, format="%.0f").classes("w-40")
                    shuf = ui.checkbox("random order", value=True)

                    def do_sweep():
                        try:
                            volts = [float(x) for x in sv.value.split(",") if x.strip()]
                            dwells = [float(x) for x in sd.value.split(",") if x.strip()]
                            assert volts and dwells
                        except Exception:
                            ui.notify("Type numbers separated by commas", type="negative"); return
                        start(rig.run_sweep, volts, dwells, int(sn.value), shuf.value)
                    run_btns.append(ui.button("Start sweep", icon="play_arrow", on_click=do_sweep))
                ui.label("Start small, for example 3 x 3 points with 5 shots, and keep voltages at 12 V or below.").classes("text-caption text-grey")
                with ui.row().classes("w-full no-wrap"):
                    h1 = ui.echart({"series": []}).classes("w-1/2 h-80")
                    h2 = ui.echart({"series": []}).classes("w-1/2 h-80")
            with ui.tab_panel(t3):
                l_folder = ui.label("Connect first. Every run is saved automatically in its own folder.").classes("text-body2")

                async def export(kind):
                    ss = rig.session
                    if not ss or not ss.rows:
                        ui.notify("No shots recorded yet", type="warning"); return
                    fn, name = {"csv": (ss.csv_bytes, "shots.csv"), "wave": (ss.waveforms_zip_bytes, "waveforms.zip"),
                                "png": (ss.pngs_zip_bytes, "plots.zip"), "pdf": (ss.pdf_bytes, "report.pdf"),
                                "all": (ss.bundle_bytes, ss.dir.name + ".zip")}[kind]
                    ui.notify("Preparing...")
                    ui.download(await run.io_bound(fn), name)
                with ui.row():
                    ui.button("Shot table (CSV, opens in Excel)", icon="table_view", on_click=lambda: export("csv"))
                    ui.button("Raw waveforms (ZIP)", icon="graphic_eq", on_click=lambda: export("wave"))
                    ui.button("Graph pictures (PNG, ZIP)", icon="image", on_click=lambda: export("png"))
                    ui.button("PDF report", icon="picture_as_pdf", on_click=lambda: export("pdf"))
                    ui.button("Everything (ZIP)", icon="folder_zip", color="secondary", on_click=lambda: export("all"))
            with ui.tab_panel(t4):
                log = ui.log(max_lines=500).classes("w-full h-64")

        # ------------------------------------------------------------------ refresh
        def refresh():
            s = rig.state
            c = s["connected"]
            for b, k in ((b_rigol, "rigol"), (b_ard, "arduino"), (b_scope, "scope")):
                b.props(f"color={'green' if c[k] else 'grey'}")
            b_mode.text = "SIMULATION" if s["sim"] else "REAL HARDWARE"; b_mode.props(f"color={'orange' if s['sim'] else 'blue'}")
            b_armed.text = "ARMED" if s["armed"] else "not armed"; b_armed.props(f"color={'red' if s['armed'] else 'grey'}")
            b_trip.text = ("TRIP: " + s["reason"]) if s["trip"] else "no trip"; b_trip.props(f"color={'red' if s['trip'] else 'green'}")
            l_status.text = s["status"] + (f"   {s['progress']}" if s["progress"] else "")
            connected = c["arduino"]
            btn_connect.set_enabled(not connected); btn_disc.set_enabled(connected); dev_box.set_enabled(not connected)
            for b in run_btns:
                b.set_enabled(connected and not s["busy"] and not s["trip"])
            btn_reset.set_enabled(s["trip"])
            if rig.session:
                l_folder.text = f"Saving to: {rig.session.dir}"
            st, last = s["stats"], s["last"]
            if last:
                metric["ipk"].text, metric["E"].text = _num(last["ipk_A"]), _num(last["E_mJ"], 0)
                metric["L"].text, metric["burn"].text = _num(last["L_est_mH"], 2), _num(last["burn_ms"], 2)
                metric["shot"].text = str(s["shot"])
            if st and st.get("n"):
                metric["mis"].text = f"{100 * st['misfire_rate']:.0f} %"
                l_stats.text = (f"Current batch ({st['n']} shots): mean E {_num(st['mean_E'])} mJ, standard deviation {_num(st['sd_E'])} mJ, "
                                f"mean peak current {_num(st['mean_ipk'], 2)} A, misfires {st['misfires']} of {st['n']}.")
            if s["shot"] != seen["shot"] and s["wave"]:
                seen["shot"] = s["shot"]
                w = s["wave"]
                wave.options["series"][0]["data"] = list(zip(w["t"], w["coil"])); wave.options["series"][1]["data"] = list(zip(w["t"], w["spark"])); wave.update()
                rows = rig.session.rows
                table.rows = [{**{k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()}, "misfire": "yes" if r["misfire"] else ""} for r in reversed(rows[-200:])]; table.update()
                e_chart.options["series"][0]["data"] = [[r["shot"], round(r["E_mJ"], 1)] for r in rows if not r["misfire"]]
                e_chart.options["series"][1]["data"] = [[r["shot"], round(r["E_mJ"], 1)] for r in rows if r["misfire"]]; e_chart.update()
            sw = s["sweep"]
            if sw is not None and (seen["sweep"] is not sw):
                seen["sweep"] = sw
                h1.options.update(_heat(sw, "mean_E", "Mean stored energy (mJ)", False)); h1.update()
                h2.options.update(_heat(sw, "rate", "Misfire rate", True)); h2.update()
            for line in s["log"][seen["log"]:]:
                log.push(line)
            seen["log"] = len(s["log"])

        ui.timer(0.3, refresh)


def run_dashboard(cfg, port=8080, root=None, config_path=None):
    rig = Rig(cfg, root)
    build(rig, config_path)
    app.on_shutdown(rig.disconnect)
    ui.run(title="Spark ignitor", port=port, reload=False, show=False)
