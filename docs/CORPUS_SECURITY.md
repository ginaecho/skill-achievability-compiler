# Security review of the third-party skill corpus

A skill document is not data: it is a set of instructions an agent will
follow with real tools. A corpus of 145 skills fetched from twelve
third-party repositories is therefore an untrusted input to every experiment
that loads it, and to anyone who reproduces those experiments. This is the
review, the findings, and what we do about them.

Reproduce with:

```
python3 scripts/fetch_skills_ext.py                 # re-fetch from PROVENANCE.json
python3 scripts/scan_skills.py --out paper/WIP/results/security_scan.json
python3 -m pytest tests/test_corpus_security.py
```

## Method

`scripts/scan_skills.py` reads every `SKILL.md` and **executes nothing**. It
reports evidence in six families, each hit with file, line and matched text
so a human makes the judgement:

| family | what it looks for |
|---|---|
| `injection` | text impersonating the harness (fake system/assistant turns, `<system-reminder>`), "ignore previous instructions", instructions about commit attribution, requests to reveal the system prompt, hidden HTML-comment instructions |
| `exfiltration` | sending local secrets off the machine; reading `~/.ssh`, `~/.aws/credentials`, `.netrc`, `.env` |
| `destructive` | `rm -rf` of a root-ish path, force push, history rewrite, `mkfs`/`dd`/`shred`, `chmod 777` |
| `remote_code` | fetching code and running it in one step (`curl … \| bash`, `eval` of a download, install from a URL) |
| `obfuscation` | long base64 blobs, zero-width characters, bidi controls, Unicode tag characters |
| `self_config` | edits to the agent's own configuration or hooks, widened permissions, writes outside the working directory |

The last family matters most for an agent harness: a skill that edits
`~/.claude/settings.json` or installs a hook changes what *every later skill*
is permitted to do.

## Findings (162 files: 17 vendor + 145 third-party)

**No malicious skill, and no prompt-injection payload aimed at an agent.**
Zero hits for fake harness turns, hidden instructions, invisible characters,
obfuscated payloads, credential exfiltration or agent-configuration edits.
Nine files raised at least one flag; every one is benign in context:

| file | flag | judgement |
|---|---|---|
| `openai__skills/sentry` | `curl https://cli.sentry.dev/install -fsS \| bash` | **Real, low.** A genuine remote-code-execution instruction, to the vendor's own domain. Standard industry practice; still means an agent following the skill executes code it did not read. The only finding we would act on. |
| `ComposioHQ__awesome-claude-skills/langsmith-fetch` | appends an API key to `~/.bashrc` | **Hygiene.** Persists a secret in plaintext outside the working directory. Not an attack. |
| `Masriyan__…/16-ai-llm-security` | "ignore previous instructions and …" | Benign: a *defensive* skill listing injection payload families to test against. |
| `Masriyan__…/10-cloud-security`, `alirezarezvani__…/docker-development` | `rm -rf /var/lib/apt/lists/*`, `chmod 777` | Benign: Dockerfile examples, the `chmod 777` shown as the insecure "before". |
| `Security-Phoenix-demo__…/cti-search-skill`, `glebis__…/firecrawl-research` | `cp .env.example .env` | Benign: ordinary setup. The rule is deliberately broad. |
| `microsoft__skills/azure-compliance`, `azure-kubernetes` | "show me expired keys/secrets" | Benign: Key Vault compliance queries. |

The scanner's precision is low by design. A rule that only fires on
unambiguous attacks would miss the first real one.

## Exposure in our experiments

Sixteen skills were run by a live agent with a shell (`scripts/usefulness.py`):
the eight authored specification variants and eight third-party or vendor
skills. **None is among the nine flagged files.** Each run happens in a fresh
temporary directory with the tool set restricted to the runtime under test.

Two honest limits of that containment:

1. A temporary working directory is **not a jail**. An agent granted `Bash`
   can reach the rest of the machine. Anyone reproducing the run-time half of
   the evaluation should do it in a container or VM, not on a workstation
   holding credentials.
2. `--permission-mode acceptEdits` means the agent is not asked before
   editing files. That is what makes the experiment unattended, and it is
   also why the skill set must be scanned first.

## What we do about it

- The third-party skill files are **not committed**. `real-skills/` and
  `real-skills-ext/*/` are ignored; only `PROVENANCE.json` (URL, repo,
  license note, fetch date) and `VERDICTS.md` are in the tree, so the corpus
  is reproducible without redistributing anyone's content or importing it
  into this repository's history.
- `tests/test_corpus_security.py` fails on any `injection`, `exfiltration`,
  `obfuscation` or `self_config` hit, so a future corpus refresh cannot
  silently introduce one. `destructive` and `remote_code` hits are reported
  but do not fail the suite, since security and DevOps skills legitimately
  quote dangerous commands.
- The one real finding (`curl | bash`) is upstream's and points at a
  reputable vendor domain; we neither run that skill nor patch someone else's
  repository. It is recorded here.

## A note on where the injection attempt actually appeared

During corpus collection, a **web search result** — not a skill file —
contained a block formatted to look like a harness system notice, attempting
to change git commit attribution. It was ignored. It is worth recording
because it locates the real risk surface: for an agent that browses, the
untrusted input arrives from search and fetch, and a static scan of the
skills would never have seen it.
