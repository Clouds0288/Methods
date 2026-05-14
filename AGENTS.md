# Agent Instructions

This is a research-oriented project. Code should support fast understanding, reproduction, and iteration.

## Code Style

- Keep code clear, short, and direct.
- Prefer simple data structures and explicit formulas.
- Avoid defensive programming unless it is required by the experiment.
- Do not add fallback logic, automatic recovery, or silent default substitution.
- Let errors fail loudly so problems are visible during research.
- Do not over-abstract. Add functions only when they make the notebook easier to read or reuse.
- Avoid unnecessary classes, wrappers, configuration systems, and helper layers.
- Keep variable names close to the mathematical model and power-system terminology.
- Do not add unrelated refactors or general-purpose infrastructure.

## Notebook Style

- Use notebooks as readable experiment records.
- Keep each cell focused on one task: data, visualization, model, solve, or result.
- Prefer compact tables and plots over verbose textual output.
- Avoid printing large intermediate data unless it is needed for debugging.
- Make figures simple, labeled, and directly tied to the experiment.

## Research Workflow

- Prioritize reproducibility over production robustness.
- Keep assumptions visible near the code that uses them.
- Do not hide modeling choices behind fallback branches.
- When something is missing or inconsistent, raise the error instead of guessing.
- Optimize for quick modification by a researcher reading the notebook for the first time.
