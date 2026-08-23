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
- optional Puter cloud path
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

### Ollama

If Ollama is already installed, the configured vision model is used.

```bash
OLLAMA_MODEL=qwen3-vl:4b ~/Infinity-Reconstruction-Lab/run.sh
```

The setup does not blindly install a package manager on Bazzite. If Ollama is missing, the Puter path remains available; Ollama can be added later according to the local Bazzite/Ollama setup.

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

## Free local operation

The core is local and open source.

Puter is only an optional remote path and depends on the valid user allowance or usage policy at the time of use. For reproducible research, the local Ollama/ComfyUI path should remain the long-term reference path.

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

