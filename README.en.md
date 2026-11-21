# second-take

**A method layer that turns a long story into shootable shots — and every shot into a reproducible prompt.**

Not a prompt collection. What it gives you is criteria, gates and ledgers: every step has a pass/fail judgement, and when something comes out wrong you can see which step stopped.

> `Take 2` on a film set means "one more, until it's right".
> `my take` means "how I see it". The name is both: **regenerate until it's correct.**

## Quick start

Python 3.11+ and git. Nothing else to install.

```bash
git clone <this repo>
cd second-take
python3 tools/bootstrap.py --check     # Windows: python tools/bootstrap.py --check
```

Exit code `0` means the environment is ready. Anything else prints exactly what is missing and how to fix it. Directories it needs, it creates itself.

Then open `开工提示词.md` (Chinese) and paste that block into your AI assistant — it asks you three questions (where the source is / what genre / how it relates to the original), then takes you to your first frame. You don't need to read anything else before that.

## What's inside

| Directory | What it is |
|---|---|
| `Agent框架/` | Per-step criteria and judgement tables. Entry point: `Agent框架/00_主轴_按环节读_v1.md` |
| `shapes/` | Empty criteria / step / handoff forms. Take one, fill it with your own rules |
| `rules/` | The *shape* of a criterion is public; the *binding* is not. Unbound reports "not green" |
| `packaging/` | Packing and de-identification: leak scan, duplicate check, package verify |
| `tools/` | Batch panel, asset measurement, bootstrap, release |
| `tests/` | 32 cases that test the checkers themselves — `python -m pytest -q` |

## Three premises

If you disagree with these, the rest will feel wrong:

1. **Long projects rely on ledgers, not memory.** Exactly one ledger decides which version counts; otherwise an old version comes back wearing the disguise of a summary.
2. **Drafts are physically separated from the source.** Until every self-check passes, the source is not touched by a single character.
3. **A character only acts on what that character knows.** What the author knows must not leak out of a character's mouth.

## Check it yourself

No trust required — three commands:

```bash
python packaging/_doctor.py                                            # which side am I on? what's missing?
python packaging/_triage.py .                                          # structural signals: secrets, local paths
python packaging/_leakscan.py --deny packaging/public_denylist.txt     # this repo's own denylist, history included
```

On a fresh clone the last two return exit code **2**. That is **"not checked"**, not "clean": wordlists belong to your project, not to this library. The scanner refuses to give you a green it didn't earn.

## Security

Local scripts only: no telemetry, no network beyond the `git` commands you run yourself, no elevated permissions. Boundaries and the reporting channel: `SECURITY.md`.

One thing to read before you run the packer: `packaging/_pack.py --out <dir>` **deletes** that output directory when a hard gate fails. Point `--out` at a dedicated, empty directory.

## License

- Code (`*.py`, scripts, CI): Apache-2.0 — commercial use allowed, modifications don't have to be open.
- Docs and methodology (`*.md`, images, prompt templates): CC BY-SA 4.0 — attribution required, derivatives under the same license.

Out of scope: any novel text, character settings, or media files. This repository contains none and does not accept pull requests containing them.

## Contributing

Issues and PRs are welcome. Read `CONTRIBUTING.md` first (there is a licensing clause) and `CODE_OF_CONDUCT.md` (three lines).
