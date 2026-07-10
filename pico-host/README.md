# Pico Host — Web-Based Config Studio

A Flask-based web server that provides a browser-accessible config editor for Raspberry Pi Pico running CircuitPython. This module solves the challenge of safely editing `config.json` on the Pico's CIRCUITPY filesystem partition with automatic mounting, session management, and safe unmounting.

---

## Why This Exists

### The Problem

When editing `config.json` on a Pico running CircuitPython:
1. **Manual mount/unmount** — Users must manually mount the CIRCUITPY partition, edit files, then remember to unmount before disconnecting. Forgetting to unmount risks filesystem corruption.
2. **Hardcoded device paths** — Scripts using `/dev/sdc1` break when the Pico appears as `/dev/sdb1` on the next boot.
3. **No remote access** — The standalone `editor.html` in the project root works only as a local file, requiring physical access to the machine.

### The Solution

This folder contains a **Dockerized Flask backend** that:
- **Auto-discovers** the CIRCUITPY partition using `blkid -L CIRCUITPY` (no hardcoded paths)
- **Auto-mounts** when you click "Load config.json" in the web UI
- **Auto-unmounts** when you save or close the browser tab (via `navigator.sendBeacon`)
- **Runs in Docker** with `--privileged` mode for safe block device access
- **Accessible remotely** — Open `http://<server-ip>:9191` from any device on the network

This is ideal for:
- **Homelab setups** where the Pico is connected to a headless server
- **Remote config editing** without SSH/file transfer
- **Safe workflows** that prevent accidental filesystem corruption

---

## What's Inside

```
pico-host/
├── app.py               # Flask backend (auto-mount API, session management)
├── Dockerfile           # Python 3.12 slim + Flask + util-linux
├── static/
│   └── index.html       # Web-based config editor UI (adapted from root editor.html)
├── build-and-run.sh     # One-command Docker build and run script
└── README.md            # This file
```

**Key difference from root `editor.html`:**
- Root `editor.html` uses browser file picker (`<input type="file">`) — works offline but requires local file access.
- `pico-host/static/index.html` calls Flask API endpoints (`/api/config`) — works remotely, handles mounting automatically.

---

## Technical Details

### How It Works

1. **Backend (Flask + Docker)**:
   - Runs Python Flask server on port `9191`
   - Uses `blkid -L CIRCUITPY` to find the Pico's partition dynamically
   - Mounts partition to `/mnt/pico` inside container when `GET /api/config` is called
   - Keeps partition mounted during editing session
   - Unmounts when `POST /api/config` (save) or `POST /api/config/cancel` (close tab) is called

2. **Frontend (Browser UI)**:
   - Loads `config.json` via `GET /api/config`
   - Renders the same drag-and-drop editor UI as the root `editor.html`
   - Saves via `POST /api/config`
   - Sends beacon on tab close to trigger emergency unmount

3. **Docker Privileged Mode**:
   - Required for accessing `/dev/sdX` block devices
   - Allows `mount` and `umount` syscalls inside container
   - Container runs with `SYS_ADMIN` capability

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Serves the web UI |
| `/api/config` | GET | Auto-discovers CIRCUITPY, mounts it, returns `config.json` |
| `/api/config` | POST | Saves JSON to mounted partition, syncs, unmounts |
| `/api/config/cancel` | POST | Emergency unmount without saving (triggered on tab close) |

---

## Deployment Guide

### Prerequisites

- Docker installed on your Linux host
- Raspberry Pi Pico with CircuitPython (CIRCUITPY partition must exist)
- Pico connected via USB to the host machine

### Quick Start

1. **Navigate to the folder:**
   ```bash
   cd pico-host
   ```

2. **Build and run (one command):**
   ```bash
   ./build-and-run.sh
   ```

3. **Open in browser:**
   ```
   http://localhost:9191
   ```

   Or from another device on the network:
   ```
   http://<server-ip>:9191
   ```

### Manual Deployment

If you prefer manual control:

1. **Build the Docker image:**
   ```bash
   docker build -t pico-config .
   ```

2. **Run the container:**
   ```bash
   docker run -d \
     -p 9191:9191 \
     --privileged \
     --name pico-config \
     pico-config
   ```

   **Flags explained:**
   - `-d` — Run in background (detached mode)
   - `-p 9191:9191` — Expose Flask server on port 9191
   - `--privileged` — Grant access to host block devices (`/dev/sdX`)
   - `--name pico-config` — Container name for easy management

3. **Open the UI:**
   ```
   http://localhost:9191
   ```

### Configuration Changes (If Needed)

**Port number:**
- Default: `9191`
- Change in `app.py` (line: `app.run(host="0.0.0.0", port=9191)`)
- Update `docker run -p` flag to match

**Mount point inside container:**
- Default: `/mnt/pico`
- Change `MOUNT_POINT` variable in `app.py` if needed

**No configuration needed for:**
- Device paths (auto-detected via `blkid -L CIRCUITPY`)
- Host filesystem access (handled by Docker `--privileged`)

---

## Container Management

### View logs:
```bash
docker logs -f pico-config
```

### Stop the container:
```bash
docker stop pico-config
```

### Restart the container:
```bash
docker restart pico-config
```

### Remove the container:
```bash
docker stop pico-config
docker rm pico-config
```

### Rebuild after code changes:
```bash
./build-and-run.sh
```
*(Script automatically stops, removes old container, rebuilds, and restarts)*

---

## Troubleshooting

### "Pico not connected or not visible to the system"
- Check physical USB connection
- Verify CircuitPython is installed on the Pico
- Test on host: `blkid -L CIRCUITPY` (should return `/dev/sdX1`)

### "Error mounting: device is busy"
- Partition is already mounted outside the container
- Unmount on host: `sudo umount /dev/sdX1`
- Check with: `mount | grep CIRCUITPY`

### "Permission denied"
- Container must run with `--privileged` flag
- Restart with correct flags (see Manual Deployment)

### Container doesn't see the device
- Ensure `--privileged` is used (not `--cap-add=SYS_ADMIN` alone)
- Alternative: `--device=/dev/sdX --cap-add=SYS_ADMIN` (but device letter may change)

### Port 9191 already in use
- Change port in `app.py` and `docker run -p` flag
- Or stop conflicting service: `sudo lsof -i :9191`

---

## Security Notice

⚠️ **Warning:** This container runs in `--privileged` mode and has access to **all block devices** on the host system (`/dev/sda`, `/dev/sdb`, etc.). 

**Use only in trusted environments:**
- Local homelab networks
- Dev machines behind firewalls
- Systems where you control physical and network access

**Do not expose** port 9191 to the public internet without authentication (Flask app has no built-in auth).

---

## Workflow Example

1. **Start the server** (one-time setup):
   ```bash
   ./build-and-run.sh
   ```

2. **Open the UI** in browser:
   ```
   http://192.168.1.100:9191
   ```

3. **Click "Load config.json":**
   - Backend finds `/dev/sdb1` (or wherever Pico appears)
   - Mounts to `/mnt/pico`
   - Returns JSON to editor

4. **Edit the config:**
   - Add menu items, outputs, scenarios
   - Change device settings, pin assignments
   - UI is identical to root `editor.html`

5. **Click "Save config.json":**
   - Backend writes to `/mnt/pico/config.json`
   - Calls `sync` to flush buffers
   - Unmounts partition
   - Pico is safe to disconnect

6. **Close the tab:**
   - Browser sends beacon to `/api/config/cancel`
   - Backend auto-unmounts if save wasn't called
   - Prevents hanging mount sessions

---

## Comparison: Root `editor.html` vs `pico-host`

| Feature | Root `editor.html` | `pico-host` Web Server |
|---------|-------------------|------------------------|
| **Access** | Local file only | Network-accessible (remote editing) |
| **Mounting** | Manual (`sudo mount`) | Automatic (via Flask API) |
| **Device detection** | Manual path entry | Auto-discovered via `blkid` |
| **Session safety** | User must remember to unmount | Auto-unmount on save or tab close |
| **Multi-user** | No | Yes (one at a time, session-based) |
| **Deployment** | Open HTML file | Docker container |

**Use root `editor.html` when:**
- Working locally on a dev machine
- No Docker available
- Prefer offline file editing

**Use `pico-host` when:**
- Server/homelab setup with headless host
- Need remote access from laptop/tablet
- Want automatic mount/unmount safety

---

## Contributing

If you extend this module (add authentication, multi-device support, config history, etc.), ensure:
1. Docker build still works without external dependencies
2. API contracts remain backward-compatible
3. Security review for `--privileged` mode implications

---

*Dockerized Flask backend for safe, remote config editing on CircuitPython Pico devices.*
