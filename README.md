<p align="center">
  <img width="1376" height="768" alt="FlatCAM Plus splash" src="https://github.com/user-attachments/assets/b4707bd9-e9cb-45d9-be65-253b034f5bd6" />
</p>

<h1 align="center">FlatCAM Plus</h1>
<h3 align="center">PCB CAM, pen plotting, CNC control, live placement, auto-leveling, and release-ready G-code in one Windows-focused workspace.</h3>

<p align="center">
  <img alt="Version" src="https://img.shields.io/badge/version-1.1.0%20beta-31b0d5" />
  <img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white" />
  <img alt="PyQt" src="https://img.shields.io/badge/UI-PyQt6-41cd52" />
  <img alt="Platform" src="https://img.shields.io/badge/platform-Windows-lightgrey?logo=windows" />
  <img alt="CNC" src="https://img.shields.io/badge/CNC-GRBL%20%7C%20FluidNC%20%7C%20Serial%20%7C%20TCP-orange" />
</p>

<p align="center">
  <strong>Modern PCB manufacturing from CAM import to machine motion.</strong><br>
  Import Gerber and Excellon files, generate PCB milling toolpaths, verify mapped G-code, simulate the real XY machine path, probe the board surface, and stream jobs directly to CNC controllers.
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> |
  <a href="#key-improvements">Key Improvements</a> |
  <a href="#new-features">New Features</a> |
  <a href="#installation-and-setup">Installation</a> |
  <a href="#support-the-project">Support</a> |
  <a href="#contributors">Contributors</a>
</p>

---

## Features

| Feature | Description |
| --- | --- |
| PCB CAM Workflow | Import Gerber and Excellon files, prepare Geometry objects, generate CNCJob output, and keep board layers aligned from CAM export to machine path. |
| PCB Pen Plotter | Generate follow or fill pen paths from Gerber copper, use the Plotter Pen DB preset, and output GRBL-safe pen-up/pen-down G-code without spindle commands. |
| Integrated CNC Control | Connect over Serial, TCP/Telnet, or FluidNC Web/HTTP with live DRO, jogging, work zeroing, macros, SD jobs, terminal commands, and queued streaming. |
| Live Placement | Place the job exactly on the workspace using canvas position plus saved X/Y/Angle adjustments before preview, probing, simulation, or engraving. |
| Safe XY Simulation | Run the transformed toolpath as XY-only motion at Safe Z, skipping Z plunges, probe moves, and spindle-on commands before the real cut. |
| Auto-Level Probing | Probe a PCB surface, build a height map, segment arcs and long moves, and apply mapped Z compensation during streaming. |
| G-Code Verification | Preview and Verify analyze the same mapped coordinates used by streaming, including bounds, warnings, travel limits, feed/spindle issues, and estimated runtime. |
| Machine Profiles | Store Safe Z, jog feed, probe feed, spindle max RPM, and X/Y/Z travel limits for repeatable machine setup. |
| Project Workspace | Start from a project splash, organize files in a tree, inspect properties in a right sidebar, and work inside a CNC-style manufacturing UI. |
| 3D CNC Preview | Render CNCJob output in a dedicated 3D preview plugin with PCB-style board visualization and engraved Z-depth channels. |
| AI Assistant | Use a project-aware assistant with OpenAI-compatible, local, Gemini, and Claude providers for CAM and CNC workflow analysis. |
| Modular Architecture | CNC Control is split into focused modules for profiles, transports, widgets, dialogs, machine profiles, and dashboard sections. |

## Why This Fork

| Feature | Description |
| --- | --- |
| Machine-first workflow | The CNC dashboard is built around what the operator needs before motion: connection, position, origin, placement, preview, simulation, probing, and streaming. |
| Preview equals stream | Preview, Verify, Simulate, probing, auto-leveling, and queue streaming share the same mapped coordinate chain. |
| Safer first cuts | The Simulate button runs the transformed job path as XY-only motion at Safe Z, so the machine path can be checked before the cutter touches the PCB. |
| Modern FlatCAM base | FlatCAM Plus keeps the proven FlatCAM CAM foundation while modernizing the UI, project model, runtime, and CNC workflow. |

## Quick Start

1. Create a project and set the PCB/workspace size.
2. Import Gerber and Excellon files, then generate Geometry and CNCJob outputs.
3. For pen plotting, open **PCB Plotter**, generate a follow/fill plotter Geometry, then create a Plotter Job.
4. Open **CNC Control**, connect over Serial, TCP/Telnet, or FluidNC Web/HTTP.
5. Use **Live Placement** to put the job exactly where it should run.
6. Click **Preview**, **Verify**, then **Simulate** to confirm the mapped XY path at Safe Z.
7. Probe the board if needed, set work zero, and run the queue.

**Current release:** `1.1.0` beta, released `2026/06/05`.

FlatCAM Plus is forked from the modern FlatCAM codebase maintained by Marius Stanciu (c) 2019 and based on [FlatCAM](http://flatcam.org/) (c) 2014-2018 Juan Pablo Caram.

---


## Key Improvements

FlatCAM Plus modernizes the FlatCAM workflow with a stronger Windows runtime, cleaner manufacturing settings, more reliable CAM data handling, and an integrated CNC control workspace.

### Platform and Reliability

| Feature | Description |
| --- | --- |
| Modern runtime | The project targets **Python 3.11+** and **PyQt6** for improved maintainability. |
| Windows-focused stability | Core application behavior is tuned for current Windows environments. |
| Safer UI updates | Background plotting and CNC UI refresh paths are hardened against deleted Qt/C++ wrapper errors. |
| Resilient plugin startup | Optional dependency and plugin loading failures are handled more gracefully. |
| Unused plugin cleanup | Removed disconnected, incomplete, or obsolete plugin remnants, including dead toolbar shortcuts, stale PDF-import hooks, the empty Geo Stitch editor plugin, and the unused standalone Transform plugin. |
| Dedicated CNC 3D Preview plugin | A new standalone CNCJob preview plugin renders generated G-code jobs in a clean EasyEDA/Fusion-style 3D canvas with a standard PCB-green board, single-sided engraved Z-depth cut channels, a corner orbit gizmo, top/fit controls, middle-mouse panning, and modular sub-sections for future expansion. |
| Legacy 3D Area removed | The old `Options -> Experimental -> 3D Area` entry and its legacy PlotCanvas3d implementation were removed in favor of the dedicated CNC 3D Preview plugin. |
| AI Assistant plugin | A project-aware assistant panel can connect to OpenAI-compatible, local, Gemini, and Claude providers to analyze Gerber, Excellon, Geometry, and CNCJob context from inside FlatCAM Plus. |
| Coordinate-preserving imports | Imported Gerber and Excellon files keep their source coordinates so copper, outline, and drill layers from the same CAM export stack remain aligned exactly as generated. |
| CNCJob compatibility hardening | Older projects that do not carry Auto Levelling option keys now receive safe fallback defaults instead of failing during CNCJob creation. |
| Localization build fix | Contributor update from [@rickwargo](https://github.com/rickwargo) excludes the Linux `.desktop` launcher from Sphinx gettext builds to prevent duplicate `FlatCAM Plus` message IDs. |
| Modern project startup | FlatCAM Plus now opens into a project splash workspace with **Create New Project** and **Open Project** actions instead of immediately showing an empty canvas. |
| Saved layout migration | The modern workspace layout version resets stale Qt window/dock state when needed, preventing older saved layouts from compressing the main canvas or splash area. |
| Gerber editor preview fix | Gerber Editor now allocates the required VisPy layers for PCB preview mode, so copper traces render over the board background without repeated shape collection index errors. |
| Geometry editor fixes | Contributor updates from [@ecp2022](https://github.com/ecp2022) restore unselected geometry line display and make Geometry Editor shape deletion safer while iterating selections. |
| Contributor stability fixes | Contributor updates from [@codehero](https://github.com/codehero) add Geometry Editor tab-cut workflow support, include interior isolation cut paths, fall back safely when translation catalogs are missing, and restore project objects on the GUI thread. |

### CAM and Tool Data

| Feature | Description |
| --- | --- |
| Improved geometry handling | High-precision buffering and stable geometry unions improve Gerber visualization and toolpath reliability. |
| Database-backed tool setup | Milling and isolation tools can use Tools Database records with automatic parameter mapping. |
| DB-first tool presets | Cutting parameters belong to Tools Database presets; Preferences provide fallback defaults only when a preset or older project is missing a value. |
| Dynamic parameter sync | Tool table, Milling parameters, and generated geometry are kept in sync before CNCJob generation. |
| CNCJob generation hardening | Missing Milling defaults in older projects or database tools are completed automatically before G-code generation. |
| V-tool accuracy | Shape, tip diameter, and related V-bit settings persist more reliably for isolation workflows. |
| Copper-aware isolation | The Isolation plugin now includes **Generate With Copper**, a second generation path that uses the selected isolation tool while preserving large copper pours and filtering frame-like outer paths. |
| PCB Plotter workflow | A new **PCB Plotter** plugin creates plotter-ready follow and fill Geometry objects from Gerber copper while preserving the existing Milling and CNC workflows. |
| Plotter Pen Tools DB preset | Tools Database now auto-seeds a non-destructive `Plotter Pen` preset with pen diameter, Z-offset, feedrate, travel Z, and `GRBL_11_pen_plotter` preprocessor values. |
| Trace-only fill plotting | `Generate Fill Path` builds hatch lines only from trace/pad copper polygons and filters large board/background regions so filled plotter jobs do not flood the whole board surface. |
| Plotter-specific operation panel | Plotter Geometry objects open a simplified right-sidebar workflow with `Generate`, `Plotter Operation`, `Pen Parameters`, `Z-Offset`, and `Generate Plotter Job` labels. |
| Project-tree aware plugin object selectors | Plugin object combo boxes now target the real Gerber, Excellon, Geometry, and CNCJob groups under the project root, so tools see actual files instead of group labels. |
| Excellon DB loading | Excellon object properties can load drilling parameters from Tools Database presets, with clearer diagnostics when matching diameters or drilling-target presets are missing. |
| Excellon Unit Scaling Fix | Restored unit conversion logic for drill objects, ensuring tool diameters and depths scale correctly between MM and IN. |
| Reference-aware rotation | Toolbar and plot-area Rotate actions use the Transform Plugin reference setting, so late-loaded Excellon drill files can be rotated around the Gerber board center instead of only their own selection bounds. |
| Gerber object action layout | Gerber object actions place editor and information controls side by side for quicker access in the object properties panel. |

### CNC Workflow

| Feature | Description |
| --- | --- |
| Integrated CNC controller | Connection management, live status, jogging, machine profiles, work zeroing, job streaming, macros, terminal commands, SD jobs, and FluidNC file operations are available inside the CNC workspace. |
| Operational dashboard layout | Feed/spindle status, G-code sender, position, jog, overrides, macros, job setup, preview, and terminal sections are arranged for direct machine operation. |
| Unified CNC-style workspace UI | Preferences, the canvas tab area, the left sidebar, project trees, and selected Gerber/Excellon/CNCJob property panels now share the CNC Control visual language with clearer buttons and bordered panels. |
| Canvas context tools | The plot-area right-click menu includes Rotate for selected objects, matching the toolbar Rotate workflow. |
| CNC toolbar connection access | The toolbar CNC connection/settings action opens the CNC connection modal directly, with serial, WiFi/TCP GRBL, and FluidNC Web/HTTP modes. |
| CNC auto connect | The connection modal can remember the last selected transport settings and automatically try to reconnect in the background on the next CNC Control startup. |
| Offline G-code validation | The CNC dashboard Preview and Verify actions work without an active controller connection and report clear status, warnings, and empty-job feedback. |
| Live Placement workflow | CNCJob coordinates now start from their canvas position and can be adjusted in the Live Placement modal with exact X, Y, and Angle values before preview, probing, auto-leveling, or streaming. |
| Workspace-bound job size | Job W and Job H are bound to the project workspace size so the CNC preview, Live Placement modal, and probing area share the same material rectangle. |
| Job-size preview canvas | The G-code preview panel includes a 2D material canvas that draws the selected job inside the configured PCB/work area, including origin, grid, saved Live Placement transform, rapid moves, cutting moves, and outside-job warnings. |
| Safe-height XY simulation | G-Code Preview / Verification now includes a Simulate action that streams the transformed job path as XY-only motion at Safe Z, skipping Z plunges, probing, and spindle-on commands for dry-run validation. |
| Section help modals | CNC Control dashboard sections include inline help icons that explain the controls and live values inside that specific panel. |
| Auto leveling | CNC Control can probe a PCB height map and apply measured Z compensation while streaming a selected CNCJob. |
| Safer streaming and jogging | Queue streaming waits for controller `ok`/`error` acknowledgements, and jog commands are serialized and blocked during probing or streaming to avoid delayed motion conflicts. |
| GRBL status visibility | Homing state and active X/Y/Z limit inputs are normalized and shown in the CNC dashboard for clearer WiFi/TCP GRBL operation. |
| Machine-aware G-code metadata | Exported G-code now records the active machine profile, travel limits, safe Z, and max spindle RPM as header comments, while Verify checks X/Y/Z motion bounds against the active profile. |
| CNC Bed Compensation | Preprocessors now support unit-aware **Bed Offset** and **Bed Skew** compensation for non-square machine beds, ensuring milling accuracy across the entire workspace. |
| Modular CNC architecture | CNC controller features are split into focused modules under `appPlugins/cnc_control/` for easier maintenance and future plugin-style extensions. |
| Centralized manufacturing preferences | Core machine setup starts from a dedicated Manufacturing Settings group before deeper plugin-specific defaults. |

### Workspace and Project UI


| Feature | Description |
| --- | --- |
| Project-first startup | On application launch, the canvas area is replaced by a modern splash panel until a project is created or opened. |
| Project creation modal | New projects request a project name and save location, then populate the left project tree with the project root and object groups. |
| Full-height project sidebar | The left sidebar is a dedicated project tree with rounded container styling and a midpoint toggle handle. |
| Right properties/tool sidebar | Gerber, Excellon, Geometry, CNCJob properties and plugin/tool panels open in a right sidebar, keeping the canvas area focused on plotting and large work surfaces. |
| Canvas tab workspace | Plot tabs remain in the main canvas container, while object and plugin settings are routed to the right sidebar unless a tool explicitly needs a large canvas-area workspace. |
| Toolbar container refresh | The top toolbar uses a rounded white outer container with a recessed inner toolbar surface, left-aligned tool actions, and a CNC connection status control on the right. |
| Status container refresh | Status, coordinates, units, grid, and activity indicators are hosted in a rounded workspace status container below the canvas area. |
| Sidebar toggles | Left project and right settings sidebars can be collapsed and restored from overlay toggle buttons positioned on the workspace edges. |
| Light themed main menu | The main toolbar menu now follows the active light theme instead of using a dark detached menu style. |
| Tree-based project organization | The project tree uses the project name as the root, with Gerber, Excellon, Geometry, CNC Job, Script, and Document groups below it. |
| Double-click properties | Double-clicking objects in the project tree opens their properties in the right sidebar. |
| Plugin compatibility with project tree | All plugin object selectors were updated for the project-root tree structure so actions such as Isolation, NCC, Milling, Paint, Panelize, Film, Punch, Rules Check, and others resolve the selected file correctly. |

---

## New Features

### PCB Pen Plotter

FlatCAM Plus now includes a dedicated PCB pen plotter workflow for drawing PCB artwork on paper or copper before transfer/etching.

| Feature | Description |
| --- | --- |
| PCB Plotter plugin | Opens from the Plugins menu or toolbar and manages pen width, pen-down Z offset, pen-up Z, draw feed, Z feed, rapid feed, mirror, and follow/fill mode. |
| Plotter Pen preset | A `Plotter Pen` Tools Database record is created automatically and can be loaded into the plotter panel without overwriting existing user edits. |
| GRBL pen preprocessor | `GRBL_11_pen_plotter` emits units, absolute positioning, pen-up travel, pen-down draw moves, and avoids `M03`/`M04` spindle start commands. |
| Generate Follow Path | Creates a plotter Geometry from Gerber follow geometry and immediately opens its right-sidebar properties panel. |
| Generate Fill Path | Creates a trace/pad-only hatch Geometry for etch-resistant pen filling while skipping large board/background polygons. |
| Simplified Geometry panel | Plotter Geometry shows a `Generate` action and hides Paint, NCC, Utilities, and Transformations controls that are not part of the plotter flow. |
| Plotter Operation panel | The downstream CNCJob panel switches to plotter wording, hides Excellon, Shape, spindle/dwell, and Common Parameters, and exposes `Pen Parameters`, `Z-Offset`, and `Generate Plotter Job`. |
| Safety examples and validator | Example pen-plotter G-code files and `scripts/validate_pen_plotter_gcode.py` check for safe units, absolute mode, pen-up travel, and no rapid XY travel while the pen is down. |

### CNC Connection and Control

FlatCAM Plus includes a built-in CNC control workflow for managing machine sessions without leaving the application.

| Feature | Description |
| --- | --- |
| Connection dialog | Serial, TCP/Telnet, and FluidNC Web/HTTP settings are managed from one modal. |
| Auto Connect | Users can enable Auto Connect after configuring the controller. On the next CNC Control startup, FlatCAM Plus tries the saved connection in the background and stops after a short retry sequence if the machine is offline. |
| Controller profiles | FluidNC, GRBL, Smoothieware, Marlin, and generic G-code profiles provide controller-specific commands. |
| WiFi GRBL mode | TCP/Telnet connections default to the GRBL profile, while Web/HTTP connections default to FluidNC. |
| Connection testing | Selected transports can be tested before opening an active machine session. |
| Live machine status | Controller reports update the toolbar, DRO, machine state, position, and controller details. |
| Limit input indicators | Active GRBL `Pn:` limit inputs are shown beside X/Y/Z DRO rows and logged only when they change. |
| Safe disconnect | Active transports, receiver threads, streaming state, and UI indicators are reset cleanly. |

### CNC Dashboard

The CNC page is organized as a compact production dashboard:

| Feature | Description |
| --- | --- |
| Top row | Feed and spindle indicators sit beside Machine Profiles and G-code job streaming. |
| Control row | Position, Jog, Overrides & System, and Saved Macros share the same row for faster access. |
| Job setup row | Workspace-bound job size, origin, Live Placement, and XY/Z/XYZ zero buttons sit next to G-Code Preview / Verification. |
| Preview row | G-Code Preview / Verification displays the material canvas, selected job statistics, transformed G-code, and warnings before sending. |
| Terminal console | Manual commands, TX/RX messages, warnings, errors, and polling controls are grouped below the machine controls with a taller console for longer GRBL sessions. |
| Context help | Each main dashboard section has a header help icon with a focused modal explaining only that section's parameters and actions. |

### Machine Profiles

| Feature | Description |
| --- | --- |
| Profile selector | Switch between saved CNC machine configurations directly from the dashboard. |
| Profile settings | Store safe Z, default jog feed, probe feed, max spindle RPM, and X/Y/Z travel limits. |
| Applied defaults | Selecting a profile updates jog feed, spindle RPM limit, probe feed behavior, and machine summary. |
| Profile manager | The **Manage** button opens a modal editor for creating, editing, deleting, and saving profiles. |
| Preferences access | Profiles are also available under `Preferences -> Plugins -> Manufacturing Settings`. |

### Auto Leveling and Probe Workflow

| Feature | Description |
| --- | --- |
| Probe pin workflow | GRBL/FluidNC probe reports are parsed from `[PRB:x,y,z:1]` responses and used by the CNC Control height-map workflow. |
| Height map probing | The Auto Level panel can fit the probing area from the selected CNCJob, probe a configurable grid, and store a reusable height map. |
| High-Precision Probing | Implemented a dual-stage **"Fast Seek + Slow Touch"** probing cycle (Candle-style) to prevent PCB surface deformation and ensure sub-micron Z-zero accuracy. |
| Advanced Auto-Leveling | Added support for **G2/G3 arc path segmentation** and G91 incremental moves within the surface-following engine, allowing precise leveling even for complex curved geometries. |
| Map application | When **Use Map** is enabled, queue streaming applies bilinear Z compensation to cutting moves while preserving the original XY placement workflow. |
| Safe probing controls | Probing uses configured safe Z, probe depth, probe feed, selected WCS, spindle stop, stop/cancel state, and progress feedback. |

### Manufacturing Preferences

| Feature | Description |
| --- | --- |
| Manufacturing Settings | A top-level production group summarizes active machine setup in one predictable place. |
| Tool preset source | Milling, Drilling, Cutout, Isolation, Paint, and NCC cutting values are intended to be configured in Tools Database presets. |
| Focused Milling defaults | Core Milling settings are shown first; advanced, exclusion, polish, laser, and Excellon milling options are collapsed by default. |
| Focused Isolation defaults | Common isolation routing controls are easier to reach while advanced options stay available when needed. |
| Fallback defaults | Preferences remain available as safe defaults for new presets, missing DB keys, older project files, and non-preset workflows. |
| Backward compatibility | Existing preference keys are preserved so saved defaults and project behavior continue to work. |

### PCB Copper Isolation

| Feature | Description |
| --- | --- |
| Generate Geometry | The existing Isolation workflow remains available for standard isolation routing. |
| Generate With Copper | A new button below **Generate Geometry** uses the selected isolation tool and parameters to create copper-pour-friendly isolation geometry. |
| Copper pour preservation | Large copper fills, such as GND pours exported from EasyEDA, are treated as copper to keep rather than copper to clear. |
| Frame filtering | Frame-like outer paths that wrap the Gerber bounds are filtered so board outlines are not accidentally included in the engraving job. |
| Same downstream flow | The resulting `_copper_iso` Geometry object is milled into a CNCJob with the normal Milling plugin workflow. |

### Job Setup, Placement, and Work Zeroing

| Feature | Description |
| --- | --- |
| Simplified setup panel | The CNC dashboard uses a focused **Job Setup / Zero** panel instead of exposing probing, WCS, probe travel, plate, feed, and retract controls during normal job setup. |
| Job size | Job W and Job H follow the project workspace size so preview, Live Placement, probing, and streaming all use the same material dimensions. |
| Origin selection | Choose the physical point to zero on the machine: Back-Left, Bottom-Left, Center, or raw absolute G-code XY. |
| Live Placement | Placement is always handled through Live Placement. Jobs open at their canvas position by default, then the **Live Placement** modal can save exact X, Y, and Angle adjustments. |
| Coordinate consistency | Preview, Verify, probing, auto-leveling, and streamed G-code use the same origin-aware Live Placement transform, including Back-Left `Y=0..H`, Bottom-Left `Y=-H..0`, and centered workspace modes. |
| Work zeroing | XY, Z, or XYZ work zero can be set with `G10 L20`; supported GRBL/FluidNC workflows activate `G54` automatically before zeroing and before queue streaming. |
| Transformed streaming | `START QUEUE` streams the same transformed coordinates shown in preview, so the controller receives the job already mapped to the configured origin and saved Live Placement transform. |
| Mapped bounds logging | Before each streamed job, the terminal reports the mapped XY bounds so the operator can confirm placement numerically. |

### Jobs, Preview, Files, and Macros

| Feature | Description |
| --- | --- |
| Direct job streaming | Generated CNCJob objects can be streamed with progress tracking, pause/resume, and stop. |
| Job Queue / Sender | Multiple CNCJob objects can be queued, reordered, removed, and streamed sequentially. |
| Queue progress | The sender table shows queued, running, stopped, and completed jobs while the global progress bar tracks total queued lines. |
| Acknowledgement-gated sender | The sender waits for controller acknowledgements before advancing to the next G-code line and reports when the controller stops responding. |
| G-Code Preview / Verification | Selected jobs show line counts, motion statistics, bounds, estimated runtime, and safety warnings. |
| Material canvas preview | The preview panel draws the selected CNCJob inside the configured job size, including grid, origin crosshair, saved Live Placement transform, rapid/cut paths, path bounds, and outside-job warnings. |
| Mapped coordinate preview | Preview and Verify analyze the transformed G-code used for streaming, not only the original plot-area coordinates. |
| XY-only simulation | The Simulate button uses the same transformed G-code chain as streaming, but sends only safe-height XY moves so the user can confirm the real machine path before engraving. |
| Offline preview refresh | Preview and Verify refresh the CNCJob list, read generated G-code from multiple CNCJob sources, and confirm successful analysis in the terminal even when no CNC is connected. |
| Verification checks | The verifier flags missing units or positioning mode, cutting before spindle/feed setup, rapid XY motion below Z zero, pause commands, and X/Y/Z travel limit risks from the active machine profile. |
| Machine profile export notes | G-code exports include the active profile name, travel limits, safe Z, and max spindle RPM as comments for traceability; controller firmware limits such as GRBL `$130/$131/$132` remain controller settings and are not overwritten by job files. |
| SD job control | Supported controllers can list SD files and start selected SD jobs. |
| Flash File System modal | FluidNC Web mode provides a modal file manager for listing, uploading, creating folders, deleting, navigating, and opening directories. |
| Saved Macros panel | Saved macros are visible in the main control row, with a **Manage Macros** modal for editing macro names and G-code content. |

### CNC Plugin Structure

The CNC control feature is organized as a plugin-like package under `appPlugins/cnc_control/`:

- `profiles.py` stores controller command profiles.
- `transports.py` contains Serial, TCP/Telnet, and FluidNC HTTP transport implementations.
- `widgets.py` contains reusable CNC widgets such as styled buttons, dashboard gauges, and the job-size G-code preview canvas.
- `machine_profiles.py` stores defaults and normalization helpers for machine profiles.
- `dialogs.py` contains modal workflows for Flash File System, macro management, and machine profile management.
- `sections.py` registers dashboard sections for gauges, machine profiles, job sender, G-code preview, position, jog, job setup, overrides, macros, terminal, and modal actions.
- `ui.py` assembles the CNC dashboard from registered sections.

### CNC 3D Preview Plugin Structure

The standalone CNC 3D preview feature is organized under `appPlugins/cnc_preview_3d/`:

- `renderer.py` owns the independent VisPy scene for CNCJob G-code rendering and draws cut paths as single-sided engraved Z-depth channels instead of mirrored or extruded underside geometry.
- `sections.py` registers modular preview panels for job selection and render stats.
- `ui.py` assembles the plugin page with a side control panel, full 3D canvas, corner orbit gizmo, top/fit controls, and middle-mouse panning support through the preview camera.

### AI Assistant Plugin Structure

The AI assistant feature is organized under `appPlugins/ai_assistant/`:

- `providers.py` contains OpenAI-compatible, OpenRouter, LM Studio, Ollama, Gemini, and Claude connection helpers.
- `dialogs.py` manages provider settings, API keys, model options, system prompts, and analysis context selection.
- `ui.py` assembles the assistant chat panel for project-aware PCB/CAM questions.

---
## Installation and Setup

### 1. Prerequisites
- **Python 3.11** or greater.
- **[Mamba](https://mamba.readthedocs.io/en/latest/installation.html)** or **[Conda](https://docs.conda.io/en/latest/miniconda.html)** (Recommended for dependency management).

### 2. Running from Sources

1. **Clone the repository:**
   ```bash
   git clone https://github.com/thebestgoodguy/FlatCAM-Plus.git
   cd FlatCAM-Plus
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

### Manual Installation (pip)
If you prefer not to use Conda, you can install dependencies via pip:
```bash
pip install -r requirements.txt
python flatcam.py
```

### 3. Desktop Packaging

FlatCAM Plus does not currently ship with official Windows, macOS, or Linux installer artifacts in this repository. Users who clone the repository can still create local desktop packages from source.

Packaging should be done on the target operating system because PyQt, OpenGL/VisPy, GDAL, Rasterio, and other native dependencies are platform-specific.

- macOS users can run `FlatCAMPlus_macos_dmg_generator.command` to build a `.app` bundle and `.dmg`.
- Linux users can run `FlatCAMPlus_linux_portable_generator.sh` to build a portable folder and `.tar.gz` archive.
- Windows users can build x32 and x64 Inno Setup installers from the separate `FlatCAMPlus_x32_installer_generator.bat` and `FlatCAMPlus_x64_installer_generator.bat` files.

See [`PACKAGING.md`](PACKAGING.md) for Windows, macOS, and Linux packaging commands.

---

## Support the Project

FlatCAM Plus is developed and maintained as an open-source project. If it helps your PCB, CNC, or CAM workflow, sponsorship helps cover the time, testing, and release work needed to keep the project alive.

Your support is appreciated and helps make continued development possible.

[Sponsor FlatCAM Plus on GitHub](https://github.com/sponsors/thebestgoodguy)

---

## Support and Contact

- **Contact:** Reach out via the application menu:
  `Menu -> Help -> About FlatCAM Plus -> Programmers -> Sadri ERCAN`

---

## Contributors

- **Sadri ERCAN** - FlatCAM Plus maintainer and project modernization.
- **[@codehero](https://github.com/codehero)** - PRs #7, #8, #9, and #10: project restore GUI-thread safety, missing translation catalog fallback, interior isolation cut paths, and Geometry Editor tab-cut workflow support.
- **[@ecp2022](https://github.com/ecp2022)** - Geometry Editor fixes for unselected line display and safer shape deletion.
- **[@rickwargo](https://github.com/rickwargo)** - PR #6 localization build fix: excluded the Linux `.desktop` launcher from gettext extraction and removed duplicate `FlatCAM Plus` translation entries.

---

## License

FlatCAM base code and MIT-licensed project components are covered by the root `LICENSE` file.

The CNC Control, PCB Plotter, CNC 3D Preview, and AI Assistant modules are licensed separately and are not covered by the root MIT license:

- `appPlugins/ToolCNCControl.py`
- `appPlugins/cnc_control/`
- `appPlugins/ToolPlotter.py`
- `preprocessors/GRBL_11_pen_plotter.py`
- `appPlugins/ToolCNCPreview3D.py`
- `appPlugins/cnc_preview_3d/`
- `appPlugins/ToolAIAssistant.py`
- `appPlugins/ai_assistant/`

See `appPlugins/cnc_control/LICENSE`, `appPlugins/cnc_preview_3d/LICENSE`, and `appPlugins/ai_assistant/LICENSE` for the separate module license terms. The PCB Plotter plugin and `GRBL_11_pen_plotter` preprocessor use the same non-commercial license terms as CNC Control. These modules may be used, studied, modified, and shared for non-commercial purposes, but they may not be sold, sublicensed, monetized, or included in a commercial product or service without separate written permission from Sadri ERCAN.
