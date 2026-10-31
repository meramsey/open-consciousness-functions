"""Deterministic metadata-derived listener documents; no narration authoring."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from html import escape as html_escape
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.sax.saxutils import escape

from .artwork_content import function_artwork_content
from .indexes import load_all_functions
from .locale import LocaleCatalog
from .paths import REPO_ROOT
from .utils import OCFError, write_bytes_atomic, write_text_atomic

MISSING = (
    "Reviewed guide instructions and relationships are not supplied here; no instructions inferred."
)


def _literal(value):
    """Keep metadata literal in the small supported Markdown subset."""
    return "`" + str(value).replace("`", "&#96;").replace("\n", " ") + "`"


def function_markdown(record, content, *, documentation=None, narration_sections=None):
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
        if narration_sections:
            lines += [
                "## Complete readable canonical narration",
                "",
                "Each canonical narration section is printed once; repetition counts describe playback, not duplicate transcript text.",
                "",
            ]
            for section in narration_sections:
                lines += [
                    f"### {section['role']} — `{section['key']}`",
                    "",
                    f"Narration status: {_literal(section['status'] or 'not labeled')}.",
                    "",
                ]
                if section["repetitions"] > 1:
                    lines += [
                        f"Audio playback repetitions: {section['repetitions']}; transcript text shown once.",
                        "",
                    ]
                lines += [section["text"], ""]
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
    narration_sections = []
    seen_sections = {}
    for item in (record.data.get("narration") or {}).get("sequence", []):
        key = item.get("key")
        if not key:
            continue
        variables = item.get("variables") or {}
        identity = (key, json.dumps(variables, sort_keys=True, ensure_ascii=False))
        repetitions = item.get("repetitions", 1)
        if isinstance(repetitions, bool) or not isinstance(repetitions, int) or repetitions < 1:
            raise OCFError(f"{record.id}: invalid narration repetition count for {key}")
        if identity in seen_sections:
            narration_sections[seen_sections[identity]]["repetitions"] += repetitions
            continue
        entry, resolution = catalog.resource(key, locale, domain="narration", fallback=False)
        narration_sections.append(
            {
                "key": key,
                "role": item.get("role") or "narration",
                "status": entry.status,
                "text": entry.render(
                    variables, plural_rules=catalog.plural_rules_for(resolution.origin_locale)
                ),
                "repetitions": repetitions,
            }
        )
        seen_sections[identity] = len(narration_sections) - 1
    return function_markdown(
        record,
        function_artwork_content(record.id, locale, catalog=catalog, strict=False),
        documentation=_function_document(record, locale, catalog),
        narration_sections=narration_sections,
    )


def markdown_documents():
    """Build the ordered source snapshot using existing content authority."""
    catalog = LocaleCatalog()
    documents = {
        "listening-guide.md": (REPO_ROOT / "docs/LISTENING_GUIDE.md").read_text(encoding="utf-8")
    }
    records = load_all_functions()
    for record in records:
        filename = f"functions/{record.id}.md"
        documents[filename] = function_guide_markdown(record, catalog=catalog)
    documents["index.md"] = _guide_catalog(records)
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


def _guide_catalog(records, page_map=None):
    """Return registry-derived function directory text grouped by canonical domain."""
    categories = {}
    for record in records:
        page = (page_map or {}).get(record.id)
        page_text = (
            f" · [Complete handbook p. {page}](complete-guide.pdf#page={page})" if page else ""
        )
        categories.setdefault(record.primary_domain or "Uncategorized", []).append(
            f"- [{record.canonical_name}](functions/{record.id}.md) — `{record.id}`{page_text}."
        )
    lines = [
        "# Open Consciousness Functions — Guide Collection",
        "",
        "Portable offline documentation. Intended procedures and catalog metadata do not establish efficacy or release approval.",
        "",
        "[General listening guide](listening-guide.md) · [Complete handbook](complete-guide.pdf)",
        "",
    ]
    for category, entries in sorted(categories.items()):
        lines.extend([f"## {category}", "", *entries, ""])
    return "\n".join(lines) + "\n"


def complete_pdf_bytes(records, documents):
    """Build the standalone handbook with a page-numbered, linked table of contents."""
    try:
        import reportlab
        from reportlab.lib import colors
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer
        from reportlab.platypus.tableofcontents import TableOfContents
    except ImportError as exc:
        raise OCFError("PDF guides require the optional .[guides] dependency") from exc

    fonts = sorted((REPO_ROOT / "brand").rglob("*.ttf"))
    font_path = fonts[0] if fonts else Path(reportlab.__file__).parent / "fonts/Vera.ttf"
    pdfmetrics.registerFont(TTFont("OCFGuide", str(font_path)))
    styles = getSampleStyleSheet()
    for name in ("Heading1", "Heading2", "Heading3"):
        styles[name].fontName = "OCFGuide"
        styles[name].textColor = colors.HexColor("#172d38")
    body = ParagraphStyle(
        "CompleteGuideBody", fontName="OCFGuide", fontSize=9.5, leading=13.5, spaceAfter=6
    )
    cover = ParagraphStyle(
        "CompleteGuideCover",
        parent=styles["Title"],
        fontName="OCFGuide",
        fontSize=28,
        leading=34,
        textColor=colors.HexColor("#172d38"),
        spaceAfter=20,
    )
    category_style = ParagraphStyle("GuideCategory", parent=styles["Heading1"], fontName="OCFGuide")
    function_style = ParagraphStyle("GuideFunction", parent=styles["Heading2"], fontName="OCFGuide")
    toc_styles = [
        ParagraphStyle("GuideTOC0", fontName="OCFGuide", fontSize=10, leading=13, leftIndent=0),
        ParagraphStyle("GuideTOC1", fontName="OCFGuide", fontSize=9, leading=12, leftIndent=18),
    ]
    stream = BytesIO()
    page_map = {}

    class Handbook(SimpleDocTemplate):
        def beforeDocument(self):
            self._guide_keys = []
            page_map.clear()

        def afterFlowable(self, flowable):
            if not isinstance(flowable, Paragraph) or flowable.style.name not in {
                "GuideCategory",
                "GuideFunction",
            }:
                return
            title = flowable.getPlainText()
            level = 0 if flowable.style.name == "GuideCategory" else 1
            key = title.split(":", 1)[0] if level == 1 else f"ocf-guide-{len(self._guide_keys)}"
            self._guide_keys.append(key)
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(title, key, level=level)
            self.notify("TOCEntry", (level, title, self.page, key))
            if level == 1:
                page_map[title.split(":", 1)[0]] = self.page

    story = [
        Spacer(1, 100),
        Paragraph("Open Consciousness Functions", cover),
        Paragraph("Complete Function Guide · Edition 0.3.0", styles["Heading2"]),
        Spacer(1, 24),
        Paragraph(
            "Offline reference handbook. Function intent, technical implementation, listening approval, and publication authorization are separate.",
            body,
        ),
        PageBreak(),
        Paragraph('<a name="handbook-contents"/>Table of Contents', styles["Heading1"]),
    ]
    toc = TableOfContents()
    toc.levelStyles = toc_styles
    toc.dotsMinLevel = 0
    story.extend([toc, PageBreak()])

    def append_markdown(text, *, remove_title=False):
        def internal_link(match):
            title, target = match.groups()
            if target.endswith("index.md"):
                target = "#handbook-contents"
            elif target.endswith("listening-guide.md"):
                target = "#ocf-guide-0"
            elif re.fullmatch(r"OCF-[A-Z]+-\d+\.md", target):
                target = "#" + target[:-3]
            return f"[{title}]({target})"

        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", internal_link, text)
        lines = text.splitlines()
        if remove_title and lines and lines[0].startswith("# "):
            lines = lines[1:]
        for block in re.split(r"\n\s*\n", "\n".join(lines).strip()):
            if not block:
                continue
            heading = re.match(r"^(#{1,3}) (.*)", block, re.DOTALL)
            if heading:
                story.append(
                    Paragraph(_inline(heading.group(2)), styles[f"Heading{len(heading.group(1))}"])
                )
            elif block.startswith("- "):
                story.extend(
                    Paragraph(_inline(line[2:]), body, bulletText="•")
                    for line in block.splitlines()
                )
            elif re.match(r"^\d+\. ", block):
                for line in block.splitlines():
                    number, value = line.split(". ", 1)
                    story.append(Paragraph(_inline(value), body, bulletText=number + "."))
            else:
                story.append(Paragraph(_inline(block.replace("\n", " ")), body))
            story.append(Spacer(1, 3))

    story.append(Paragraph("General Listening Guide", category_style))
    append_markdown(documents["listening-guide.md"], remove_title=True)
    grouped = {}
    for record in records:
        grouped.setdefault(record.primary_domain or "Uncategorized", []).append(record)
    for category, functions in sorted(grouped.items()):
        story.extend([PageBreak(), Paragraph(escape(category), category_style)])
        for record in functions:
            lines = documents[f"functions/{record.id}.md"].splitlines()
            story.append(
                Paragraph(_inline(f"{record.id}: {record.canonical_name}"), function_style)
            )
            append_markdown("\n".join(lines[1:]))

    def page_number(canvas, document):
        canvas.setFont("OCFGuide", 8)
        canvas.drawRightString(document.pagesize[0] - document.rightMargin, 30, str(document.page))

    document = Handbook(
        stream,
        title="Open Consciousness Functions — Complete Guide",
        author="Open Consciousness Functions",
        invariant=1,
        leftMargin=52,
        rightMargin=52,
        topMargin=48,
        bottomMargin=48,
    )
    document.multiBuild(story, onFirstPage=page_number, onLaterPages=page_number)
    data = stream.getvalue()
    validate_handbook(data, records, page_map)
    return data, page_map


def validate_handbook(data, records, page_map):
    """Check the finished PDF, not estimated layout or renderer notifications."""
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data), strict=True)
    texts = [page.extract_text() for page in reader.pages]
    outlines = {}

    def visit(entries):
        for entry in entries:
            if isinstance(entry, list):
                visit(entry)
            else:
                page = reader.get_destination_page_number(entry)
                if page is None or not 0 <= page < len(texts):
                    raise OCFError("Handbook outline destination out of bounds")
                title = entry.title
                if title not in texts[page]:
                    raise OCFError(f"Handbook outline does not match page: {title}")
                outlines[title] = page + 1

    visit(reader.outline)
    expected = {"General Listening Guide"}
    expected.update(record.primary_domain or "Uncategorized" for record in records)
    expected.update(f"{record.id}: {record.canonical_name}" for record in records)
    if set(outlines) != expected or set(page_map) != {record.id for record in records}:
        raise OCFError("Handbook directory/outline inventory mismatch")
    for record in records:
        page = page_map[record.id]
        if type(page) is not int or page != outlines[f"{record.id}: {record.canonical_name}"]:
            raise OCFError(f"Handbook page reference mismatch: {record.id}")

    first_section = outlines["General Listening Guide"] - 1
    toc_text = "\n".join(texts[1:first_section])
    toc_links = []
    for number, page in enumerate(reader.pages):
        rows = {}
        if 1 <= number < first_section:

            def collect_row(text, cm, tm, font, size):
                if text.strip():
                    rows.setdefault(round(cm[5] + tm[5], 2), []).append(text.strip())

            page.extract_text(visitor_text=collect_row)
        for ref in page.get("/Annots", []):
            annotation = ref.get_object()
            action = annotation.get("/A", {})
            destination = annotation.get("/Dest")
            if action.get("/S") == "/GoTo":
                destination = action.get("/D")
            if destination is None:
                continue
            if isinstance(destination, str):
                destination = reader.named_destinations.get(destination)
                if destination is None:
                    raise OCFError("Dangling handbook named destination")
                target = reader.get_destination_page_number(destination)
            else:
                target = reader.get_page_number(destination[0].get_object())
            if target is None or not 0 <= target < len(texts):
                raise OCFError("Handbook link destination out of bounds")
            if 1 <= number < first_section:
                rect = annotation["/Rect"]
                row = [
                    parts
                    for y, parts in rows.items()
                    if float(rect[1]) - 0.1 <= y <= float(rect[3]) + 0.1
                ]
                if len(row) != 1 or len(row[0]) != 2:
                    raise OCFError("Handbook TOC link does not identify one visible row")
                digits, title = row[0]
                printed = re.search(r"(\d+)$", digits)
                if (
                    title not in outlines
                    or not printed
                    or int(printed[1]) != target + 1
                    or outlines[title] != target + 1
                ):
                    raise OCFError(f"Handbook TOC link/printed page/outline disagree: {title}")
                toc_links.append(target + 1)
    for title, page in outlines.items():
        # ReportLab emits page numbers before titles in extracted TOC text.
        pattern = rf"{page}\s+{re.escape(title)}(?:\s|$)"
        if not re.search(pattern, toc_text) or page not in toc_links:
            raise OCFError(f"Handbook visible/clickable TOC mismatch: {title}")
    if len(toc_links) != 2 * len(outlines):
        raise OCFError("Handbook TOC link inventory mismatch")
    return {"pages": len(texts), "toc_entries": len(outlines), "toc_links": len(toc_links)}


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
    catalog = LocaleCatalog()
    cards_by_category = {}
    for record in records:
        content = function_artwork_content(record.id, "en-US", catalog=catalog, strict=False)
        cue = (content.get("primary") or {}).get("display_cue", "Not supplied")
        description = (
            content.get("description") or content.get("purpose") or "No description supplied."
        )
        category = record.primary_domain or "Uncategorized"
        cards_by_category.setdefault(category, []).append(
            "<article class='card' data-search='{}' data-category='{}'>"
            "<h3><a href='functions/{}.html'>{}</a></h3>"
            "<p class='meta'>{} · {}</p><p>{}</p>"
            "<p><a href='functions/{}.html'>Read guide</a> · "
            "<a href='functions/{}.pdf'>PDF</a> · "
            "<a href='functions/{}.md'>Markdown</a></p></article>".format(
                html_escape(
                    " ".join(str(x) for x in (record.id, record.canonical_name, cue, description))
                ),
                html_escape(category),
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
    sections = "".join(
        f"<section class='category' data-category='{html_escape(category)}'><h2>{escape(category)}</h2><div class='grid'>"
        + "".join(cards)
        + "</div></section>"
        for category, cards in sorted(cards_by_category.items())
    )
    css = """
    :root{color-scheme:light dark;--bg:#f6f7f5;--fg:#172d38;--card:#fff;--accent:#2c6e72;--muted:#61747a}
    @media(prefers-color-scheme:dark){:root{--bg:#172027;--fg:#eef5f2;--card:#223039;--accent:#8bd0c8;--muted:#b4c7c4}}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,-apple-system,Segoe UI,sans-serif}
    main{max-width:1120px;margin:auto;padding:2rem 1rem 4rem}a{color:var(--accent)}.hero{padding:2rem 0 1rem}
    .hero h1{font-size:clamp(2rem,5vw,4rem);margin:.2rem 0}.meta{color:var(--muted);font-size:.92rem}
    input{width:100%;padding:.8rem 1rem;border:1px solid var(--muted);border-radius:.6rem;background:var(--card);color:var(--fg);font-size:1rem;margin:1rem 0 1.5rem}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:1rem}.card{background:var(--card);border-radius:.8rem;padding:1rem 1.1rem;box-shadow:0 2px 12px #0002}.card h3{font-size:1.2rem;margin:.1rem 0}.card p{margin:.45rem 0}.category{margin:2rem 0}
    @media print{input{display:none}.card{box-shadow:none;border:1px solid #ccc;break-inside:avoid}.grid{display:block}.card{margin:.5rem 0}}
    """
    js = """
    const q=document.querySelector('#search'),cards=[...document.querySelectorAll('.card')],groups=[...document.querySelectorAll('.category')],empty=document.querySelector('.no-results');
    q.addEventListener('input',()=>{const v=q.value.toLowerCase().trim();let n=0;cards.forEach(c=>{const ok=!v||c.dataset.search.toLowerCase().includes(v)||c.dataset.category.toLowerCase().includes(v);c.hidden=!ok;if(ok)n++});groups.forEach(g=>g.hidden=!g.querySelector('.card:not([hidden])'));empty.hidden=n>0});
    """
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>Open Consciousness Functions — Guide Collection v{escape(edition)}</title><style>{css}</style></head><body><main>"
        f"<header class='hero'><p class='meta'>Open Consciousness Functions · portable offline documentation · v{escape(edition)}</p>"
        "<h1>Function Guides</h1><p>Readable, self-contained guides for all implemented OCF functions. These documents are not listening approval or release authorization.</p>"
        "<p><a href='listening-guide.html'>General listening guide</a> · <a href='complete-guide.pdf'>Complete PDF handbook</a> · <a href='index.pdf'>PDF directory</a></p>"
        "<label for='search'>Search by title, ID, cue, or description</label><input id='search' type='search' placeholder='Search the 58 function guides'></header>"
        "<p class='no-results' hidden>No matching guides.</p>"
        + sections
        + f"<script>{js}</script></main></body></html>\n"
    ).encode("utf-8")


def validate_portable_collection(output):
    """Validate relocated Markdown, HTML/assets and PDF navigation without audio."""
    from pypdf import PdfReader

    output = Path(output).resolve()
    records = load_all_functions()
    directory = (output / "index.md").read_text(encoding="utf-8")
    references = re.findall(
        r"`(OCF-[A-Z]+-\d+)` · \[Complete handbook p\. (\d+)\]\(complete-guide.pdf#page=(\d+)\)",
        directory,
    )
    page_map = {}
    for identity, page, fragment in references:
        if page != fragment or identity in page_map:
            raise OCFError("Duplicate or inconsistent directory page reference")
        page_map[identity] = int(page)
    result = validate_handbook((output / "complete-guide.pdf").read_bytes(), records, page_map)
    checked = 0
    html_links = 0

    def check_link(path, target):
        nonlocal checked
        url = urlsplit(target)
        if url.scheme in {"http", "https", "mailto"}:
            return
        resolved = (path.parent / unquote(url.path)).resolve() if url.path else path
        if url.scheme or not resolved.is_relative_to(output) or not resolved.is_file():
            raise OCFError(f"Broken or nonportable link: {path.name}: {target}")
        if url.fragment and resolved.suffix == ".pdf":
            match = re.fullmatch(r"page=(\d+)", url.fragment)
            if not match or not 1 <= int(match[1]) <= len(PdfReader(resolved).pages):
                raise OCFError(f"Invalid PDF page link: {target}")
        checked += 1

    class Links(HTMLParser):
        def handle_starttag(self, tag, attrs):
            for name, value in attrs:
                if name in {"href", "src"} and value:
                    check_link(self.path, value)

    paths = sorted(path for path in output.rglob("*") if path.is_file())
    for path in paths:
        if path.suffix == ".md":
            for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
                check_link(path, target)
        elif path.suffix == ".html":
            parser = Links()
            parser.path = path
            before = checked
            parser.feed(path.read_text(encoding="utf-8"))
            html_links += checked - before
        elif path.suffix == ".pdf":
            reader = PdfReader(path, strict=True)

            def check_outlines(entries):
                for entry in entries:
                    if isinstance(entry, list):
                        check_outlines(entry)
                    else:
                        target = reader.get_destination_page_number(entry)
                        if target is None or not 0 <= target < len(reader.pages):
                            raise OCFError(f"Dangling PDF outline: {path.name}")

            check_outlines(reader.outline)
            if path.name == "index.pdf":
                text = " ".join(" ".join(page.extract_text().split()) for page in reader.pages)
                for record in records:
                    expected = f"{record.canonical_name} — {record.id} · Complete handbook p. {page_map[record.id]}"
                    if expected not in text:
                        raise OCFError(f"PDF directory reference mismatch: {record.id}")
            for page in reader.pages:
                for ref in page.get("/Annots", []):
                    annotation = ref.get_object()
                    action = annotation.get("/A", {})
                    if action.get("/S") == "/URI":
                        check_link(path, str(action["/URI"]))
                    destination = annotation.get("/Dest")
                    if action.get("/S") == "/GoTo":
                        destination = action.get("/D")
                    if destination is not None:
                        if isinstance(destination, str):
                            named = reader.named_destinations.get(destination)
                            target = reader.get_destination_page_number(named) if named else None
                        else:
                            target = reader.get_page_number(destination[0].get_object())
                        if target is None or not 0 <= target < len(reader.pages):
                            raise OCFError(f"Dangling PDF destination: {path.name}")
                        checked += 1
    result.update(
        files=len(paths),
        markdown=sum(path.suffix == ".md" for path in paths),
        html=sum(path.suffix == ".html" for path in paths),
        pdf=sum(path.suffix == ".pdf" for path in paths),
        checked_links=checked,
        html_links=html_links,
        broken_links=0,
    )
    return result


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
    for name, text in markdown.items():
        if name == "index.md":
            continue
        path = output / name
        write_bytes_atomic(path.with_suffix(".html"), html_bytes(text), overwrite=False)
        write_bytes_atomic(path.with_suffix(".pdf"), pdf_bytes(text), overwrite=False)
    handbook, page_map = complete_pdf_bytes(records, markdown)
    directory = _guide_catalog(records, page_map)
    write_text_atomic(output / "index.md", directory)
    write_bytes_atomic(output / "complete-guide.pdf", handbook, overwrite=False)
    write_bytes_atomic(
        output / "index.html", portable_index_html(records, edition=edition), overwrite=False
    )
    write_bytes_atomic(output / "index.pdf", pdf_bytes(directory), overwrite=False)
    validation = validate_portable_collection(output)
    if zip_path:
        zip_path = Path(zip_path).resolve()
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(output.rglob("*")):
                if path.is_file():
                    info = zipfile.ZipInfo(
                        path.relative_to(output).as_posix(), (1980, 1, 1, 0, 0, 0)
                    )
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o100644 << 16
                    archive.writestr(info, path.read_bytes())
    return {
        "functions": len(records),
        "files": len([p for p in output.rglob("*") if p.is_file()]),
        "output": str(output),
        "zip": str(zip_path) if zip_path else None,
        "validation": validation,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--portable-output", type=Path)
    parser.add_argument(
        "--validate-portable", type=Path, help="Verify an existing relocated collection"
    )
    parser.add_argument("--zip", type=Path, help="ZIP path for --portable-output")
    parser.add_argument("--check", action="store_true", help="Check freshness without writing")
    parser.add_argument("--markdown-only", action="store_true")
    args = parser.parse_args(argv)
    if args.validate_portable:
        try:
            result = validate_portable_collection(args.validate_portable)
        except (OCFError, OSError) as exc:
            parser.exit(1, f"{exc}\n")
        print(json.dumps(result, indent=2))
        return 0
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
