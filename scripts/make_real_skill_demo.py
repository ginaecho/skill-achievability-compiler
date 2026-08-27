#!/usr/bin/env python3
"""Run and record natural-language -> LLM pack -> checker for five real skills."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo" / "real-skill-cases"
SOURCES = DEMO / "natural-language"
PACKS = DEMO / "generated-packs"
RESULTS = DEMO / "results.json"
TRANSCRIPT = DEMO / "transcript.txt"
VIDEO = DEMO / "skillc-real-skills-demo.mp4"
UPSTREAM = "https://raw.githubusercontent.com/anthropics/skills"
COMMIT = "3b3fad96af16a10759d930941b4520ba0c40edae"
SKILLS = [
    "webapp-testing",
    "mcp-builder",
    "frontend-design",
    "slack-gif-creator",
    "algorithmic-art",
]


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()


def fetch_sources() -> list[dict]:
    rows = []
    for name in SKILLS:
        folder = SOURCES / name
        folder.mkdir(parents=True, exist_ok=True)
        skill = fetch(f"{UPSTREAM}/{COMMIT}/skills/{name}/SKILL.md")
        license_text = fetch(f"{UPSTREAM}/{COMMIT}/skills/{name}/LICENSE.txt")
        (folder / "SKILL.md").write_bytes(skill)
        (folder / "LICENSE.txt").write_bytes(license_text)
        rows.append({
            "name": name,
            "source_url": (
                f"https://github.com/anthropics/skills/blob/{COMMIT}/"
                f"skills/{name}/SKILL.md"
            ),
            "source_sha256": hashlib.sha256(skill).hexdigest(),
            "source_bytes": len(skill),
            "license": "Apache-2.0",
        })
    return rows


def compact_and_check(rows: list[dict], provider: str, model: str,
                      attempts: int) -> list[dict]:
    from skillc import check
    from skillc.frontend.llm import DEVELOPER_ABILITIES, compact
    from skillc.pack import PackError, pack_digest

    PACKS.mkdir(parents=True, exist_ok=True)
    completed = []
    for row in rows:
        path = SOURCES / row["name"] / "SKILL.md"
        natural_language = path.read_text(encoding="utf-8")
        failures = []
        pack = None
        for attempt in range(1, attempts + 1):
            try:
                pack = compact(
                    natural_language,
                    provider=provider,
                    model=model,
                    runtime_abilities=DEVELOPER_ABILITIES,
                )
                break
            except (PackError, ValueError) as error:
                failures.append(
                    {"attempt": attempt, "schema_error": str(error)})
        if pack is None:
            raise RuntimeError(
                f"{row['name']}: schema gate rejected all {attempts} attempts: "
                f"{failures}")

        pack_path = PACKS / f"{row['name']}.json"
        pack_path.write_text(
            json.dumps(pack, indent=2) + "\n", encoding="utf-8")
        verdict = check(pack)
        completed.append({
            **row,
            "provider": provider,
            "model": model,
            "runtime_profile": "developer",
            "schema_failures": failures,
            "accepted_attempt": len(failures) + 1,
            "pack_path": str(pack_path.relative_to(ROOT)).replace("\\", "/"),
            "pack_digest": pack_digest(pack),
            "pack_summary": {
                "roles": pack["roles"],
                "capabilities": sorted(pack["capabilities"]),
                "protocol_steps": len(pack["protocol"]),
                "goal": pack["goal"],
            },
            "verdict": verdict.to_dict(),
        })
    return completed


def excerpt(path: Path, max_lines: int = 12) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    selected = lines[:max_lines]
    suffix = "\n..." if len(lines) > max_lines else ""
    return "\n".join(selected) + suffix


def write_evidence(rows: list[dict]) -> None:
    RESULTS.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    lines = [
        "SKILLC END-TO-END REAL-SKILL DEMO",
        f"Upstream: anthropics/skills@{COMMIT}",
        "Pipeline: natural language -> untrusted LLM -> schema gate -> checker",
        "",
    ]
    for index, row in enumerate(rows, 1):
        skill_path = SOURCES / row["name"] / "SKILL.md"
        summary = row["pack_summary"]
        verdict = row["verdict"]
        lines += [
            f"CASE {index}: {row['name']}",
            f"Source: {row['source_url']}",
            f"Input: {row['source_bytes']} bytes, sha256:{row['source_sha256']}",
            "",
            "NATURAL-LANGUAGE SKILL (opening excerpt)",
            excerpt(skill_path),
            "",
            f"COMPACT> provider={row['provider']} model={row['model']} "
            f"runtime={row['runtime_profile']}",
        ]
        for failure in row["schema_failures"]:
            lines.append(
                f"SCHEMA GATE attempt {failure['attempt']}: REJECTED - "
                f"{failure['schema_error']}")
        lines += [
            f"SCHEMA GATE attempt {row['accepted_attempt']}: ACCEPTED",
            f"PACK> roles={summary['roles']}",
            f"PACK> capabilities={len(summary['capabilities'])}, "
            f"protocol_steps={summary['protocol_steps']}",
            f"PACK> goal={json.dumps(summary['goal'])}",
            f"PACK> digest={row['pack_digest']}",
            f"CHECK> {verdict['verdict']} [{verdict['reason']}]",
        ]
        if verdict["witness"]:
            lines.append(
                "WITNESS> " + " -> ".join(
                    f"{kind}:{value}" for kind, value in verdict["witness"]))
        if verdict["frontier"]:
            lines.append("FRONTIER> " + json.dumps(verdict["frontier"]))
        lines.append("")
    TRANSCRIPT.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def font(size: int, bold: bool = False):
    names = ["consolab.ttf", "consola.ttf"] if bold else ["consola.ttf"]
    for name in names:
        path = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / name
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def wrap(text: str, width: int = 105) -> str:
    return "\n".join(
        textwrap.fill(line, width=width, replace_whitespace=False)
        if len(line) > width else line
        for line in text.splitlines())


def slide(title: str, subtitle: str, content: str,
          verdict: str = "") -> Image.Image:
    image = Image.new("RGB", (1920, 1080), "#08111f")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((70, 55, 1850, 1025), radius=22, fill="#0f1b2d",
                           outline="#334761", width=3)
    draw.rectangle((70, 55, 1850, 125), fill="#17263b")
    for x, color in ((105, "#ff5f57"), (145, "#febc2e"), (185, "#28c840")):
        draw.ellipse((x - 10, 80, x + 10, 100), fill=color)
    draw.text((230, 72), "skillc: natural language -> verified verdict",
              fill="#9fb3c8", font=font(25))
    draw.text((110, 150), title, fill="#f2f7ff", font=font(42, bold=True))
    draw.multiline_text((112, 210), wrap(subtitle, 96), fill="#a8bad0",
                        font=font(25), spacing=7)
    if verdict:
        color = "#59d185" if verdict == "ACHIEVABLE" else "#ff7b72"
        draw.rounded_rectangle((1490, 145, 1805, 210), radius=14,
                               fill="#0b1422", outline=color, width=3)
        draw.text((1520, 160), verdict, fill=color, font=font(27, bold=True))
    draw.rounded_rectangle((105, 315, 1815, 950), radius=14, fill="#050b13",
                           outline="#26384d", width=2)
    draw.multiline_text((135, 345), wrap(content), fill="#d7e2ef",
                        font=font(24), spacing=9)
    draw.text((110, 975), "Input and generated pack hashes are recorded",
              fill="#6f849b", font=font(21))
    draw.ellipse((1760, 72, 1780, 92), fill="#ff4d4f")
    draw.text((1790, 70), "REC", fill="#ff8f8f", font=font(22, bold=True))
    return image


def record(rows: list[dict]) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to create the MP4")
    slides = [(
        slide(
            "No pre-compacted JSON",
            "Five real Apache-2.0 SKILL.md files at a pinned upstream commit.",
            "1. Read natural-language SKILL.md\n"
            "2. Azure OpenAI compacts meaning into a formal pack\n"
            "3. Deterministic schema gate accepts or rejects the output\n"
            "4. Trusted skillc checker returns a structured verdict",
        ), 8)]
    for index, row in enumerate(rows, 1):
        skill_path = SOURCES / row["name"] / "SKILL.md"
        summary = row["pack_summary"]
        verdict = row["verdict"]
        source_content = "NATURAL LANGUAGE\n" + excerpt(skill_path, 8)
        slides.append((
            slide(
                f"{index}/5  {row['name']}: source",
                f"anthropics/skills@{COMMIT[:8]} | {row['license']} | "
                f"{row['source_bytes']} bytes",
                source_content,
            ), 8))
        gate_lines = [
            f"COMPACT> {row['provider']} / {row['model']}",
            f"Runtime assumptions: {row['runtime_profile']}",
        ]
        gate_lines.extend(
            f"SCHEMA GATE attempt {item['attempt']}: REJECTED\n"
            f"  {item['schema_error']}"
            for item in row["schema_failures"])
        gate_lines += [
            f"SCHEMA GATE attempt {row['accepted_attempt']}: ACCEPTED",
            f"PACK> {len(summary['roles'])} roles, "
            f"{len(summary['capabilities'])} capabilities, "
            f"{summary['protocol_steps']} protocol steps",
            f"GOAL> {json.dumps(summary['goal'])}",
            f"DIGEST> {row['pack_digest']}",
            "",
            f"CHECK> {verdict['verdict']} [{verdict['reason']}]",
        ]
        if verdict["witness"]:
            gate_lines.append(
                "WITNESS> " + " -> ".join(
                    f"{k}:{v}" for k, v in verdict["witness"]))
        if verdict["frontier"]:
            gate_lines.append("FRONTIER> " + json.dumps(verdict["frontier"]))
        slides.append((
            slide(
                f"{index}/5  {row['name']}: generated pack",
                "The JSON was generated live, schema-gated, saved, and checked.",
                "\n".join(gate_lines),
                verdict["verdict"],
            ), 10))
    slides.append((
        slide(
            "End-to-end evidence saved",
            "Every verdict names the exact generated pack via SHA-256.",
            "natural-language/   pinned upstream SKILL.md inputs\n"
            "generated-packs/    schema-accepted LLM outputs\n"
            "results.json        provider, model, hashes, packs, verdicts\n"
            "transcript.txt      readable execution record\n\n"
            f"Completed {len(rows)}/5 natural-language skill pipelines.",
        ), 9))

    with tempfile.TemporaryDirectory(prefix="skillc-e2e-demo-") as tmp:
        temp = Path(tmp)
        args = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
        for index, (image, duration) in enumerate(slides):
            path = temp / f"slide-{index:02d}.png"
            image.save(path)
            args += ["-loop", "1", "-t", str(duration), "-i", str(path)]
        filters = []
        normalized = []
        for index in range(len(slides)):
            filters.append(
                f"[{index}:v]fps=24,scale=1920:1080,format=yuv420p[v{index}]")
            normalized.append(f"[v{index}]")
        filters.append(
            "".join(normalized)
            + f"concat=n={len(slides)}:v=1:a=0[outv]")
        args += [
            "-filter_complex", ";".join(filters),
            "-map", "[outv]", "-c:v", "libx264", "-preset", "medium",
            "-crf", "20", "-movflags", "+faststart", str(VIDEO),
        ]
        subprocess.run(args, cwd=ROOT, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--provider", choices=("anthropic", "azure-openai"),
        default=os.environ.get("SKILLC_LLM_PROVIDER", "azure-openai"))
    parser.add_argument(
        "--model", default=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-5.4"))
    parser.add_argument("--attempts", type=int, default=3)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_rows = fetch_sources()
    rows = compact_and_check(
        source_rows, args.provider, args.model, args.attempts)
    write_evidence(rows)
    record(rows)
    for row in rows:
        verdict = row["verdict"]
        print(
            f"{row['name']}: {verdict['verdict']} [{verdict['reason']}] "
            f"(schema attempt {row['accepted_attempt']})")
    print(f"wrote {RESULTS.relative_to(ROOT)}")
    print(f"wrote {TRANSCRIPT.relative_to(ROOT)}")
    print(f"wrote {VIDEO.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "src"))
    raise SystemExit(main())
