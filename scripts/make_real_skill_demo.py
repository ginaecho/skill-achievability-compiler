#!/usr/bin/env python3
"""Run five sourced skill cases and render their exact output as an MP4."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo" / "real-skill-cases"
VIDEO = DEMO / "skillc-real-skills-demo.mp4"
RESULTS = DEMO / "results.json"
TRANSCRIPT = DEMO / "transcript.txt"

CASES = [
    {
        "path": "01-docx-render-verify/SKILL.md",
        "title": "DOCX: create, render, inspect",
        "source": "anthropics/skills: skills/docx/SKILL.md",
        "expect": "ACHIEVABLE",
        "reason": "All mandatory verification capabilities are declared.",
    },
    {
        "path": "02-github-pr-review/SKILL.md",
        "title": "GitHub: PR and human review handoff",
        "source": "GitHub Copilot cloud agent + github-mcp-server",
        "expect": "ACHIEVABLE",
        "reason": "The agent goal stops at requesting review, not self-approval.",
    },
    {
        "path": "03-fetch-is-not-search/SKILL.md",
        "title": "MCP fetch: retrieval is not search",
        "source": "modelcontextprotocol/servers: src/fetch",
        "expect": "IMPOSSIBLE",
        "expected_reason": "MISSING_CAPABILITY",
        "reason": "The workflow invokes search_web, but fetch only accepts known URLs.",
    },
    {
        "path": "04-protected-deployment/SKILL.md",
        "title": "GitHub Actions: protected deployment",
        "source": "GitHub Actions protected environments",
        "expect": "IMPOSSIBLE",
        "expected_reason": "BLOCKED_GUARD",
        "reason": "Prevent-self-review leaves environment_approved unestablished.",
    },
    {
        "path": "05-xlsx-recalc-required/SKILL.md",
        "title": "XLSX: recalculation is mandatory",
        "source": "anthropics/skills: skills/xlsx/SKILL.md",
        "expect": "IMPOSSIBLE",
        "expected_reason": "GOAL_UNSAT",
        "reason": "The restricted sandbox can write formulas but cannot verify them.",
    },
]


def run_cases() -> list[dict]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    rows = []
    for case in CASES:
        rel = Path("demo") / "real-skill-cases" / case["path"]
        command = [sys.executable, "-m", "skillc.cli", "check", str(rel), "-v"]
        proc = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
        output = (proc.stdout + proc.stderr).strip()
        expected = case["expect"]
        expected_reason = case.get("expected_reason")
        ok = expected in output and (
            expected_reason is None or expected_reason in output
        )
        expected_exit = 0 if expected == "ACHIEVABLE" else 1
        ok = ok and proc.returncode == expected_exit
        rows.append(
            {
                **case,
                "command": "python -m skillc.cli check "
                + str(rel).replace("/", "\\")
                + " -v",
                "output": output,
                "exit_code": proc.returncode,
                "passed": ok,
            }
        )
    return rows


def write_results(rows: list[dict]) -> None:
    RESULTS.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    lines = [
        "SKILLC REAL-SKILL DEMO",
        "Sourced, manually declared packs; no upstream tool is executed.",
        "",
    ]
    for index, row in enumerate(rows, 1):
        lines += [
            f"CASE {index}: {row['title']}",
            f"Source: {row['source']}",
            f"Scenario: {row['reason']}",
            f"PS> {row['command']}",
            row["output"],
            f"exit code: {row['exit_code']}",
            "",
        ]
    passed = sum(row["passed"] for row in rows)
    lines.append(f"EXPECTED RESULTS: {passed}/{len(rows)}")
    TRANSCRIPT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def font(size: int, bold: bool = False):
    names = ["consolab.ttf", "consola.ttf"] if bold else ["consola.ttf"]
    for name in names:
        path = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / name
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def wrapped(text: str, width: int) -> str:
    return "\n".join(
        textwrap.fill(line, width=width, replace_whitespace=False)
        if len(line) > width
        else line
        for line in text.splitlines()
    )


def slide(title: str, subtitle: str, terminal: str, verdict: str = "") -> Image.Image:
    image = Image.new("RGB", (1920, 1080), "#08111f")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((70, 55, 1850, 1025), radius=22, fill="#0f1b2d",
                           outline="#334761", width=3)
    draw.rectangle((70, 55, 1850, 125), fill="#17263b")
    for x, color in ((105, "#ff5f57"), (145, "#febc2e"), (185, "#28c840")):
        draw.ellipse((x - 10, 80, x + 10, 100), fill=color)
    draw.text((230, 72), "skillc demo - declared-pack verification",
              fill="#9fb3c8", font=font(25))
    draw.text((110, 160), title, fill="#f2f7ff", font=font(46, bold=True))
    draw.multiline_text((112, 225), wrapped(subtitle, 92), fill="#a8bad0",
                        font=font(27), spacing=8)
    if verdict:
        color = "#59d185" if verdict == "ACHIEVABLE" else "#ff7b72"
        draw.rounded_rectangle((1460, 155, 1805, 220), radius=14,
                               fill="#0b1422", outline=color, width=3)
        draw.text((1490, 170), verdict, fill=color, font=font(29, bold=True))
    draw.rounded_rectangle((105, 325, 1815, 950), radius=14, fill="#050b13",
                           outline="#26384d", width=2)
    draw.multiline_text((140, 360), wrapped(terminal, 102), fill="#d7e2ef",
                        font=font(28), spacing=12)
    draw.text((110, 975), "Actual skillc output | skillc 0.3.0 | may semantics",
              fill="#6f849b", font=font(22))
    draw.ellipse((1760, 72, 1780, 92), fill="#ff4d4f")
    draw.text((1790, 70), "REC", fill="#ff8f8f", font=font(22, bold=True))
    return image


def render_video(rows: list[dict]) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to create the MP4")
    if not all(row["passed"] for row in rows):
        raise RuntimeError("refusing to record: one or more demo cases failed")

    slides: list[tuple[Image.Image, int]] = []
    slides.append(
        (
            slide(
                "Can this agent skill achieve its goal?",
                "Five workflows grounded in first-party skills and product docs. "
                "The compiler checks declared capabilities, guards, protocol, "
                "and goal before any external tool runs.",
                "PS> python scripts\\make_real_skill_demo.py\n"
                "Running 5 schema-gated skill declarations...",
            ),
            7,
        )
    )
    for index, row in enumerate(rows, 1):
        terminal = (
            f"PS> {row['command']}\n\n{row['output']}\n\n"
            f"exit code: {row['exit_code']}"
        )
        slides.append(
            (
                slide(
                    f"{index}/5  {row['title']}",
                    f"Source: {row['source']}\nScenario: {row['reason']}",
                    terminal,
                    row["expect"],
                ),
                12,
            )
        )
    summary = "\n".join(
        f"{i}. {row['expect']:<10} {row.get('expected_reason', 'OK'):<20} "
        f"{row['title']}"
        for i, row in enumerate(rows, 1)
    )
    slides.append(
        (
            slide(
                "Result: 5/5 expected verdicts",
                "Two valid workflows accepted; three impossible deployments "
                "refuted with the specific missing capability, blocked guard, "
                "or unestablished goal.",
                summary
                + "\n\nEvidence: demo\\real-skill-cases\\results.json\n"
                "Sources: docs\\REAL_SKILL_DEMO_SOURCES.md",
            ),
            10,
        )
    )

    with tempfile.TemporaryDirectory(prefix="skillc-demo-") as tmp:
        temp = Path(tmp)
        args = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
        for index, (image, duration) in enumerate(slides):
            path = temp / f"slide-{index:02d}.png"
            image.save(path)
            args += ["-loop", "1", "-t", str(duration), "-i", str(path)]
        filters = []
        normalized = []
        for index in range(len(slides)):
            label = f"v{index}"
            filters.append(
                f"[{index}:v]fps=24,scale=1920:1080,format=yuv420p[{label}]"
            )
            normalized.append(f"[{label}]")
        filters.append(
            "".join(normalized)
            + f"concat=n={len(slides)}:v=1:a=0[outv]"
        )
        args += [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[outv]",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-movflags",
            "+faststart",
            str(VIDEO),
        ]
        subprocess.run(args, cwd=ROOT, check=True)


def main() -> int:
    rows = run_cases()
    write_results(rows)
    for row in rows:
        status = "PASS" if row["passed"] else "FAIL"
        print(f"{status}  {row['title']}: {row['output'].splitlines()[0]}")
    render_video(rows)
    print(f"wrote {RESULTS.relative_to(ROOT)}")
    print(f"wrote {TRANSCRIPT.relative_to(ROOT)}")
    print(f"wrote {VIDEO.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
