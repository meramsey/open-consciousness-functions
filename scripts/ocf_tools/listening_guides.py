"""Deterministic metadata-derived listener documents; no narration authoring."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit
from xml.sax.saxutils import escape

from .artwork_content import function_artwork_content
from .indexes import load_all_functions
from .locale import LocaleCatalog
from .paths import REPO_ROOT
from .utils import OCFError, write_bytes_atomic

MISSING = (
    "Reviewed guide instructions and relationships are not supplied here; no instructions inferred."
)


def _literal(value):
    """Keep metadata literal in the small supported Markdown subset."""
    return "`" + str(value).replace("`", "&#96;").replace("\n", " ") + "`"


def function_markdown(record, content, *, documentation=None):
    """Render a registry record and existing artwork/cue helper result."""
    lines = [
        f"# {record.id}: {documentation['title']['text'] if documentation else record.canonical_name}",
        "",
        "Current catalog and documented instructions; not listening or release approval."
        if documentation
        else "Metadata snapshot, not reviewed session instructions or release approval.",
        "",
        "[All function guides](../index.md)",
        "",
        "## Purpose and description",
        "",
    ]
    for name in ("purpose", "description"):
        resolution = content.get(f"{name}_resolution") or {}
        value = content.get(name)
        if name == "description" and documentation:
            value = documentation["short_description"]["text"]
            resolution = {"status": "canonical catalog description"}
            if value == content.get("purpose"):
                continue
        lines += [
            f"{name.title()} ({resolution.get('status', 'not-supplied')}): "
            + (_literal(value) if value else "Not supplied."),
            "",
        ]
    lines += ["## Exact current cues", ""]
    cues = ([content["primary"]] if content.get("primary") else []) + content.get(
        "secondary_commands", []
    )
    if not content.get("primary"):
        lines += ["Primary cue: Not supplied.", ""]
    for cue in cues:
        designation = "Primary" if cue == content.get("primary") else "Secondary"
        lines += [
            f"### {designation}: {cue['command_id']}",
            "",
            f"Display cue: {_literal(cue['display_cue'])}",
            "",
            "Spoken cue: "
            + (
                _literal(cue["spoken_cue"])
                if cue.get("binding_status") == "resolved" and cue.get("spoken_cue")
                else "Not supplied as reviewed speech."
            ),
            "",
            f"Cue binding status: {_literal(cue['binding_status'])}",
            "",
        ]
        if documentation:
            command = next(c for c in documentation["commands"] if c["id"] == cue["command_id"])
            lines += [
                f"Role: {_literal(command['role'])}",
                "",
                f"Usage: {command['usage']['text']}",
                "",
                f"Meaning: {command['explanation']['text']}",
                "",
                "Ordered activation procedure:",
                "",
            ]
            steps = command["procedure_steps"]
            if steps:
                lines += [f"{i}. {step['instruction']['text']}" for i, step in enumerate(steps, 1)]
            else:
                lines += ["Not specified; do not infer an activation ritual."]
            lines += [
                "",
                f"Intended effect scope: {_literal(command.get('effect_scope', 'not specified'))}.",
                "",
            ]
            invocation = command.get("invocation_scope")
            if invocation:
                lines += [
                    f"Invocation: {_literal(invocation.get('activation'))}; {_literal(invocation['persistence'])}. {invocation['description']}",
                    "",
                ]
            for relation in command.get("related_commands", []):
                lines += [
                    relation["label"]["text"]
                    + ": "
                    + ", ".join(_literal(x["phrase"]) for x in relation["commands"]),
                    "",
                ]
            evidence = set((command.get("procedure") or {}).get("evidence_keys", []))
            bound = {item["key"] for item in record.data.get("narration", {}).get("sequence", [])}
            if evidence and evidence.isdisjoint(bound):
                lines += [
                    "Procedure evidence points outside this function's bound narration sequence. Do not assume an existing recording teaches this command.",
                    "",
                ]
    if documentation:
        life = record.data.get("lifecycle", {})
        lines += [
            "## Operating behavior and modes",
            "",
            "These are intended exercise behaviors, not software sensors, physiological controls or demonstrated effects.",
            "",
            f"Function activation: {_literal(life.get('activation'))}. Intended persistence: {_literal(life.get('persistence'))}.",
            "",
        ]
        for scope in documentation["lifecycle_scopes"]:
            activation = f"; activation: {scope['activation']}" if scope.get("activation") else ""
            lines += [
                f"- {scope['label']['text']} ({scope['persistence']}{activation}): {scope['description']['text']}"
            ]
        for condition in life.get("trigger_conditions", []):
            lines += [f"- Declared condition or reset: {condition}"]
        release = life.get("release", {})
        lines += [
            "",
            "Declared return/release command: "
            + (
                _literal(release["command"])
                if release.get("command")
                else "None separately specified."
            ),
            "",
            "If no duration or reset condition is declared, no clock duration or additional reset is inferred. Playback controls are not semantic release commands.",
            "",
            "## Related functions",
            "",
        ]
        for relation in documentation.get("related_functions", []):
            lines += [
                f"- Optional: [{relation['title']['text']}]({relation['function_id']}.md). {relation['description']['text']} Approval: {relation['approval']}."
            ]
        if not documentation.get("related_functions"):
            lines += [
                "No approved complementary-function link is declared. This does not prevent independent choice."
            ]
        lines += ["", "## Historical lookup and compatibility", ""]
        from .commands import is_active, resolve_phrase

        historical = record.data.get("historical_lookup", [])
        lines += [
            f"- Historical only ({item['kind']}): {_literal(item['text'])}." for item in historical
        ]
        for command in record.command_records:
            if not is_active(command):
                lines += [
                    f"- Historical command identity {_literal(command.id)}: {_literal(resolve_phrase(record, command))}. Not a current activation instruction."
                ]
            elif command.role == "legacy-alias":
                lines += [
                    f"- Retained compatibility alias {_literal(command.id)}: {_literal(resolve_phrase(record, command))}. Not an additional mode or a new primary command."
                ]
        if not historical and not any(
            c.role == "legacy-alias" or not is_active(c) for c in record.command_records
        ):
            lines += ["No separate historical lookup wording is declared."]
        lines += [
            "",
            "## Practice and edition materials",
            "",
            "Use the documented procedure for your chosen command; do not add repetition, breath holds or prerequisite functions. Practice remains optional. The listed steps use structured instruction metadata; edition narration supplies any further qualifications.",
            "",
            "Narration wording and recordings are edition-specific. [Guide and edition navigation](../index.md) lists included files when this guide is packaged. A source plan or approved script is not evidence of a released recording.",
            "",
        ]
    else:
        lines += [
            "## Activation procedures and relationships",
            "",
            MISSING,
            "",
            "This guide does not publish procedures or relationships without a uniform "
            "review gate; consult reviewed instructions for the specific edition.",
            "",
        ]
    lines += ["## Declared catalog metadata", ""]
    for label, value in (
        ("Domain", record.primary_domain),
        ("Activation", record.activation),
        ("Persistence", record.persistence),
        ("Historical source availability", record.source_availability),
        ("Reimplementation", record.reimplementation_status),
        ("Audio implementation", record.audio_implementation_status),
        ("Evidence", record.evidence_state),
        ("Command review", record.command_review),
    ):
        lines.append(f"- {label}: {_literal(value) if value else 'Not supplied.'}")
    lines += [
        "",
        "These declarations do not establish effects, duration, release instructions, "
        "render eligibility, or listening approval.",
        "",
        "## Precautions",
        "",
        "Do not listen while driving or doing anything requiring vigilance. Stop if "
        "uncomfortable. This is not medical advice or a substitute for healthcare.",
        "",
    ]
    lines += [f"- {_literal(note)}" for note in record.safety_notes]
    if not record.safety_notes:
        lines.append("Function-specific safety notes: Not supplied in catalog metadata.")
    source = (
        record.path.relative_to(REPO_ROOT)
        if record.path.is_relative_to(REPO_ROOT)
        else record.path.name
    )
    lines += [
        "",
        "## Sources and limits",
        "",
        f"Canonical function: {_literal(source)}",
        "",
        f"Locale: {_literal(content['locale'])}. Cues resolve through existing "
        "command/locale helpers; purpose and description use artwork_content.",
        "",
        "[General listening guide](../listening-guide.md)",
        "",
    ]
    return "\n".join(lines)


def function_guide_markdown(record, *, catalog=None, locale="en-US"):
    """One production projection of existing command/locale/lifecycle services."""
    from .command_docs import _function_document

    if locale != "en-US":
        raise OCFError(
            "listener guides currently support en-US only; no silent translation fallback"
        )
    catalog = catalog or LocaleCatalog()
    return function_markdown(
        record,
        function_artwork_content(record.id, locale, catalog=catalog, strict=False),
        documentation=_function_document(record, locale, catalog),
    )


def markdown_documents():
    """Build the ordered source snapshot using existing content authority."""
    catalog = LocaleCatalog()
    documents = {
        "listening-guide.md": (REPO_ROOT / "docs/LISTENING_GUIDE.md").read_text(encoding="utf-8")
    }
    records = load_all_functions()
    index = [
        "# Open Consciousness Functions — Guide Collection",
        "",
        "Portable offline documentation. Historical source availability, technical implementation, listening approval, and publication status are separate.",
        "",
        "[General listening guide](listening-guide.md) · [Complete PDF handbook](complete-guide.pdf)",
        "",
    ]
    for record in records:
        filename = f"functions/{record.id}.md"
        documents[filename] = function_guide_markdown(record, catalog=catalog)
    for category in sorted({record.primary_domain or "Uncategorized" for record in records}):
        index += [f"## {category}", ""]
        for record in records:
            if (record.primary_domain or "Uncategorized") != category:
                continue
            content = function_artwork_content(record.id, "en-US", catalog=catalog, strict=False)
            cue = content.get("primary") or {}
            description = content.get("description") or content.get("purpose") or "Description not supplied."
            index.append(
                f"- [{record.canonical_name}]({filename_for(record.id)}) — `{record.id}`; "
                f"Primary cue: {cue.get('display_cue', 'Not supplied')}; {description}."
            )
        index.append("")
    documents["index.md"] = "\n".join(index) + "\n"
    return documents


def filename_for(function_id: str) -> str:
    return f"functions/{function_id}.md"


def _inline(text, suffix=".pdf"):
    parts = []
    position = 0
    for match in re.finditer(r"`([^`]+)`|\[([^\]]+)\]\(([^)]+)\)", text):
        parts.append(escape(text[position : match.start()]))
        if match.group(1) is not None:
            parts.append(escape(match.group(1).replace("&#96;", "`")))
        else:
            target = match.group(3)
            if urlsplit(target).scheme not in {"", "http", "https"}:
                parts.append(escape(match.group(2)))
                position = match.end()
                continue
            if target.endswith(".md"):
                target = target[:-3] + suffix
            target = escape(target, {'"': "&quot;"})
            parts.append(f'<a href="{target}">{escape(match.group(2))}</a>')
        position = match.end()
    parts.append(escape(text[position:]))
    return "".join(parts)


def html_bytes(markdown):
    """Render the same small Markdown subset as accessible offline HTML."""
    title = escape(markdown.splitlines()[0].lstrip("# "))
    blocks = []
    for block in re.split(r"\n\s*\n", markdown.strip()):
        heading = re.match(r"^(#{1,3}) (.*)", block, re.DOTALL)
        if heading:
            level = len(heading.group(1))
            blocks.append(f"<h{level}>{_inline(heading.group(2), '.html')}</h{level}>")
        elif re.match(r"^\d+\. ", block):
            blocks.append(
                "<ol>"
                + "".join(
                    "<li>" + _inline(line.split(". ", 1)[1], ".html") + "</li>"
                    for line in block.splitlines()
                )
                + "</ol>"
            )
        elif block.startswith("- "):
            blocks.append(
                "<ul>"
                + "".join(f"<li>{_inline(line[2:], '.html')}</li>" for line in block.splitlines())
                + "</ul>"
            )
        else:
            blocks.append("<p>" + _inline(block.replace("\n", " "), ".html") + "</p>")
    css = """
    :root{color-scheme:light dark;--bg:#f6f7f5;--fg:#172d38;--card:#fff;--accent:#2c6e72}
    @media(prefers-color-scheme:dark){:root{--bg:#172027;--fg:#eef5f2;--card:#223039;--accent:#8bd0c8}}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 system-ui,-apple-system,Segoe UI,sans-serif}
    main{max-width:960px;margin:0 auto;padding:2rem 1rem 4rem}a{color:var(--accent)}h1,h2,h3{line-height:1.2}
    nav{margin-bottom:1.5rem}code{font-family:ui-monospace,SFMono-Regular,monospace}
    """
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{title}</title><style>{css}</style></head><body><main>\n"
        + "\n".join(blocks)
        + "\n</main></body></html>\n"
    ).encode("utf-8")


def pdf_bytes(markdown):
    """Render the supported Markdown subset as actual embedded-font text."""
    try:
        import reportlab
        from reportlab.lib import colors
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except ImportError as exc:
        raise OCFError("PDF guides require the optional .[guides] dependency") from exc

    fonts = sorted((REPO_ROOT / "brand").rglob("*.ttf"))
    font_path = fonts[0] if fonts else Path(reportlab.__file__).parent / "fonts/Vera.ttf"
    font = TTFont("OCFGuide", str(font_path))
    pdfmetrics.registerFont(font)
    missing = sorted(
        {c for c in markdown if not c.isspace() and ord(c) not in font.face.charToGlyph}
    )
    if missing:
        raise OCFError("Guide font lacks glyphs: " + " ".join(f"U+{ord(c):04X}" for c in missing))
    styles = getSampleStyleSheet()
    body = ParagraphStyle("GuideBody", fontName="OCFGuide", fontSize=10, leading=15, spaceAfter=8)
    for name in ("Heading1", "Heading2", "Heading3"):
        styles[name].fontName = "OCFGuide"
        styles[name].textColor = colors.HexColor("#172d38")
    stream = BytesIO()

    class GuideDocument(SimpleDocTemplate):
        def afterFlowable(self, flowable):
            if isinstance(flowable, Paragraph) and flowable.style.name.startswith("Heading"):
                key = f"heading-{self.seq.nextf('heading')}"
                self.canv.bookmarkPage(key)
                level = max(0, int(flowable.style.name.removeprefix("Heading")) - 1)
                self.canv.addOutlineEntry(flowable.getPlainText(), key, level=level)

    def page_number(canvas, document):
        canvas.setFont("OCFGuide", 8)
        canvas.drawRightString(document.pagesize[0] - document.rightMargin, 32, str(document.page))

    story = []
    for block in re.split(r"\n\s*\n", markdown.strip()):
        for line in (
            block.splitlines() if block.startswith("- ") or re.match(r"^\d+\. ", block) else [block]
        ):
            heading = re.match(r"^(#{1,3}) (.*)", line, re.DOTALL)
            if heading:
                story.append(
                    Paragraph(_inline(heading.group(2)), styles[f"Heading{len(heading.group(1))}"])
                )
            elif line.startswith("- "):
                story.append(Paragraph(_inline(line[2:]), body, bulletText="•"))
            elif re.match(r"^\d+\. ", line):
                number, text = line.split(". ", 1)
                story.append(Paragraph(_inline(text), body, bulletText=number + "."))
            else:
                story.append(Paragraph(_inline(line.replace("\n", " ")), body))
        story.append(Spacer(1, 3))
    document = GuideDocument(
        stream,
        title=markdown.splitlines()[0].lstrip("# "),
        author="Open Consciousness Functions",
        invariant=1,
        leftMargin=54,
        rightMargin=54,
        topMargin=48,
        bottomMargin=48,
    )
    document.build(story, onFirstPage=page_number, onLaterPages=page_number)
    return stream.getvalue()


def write_documents(documents, output, *, check=False, markdown_only=False):
    """Preflight every target before writing; freshness checks never modify files."""
    targets = {}
    for name, markdown in documents.items():
        targets[Path(output) / name] = markdown.encode("utf-8")
        if not markdown_only:
            targets[(Path(output) / name).with_suffix(".pdf")] = pdf_bytes(markdown)
            targets[(Path(output) / name).with_suffix(".html")] = html_bytes(markdown)
    for path, data in targets.items():
        if check:
            if not path.is_file() or path.read_bytes() != data:
                raise OCFError(f"Guide missing or stale: {path}")
        elif path.exists():
            raise OCFError(f"Refusing to overwrite existing guide: {path}")
    if not check:
        for path, data in targets.items():
            write_bytes_atomic(path, data, overwrite=False)
    return len(targets)


def portable_index_html(records, *, edition="0.3.0") -> bytes:
    """Build a self-contained, searchable offline browser for the 58 guides."""
    cards = []
    for record in records:
        content = function_artwork_content(
            record.id, "en-US", catalog=LocaleCatalog(), strict=False
        )
        cue = (content.get("primary") or {}).get("display_cue", "Not supplied")
        description = (
            content.get("description") or content.get("purpose") or "No description supplied."
        )
        cards.append(
            "<article class='card' data-search='{}'>"
            "<h2><a href='functions/{}.html'>{}</a></h2>"
            "<p class='meta'>{} · {}</p><p>{}</p>"
            "<p><a href='functions/{}.html'>Read guide</a> · "
            "<a href='functions/{}.pdf'>PDF</a> · "
            "<a href='functions/{}.md'>Markdown</a></p></article>".format(
                escape(
                    " ".join(str(x) for x in (record.id, record.canonical_name, cue, description))
                ),
                record.id,
                escape(record.canonical_name),
                escape(record.id),
                escape(cue),
                escape(str(description)),
                record.id,
                record.id,
                record.id,
            )
        )
    css = """
    :root{color-scheme:light dark;--bg:#f6f7f5;--fg:#172d38;--card:#fff;--accent:#2c6e72;--muted:#61747a}
    @media(prefers-color-scheme:dark){:root{--bg:#172027;--fg:#eef5f2;--card:#223039;--accent:#8bd0c8;--muted:#b4c7c4}}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,-apple-system,Segoe UI,sans-serif}
    main{max-width:1120px;margin:auto;padding:2rem 1rem 4rem}a{color:var(--accent)}.hero{padding:2rem 0 1rem}
    .hero h1{font-size:clamp(2rem,5vw,4rem);margin:.2rem 0}.meta{color:var(--muted);font-size:.92rem}
    input{width:100%;padding:.8rem 1rem;border:1px solid var(--muted);border-radius:.6rem;background:var(--card);color:var(--fg);font-size:1rem;margin:1rem 0 1.5rem}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:1rem}.card{background:var(--card);border-radius:.8rem;padding:1rem 1.1rem;box-shadow:0 2px 12px #0002}.card h2{font-size:1.2rem;margin:.1rem 0}.card p{margin:.45rem 0}.no-results{display:none}
    @media print{input{display:none}.card{box-shadow:none;border:1px solid #ccc;break-inside:avoid}.grid{display:block}.card{margin:.5rem 0}}
    """
    js = """
    const q=document.querySelector('#search'),cards=[...document.querySelectorAll('.card')],empty=document.querySelector('.no-results');
    q.addEventListener('input',()=>{const v=q.value.toLowerCase().trim();let n=0;cards.forEach(c=>{const ok=!v||c.dataset.search.toLowerCase().includes(v);c.hidden=!ok;if(ok)n++});empty.hidden=n>0});
    """
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>Open Consciousness Functions — Guide Collection v{escape(edition)}</title><style>{css}</style></head><body><main>"
        f"<header class='hero'><p class='meta'>Open Consciousness Functions · portable offline documentation · v{escape(edition)}</p>"
        "<h1>Function Guides</h1><p>Readable, self-contained guides for all implemented OCF functions. These documents are not listening approval or release authorization.</p>"
        "<p><a href='listening-guide.html'>General listening guide</a> · <a href='complete-guide.pdf'>Complete PDF handbook</a> · <a href='index.pdf'>PDF directory</a></p>"
        "<label for='search'>Search by title, ID, cue, or description</label><input id='search' type='search' placeholder='Search the 58 function guides'></header>"
        "<p class='no-results' hidden>No matching guides.</p><section class='grid'>"
        + "".join(cards)
        + f"</section><script>{js}</script></main></body></html>\n"
    ).encode("utf-8")


def build_portable_collection(
    output: Path, *, edition="0.3.0", zip_path: Path | None = None
) -> dict:
    """Generate a self-contained guide package without private audio dependencies."""
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise OCFError(f"refusing to overwrite non-empty guide collection: {output}")
    records = load_all_functions()
    markdown = markdown_documents()
    output.mkdir(parents=True, exist_ok=True)
    write_documents(markdown, output, markdown_only=True)
    # Replace the raw registry list with the reader-facing searchable index.
    (output / "index.md").write_text(
        "# Open Consciousness Functions — Guide Collection\n\n"
        f"Portable offline documentation, edition {edition}.\n\n"
        "[General listening guide](listening-guide.md) · [Complete handbook](complete-guide.pdf)\n\n"
        + "\n".join(
            f"- [{record.canonical_name}](functions/{record.id}.md) — `{record.id}`"
            for record in records
        )
        + "\n",
        encoding="utf-8",
    )
    for name, text in markdown.items():
        if name == "index.md":
            continue
        path = output / name
        write_bytes_atomic(path.with_suffix(".html"), html_bytes(text), overwrite=False)
        write_bytes_atomic(path.with_suffix(".pdf"), pdf_bytes(text), overwrite=False)
    complete = "# Open Consciousness Functions — Complete Guide\n\n" + "\n\n".join(
        markdown[name]
        for name in (
            "listening-guide.md",
            *sorted(n for n in markdown if n.startswith("functions/")),
        )
    )
    write_bytes_atomic(output / "complete-guide.pdf", pdf_bytes(complete), overwrite=False)
    write_bytes_atomic(
        output / "index.html", portable_index_html(records, edition=edition), overwrite=False
    )
    write_bytes_atomic(
        output / "index.pdf",
        pdf_bytes((output / "index.md").read_text(encoding="utf-8")),
        overwrite=False,
    )
    if zip_path:
        zip_path = Path(zip_path).resolve()
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(output.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(output).as_posix())
    return {
        "functions": len(records),
        "files": len([p for p in output.rglob("*") if p.is_file()]),
        "output": str(output),
        "zip": str(zip_path) if zip_path else None,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--portable-output", type=Path)
    parser.add_argument("--zip", type=Path, help="ZIP path for --portable-output")
    parser.add_argument("--check", action="store_true", help="Check freshness without writing")
    parser.add_argument("--markdown-only", action="store_true")
    args = parser.parse_args(argv)
    if args.portable_output:
        try:
            result = build_portable_collection(args.portable_output, zip_path=args.zip)
        except (OCFError, OSError) as exc:
            parser.exit(1, f"{exc}\n")
        print(json.dumps(result, indent=2))
        return 0
    if not args.output:
        parser.error("--output is required unless --portable-output is used")
    output = args.output if args.output.is_absolute() else REPO_ROOT / args.output
    try:
        count = write_documents(
            markdown_documents(), output, check=args.check, markdown_only=args.markdown_only
        )
    except (OCFError, OSError) as exc:
        parser.exit(1, f"{exc}\n")
    print(f"{'Checked' if args.check else 'Generated'} {count} guide files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
