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
