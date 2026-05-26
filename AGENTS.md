# Agent Instructions

This is a research-oriented project. Code should support fast understanding, reproduction, and iteration.

## Core Research Principle

- Optimize for the simplest code that directly expresses the mathematical model and experiment.
- Do not add redundant helpers, fallback branches, automatic recovery, silent defaults, broad wrappers, or general-purpose infrastructure.
- Let missing data, inconsistent dimensions, solver errors, and modeling mistakes fail loudly.
- Prefer one readable script over multiple files unless the split is materially necessary for understanding the experiment.
- When extending this project, first ask whether the extra line, function, file, or abstraction makes the research model easier to inspect; if not, do not add it.

## Code Style

- Keep code clear, short, and direct.
- Prefer compact experiment scripts: short imports, top-level constants, explicit tables, direct loops, and formulas written close to the mathematical model.
- Prefer one-line Gurobi constraints when the full formula still reads clearly; use multiline formatting only when a formula becomes hard to scan.
- Prefer Chinese inline trailing comments placed directly after the relevant code; avoid standalone comment lines unless they label a larger block.
- Prefer compact `pd.DataFrame` construction: keep tuple rows visually tight, keep short `columns=[...]` lists inline, and avoid overly expanded bracket-only formatting.
- Keep the project file count small. Prefer one clear `main.py` plus compact role scripts; merge adjacent reporting/export/plotting helpers unless splitting them materially improves readability.
- Split scripts by experiment role, such as data preparation, solve, and plotting. Do not hide the main workflow behind unnecessary entrypoint layers.
- Keep comments concise and useful: explain data assumptions, model equations, variable meanings, and plots; avoid restating obvious Python syntax.
- Use detailed modeling comments when they clarify units, per-unit scaling, relaxations, or the physical meaning of an equation.
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

## Documentation Style

- Write mathematical formulas in Markdown with directly renderable LaTeX.
- Use `$$ ... $$` for display equations and `$...$` for inline symbols.
- Do not use backslash-escaped square-bracket or parenthesis delimiters in project documents.
- Prefer aligned, readable display equations for objectives, constraints, cuts, and update rules; formulas should be human-readable in rendered Markdown, not just as raw text.
- Explain each symbol near the first formula where it appears, especially Benders variables such as `theta`, `Q`, `LB`, `UB`, `gap`, dual variables, and cut coefficients.

## Research Workflow

- Prioritize reproducibility over production robustness.
- Keep assumptions visible near the code that uses them.
- Do not hide modeling choices behind fallback branches.
- When something is missing or inconsistent, raise the error instead of guessing.
- Optimize for quick modification by a researcher reading the notebook for the first time.
