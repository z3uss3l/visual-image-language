# Infinity Reconstruction Lab

## Für interessierte Menschen

Das Infinity Reconstruction Lab untersucht, wie gut sich ein Bild allein durch Sprache und lokale Bildgenerierung rekonstruieren lässt. Ein Originalbild bleibt unverändert als Referenz erhalten. Das System beschreibt es, formuliert daraus einen Bildprompt und erzeugt mehrere Varianten.

Jede Variante wird automatisch mit dem Original verglichen. Dabei werden nicht nur einzelne Pixel betrachtet, sondern unter anderem Struktur, Kanten, Farben, Verläufe und die grobe Bildwirkung. Zusätzlich kann ein Mensch jede Variante schnell von 1 bis 10 bewerten und seinen bevorzugten Vertreter markieren.

Der Ablauf einer Runde ist:

`Originalbild → Analyse → Prompt → Varianten → Vergleich → menschliche Bewertung → Gewinner → nächste Runde`

Der Gewinner wird zur Grundlage der nächsten Runde. Alle Bilder, Prompts, Messwerte, Bewertungen und Beziehungen zwischen den Generationen werden lokal archiviert. So bleibt nachvollziehbar, warum sich das Ergebnis verändert hat.

Das Projekt ist ein experimenteller Prototyp, kein Beweis dafür, dass ein automatischer Score menschliche Wahrnehmung vollständig ersetzt. Gerade deshalb werden menschliche Bewertungen gespeichert und im Modus „Score + Mensch“ gemeinsam mit den technischen Messwerten verwendet.

## Technische Übersicht

- Python-Backend mit FastAPI
- Browser-Oberfläche ohne Build-Schritt
- lokale Bildanalyse und Promptbearbeitung über Ollama
- lokale Bildgenerierung über ComfyUI
- technische Bildvergleiche mit OpenCV und scikit-image
- SQLite-Archiv mit Prompt-, Bild- und Abstammungsdaten
- automatische Abbruchbedingungen für Schwelle, Plateau und maximale Rundenzahl
- Human-Bewertung von 1 bis 10 pro Kandidat

Der Composite-Score setzt sich aktuell aus SSIM, Edge IoU, HSV-Farbähnlichkeit, Gradientensimilarität und einer niedrig aufgelösten Thumbnail-Ähnlichkeit zusammen. Die Gewichtung ist eine erste experimentelle Formulierung und keine trainierte Wahrnehmungsmetrik.

## Installation

### Voraussetzungen

- Linux, macOS oder eine vergleichbare Unix-Umgebung
- Python 3 mit `venv`
- `curl`
- für Analyse und Prompting: [Ollama](https://ollama.com/)
- für Bildgenerierung: lokale [ComfyUI](https://github.com/comfyanonymous/ComfyUI)-Installation

Das Setup installiert keine Systemdienste und entfernt keine vorhandenen Pakete. Ollama und ComfyUI werden bewusst separat betrieben.

### Projekt installieren

Im Repository ausführen:

```bash
chmod +x setup.sh
./setup.sh
```

Das Setup kopiert die Anwendung nach `~/Infinity-Reconstruction-Lab`, erstellt dort eine virtuelle Python-Umgebung und installiert die Python-Abhängigkeiten. Der Start erfolgt mit:

```bash
~/Infinity-Reconstruction-Lab/run.sh
```

Danach im Browser öffnen:

http://127.0.0.1:8765

### Ollama vorbereiten

Ollama in einem separaten Terminal starten:

```bash
ollama serve
```

In einem weiteren Terminal ein Vision-Modell laden. Das Setup wählt anhand des erkannten RAM automatisch `qwen3-vl:4b` ab 24 GiB und sonst die sparsame `qwen3-vl:2b`-Variante:

```bash
ollama pull qwen3-vl:2b
```

Auf einem Rechner mit mindestens 24 GiB RAM kann die 4B-Variante verwendet werden:

```bash
MODEL=qwen3-vl:4b ./setup.sh
```

Größere Varianten wie `qwen3-vl:8b` werden nicht automatisch installiert, weil integrierte Radeon-Grafik den GPU-Speicher aus dem normalen RAM nimmt. Sie können bei Bedarf manuell installiert und in der Oberfläche ausgewählt werden, sollten aber bei 32 GiB gemeinsamem Speicher nicht die Ausgangskonfiguration sein.

Die Oberfläche liest die lokal verfügbaren Modelle automatisch über `http://127.0.0.1:11434/api/tags` ein.

### ComfyUI vorbereiten

1. ComfyUI lokal installieren und starten.
2. Einen Workflow mit einem oder mehreren `CLIPTextEncode`-Knoten öffnen.
3. Den Workflow als API-Format exportieren.
4. Als `config/comfyui-workflow.json` im installierten Projekt ablegen.
5. ComfyUI auf `127.0.0.1:8188` erreichbar machen.

Die Anwendung ersetzt im Workflow den Text jedes `CLIPTextEncode`-Knotens durch den aktuellen Prompt, wartet auf die Ausführung und lädt das erzeugte Bild zurück. Ollama erzeugt selbst keine Bilder; dafür ist ComfyUI zuständig.

## Bedienung

1. Anwendung starten und ein PNG-, JPEG- oder WebP-Originalbild laden.
2. Mit „Nur analysieren“ zunächst Beschreibung und Prompt erzeugen und prüfen.
3. Ein Ollama-Modell auswählen.
4. Den Optimierungsmodus wählen:
	- **Auto:** technischer Composite-Score entscheidet.
	- **Human-in-the-loop:** jede Variante von 1 bis 10 bewerten und einen Vertreter markieren.
	- **Score + Mensch:** technische Werte, Human-Bewertung und Markierung werden kombiniert.
5. „Start“ drücken.
6. Während jeder Runde erscheinen die laufende Rundennummer, die erzeugten Kandidaten und ihre technischen Werte.
7. Im Human-Modus jede Kandidatenkarte bewerten, eine Karte markieren und „Vertreter übernehmen“ drücken.
8. „Stop“ beendet den Loop nach der aktuellen Aktion. Der Gewinner wird als Basis für die nächste Runde verwendet.

Die wichtigsten Einstellungen sind:

- **Abbruchschwelle:** erforderlicher Composite-Score.
- **Konsekutive Treffer:** wie oft die Schwelle nacheinander erreicht werden muss.
- **Plateau-Fenster:** Anzahl der Runden für die Fortschrittsprüfung.
- **Min. Verbesserung im Plateau:** kleinste noch messbare Verbesserung.
- **Varianten pro Runde:** aktuell maximal zwei Varianten.
- **Max. Generationen:** harte Obergrenze des Loops.

## Archiv und Daten

Das Archiv liegt im installierten Projekt unter:

```text
~/Infinity-Reconstruction-Lab/archive/
```

Die SQLite-Datenbank ist `archive/experiments.sqlite3`. Für jede Variante werden Bild, Prompt, Beschreibung, technische Metriken, vorheriger Treffer, Human-Bewertung und Auswahlstatus gespeichert. Gewinner erhalten zusätzlich ihre Eltern-ID und bilden damit eine nachvollziehbare Prompt-Linie.

Das Archiv kann über die Oberfläche mit MetaMaster ausgewertet werden. Dabei werden erfolgreiche Prompt-Linien und vorhandene Human-Bewertungen an Ollama übergeben und als neue Master-Prompt-Vorlage archiviert.

## Fehlerbehebung

- **Ollama nicht erreichbar:** `ollama serve` starten und mit `ollama list` prüfen, ob ein Modell installiert ist.
- **Keine Bildgenerierung:** ComfyUI starten und den API-Workflow unter `config/comfyui-workflow.json` ablegen.
- **Port belegt:** `PORT=8766 ~/Infinity-Reconstruction-Lab/run.sh` verwenden.
- **Sauber entfernen:** im Repository `./setup.sh --rollback` ausführen. Das entfernt nur vom Setup verwaltete Projektdateien und lässt Systempakete unangetastet.

## Grenzen und nächste Schritte

Der aktuelle Score ist bewusst transparent und lokal, aber noch keine moderne semantische Wahrnehmungsmetrik. Sinnvolle nächste Schritte sind LPIPS-, DINO- oder CLIP-Vergleiche, Seed- und Parameter-Tracking, mehrere Seeds pro Prompt, mehr als zwei Kandidaten pro Runde sowie eine Kalibrierung des Scores anhand menschlicher Bewertungen.

