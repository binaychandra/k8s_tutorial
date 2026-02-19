"""
Demo FastAPI app to demonstrate Kubernetes Persistent Storage.

This app uses a PersistentVolumeClaim to store data that survives
Pod restarts. It exposes endpoints to write, read, list, and delete
files on the persistent volume — proving that data persists.

Mount path: /app/data (backed by a PVC)
"""

import os
import time
import socket
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse

# ──────────────────────────────────────────────────────────
# Storage Configuration
# ──────────────────────────────────────────────────────────
DATA_DIR = os.getenv("DATA_DIR", "/app/data")
POD_NAME = os.getenv("HOSTNAME", "unknown-pod")
APP_NAME = os.getenv("APP_NAME", "storage-demo")
STORAGE_TYPE = os.getenv("STORAGE_TYPE", "PersistentVolumeClaim")

# Ensure data directory exists (for local dev without volume mount)
Path(DATA_DIR).mkdir(parents=True, exist_ok=True)

# Write a startup marker so we can track restarts
STARTUP_FILE = os.path.join(DATA_DIR, ".startup-log.txt")
with open(STARTUP_FILE, "a") as f:
    f.write(f"[{datetime.now().isoformat()}] Pod '{POD_NAME}' started\n")


app = FastAPI(
    title="Kubernetes Storage Demo",
    description="A demo app for learning Kubernetes PV, PVC, and StorageClass",
)


# ──────────────────────────────────────────────────────────
# Helper Functions
# ──────────────────────────────────────────────────────────

def _get_storage_stats() -> dict:
    """Get storage usage statistics for the data directory."""
    try:
        stat = os.statvfs(DATA_DIR)
        total = stat.f_blocks * stat.f_frsize
        free = stat.f_bfree * stat.f_frsize
        used = total - free
        return {
            "total_bytes": total,
            "used_bytes": used,
            "free_bytes": free,
            "total_human": _human_size(total),
            "used_human": _human_size(used),
            "free_human": _human_size(free),
        }
    except (OSError, AttributeError):
        # os.statvfs not available on Windows; fallback
        return {"info": "Storage stats not available on this platform"}


def _human_size(nbytes: int) -> str:
    """Convert bytes to human-readable size."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if nbytes < 1024:
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} PB"


def _list_user_files() -> list[dict]:
    """List all user files (excluding hidden files) in the data directory."""
    files = []
    for f in sorted(Path(DATA_DIR).iterdir()):
        if f.name.startswith("."):
            continue
        files.append({
            "name": f.name,
            "size": _human_size(f.stat().st_size),
            "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
        })
    return files


def _read_startup_log() -> str:
    """Read the startup log (tracks pod restarts)."""
    try:
        with open(STARTUP_FILE, "r") as f:
            return f.read()
    except FileNotFoundError:
        return "(no startup log found)"


# ──────────────────────────────────────────────────────────
# ENDPOINTS
# ──────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def home():
    files = _list_user_files()
    storage = _get_storage_stats()
    startup_log = _read_startup_log()

    file_rows = ""
    for f in files:
        file_rows += f"""
        <tr>
            <td><a href="/read?filename={f['name']}">{f['name']}</a></td>
            <td>{f['size']}</td>
            <td>{f['modified']}</td>
            <td><a href="/delete?filename={f['name']}" style="color:red;">🗑️ Delete</a></td>
        </tr>"""

    if not files:
        file_rows = '<tr><td colspan="4" style="text-align:center;color:#999;">No files yet — try writing one!</td></tr>'

    storage_info = ""
    if "total_human" in storage:
        storage_info = f"""
            <p><span class="label">Total:</span> <span class="value">{storage['total_human']}</span></p>
            <p><span class="label">Used:</span> <span class="value">{storage['used_human']}</span></p>
            <p><span class="label">Free:</span> <span class="value">{storage['free_human']}</span></p>
        """
    else:
        storage_info = f'<p class="label">{storage.get("info", "N/A")}</p>'

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{APP_NAME}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background: #f0f2f5; }}
            .card {{ background: white; border-radius: 10px; padding: 25px;
                     margin: 15px 0; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
            h1 {{ color: #2c3e50; }}
            h3 {{ color: #34495e; margin-bottom: 5px; }}
            .label {{ color: #7f8c8d; font-size: 0.85rem; }}
            .value {{ color: #2980b9; font-weight: bold; font-size: 1.1rem; }}
            pre {{ background: #ecf0f1; padding: 15px; border-radius: 5px;
                   overflow-x: auto; font-size: 0.85rem; white-space: pre-wrap; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ecf0f1; }}
            th {{ background: #f8f9fa; color: #2c3e50; }}
            a {{ color: #3498db; text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
            .form-group {{ margin: 10px 0; }}
            input, textarea {{ padding: 8px; border: 1px solid #ddd; border-radius: 5px;
                               font-size: 0.95rem; }}
            button {{ background: #2980b9; color: white; border: none; padding: 10px 20px;
                      border-radius: 5px; cursor: pointer; font-size: 0.95rem; }}
            button:hover {{ background: #2471a3; }}
            .success {{ color: #27ae60; }}
            .persist {{ background: #eafaf1; border-left: 4px solid #27ae60; padding: 15px;
                        border-radius: 5px; margin: 10px 0; }}
        </style>
    </head>
    <body>
        <h1>💾 Kubernetes Storage Demo</h1>
        <p>This app writes and reads files from a <b>PersistentVolumeClaim</b>.
           Data survives Pod restarts!</p>

        <div class="persist">
            <b>🧪 Persistence Test:</b> Write a file → delete the pod →
            check if the file still exists when the new pod starts!
        </div>

        <div class="card">
            <h3>📋 Pod & Storage Info</h3>
            <p><span class="label">Pod Name:</span> <span class="value">{POD_NAME}</span></p>
            <p><span class="label">Data Path:</span> <span class="value">{DATA_DIR}</span></p>
            <p><span class="label">Storage Type:</span> <span class="value">{STORAGE_TYPE}</span></p>
            {storage_info}
        </div>

        <div class="card">
            <h3>✏️ Write a File</h3>
            <form action="/write" method="get">
                <div class="form-group">
                    <label>Filename: </label>
                    <input type="text" name="filename" placeholder="hello.txt" required>
                </div>
                <div class="form-group">
                    <label>Content: </label><br>
                    <textarea name="content" rows="3" cols="50" placeholder="Hello from Kubernetes!"></textarea>
                </div>
                <button type="submit">💾 Save File</button>
            </form>
        </div>

        <div class="card">
            <h3>📁 Files in Storage ({len(files)} files)</h3>
            <table>
                <tr><th>Name</th><th>Size</th><th>Modified</th><th>Action</th></tr>
                {file_rows}
            </table>
        </div>

        <div class="card">
            <h3>🔄 Pod Restart History</h3>
            <p class="label">Each line below = a pod start. If you see multiple entries,
               it means the data survived pod restarts!</p>
            <pre>{startup_log}</pre>
        </div>

        <div class="card">
            <h3>🔗 API Endpoints</h3>
            <table>
                <tr><th>Method</th><th>Path</th><th>Description</th></tr>
                <tr><td>GET</td><td><a href="/">/</a></td><td>This dashboard</td></tr>
                <tr><td>GET/POST</td><td>/write?filename=X&content=Y</td><td>Write a file</td></tr>
                <tr><td>GET</td><td><a href="/list">/list</a></td><td>List all files (JSON)</td></tr>
                <tr><td>GET</td><td>/read?filename=X</td><td>Read a file</td></tr>
                <tr><td>DELETE/GET</td><td>/delete?filename=X</td><td>Delete a file</td></tr>
                <tr><td>GET</td><td><a href="/health">/health</a></td><td>Health check</td></tr>
            </table>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.api_route("/write", methods=["GET", "POST"])
def write_file(
    filename: str = Query(..., description="Name of the file to write"),
    content: str = Query("Hello from Kubernetes Storage!", description="Content to write"),
):
    """Write content to a file in the persistent volume."""
    # Security: prevent path traversal
    safe_name = Path(filename).name
    if not safe_name or safe_name.startswith("."):
        raise HTTPException(status_code=400, detail="Invalid filename")

    filepath = os.path.join(DATA_DIR, safe_name)
    with open(filepath, "w") as f:
        f.write(content)

    return {
        "status": "success",
        "message": f"File '{safe_name}' written successfully",
        "pod": POD_NAME,
        "path": filepath,
        "size": _human_size(os.path.getsize(filepath)),
        "tip": "Now try deleting the pod and see if this file survives!",
    }


@app.get("/read")
def read_file_endpoint(
    filename: str = Query(..., description="Name of the file to read"),
):
    """Read a file from the persistent volume."""
    safe_name = Path(filename).name
    filepath = os.path.join(DATA_DIR, safe_name)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"File '{safe_name}' not found")

    with open(filepath, "r") as f:
        content = f.read()

    return {
        "filename": safe_name,
        "content": content,
        "pod": POD_NAME,
        "size": _human_size(os.path.getsize(filepath)),
    }


@app.get("/list")
def list_files():
    """List all files in the persistent volume."""
    return {
        "data_dir": DATA_DIR,
        "pod": POD_NAME,
        "files": _list_user_files(),
        "startup_log": _read_startup_log(),
    }


@app.api_route("/delete", methods=["GET", "DELETE"])
def delete_file(
    filename: str = Query(..., description="Name of the file to delete"),
):
    """Delete a file from the persistent volume."""
    safe_name = Path(filename).name
    filepath = os.path.join(DATA_DIR, safe_name)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"File '{safe_name}' not found")

    os.remove(filepath)
    return {
        "status": "success",
        "message": f"File '{safe_name}' deleted",
        "pod": POD_NAME,
    }


@app.get("/health")
def health():
    """Health check + storage status."""
    writable = True
    try:
        test_file = os.path.join(DATA_DIR, ".health-check")
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
    except Exception:
        writable = False

    return {
        "status": "healthy" if writable else "degraded",
        "pod": POD_NAME,
        "data_dir": DATA_DIR,
        "storage_writable": writable,
        "storage_stats": _get_storage_stats(),
        "files_count": len(_list_user_files()),
        "timestamp": datetime.now().isoformat(),
    }
