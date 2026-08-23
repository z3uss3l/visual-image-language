# Infinity Reconstruction Lab — VLR Experimental Prototype v2

A local experimental framework for iterative visual reconstruction through language, generation, comparison, and human-in-the-loop selection.

The system treats a source image as an immutable reference and attempts to reconstruct it through successive cycles of:

- image analysis
- structured description
- prompt synthesis
- competing candidate generation
- multi-metric comparison against the original
- human preference or score-based winner selection
- archival of all generations and prompts
- reuse of the best-performing lineage as the next generation basis

This prototype follows the Visual Language Reconstruction (VLR) workflow:

Original → Description → Prompt → Competing Reconstructions → Multi-Metric Evaluation → Human Ranking → Archive → Next Generation

## What is inside

- immutable original as a reference for every generation
- comparison of each candidate against both the original and the previous winner
- separate metrics instead of a single blind pixel threshold
- transparent composite score
- structural and color metrics
- low-frequency thumbnail similarity
- gradient and structure similarity
- SQLite experiment archive
- complete prompt and parent lineage tracking
- human-in-the-loop pair comparison
- MetaMaster archive
- convergence logic with plateau detection
- local Ollama vision path
- native Ollama API integration for analysis, prompt synthesis, mutations, and MetaMaster
- dynamic list of locally downloaded Ollama models
- optional local ComfyUI API adapter for image generation
- no synthetic fake images or mock data

## Methodological change

The 98% threshold does not mean 98% pixel identity.

The composite score combines:

- SSIM
- Edge IoU
- HSV color distribution similarity
- gradient structure similarity
- 32×32 low-frequency appearance similarity

This is intentionally a first experimental formulation. Later versions can add LPIPS, DINO/CLIP, and human-calibrated ranking as additional independent dimensions.

## Convergence

A run terminates when:

1. the composite score exceeds the threshold for N consecutive generations, or
2. there is no measurable progress over several generations, or
3. the maximum generation limit is reached.

Each generation is still preserved in the archive.

## Installation

```bash
chmod +x setup.sh
./setup.sh
~/Infinity-Reconstruction-Lab/run.sh
```

Then open:

http://127.0.0.1:8765

### Fully local and free

The language pipeline is independent of Puter.js and uses Ollama directly on `127.0.0.1:11434`. The UI reads the installed model list from Ollama, so changing or adding models requires no frontend edit.

```bash
OLLAMA_MODEL=qwen3-vl:4b ~/Infinity-Reconstruction-Lab/run.sh
```

Recommended local model roles:

- `qwen3-vl:4b` for fast vision analysis on modest hardware
- `qwen3-vl:8b` for better descriptions when more VRAM/RAM is available
- `qwen3:8b` for fast text-only prompt operations if a separate vision model is selected

For local image generation, run ComfyUI on `127.0.0.1:8188` with a free SDXL or FLUX model and export an API-format workflow to `config/comfyui-workflow.json`. The backend injects the generated prompt, submits the workflow, waits for the result, and returns the image without a cloud account or API key. Ollama itself is a language/vision model runner and does not generate images, so ComfyUI is the local image provider.

The setup does not blindly install system packages or services. Start Ollama with `ollama serve`; start ComfyUI using its own local installation. Both services remain optional and are accessed only through localhost.

## Experimental workflow

1. load the target image
2. run analysis only
3. review the description
4. start the loop
5. generate two competing prompt mutations
6. evaluate both candidates against the original
7. choose the winner in human or score mode
8. promote the winner as the new prompt basis
9. archive generation data as it grows
10. use MetaMaster to analyze stored winners

## What this project does not claim

This prototype does not claim that its composite score perfectly matches human visual similarity. That is exactly why human ranking is stored and tracked. The next development target is an independent perceptual metric layer, followed by calibration of the automatic score against human pair decisions.

## Data

All experimental artifacts are stored under:

~/Infinity-Reconstruction-Lab/archive/

The SQLite database is:

archive/experiments.sqlite3

The original file remains in the browser as an immutable reference; candidates are archived with parent IDs, prompts, descriptions, metrics, and human selections.

## Local operation

The core is local and open source.

No Puter.js, cloud account, API key, or remote inference path is required by the application. Reproducible operation uses Ollama plus ComfyUI locally.

## Natural next step

- ComfyUI as a local generator adapter
- real LPIPS/DINO/CLIP metrics
- seed and parameter tracking
- multiple seeds per prompt
- beam search instead of only two variants
- blind human pairwise ranking
- trainable human-calibrated similarity model
- benchmark dataset and train/test split
- Meta-Grammar instead of a single Meta-Prompt

## Summary

This project is a research-oriented prototype for faithful visual reconstruction through iterative language-driven image synthesis. It is designed to make the reconstruction process auditable, measurable, and extensible rather than opaque or purely aesthetic.

