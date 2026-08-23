import base64
import io
import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import requests
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from PIL import Image
from skimage.metrics import structural_similarity as ssim

ROOT = Path(__file__).resolve().parent
ARCHIVE = ROOT / "archive"
STATIC = ROOT / "static"
DB = ARCHIVE / "experiments.sqlite3"
ARCHIVE.mkdir(exist_ok=True)
STATIC.mkdir(exist_ok=True)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3-vl:4b")
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8765"))

app = FastAPI(title="Infinity Reconstruction Lab", version="2.0.0")


def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS experiments (
            id TEXT PRIMARY KEY, created_at REAL NOT NULL, generation INTEGER,
            label TEXT, parent_id TEXT, prompt TEXT, description TEXT,
            metrics_json TEXT, human_selected INTEGER DEFAULT 0,
            original_match REAL, previous_match REAL
        );
        CREATE TABLE IF NOT EXISTS meta_prompts (
            id TEXT PRIMARY KEY, created_at REAL NOT NULL, source_count INTEGER,
            content TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_exp_generation ON experiments(generation);
        """)
init_db()


def load_image(data: bytes) -> np.ndarray:
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Ungültige Bilddatei")
    return img


def resize_pair(a, b, size=(512, 512)):
    return (cv2.resize(a, size, interpolation=cv2.INTER_AREA),
            cv2.resize(b, size, interpolation=cv2.INTER_AREA))


def cosine(a, b):
    den = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / den) if den else 1.0


def gradient_similarity(a, b):
    ga = cv2.Laplacian(cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), cv2.CV_32F)
    gb = cv2.Laplacian(cv2.cvtColor(b, cv2.COLOR_BGR2GRAY), cv2.CV_32F)
    # Normalize to remove absolute contrast scale while retaining structure.
    ga = (ga - ga.mean()) / (ga.std() + 1e-6)
    gb = (gb - gb.mean()) / (gb.std() + 1e-6)
    return max(0.0, min(1.0, (cosine(ga.ravel(), gb.ravel()) + 1) / 2))


def color_similarity(a, b):
    ah = cv2.cvtColor(a, cv2.COLOR_BGR2HSV)
    bh = cv2.cvtColor(b, cv2.COLOR_BGR2HSV)
    ha = cv2.calcHist([ah], [0, 1], None, [32, 32], [0, 180, 0, 256])
    hb = cv2.calcHist([bh], [0, 1], None, [32, 32], [0, 180, 0, 256])
    cv2.normalize(ha, ha); cv2.normalize(hb, hb)
    corr = float(cv2.compareHist(ha, hb, cv2.HISTCMP_CORREL))
    return max(0.0, min(1.0, (corr + 1.0) / 2.0))


def edge_iou(a, b):
    ag = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
    bg = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
    ea, eb = cv2.Canny(ag, 80, 180), cv2.Canny(bg, 80, 180)
    inter = np.logical_and(ea > 0, eb > 0).sum()
    union = np.logical_or(ea > 0, eb > 0).sum()
    return float(inter / union) if union else 1.0


def thumbnail_similarity(a, b):
    # Low-frequency spatial appearance. More useful than raw pixel equality for generated images.
    a = cv2.resize(a, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
    b = cv2.resize(b, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
    return max(0.0, min(1.0, (cosine(a.ravel(), b.ravel()) + 1) / 2))


def compare_images(a_bytes: bytes, b_bytes: bytes):
    a, b = resize_pair(load_image(a_bytes), load_image(b_bytes))
    ag = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
    bg = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
    mse = float(np.mean((a.astype(np.float32) - b.astype(np.float32)) ** 2))
    psnr = float(cv2.PSNR(a, b)) if mse > 0 else 99.0
    ssim_score = float(ssim(ag, bg, data_range=255))
    edge = edge_iou(a, b)
    color = color_similarity(a, b)
    grad = gradient_similarity(a, b)
    thumb = thumbnail_similarity(a, b)

    # Composite deliberately emphasizes structure/appearance rather than raw pixels.
    composite = (
        0.28 * ssim_score +
        0.18 * edge +
        0.18 * color +
        0.18 * grad +
        0.18 * thumb
    )
    return {
        "mse": mse, "psnr_db": psnr, "ssim": ssim_score,
        "edge_iou": edge, "color_similarity": color,
        "gradient_similarity": grad, "thumbnail_similarity": thumb,
        "composite": float(composite),
        "threshold_98": bool(composite >= 0.98),
        "metric_version": "vlr-composite-v2"
    }


def ollama_available():
    try:
        return requests.get(f"{OLLAMA_URL}/api/tags", timeout=2).ok
    except requests.RequestException:
        return False


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health():
    return {"ok": True, "ollama": ollama_available(),
            "ollama_model": OLLAMA_MODEL, "archive": str(ARCHIVE),
            "db": str(DB), "version": app.version}


@app.post("/api/compare")
async def compare(reference: UploadFile = File(...), candidate: UploadFile = File(...)):
    try:
        return compare_images(await reference.read(), await candidate.read())
    except Exception as e:
        raise HTTPException(400, f"Vergleich fehlgeschlagen: {e}")


@app.post("/api/archive")
async def archive(image: UploadFile = File(...), metadata: str = ""):
    run_id = uuid.uuid4().hex
    try:
        meta = json.loads(metadata) if metadata else {}
    except json.JSONDecodeError:
        meta = {"raw_metadata": metadata}
    generation = str(meta.get("generation", "unknown"))
    folder = ARCHIVE / f"gen_{generation}_{run_id[:8]}"
    folder.mkdir(parents=True, exist_ok=True)
    image_path = folder / "image.png"
    data = await image.read()
    image_path.write_bytes(data)
    meta.update({"run_id": run_id, "archived_at": time.time(),
                 "image": str(image_path.relative_to(ROOT))})
    (folder / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    with db() as c:
        c.execute("""INSERT OR REPLACE INTO experiments
            (id,created_at,generation,label,parent_id,prompt,description,metrics_json,
             human_selected,original_match,previous_match)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (
            run_id, meta["archived_at"], int(meta.get("generation", -1)) if str(meta.get("generation","")).isdigit() else -1,
            meta.get("label"), meta.get("parent_id"), meta.get("prompt",""), meta.get("description",""),
            json.dumps(meta.get("metrics",{}), ensure_ascii=False),
            int(bool(meta.get("human_selected"))),
            float(meta.get("metrics",{}).get("composite",0)),
            float(meta.get("previous_match",0))
        ))
    return {"ok": True, "run_id": run_id, "path": str(folder)}


@app.post("/api/archive/meta")
async def archive_meta(metadata: str = ""):
    try: meta = json.loads(metadata)
    except json.JSONDecodeError: meta = {}
    mid = uuid.uuid4().hex
    content = meta.get("content","")
    with db() as c:
        c.execute("INSERT INTO meta_prompts VALUES (?,?,?,?)",
                  (mid, time.time(), int(meta.get("source_count",0)), content))
    (ARCHIVE / f"metamaster_{mid[:8]}.md").write_text(content, encoding="utf-8")
    return {"ok": True, "id": mid}


@app.get("/api/history")
def history(limit: int = 100):
    with db() as c:
        rows = c.execute("""SELECT id,created_at,generation,label,parent_id,prompt,
            human_selected,original_match,previous_match,metrics_json
            FROM experiments ORDER BY created_at DESC LIMIT ?""", (max(1,min(limit,1000)),)).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/meta-history")
def meta_history(limit: int = 20):
    with db() as c:
        rows = c.execute("SELECT * FROM meta_prompts ORDER BY created_at DESC LIMIT ?",
                         (max(1,min(limit,100)),)).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/ollama/analyze")
async def ollama_analyze(file: UploadFile = File(...), instruction: str = ""):
    if not ollama_available():
        raise HTTPException(503, "Lokales Ollama ist nicht erreichbar.")
    data = await file.read()
    b64 = base64.b64encode(data).decode("ascii")
    prompt = instruction or "Describe this image for faithful reconstruction. Do not invent."
    payload = {"model": OLLAMA_MODEL,
               "messages": [{"role": "user", "content": prompt, "images": [b64]}],
               "stream": False, "options": {"temperature": 0.1}}
    try:
        r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=300)
        r.raise_for_status()
        return {"model": OLLAMA_MODEL, "text": r.json().get("message", {}).get("content", "")}
    except requests.RequestException as e:
        raise HTTPException(502, f"Ollama request failed: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
