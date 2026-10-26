"""Deterministic metadata-derived listener documents; no narration authoring."""

from __future__ import annotations

import argparse
import re
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
    index = ["# OCF function guides", "", "[General listening guide](listening-guide.md)", ""]
    for record in load_all_functions():
        filename = f"functions/{record.id}.md"
        documents[filename] = function_guide_markdown(record, catalog=catalog)
        index.append(f"- [{record.id}: {record.canonical_name}]({filename})")
    documents["index.md"] = "\n".join(index) + "\n"
    return documents


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
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{title}</title></head><body><main>\n"
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
                self.canv.addOutlineEntry(flowable.getPlainText(), key, level=0)

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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--check", action="store_true", help="Check freshness without writing")
    parser.add_argument("--markdown-only", action="store_true")
    args = parser.parse_args(argv)
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
