# OMP Collab

[中文](README.md) · MIT License

An Agent Skill for delegating bounded reviews, derivations, or drafts from a primary assistant to an existing [Oh My Pi (OMP)](https://github.com/can1357/oh-my-pi) model, then checking the answer before integration.

The package includes a Python standard-library runner. It does not install OMP, configure providers, or treat another model's answer as verified evidence.

## Install

Requires Python 3.10+, OMP, and an already configured model account. OMP runs locally; inference may use a remote paid provider.

```sh
git clone https://github.com/jasonroject/omp-collab.git
```

Copy the complete `skills/omp-collab` directory to `~/.codex/skills/` (or your custom `$CODEX_HOME/skills/`) without overwriting an existing skill. Preserve its supporting directories and start a new session for discovery. Other clients supporting `SKILL.md` can use the same package in their own skill directories.

Example instruction:

> Use $omp-collab to ask my configured OMP model for an independent review, then verify and integrate its findings.

## Run directly

```sh
omp --help
omp models find deepseek
python skills/omp-collab/scripts/omp_delegate.py --model deepseek/deepseek-flash --task examples/review-task.md --output .omp-collab-runs --timeout 180
```

Replace the model identifier with a configured `provider/model`. Use `--omp` for an explicit native executable path; `.cmd`, `.bat`, and `.ps1` wrappers are unsupported. The runner never silently switches providers or retries requests.

Each invocation creates a fresh working directory with `request.md`, `response.txt`, `stderr.txt`, and `run.json`. A `returned` status means only a zero exit code and nonempty stdout. Review completeness, citations, calculations, units, and code; add a `review.md` recording accepted, corrected, and unresolved findings.

The CLI requests disabled built-in tools, extensions, rules, skills, LSP, and session persistence. OMP may still discover MCP, custom tools, and user or ancestor configuration. Use a trusted configuration: `--no-tools` is not a universal capability denylist. See the [compatibility notes](skills/omp-collab/references/compatibility.md). The model is instructed to return text without tool use; this version does not enforce a complete sandbox. Supply necessary source excerpts and check its conclusions independently.

Timeouts and Ctrl-C attempt to terminate the invocation's process group/tree and retain captured output. Cleanup may take up to 10 extra seconds; failures are recorded in diagnostics and descendants may remain. Task text is supplied through a file with an argument-array process launch, not shell interpolation. Artifacts can contain private context and diagnostics: keep them private. Only the default `.omp-collab-runs/` output directory is covered by this repository's ignore rule; exclude custom locations separately.

## Parallel workers

Independent briefs can run in separate OMP processes, with two concurrent calls by default:

```sh
python skills/omp-collab/scripts/omp_parallel.py --model deepseek/deepseek-flash --task examples/review-task.md --task examples/unit-check-task.md --jobs 2 --timeout 180
```

Each worker has separate artifacts; `batch.json` tracks progress. Per-task timeouts exclude queue time. Failure or timeout stops new launches while existing calls may finish. Ctrl-C requests cancellation of running workers and skips queued tasks. Every call starts a fresh session: provide its context explicitly and run dependent tasks sequentially.

Workers share provider quotas and rate limits, with separate request costs. More processes do not guarantee a speedup. Start with two and increase only when useful. The primary assistant integrates proposed changes and verifies answers; workers must not own the same output files.

## Tests

```sh
python -m unittest discover -s tests -v
```

Offline tests cover Unicode output, process failures, timeout termination, task isolation, and argument handling. CI runs on Windows and Linux without provider credentials. Live model access requires an authenticated OMP installation and is not proven by offline tests.

Initial integration environment: Windows, Python 3.14, OMP 18.8.4. Check CLI compatibility on other versions. A successful model request does not establish answer correctness.

Contributions should include relevant checks and must exclude credentials or private task material. [MIT licensed](LICENSE). Independent of OpenAI, DeepSeek, and OMP; no model weights or OMP distribution included.
