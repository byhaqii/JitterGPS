# Product Requirement Document (PRD): Jitter GPS Desktop

## 1. Executive Summary
**Jitter GPS Desktop** is a standalone, cross-platform desktop application for macOS and Windows. It overrides and spoofs browser geolocation at the protocol level using Chrome DevTools Protocol (CDP `Emulation.setGeolocationOverride`). Users set a center point, a radius, and an update interval. The app continuously calculates collision-free, randomized coordinates within the defined perimeter and pushes them into all active browser tabs.

---

## 2. Target Platforms & Runtime
- **macOS**: macOS 12+ (Apple Silicon & Intel)
- **Windows**: Windows 10 & 11 (x64)
- **Supported Browsers**: Google Chrome, Microsoft Edge, Brave, Chromium-based browsers.
- **Tech Stack**: Python 3.10+ with `customtkinter` (or native Tkinter) + `websockets` + `requests`. Packageable to `.app` and `.exe` via PyInstaller.

---

## 3. Core Objectives & Non-Goals
### 3.1 Objectives
- **Zero Extension Requirement**: No browser extensions to install, no Chrome Web Store fees.
- **Unbypassable Interception**: Emulates location directly via CDP protocol level, bypassing website anti-extension shields.
- **True Uniform Disc Sampling**: Coordinates distributed evenly across circular area (no center-cluster bias).
- **Collision-Free Coordinates**: Every relocation cycle yields unique `(latitude, longitude)` values within a 6-decimal precision (~11 cm resolution).
- **Cross-Platform Compatibility**: Single codebase runs natively on macOS and Windows with auto-detection of browser binary paths.

### 3.2 Non-Goals
- Spoofing native OS CoreLocation/Windows Geolocation API for non-browser apps (SIP/driver level).
- IP address / VPN / proxy masking.

---

## 4. Functional Specifications

### 4.1 Browser Launch & Attachment
- Detect default browser executable path based on OS:
  - macOS: `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` or Brave/Edge equivalents.
  - Windows: `C:\Program Files\Google\Chrome\Application\chrome.exe` or `C:\Program Files (x86)\...`
- Launch target browser with `--remote-debugging-port=<port>` (default: `9222`) and optional `--user-data-dir` profile flag to avoid interfering with primary browser instances.
- Query `http://127.0.0.1:9222/json/list` to fetch active page sessions.
- Connect to page targets via WebSocket (`webSocketDebuggerUrl`).

### 4.2 Geolocation Jitter Engine
- **Inputs**:
  - `Center Latitude` (float, -90.0 to 90.0)
  - `Center Longitude` (float, -180.0 to 180.0)
  - `Radius` (meters, 5 to 50,000)
  - `Interval` (seconds, 1 to 300)
  - `Accuracy` (meters, default: 10.0)
- **Math Formula (Uniform Disc)**:
  $$r = R \cdot \sqrt{u}, \quad \theta = 2\pi v \quad (u, v \sim \mathcal{U}[0, 1])$$
  $$\Delta \text{lat} = \frac{r \cdot \cos\theta}{111320}$$
  $$\Delta \text{lng} = \frac{r \cdot \sin\theta}{111320 \cdot \cos(\text{center\_lat} \cdot \frac{\pi}{180})}$$
- **Duplicate Prevention**:
  - Values formatted to 6 decimal places: `f"{lat:.6f},{lng:.6f}"`.
  - Stored in a bounded memory set (`seen_coords`, max size 50,000).
  - Loop re-rolls if coordinate already exists in set.

### 4.3 CDP Command Payload
```json
{
  "id": 1,
  "method": "Emulation.setGeolocationOverride",
  "params": {
    "latitude": -6.208812,
    "longitude": 106.845643,
    "accuracy": 10.0
  }
}
```

### 4.4 User Interface Requirements
- Single compact window (dark mode).
- Form fields: Center Lat, Center Lng, Radius (m), Interval (s).
- Action Buttons:
  - **Launch Browser**: Spawns Chrome/Edge with CDP port enabled.
  - **Start / Stop Spoofing**: Starts background thread dispatching coordinates.
  - **Get IP Location**: Resolves current approx coordinates via public IP API for quick center-point setup.
- Activity Log: Scrollable log pane displaying timestamp, generated coordinates, and distance from center.

---

## 5. Error Handling & Edge Cases
- **Port In Use / Connection Refused**: Display clear warning with button to relaunch browser with isolated profile.
- **Tab Closed**: Cleanly drop closed WebSocket connections without crashing background worker.
- **Invalid Inputs**: Block start button and display error badge if latitude/longitude are outside valid geographic limits.
