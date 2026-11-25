# Setup on a new PC (step by step)

You only do this once per PC. It takes about 5 minutes with a good internet connection.

## What you need
- A Windows PC (Windows 10 or 11).
- Internet access (the setup downloads the packages).
- **Python 3.12** from https://www.python.org/downloads/ (any 3.10 or newer also works).
  - In the installer, **tick "Add python.exe to PATH"** before you press Install.
- **Git** (optional, only to download the project). https://git-scm.com/download/win

## Step 1: get the project
Either:
- **With Git:** open PowerShell and type
  ```
  git clone https://github.com/meindein11/spark-ignitor-app.git
  ```
- **Without Git:** on the GitHub page, click the green **Code** button, then **Download ZIP**. Unzip it somewhere you can find it, for example `Documents\GitHub\spark-ignitor-app`.

## Step 2: run the setup (once)
1. Open the project folder.
2. Double-click **setup.bat**.
3. A black window opens. It will:
   - find Python,
   - create a folder called `.venv` (this is the app's private Python, nothing is installed system-wide),
   - download and install all the packages,
   - run the selftest (no hardware needed).
4. At the end it must say **SETUP COMPLETE**. Press a key to close the window.

If it says **ERROR**, read the red text. The messages in the file tell you what to do. The most common causes are: Python not installed or not on PATH, or no internet access.

## Step 3: start the app (every time)
1. Double-click **START_DASHBOARD.bat**.
2. Wait about 10 seconds. The browser opens at http://localhost:8080 (or 8081 if 8080 is busy on your PC). If the browser doesn't open, look at the window for the address and type it in yourself.
3. **Keep the black window open** while you use the page. Closing it stops the app.
4. The page starts in **simulation**, so no hardware is needed. Press **Connect**, then **Fire once**.

To stop: click the black window and press **Ctrl+C**, or close it.

## Running the tests (optional)
Double-click the setup again, or in PowerShell, from the project folder:
```
.venv\Scripts\python.exe -m pytest -q
```
You should see `5 passed`.

## Tested versions
These were installed and tested on Windows 11 with Python 3.14.6:

| Package | Version |
|---|---|
| nicegui | 4.1.0 |
| numpy | 2.5.5 |
| matplotlib | 3.11.2 |
| pyserial | 3.5 |
| pyvisa | 1.16.2 |
| pyvisa-py | 0.8.1 |
| picosdk | 1.1 |
| pytest | 9.2.0 |
| pytest-asyncio | 1.5.0 |

Python 3.12 is recommended for new PCs. It is not yet tested on this project.

## If something goes wrong
| What you see | What to do |
|---|---|
| "Python was not found" | Install Python 3.12 and tick "Add python.exe to PATH". Then run setup.bat again. |
| "the package install failed" | Check the internet connection. Run setup.bat again. |
| "the selftest failed" | Send the whole black-window text to the project owner. |
| "The app is not set up yet" | Run setup.bat first. |
| The browser shows "This site can't be reached" | The black window is closed or still starting. Wait 10 seconds and refresh. |
| "Could not save settings" (orange message) | The folder is read-only, or `config.json` is open in another program. |

## Hardware
The app starts in simulation. Connecting real hardware (Arduino, Rigol power supply, PicoScope) is a separate step. Read `docs/OPERATING_GUIDE.md` first, and do not connect the coil without a supervisor.
