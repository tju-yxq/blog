#!/usr/bin/env python3
"""Sync notes and assets from tju-yxq/wiki into tju-yxq/blog (Hexo + ParticleX)."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

CATEGORY_MAP = {
    "ai-infra": "AI Infra",
    "llm-safety": "LLM Safety",
    "multi-agent": "Multi-Agent System",
    "security": "Cybersecurity",
    "engineering": "Engineering",
}

DEFAULT_TAGS = {
    "qwen38-kv-budget": ["KV Cache", "vLLM", "Qwen3.8", "AgentX"],
    "block-size-gemma4": ["Block Size", "vLLM", "Gemma 4", "SWA"],
    "block-size-weekly": ["Block Size", "vLLM", "Qwen3.5", "Hybrid Attention"],
    "block-size-modifiable": ["Block Size", "vLLM", "Prefix Cache"],
    "block-size-hybrid": ["Block Size", "Hybrid Attention", "vLLM"],
    "long-context-attention": ["Attention", "KV Cache", "DSA"],
}


def git_last_commit_date(repo_dir: Path, rel_path: str) -> str:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(repo_dir), "log", "-1", "--format=%ci", "--", rel_path],
            text=True,
        ).strip()
        if out:
            # Format: 2026-11-25 18:46:44 +0800 -> 2026-11-25 18:46:44
            return " ".join(out.split()[:2])
    except Exception:
        pass
    return "2026-11-25 12:00:00"


def extract_existing_meta(post_path: Path) -> tuple[str | None, str | None, list[str]]:
    """Preserve existing date/description/tags if already customized in blog."""
    if not post_path.exists():
        return None, None, []
    text = post_path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, flags=re.S)
    if not m:
        return None, None, []
    fm = m.group(1)
    date_m = re.search(r"^date:\s*(.+)$", fm, flags=re.M)
    desc_m = re.search(r"^description:\s*(.+)$", fm, flags=re.M)
    tags = re.findall(r"^\s*-\s+(.+)$", fm.split("tags:", 1)[1], flags=re.M) if "tags:" in fm else []
    date_val = date_m.group(1).strip() if date_m else None
    desc_val = desc_m.group(1).strip().strip('"').strip("'") if desc_m else None
    return date_val, desc_val, [t.strip() for t in tags]


def auto_summary(body: str) -> str:
    for para in body.split("\n\n"):
        line = para.strip()
        if not line or line.startswith(("#", ">", "|", "![", "```", "-", "*")):
            continue
        plain = re.sub(r"`([^`]+)`", r"\1", line)
        plain = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", plain)
        plain = re.sub(r"\*\*([^*]+)\*\*", r"\1", plain)
        plain = re.sub(r"\s+", " ", plain).strip()
        if len(plain) >= 20:
            return plain[:130] + ("…" if len(plain) > 130 else "")
    return "技术与实验记录。"


def sync(wiki_root: Path, blog_root: Path) -> None:
    wiki_docs = wiki_root / "docs"
    blog_src = blog_root / "source"
    posts_dir = blog_src / "_posts"
    posts_dir.mkdir(parents=True, exist_ok=True)

    # 1. Sync static assets
    asset_pairs = [
        (wiki_docs / "public/img", blog_src / "img"),
        (wiki_docs / "public/blk", blog_src / "blk"),
        (wiki_docs / "public/lectures", blog_src / "lectures"),
        (wiki_docs / "notes/ai-infra/block-size", blog_src / "img/block-size"),
    ]
    for src, dst in asset_pairs:
        if src.exists():
            shutil.copytree(src, dst, dirs_exist_ok=True)

    # 2. Sync all notes under docs/notes/<category>/*.md (excluding index.md)
    notes_root = wiki_docs / "notes"
    synced = 0
    for cat_dir in sorted(notes_root.iterdir()):
        if not cat_dir.is_dir():
            continue
        cat_name = CATEGORY_MAP.get(cat_dir.name, cat_dir.name)
        for md_file in sorted(cat_dir.glob("*.md")):
            if md_file.name == "index.md":
                continue
            slug = md_file.stem
            raw = md_file.read_text(encoding="utf-8")

            title = slug
            wiki_desc = ""
            fm_match = re.match(r"^---\n(.*?)\n---\n+", raw, flags=re.S)
            if fm_match:
                fm = fm_match.group(1)
                mt = re.search(r"^title:\s*(.+)$", fm, flags=re.M)
                if mt:
                    title = mt.group(1).strip().strip('"').strip("'")
                md = re.search(r"^description:\s*(.+)$", fm, flags=re.M)
                if md:
                    wiki_desc = md.group(1).strip().strip('"').strip("'")
                body = raw[fm_match.end():]
            else:
                mh1 = re.match(r"^#\s+(.+)\n+", raw)
                if mh1:
                    title = mh1.group(1).strip()
                body = raw

            # Remove leading H1 (ParticleX renders page.title as H1)
            body = re.sub(r"^#\s+.*\n+", "", body, count=1)

            # Normalize image & internal links (no /blog prefix; Hexo prepends root automatically)
            body = re.sub(r"\]\(<([^>]+)>\)", r"](\1)", body)
            body = re.sub(r"\]\(\./block-size/", "](/img/block-size/", body)
            body = re.sub(r"\]\(block-size/", "](/img/block-size/", body)
            body = re.sub(r"\]\(/notes/[a-z0-9-]+/([a-z0-9-]+)(?:\.html)?\)", r"](/posts/\1/)", body)
            body = re.sub(r"\]\(/notes/ai-infra/\)", "](/categories/AI-Infra/)", body)

            # Convert VitePress ::: container blocks to standard blockquotes
            body = re.sub(
                r"^:::\s*(?:tip|info|warning|danger)\s*(.*)\n([\s\S]*?)^:::\s*$",
                lambda m: "> **" + (m.group(1).strip() or "说明") + "**\n> " + m.group(2).strip().replace("\n", "\n> "),
                body,
                flags=re.M,
            )

            out_file = posts_dir / f"{slug}.md"
            prev_date, prev_desc, prev_tags = extract_existing_meta(out_file)
            rel_wiki_path = str(md_file.relative_to(wiki_root))
            wiki_date = git_last_commit_date(wiki_root, rel_wiki_path)
            date_str = prev_date or wiki_date
            desc = wiki_desc or prev_desc or auto_summary(body)
            desc = desc.replace('"', '\\"')
            tags = prev_tags or DEFAULT_TAGS.get(slug, [cat_name])
            tags_yaml = "\n".join(f"  - {t}" for t in tags)

            frontmatter = (
                f'---\n'
                f'title: "{title}"\n'
                f'date: {date_str}\n'
                f'updated: {wiki_date}\n'
                f'description: "{desc}"\n'
                f'categories:\n'
                f'  - {cat_name}\n'
                f'tags:\n'
                f'{tags_yaml}\n'
                f'---\n\n'
            )
            out_file.write_text(frontmatter + body.strip() + "\n", encoding="utf-8")
            synced += 1

    print(f"Synced {synced} posts from {wiki_root} -> {blog_root}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: sync_from_wiki.py <wiki_dir> <blog_dir>")
    sync(Path(sys.argv[1]), Path(sys.argv[2]))
