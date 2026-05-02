# FlatCAM Plus (BETA) (c) 2026 - by Sadri ERCAN

**FlatCAM Plus** is a modernized fork of FlatCAM, a program for preparing CNC jobs for making PCBs on a CNC router. It takes Gerber files and creates G-Code for isolation routing, drilling, and more.

Forked from [FlatCAM EVO](https://github.com/marius-stanciu/FlatCAM) (c) 2019 - by Marius Stanciu.
Based on [FlatCAM](http://flatcam.org/) (c) 2014-2018 Juan Pablo Caram.

---

### 🚀 Key Improvements in FlatCAM Plus (2026)

*   **Windows 11 Optimization:** Core logic optimized for modern Windows environments, ensuring stability and performance.
*   **Thread Safety:** Resolved critical threading crashes (e.g., C/C++ object deletion errors) in the background plotting engine.
*   **Enhanced Rendering:** High-precision buffering (1e-6) and stable geometry unions for reliable Gerber visualization.
*   **Resilient Plugin System:** Safe import mechanisms prevent crashes due to missing third-party dependencies.
*   **Modern Stack:** Updated for **Python 3.11+** and **PyQt6**, ensuring long-term maintainability.
*   **Isolation Tool Enhancements (New):**
    *   **Direct Database Integration:** Seamlessly transfer tools from the Tools Database into the Isolation Tool with automatic parameter mapping.
    *   **Dynamic Parameter Sync:** All milling settings (Cut Z, Feedrates, etc.) are synchronized from the UI to the tool data immediately before geometry generation, ensuring "combined" objects always use current settings.
    *   **Intelligent V-Tool Support:** Fixed shape and tip-diameter persistence when loading tools from the database, enabling accurate isolation for V-shaped milling bits.
    *   **Data Consistency:** Resolved "C1" shape reset issues and improved UI-to-storage data binding for all tool types.
*   **CNC Connection and Control Page:** Added a complete CNC controller workflow with a topbar connection entry point, connection modal, live machine status, jogging, streaming, SD control, terminal commands, and FluidNC file management.

---

## New Feature: CNC Connection and CNC Control Page

FlatCAM Plus now includes an integrated CNC controller workspace for connecting to machines, checking controller status, jogging axes, sending commands, streaming generated CNC jobs, and managing FluidNC files without leaving the application.

### CNC Connection Workflow

- **Topbar connection status:** The plugins toolbar now includes a CNC shortcut and a dedicated connection status area. When no machine is connected it shows **Connect**; after a successful connection it changes to **Connected**.
- **Clickable connection entry:** Clicking the topbar connection area opens the CNC connection modal directly, so the machine connection can be managed without searching through the full CNC page.
- **Connection modal:** The modal contains all connection settings in one place: connection mode, controller profile, serial port, baud rate, TCP host/port, FluidNC Web URL, username, and password.
- **Supported connection modes:** COM/USB serial, WiFi TCP/Telnet, and FluidNC Web/HTTP are supported through separate transport layers.
- **Controller profiles:** Includes controller command profiles for FluidNC/GRBL, GRBL, Smoothieware, Marlin, and a generic G-code profile.
- **COM port refresh:** Serial ports can be refreshed from the modal before connecting.
- **Test Connection:** Opens the selected transport temporarily, verifies that the configured endpoint can be reached, reports success or failure, and then closes the test transport without changing the active machine session.
- **Connect:** Opens the selected transport, stores the active CNC session, starts the receiver thread, updates the topbar, and requests controller information/status.
- **Connected view:** After connection, the modal switches to a connection details view showing the active endpoint, mode, controller profile, and detected controller information when available.
- **Disconnect:** Closes the active transport, stops the receiver loop, resets streaming state, updates the CNC page, and returns the topbar status to **Connect**.
- **Live status updates:** GRBL/FluidNC status reports and Marlin position reports update the CNC page and topbar state with colors for Idle, Run, Jog, Hold, Alarm, and related machine states.
- **Status polling options:** The terminal panel includes options to enable/disable status polling and hide/show status report messages in the console.

### CNC Control Page Functions

- **Connection panel:** Shows the current connection state, endpoint description, detected controller details, and a compact button for opening the connection modal.
- **Position/DRO panel:** Displays work coordinates and machine coordinates for X, Y, and Z using parsed controller status responses.
- **Jog panel:** Provides X/Y/Z jogging controls, selectable step sizes, and adjustable jog feed rate.
- **Zero controls:** Supports zeroing X, Y, Z, or all axes through the active controller profile.
- **Overrides and system controls:** Provides homing, unlock, reset, hold, resume, feed override up/down/reset, spindle override up/down/reset, controller info, and controller configuration dump actions where supported by the selected profile.
- **Macro controls:** Includes probe Z and laser toggle commands driven by the active controller profile.
- **Direct G-code streaming:** Streams the selected CNCJob object directly to the connected controller, tracks progress, and supports pause/resume and stop.
- **Optional SD job controls:** Requests SD file listings from supported controllers and can start an SD file job from the selected file.
- **Terminal console:** Shows timestamped TX/RX/info/warning/error messages and allows manual G-code or controller command entry.
- **Command safety:** Commands are checked against connection state before sending, and unsupported profile commands report a warning instead of failing silently.
- **Receiver loop:** Continuously reads controller responses in the background, parses status, SD listings, controller information, and error/alarm messages.
- **FluidNC file manager:** In FluidNC Web mode, the Files tab can list files, switch filesystems, upload files, create folders, delete files/folders, move up to parent folders, return to root, and enter folders by double-clicking.
- **Busy and progress feedback:** File operations and G-code streaming report progress or busy messages in the CNC interface.
- **Integrated toolbar launch:** The CNC toolbar button opens the CNC page, while the adjacent **Connect/Connected** status opens only the connection modal.

---

## 🛠 Installation & Setup

### 1. Prerequisites
- **Python 3.11** or greater.
- **[Mamba](https://mamba.readthedocs.io/en/latest/installation.html)** or **[Conda](https://docs.conda.io/en/latest/miniconda.html)** (Recommended for dependency management).

### 2. Running from Sources

1. **Clone the repository:**
   ```bash
   git clone https://github.com/thebestgoodguy/flatcam.git
   cd flatcam
   ```

2. **Create the environment:**
   ```bash
   mamba env create -f environment.yml
   ```

3. **Activate the environment:**
   ```bash
   mamba activate flatcam
   ```

4. **Launch FlatCAM Plus:**
   ```bash
   python flatcam.py
   ```

### 📦 Manual Installation (pip)
If you prefer not to use Conda, you can install dependencies via pip:
```bash
pip install -r requirements.txt
python flatcam.py
```

---

## ℹ️ Support & Contact

- **Contact:** Reach out via the application menu:
  `Menu -> Help -> About FlatCAM Plus -> Programmers -> Sadri ERCAN`

---

## ⚖ License
FlatCAM is open-source software. Refer to the `LICENSE` file for details.
