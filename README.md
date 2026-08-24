# Infinity Reconstruction Lab — VLR v3.2

Das Infinity Reconstruction Lab untersucht experimentell, wie weit sich ein konkretes Bild ausschließlich durch sprachliche Beschreibung rekonstruieren lässt.

Der Prototyp verwendet bewusst **ein KI-Modell zur Zeit**. Auf einem Rechner mit 32 GB gemeinsamem RAM und einer Radeon 780M soll dadurch vermieden werden, dass ein großes Qwen-Modell und ein Bildgenerator gleichzeitig den Speicher blockieren.

## Experimenteller Loop

```text
Original
  ↓
Qwen Vision/Reasoning
  ↓
kanonische Beschreibung
  ↓
Prompt / zwei gezielte Mutationen
  ↓
Qwen UNLOAD
  ↓
ComfyUI Bildgeneration
  ↓
ComfyUI UNLOAD / Memory Free
  ↓
objektive Bildmetriken
  ↓
Human A/B Ranking
  ↓
Winner
  ↓
Archiv + Retention
  ↓
Qwen wieder laden
  ↓
nächste Generation
```

Qwen wird innerhalb einer Analyse-/Optimierungsphase über `keep_alive` resident gehalten. Vor dem Generator wird es explizit über Ollamas `keep_alive: 0` entladen. Nach der Generierung wird ComfyUI über `POST /free` mit `unload_models=true` und `free_memory=true` freigegeben. Diese Endpunkte sind Bestandteil der aktuellen APIs. Die Anwendung prüft danach den Zustand, anstatt nur anzunehmen, dass Speicher freigegeben wurde.

## Modell

Standard ist:

```text
qwen3.8:27b
```

Das Modell wird **nicht automatisch heruntergeladen**. Das Setup verwendet ein bereits lokal vorhandenes Modell und warnt lediglich, wenn es nicht sichtbar ist.

Ein anderes Modell kann über `MODEL=... ./setup.sh` konfiguriert werden.

## Architektur

- FastAPI/Python Backend
- Browser-UI ohne Build-Schritt
- Ollama als einzelnes lokales Vision-/Reasoning-Modell
- ComfyUI als lokaler Bildgenerator
- OpenCV + scikit-image als deterministische Baseline-Evaluation
- SQLite für vollständige Prompt-/Score-/Abstammungsmetadaten
- Human-in-the-loop als finale Auswahl im Human-Modus
- Retention Policy für Bilddateien
- MetaMaster aus archivierten erfolgreichen Promptlinien

### Wichtige Trennung

Die **Originalbeschreibung bleibt konzeptionell Referenzmaterial**. Der aktuelle Gewinner wird zwar erneut beschrieben, aber diese neue Beschreibung ersetzt nicht rückwirkend die Originalreferenz.

Der aktuelle Composite ist:

- SSIM
- Edge IoU
- HSV-Farbähnlichkeit
- Gradientensimilarität
- Low-resolution Thumbnail Similarity

Er wird als **VLR Composite v3** bezeichnet. `98 %` bedeutet `0.98 VLR Composite`, nicht 98 % Pixelidentität und nicht automatisch 98 % menschliche Wahrnehmungsähnlichkeit.

## Human-in-the-loop

Im Human-Modus entscheidet der Mensch endgültig. Eine technische Punktzahl darf die explizite menschliche Auswahl nicht überschreiben.

Bewertungen und Auswahl werden mit archiviert und stehen später für die Kalibrierung einer besseren Bewertungsfunktion zur Verfügung.

## Retention Policy

Default:

```text
letzte 5 Generationen behalten
+ Verbesserungsstände behalten
+ Winner/Best schützen
+ Original immer behalten
```

Ältere Bilddateien werden entfernt, **aber ihre SQLite-/JSON-Metadaten bleiben erhalten**. Damit bleibt die Experimenthistorie analytisch vollständig, ohne die Festplatte mit überholten PNGs zu füllen.

Die UI kann jederzeit auf:

```text
Vollständige Bildhistorie behalten
```

umgestellt werden.

## Performance-Modus

`run.sh` ruft vor dem Start `prepare-performance.sh` auf. Dieses Script darf ausschließlich bekannte, benutzerseitige Desktop-Anwendungen beenden, die typischerweise unnötig RAM/GPU verbrauchen. Es deaktiviert **keine** System-, Sicherheits-, Netzwerk-, Audio-, Display- oder Update-Dienste.

Das Performance-Profil wird, falls `powerprofilesctl` vorhanden ist, auf `performance` gestellt.

## Installation

```bash
chmod +x setup.sh
./setup.sh
~/Infinity-Reconstruction-Lab/run.sh
```

Ollama muss separat laufen. Prüfen:

```bash
ollama list
ollama ps
```

ComfyUI muss im Native-Modus auf `127.0.0.1:8188` bzw. im Podman-Modus auf `127.0.0.1:8189` laufen und einen API-Workflow unter

```text
config/comfyui-workflow.json
```

bereitstellen.

## Prüfung

Vor einem echten Experiment sollte:

1. `/api/health` Ollama und ComfyUI erkennen,
2. `qwen3.8:27b` in Ollama sichtbar sein,
3. ein Bild geladen und als Original archiviert werden,
4. eine Analyse funktionieren,
5. Qwen nach der Analyse/Mutation nicht mehr unter `ollama ps` erscheinen,
6. ComfyUI ein Bild erzeugen,
7. ComfyUI nach `/free` keine residenten Modelle mehr melden,
8. die Metrikberechnung laufen,
9. Human-Auswahl nicht durch den Composite überschrieben werden,
10. Retention alte Bilddateien entfernen, aber Metadaten behalten.

## Grenzen

VLR v3.2 ist noch keine trainierte Wahrnehmungsmetrik. LPIPS/DINO/CLIP und eine statistische Kalibrierung gegen Human Rankings sind die nächsten wissenschaftlichen Ausbaustufen.

## Storage Audit

Für die Suche nach großen Dateien und bekannten Cache-Verzeichnissen:

```bash
~/Infinity-Reconstruction-Lab/storage-audit.sh
```

Der Audit löscht nichts. Er schreibt einen Bericht nach `logs/`. Das ist absichtlich getrennt von der VLR-Archiv-Retention: Modellgewichte und andere große Dateien sind nicht automatisch „Datenleichen“.

## Podman-Runtime (Bazzite empfohlen)

VLR 3.2 unterstützt einen Podman-/Quadlet-first Modus. Wenn die komplette Containerkonfiguration gesetzt ist, wird genau **ein KI-Container pro Phase** betrieben:

`Ollama/Qwen → unload → Container stop → ComfyUI → /free → Container stop → Evaluation`

Damit gibt es sowohl Modell-Unload als auch eine harte Prozessgrenze. Die persistenten Podman-Volumes behalten Modelle und Nutzdaten, obwohl die Container gestoppt werden.

Standardports der Container sind `11435` (Ollama) und `8189` (ComfyUI), damit vorhandene native Dienste auf `11434/8188` nicht verdrängt werden.

### Konfiguration

In `config/defaults.env`:

- `VLR_RUNTIME=podman` — Standard und empfohlen für Bazzite/Radeon 780M; Podman zwingend.
- `VLR_RUNTIME=auto` — optionaler Kompatibilitätsmodus mit native fallback.
- `VLR_RUNTIME=native` — Containerorchestrierung aus.
- `VLR_OLLAMA_IMAGE=docker.io/ollama/ollama:latest`
- `VLR_COMFYUI_IMAGE=...` — muss für den Podman-ComfyUI-Teil gesetzt werden.

### Bazzite/AMD

Rootless Podman erhält `/dev/dri` und `/dev/kfd` nur dann, wenn die Geräte auf dem Host vorhanden sind, und nutzt `--group-add keep-groups`. Für die Zielhardware Radeon 780M wird Ollama bevorzugt mit Vulkan betrieben; ein `HSA_OVERRIDE_GFX_VERSION` wird nicht pauschal gesetzt. Es werden keine SELinux-Regeln oder Systemdienste automatisch verändert. Ollamas offizielles Container-Image unterstützt AMD und Vulkan; VLR aktiviert Vulkan standardmäßig.

### Setup-Verhalten

`./setup` bzw. `./setup.sh` ist **installations-only**: Das Setup startet weder Ollama noch ComfyUI noch die VLR-Webanwendung automatisch. Nach erfolgreichem Setup liegen `~/Infinity-Reconstruction-Lab/setup` und `setup.sh` auch im Zielverzeichnis, sodass ein späteres Reparatur-/Update-Setup direkt dort erneut ausgeführt werden kann. Fehler werden mit Zeile und ausgeführtem Befehl ausgegeben. Container-Images werden erst beim expliziten Runtime-Start gepullt; der Image-Pull unterliegt keinem kurzen Healthcheck-Timeout und zeigt den Podman-Fortschritt direkt im Terminal.

### Verwaltung

```bash
./vlr-podman.sh doctor
./vlr-podman.sh status
./vlr-podman.sh start-ollama
./vlr-podman.sh stop-ollama
./vlr-podman.sh pull-model qwen3.8:27b
./vlr-podman.sh start-comfyui
./vlr-podman.sh stop-comfyui
./vlr-podman.sh stop-all
```

Der Qwen-Modelcache liegt in `vlr-ollama-models`. Der Container wird also beendet, das Modell aber nicht gelöscht.

### Laufzeitdiagnose

Der Webserver schreibt jede Bildgeneration als strukturiertes Ereignis auf stdout:

```text
[VLR] {"event":"generation_start", ...}
[VLR] {"event":"generation_complete", "seconds": ...}
[VLR] {"event":"generation_failed", "error": ...}
```

Bei einem Lauf mit zwei Kandidaten bleibt ComfyUI für beide Kandidaten aktiv und wird erst nach dem Vergleich einmal beendet. Die Kandidatenkennung und die Generationsnummer stehen sowohl im Browser-Log als auch in den Backend-Ereignissen. Auf dem Zielhost kann der Verlauf mit `journalctl --user` oder dem direkten Server-Log geprüft werden. Für Podman-Zustände sind `./vlr-podman.sh status`, `./vlr-podman.sh doctor` und `podman logs vlr-comfyui` die maßgeblichen Diagnosen.
