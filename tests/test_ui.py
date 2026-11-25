import asyncio
import tempfile
from pathlib import Path
from nicegui import ui
from nicegui.testing import User
from spark_ignitor.app import build
from spark_ignitor.config import Config
from spark_ignitor.rig import Rig


async def wait_until(cond, timeout=10.0):
    t = 0.0
    while not cond() and t < timeout:
        await asyncio.sleep(0.1); t += 0.1
    assert cond(), "timed out"


def make(tmp, **kw):
    rig = Rig(Config(min_rest_s=0.0, data_dir=tmp, **kw)); build(rig); return rig


async def test_page_loads_and_connects(user: User):
    with tempfile.TemporaryDirectory() as tmp:
        rig = make(tmp)
        await user.open("/")
        await user.should_see("Spark ignitor dashboard")
        await user.should_see("Fire once")
        user.find(kind=ui.button, content="Connect").click()
        await wait_until(lambda: rig.state["connected"]["arduino"])
        await asyncio.sleep(0.6)
        await user.should_see("SIMULATION")
        rig.disconnect()


async def test_batch_updates_page(user: User):
    with tempfile.TemporaryDirectory() as tmp:
        rig = make(tmp)
        await user.open("/")
        user.find(kind=ui.button, content="Connect").click()
        await wait_until(lambda: rig.state["connected"]["arduino"])
        await asyncio.sleep(0.6)
        user.find(kind=ui.button, content="Run batch").click()
        await wait_until(lambda: rig.state["shot"] == 20 and not rig.state["busy"])
        await asyncio.sleep(0.8)
        await user.should_see(content="Current batch (20 shots)")
        assert len(rig.session.rows) == 20 and rig.state["stats"]["misfires"] == 0
        rig.disconnect()


async def test_trip_shows_on_page_and_blocks_runs(user: User):
    with tempfile.TemporaryDirectory() as tmp:
        rig = make(tmp, I_trip_A=3.0)
        await user.open("/")
        user.find(kind=ui.button, content="Connect").click()
        await wait_until(lambda: rig.state["connected"]["arduino"])
        await asyncio.sleep(0.6)
        user.find(kind=ui.button, content="Fire once").click()
        await wait_until(lambda: rig.state["trip"])
        await asyncio.sleep(0.8)
        await user.should_see(content="TRIP: peak current")
        assert not rig.rigol.on and not rig.arduino.armed
        rig.reset_trip(); rig.disconnect()


async def test_devices_panel_saves_config(user: User):
    with tempfile.TemporaryDirectory() as tmp:
        cfg_path = Path(tmp) / "config.json"
        rig = Rig(Config(min_rest_s=0.0, data_dir=tmp)); build(rig, cfg_path)
        await user.open("/")
        user.find(kind=ui.input, content="Arduino port").elements.pop().value = "COM9"
        assert Config.load(cfg_path).arduino_port == "COM9"
        rig.disconnect()


async def test_stop_button_ends_auto_fire(user: User):
    with tempfile.TemporaryDirectory() as tmp:
        rig = make(tmp)
        rig.cfg.min_rest_s = 0.05
        await user.open("/")
        user.find(kind=ui.button, content="Connect").click()
        await wait_until(lambda: rig.state["connected"]["arduino"])
        await asyncio.sleep(0.6)
        user.find(kind=ui.button, content="Auto-fire").click()
        await wait_until(lambda: rig.state["shot"] >= 3)
        user.find(kind=ui.button, content="STOP").click()
        await wait_until(lambda: not rig.state["busy"])
        assert not rig.rigol.on and not rig.arduino.armed and not rig.state["trip"]
        rig.disconnect()
