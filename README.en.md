# second-take

> **Chinese version (complete):** [README.md](README.md) — the Chinese text is the normative one; this English page is a full translation of it.

A method layer that turns a long story into shootable shots — and every shot into a reproducible prompt. Every step has a criterion; when something comes out wrong you can see which step stopped.

## What it does

- Story → storyboard → reproducible prompts → an image, without coming back to ask a human halfway.
- Every frame records *why* it is shot that way — not "roll until something looks right".
- Every step has an acceptance test: what counts as passed, who decides when it fails.
- The skills you already use stay: they generate, this library judges.

## What it doesn't do

- **It does not generate images, edit video, or voice anything.** Pictures and cuts still come from your own models and tools; this library only decides whether a frame passes.
- **It does not decide for you.** Where judgement is needed it stops and asks, instead of walking on.
- **It is not a prompt template collection.** Copying it as templates will waste it (see "Boundaries").
- **No network, no upload, no reading elsewhere on your machine.** Criteria are files, not services: no MCP, no vector store, no memory plugin, no pile of skills, and no API key needed to self-check.

## Three steps

### 1. Get the package

Download `second-take-x.y.z-win.zip` from [Releases](https://github.com/O2wuyanliuse/second-take/releases), or `git clone` this repository (clone only matters if you want to follow updates).

**You need Python 3.11+**, nothing else. The `-win` in the file name is history, not a platform limit: the package is plain text and Python, no binaries; macOS and Linux use the same one.

### 2. Install

Installing only prepares the environment. It does not start work — that is step 3.

**A. Let your AI install it (recommended — the path shown in the demo video)**

Drag the zip straight into your AI workbench's chat (DSH, Claude Code, Cursor — any of them) together with this line:

> Unpack this archive into an empty directory, run `python tools/bootstrap.py` there, and paste back the three lines it prints. It only means the install worked, not that work has started.

**If you don't want to open a terminal, that is the whole install.**

**B. Do it yourself**

In the unpacked directory:

```bash
python tools/bootstrap.py           # create the workspace, then self-check once
python tools/bootstrap.py --check   # inspect only, writes nothing
```

**On a clean machine the first command is always `bootstrap.py`, never `--check`**: the workspace does not exist yet, so `--check` will fail — that is "not built yet", not "broken".

`pytest` and `ruff` are optional: you can start without them. The test suite and CI dependencies are maintainer-only and not shipped with the package — see the repository page if you want to run them.

### 3. Read what it said

At this point it is still idle: paste the kickoff prompt to wake it.

What you get is not a wall of green — it is these three lines:

```
我在哪：工作区已建好，但 input/ 里还没有原文   (where I am: workspace built, no source text in input/ yet)
能自动检查的：3/19（16%）                      (machine-checkable: 3 of 19)
下一步：① 放原文进 workspace/input/ ② 对 AI 说「按 E0 开工」   (next steps)
```

The same text is written to `workspace/开工报告.md`; to see it again at any time: `python tools/status.py`.

**About that 16%.** There are 19 criteria, and the machine can judge only a small part of them today; the rest rely on the criteria tables and your own eyes. The number is there to help you estimate risk, not to be a score — it going up is what would mean this thing actually got stronger. And it is not a threshold: you can start with nothing passing, there is just no protection on that stretch of road — deviations have to be spotted by a human.

## Then: your first frame

Open `开工提示词.md` (Chinese) and paste that block into your AI. It asks you three questions first (where the source is / what genre / how it relates to the original), then takes you to your first frame. **You do not need to read any other document before that.**

Stuck or nothing comes out: [open an Issue](https://github.com/O2wuyanliuse/second-take/issues) with the output of `python tools/doctor.py`.

## What's inside

| Directory | What it is |
|---|---|
| `Agent框架/` | Per-step criteria and judgement tables (count with `ls`; docs don't quote numbers) |
| `shapes/` | Empty criteria / step / handoff forms. Take one, fill it with your own rules |
| `rules/` | The *shape* of a criterion is public; the *binding* is not. Unbound reports "not green" |
| `skills/` | Two loadable skills: the main pipeline and character turnaround; install and invoke lines sit at the top of each SKILL.md |
| `tools/` | `bootstrap.py` installs, `status.py` shows progress, `doctor.py` health-checks, `evidence.py` stores proof; plus a batch panel and asset measurement |
| `docs/` | Upgrade and rollback (`docs/upgrade.md`); the release process is maintainer-only and lives on the repository page |

To read by pipeline stage, start at `Agent框架/00_主轴_按环节读_v1.md`; if you don't know where to start, open `INDEX.md`.

## Three premises

If you disagree with these, the rest will feel wrong:

1. **Long projects rely on ledgers, not memory.** Exactly one ledger decides which version counts; otherwise an old version comes back wearing the disguise of a summary.
2. **Drafts are physically separated from the source.** Until every self-check passes, the source is not touched by a single character.
3. **A character only acts on what that character knows.** What the author knows must not leak out of a character's mouth.

## Trust and verification

- **No network, no telemetry, no reading elsewhere on your machine**; Python is the only thing to install.
- Want to know **where you are and what will trip you**: `python tools/status.py` — plain language only: coverage, risks, next steps; it always exits 0 (a mirror, not a gate — it never blocks you).
- Want to know **the state of this repository and workspace**: `python tools/doctor.py` (six lines: python / git / version / workspace / config / last evidence).
- Want to know **whether you shipped something you shouldn't have**: de-identification and packing are maintainer-only and not shipped with the package — get them from the repository page. This library never ships a wordlist: a wordlist spells out the words it bans, so it belongs to your project.

Never place this package in a global AI config directory such as ~/.dsh/AGENTS.md — it would be read in every project, which is pollution. The only supported install is a project-local AGENTS.md.

## Boundaries

**This is not a prompt encyclopedia; it is criteria and gates.**

It does not replace production. It turns the method you already use into machine-checkable rules, and points at contradictions in your operation and conflicts with the criteria.

Its scope: when the result is off, it helps you tell whether the prompt was the problem or something else. If you already run a mature prompt skill, keep it — let the model turn that run's practice into a few criteria, and use those to judge the next one.

The prompt experience in this repository is used in exactly two ways: **calibration** (does the skill's output contradict itself, does it turn literary words into numbers, does it fight the criteria) and **judging** (does this frame pass).

**One line: skills generate, this repository judges.**

## The name

`Take 2` on a film set means "one more, until it's right"; `my take` means "how I see it". The name is both: **regenerate until it's correct.**

## License

- Code (`*.py`, scripts, CI): [Apache-2.0](LICENSE) — commercial use allowed, modifications don't have to be open.
- Docs and methodology (`*.md`, images, prompt templates): [CC BY-SA 4.0](LICENSE-DOCS) — attribution required, derivatives under the same license.

Out of scope: any novel text, character settings, or media files. This repository contains none and does not accept pull requests containing them.

## Contributing

Issues and PRs are welcome. The code of conduct (three lines) is in the package as `CODE_OF_CONDUCT.md`; the contribution rules, including the licensing clause, live on the repository page.
