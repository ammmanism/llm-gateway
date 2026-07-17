# Benchmarking Methodology

All benchmarks are **reproducible** and **falsifiable**. We use:

- **Mock providers** with fixed costs/latencies to ensure stable comparisons.
- **Realistic query distributions** (paraphrases + unique) to reflect production traffic.
- **Multiple runs** (we average 5 runs, but results shown are from a single run to avoid obscuring variance).

Environment:
- Windows 11 / Python 3.11
- Redis running locally (for exact cache)
- FAISS CPU version (no GPU)

To replicate:
1. Set up `.env` with your API keys (optional - mocks work without).
2. Run `python benchmarks/run_all.py`.
3. All results land in `benchmarks/results/`.

We commit the output JSON so reviewers can trust numbers - they can also rerun to verify.
