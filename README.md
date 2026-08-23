# Infinity Reconstruction Lab — VLR Experimental Prototype v2

Das Toolkit wurde auf den im Projekt definierten **Visual Language Reconstruction (VLR)**-Versuchsaufbau erweitert.

## Was jetzt im Prototyp steckt

**Original → Beschreibung → Prompt → konkurrierende Rekonstruktionen → Multi-Metrik → Human Ranking → Archiv → nächste Generation**

Zusätzlich:

- unveränderliches Original als Referenz für **jede** Generation
- Vergleich des Kandidaten sowohl mit dem Original als auch mit dem vorherigen Gewinner
- getrennte Metriken statt blindem Pixel-98%-Kriterium
- transparenter Composite-Score
- strukturelle und farbliche Metriken
- räumlich niedrigfrequente Thumbnail-Ähnlichkeit
- Gradienten-/Strukturähnlichkeit
- SQLite-Experimentarchiv
- vollständiger Prompt-/Parent-Stammbaum
- Human-in-the-loop Paarvergleich
- MetaMaster-Archiv
- stabile Konvergenzbedingung + Plateau-Abbruch
- lokaler Ollama-Visionpfad
- Puter als optionaler kostenloser/allowance-basierter Cloudpfad
- keine synthetischen Fake-Bilder und keine Mock-Daten

## Wichtige methodische Änderung

Die 98%-Schwelle bedeutet **nicht** 98% Pixelidentität.

Der Composite-Score v2 kombiniert:

- SSIM
- Edge IoU
- HSV-Farbverteilung
- Gradientenstruktur
- 32×32-Low-Frequency-Appearance

Das ist bewusst ein erster Experimentator. Später können LPIPS, DINO/CLIP und ein menschlich kalibriertes Rankingmodell als weitere unabhängige Dimensionen ergänzt werden.

## Konvergenz

Ein Lauf beendet sich bei:

1. Composite ≥ Schwelle über N aufeinanderfolgende Generationen, **oder**
2. fehlendem messbarem Fortschritt über mehrere Generationen (Plateau), **oder**
3. Maximalgeneration.

Jede Generation bleibt trotzdem im Archiv.

## Installation

```bash
chmod +x setup.sh
./setup.sh
~/Infinity-Reconstruction-Lab/run.sh
```

Dann:

`http://127.0.0.1:8765`

### Ollama

Wenn Ollama bereits installiert ist, wird das konfigurierte Vision-Modell verwendet.

```bash
OLLAMA_MODEL=qwen3-vl:4b ~/Infinity-Reconstruction-Lab/run.sh
```

Das Setup installiert **nicht blind** irgendeinen Paketmanager auf Bazzite. Falls Ollama fehlt, bleibt der Puter-Pfad verfügbar; Ollama kann anschließend entsprechend der eigenen Bazzite-/Ollama-Installation ergänzt werden.

## Experimental workflow

1. Goldbild laden.
2. `Nur analysieren`.
3. Beschreibung prüfen.
4. Loop starten.
5. Zwei konkurrierende Promptmutationen erzeugen.
6. Beide Kandidaten gegen das Original messen.
7. Bei Human/Both A/B auswählen.
8. Gewinner wird neue Promptbasis.
9. Archiv wächst generationenweise.
10. `MetaMaster erzeugen` analysiert die gespeicherten Gewinner.

## Noch bewusst nicht behauptet

Der Prototyp behauptet nicht, dass sein Composite-Score menschliche visuelle Ähnlichkeit perfekt abbildet. Genau deshalb wird Human Ranking gespeichert. Das nächste Entwicklungsziel ist eine unabhängige Perceptual-Metrikschicht und danach die Kalibrierung des automatischen Scores gegen menschliche Paarentscheidungen.

## Daten

Alle experimentellen Artefakte liegen unter:

`~/Infinity-Reconstruction-Lab/archive/`

Die SQLite-Datenbank ist:

`archive/experiments.sqlite3`

Die Originaldatei wird im Browser als unveränderliche Referenz gehalten; Kandidaten werden mit `parent_id`, Prompt, Beschreibung, Metriken und Human-Auswahl archiviert.

## Kostenloser Betrieb

Der Kern ist lokal und Open Source.

Puter ist nur ein optionaler Remote-Pfad und hängt von dessen jeweils gültiger Benutzer-/Nutzungsfreigabe ab. Für reproduzierbare Forschung sollte der lokale Ollama/ComfyUI-Pfad die langfristige Referenz bleiben.

## Nächster sinnvoller Ausbau

- ComfyUI als lokaler Generatoradapter
- echte LPIPS/DINO/CLIP-Metriken
- Seed-/Parameter-Tracking
- mehrere Seeds je Prompt
- Beam Search statt nur zwei Varianten
- Blindes Human Pairwise Ranking
- trainierbares Human-Calibrated Similarity Model
- Benchmark-Datensatz und Train/Test-Split
- Meta-Grammar statt bloßem Meta-Prompt
