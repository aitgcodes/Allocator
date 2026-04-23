# MS Thesis Advisor Allocation — Windows Docker Installation Guide

This guide covers how to run the Allocator on Windows using Docker Desktop.
No Python, Conda, or any other runtime needs to be installed — Docker bundles everything.

---

## 1. Prerequisites

### 1.1 System requirements

| Requirement | Minimum |
|-------------|---------|
| Windows version | Windows 10 (version 2004, Build 19041) or Windows 11 |
| RAM | 4 GB (8 GB recommended) |
| Disk space | ~2 GB free for the Docker image |
| Architecture | x86-64 (Intel / AMD) — ARM devices not supported |

WSL 2 (Windows Subsystem for Linux 2) must be enabled. Docker Desktop installs it automatically if it is not already present.

---

### 1.2 Install Docker Desktop

1. Download Docker Desktop for Windows from [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/).
2. Run the installer. Accept the default options — "Use WSL 2 instead of Hyper-V" should be selected.
3. When prompted, restart your computer.
4. After reboot, Docker Desktop launches automatically. Wait for the whale icon in the system tray to stop animating — that means Docker is ready.

> **First-time setup:** Docker Desktop may prompt you to install or update WSL 2. Follow the on-screen instructions; this is a one-time step.

---

### 1.3 Install Git (optional)

Git is only needed to download the project. If you already have the project folder, skip this step.

Download the installer from [git-scm.com](https://git-scm.com) and run it with default options.

---

## 2. Download the Project

Open **PowerShell** (press `Win + X` → "Windows PowerShell") and run:

```powershell
git clone https://github.com/aitgcodes/Allocator.git
cd Allocator
```

If you received the project as a ZIP file instead, extract it and open PowerShell inside the extracted folder:

```powershell
cd C:\path\to\Allocator
```

---

## 3. Build and Start the Container

All commands below are run from the `Allocator` folder in PowerShell.

### 3.1 First run — build the image and start

```powershell
docker compose up --build
```

This downloads the base Python image, installs all dependencies, and starts the app.
It takes **2–5 minutes** on the first run. Subsequent starts are nearly instant.

You will see output like:

```
 [+] Container allocator-allocator-1  Started
...
Dash is running on http://0.0.0.0:8050/
```

### 3.2 Open the app

Open any browser and go to:

```
http://localhost:8050
```

The Allocator interface will load immediately.

---

## 4. Normal Usage (after the first run)

### Start the app

```powershell
docker compose up
```

### Stop the app

Press `Ctrl + C` in the PowerShell window where the container is running, or from a second PowerShell window:

```powershell
docker compose down
```

### Start in the background (optional)

```powershell
docker compose up -d
```

To stop a background container:

```powershell
docker compose down
```

---

## 5. Uploading Your Own Data

The Allocator accepts CSV or Excel files uploaded directly through the browser UI — no file-system access is required.

1. Prepare your files according to the formats below.
2. Open `http://localhost:8050`.
3. Drag and drop (or click to browse) the student file onto the **Students** upload area and the faculty file onto the **Faculty** upload area.
4. Click **Clean & Load** to auto-clean preference columns before loading, or **Load directly** to skip cleaning.

### Student file format

```
student_id, name, cpi, pref_1, pref_2, ...
```

- `student_id` — unique identifier (e.g. `S01`)
- `name` — full name
- `cpi` — cumulative performance index (numeric)
- `pref_1`, `pref_2`, … — faculty IDs in preference order

### Faculty file format

```
faculty_id, name, max_load
```

- `faculty_id` — unique identifier (e.g. `F01`)
- `name` — full name
- `max_load` — maximum students the advisor can take; leave blank to auto-compute

Sample files are bundled with the project at `data/sample_students.csv` and `data/sample_faculty.csv`. Use them to verify the app is working before uploading your own data.

---

## 6. Rebuilding After a Code Update

If the project files change (e.g. you pull a newer version), rebuild the image:

```powershell
git pull
docker compose up --build
```

---

## 7. Troubleshooting

### Docker Desktop is not running

The whale icon in the system tray must be present and steady before running any `docker` command. If it is missing, launch Docker Desktop from the Start menu and wait for it to finish starting.

### Port 8050 is already in use

Another application is occupying port 8050. Either stop that application or change the port mapping in `docker-compose.yml`:

```yaml
ports:
  - "9090:8050"   # change 9090 to any free port
```

Then open `http://localhost:9090` instead.

### `docker compose` command not found

Older Docker installations used `docker-compose` (with a hyphen) as a separate tool. Try:

```powershell
docker-compose up --build
```

If this also fails, update Docker Desktop to the latest version.

### The browser shows "This site can't be reached"

- Confirm the container is running: `docker compose ps` should show `running`.
- Confirm you are using `http://` not `https://`.
- Try `http://127.0.0.1:8050` as an alternative to `localhost`.

### WSL 2 installation fails

If Docker Desktop reports that WSL 2 cannot be installed, enable virtualisation in your BIOS/UEFI settings (look for "Intel VT-x" or "AMD-V") and re-run the Docker Desktop installer.

---

## 8. Uninstalling

To remove the container and image:

```powershell
docker compose down --rmi all
```

To fully uninstall Docker Desktop, use **Settings → Apps → Docker Desktop** in Windows.

---

## Summary

| Step | Command |
|------|---------|
| First start (build + run) | `docker compose up --build` |
| Normal start | `docker compose up` |
| Stop | `Ctrl + C` or `docker compose down` |
| Background start | `docker compose up -d` |
| Rebuild after update | `git pull && docker compose up --build` |
| Remove image | `docker compose down --rmi all` |
