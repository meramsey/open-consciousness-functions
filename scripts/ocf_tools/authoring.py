"""Read-only, buffer-aware OCF authoring services shared by editor/CLI adapters.

Schema, command, locale and inheritance rules remain in their existing services.
This layer supplies source locations, contained I/O, indexing and adapter-neutral
diagnostics. It does not render audio, execute commands, apply renames or write
workspace files.
"""

from __future__ import annotations

import fnmatch
import json
import math
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace
from urllib.parse import unquote, urlparse

import yaml
from jsonschema import SchemaError
from jsonschema.validators import validator_for
from yaml.nodes import MappingNode, ScalarNode, SequenceNode

from . import validators
from .locale import LocaleCatalog
from .models import FunctionRecord
from .paths import SCHEMAS_DIR
from .utils import OCFError, yaml_safe_load

MAX_BYTES = 2 * 1024**2
MAX_NODES = 30000
MAX_DEPTH = 64
MAX_FILES = 1500
WORD = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.:/-]*")
SCHEMAS = {
    "function": "function.schema.json",
    "template": "session-template.schema.json",
    "pacing": "session-pacing.schema.json",
    "stage": "session-stage.schema.json",
    "dsp": "semantic-dsp-profile.schema.json",
    "voice": "voice-profile.schema.json",
    "background": "background-audio.schema.json",
    "implementation": "audio-implementation.schema.json",
    "theme": "theme.schema.json",
    "locale-key": "locale-resource.schema.json",
}
SOURCE_FOLDERS = (
    "functions",
    "function-content/bindings",
    "locales",
    "audio/templates/sessions",
    "audio/templates/pacing",
    "audio/templates/stages",
    "audio/background/state-profiles",
    "audio/background/manifests",
    "audio/voices/profiles",
    "audio/voices/registry",
    "audio/manifests",
    "audio/cues/profiles",
    "brand/themes",
    "audio/scripts",
    "audio/session-plans",
)


def uri_path(uri: str) -> Path:
    parsed = urlparse(uri)
    if (
        parsed.scheme != "file"
        or parsed.netloc not in ("", "localhost")
        or parsed.query
        or parsed.fragment
    ):
        raise OCFError("authoring requires a local file URI inside its workspace")
    raw = unquote(parsed.path)
    if "\0" in raw:
        raise OCFError("invalid file URI")
    if os.name == "nt" and re.match(r"^/[A-Za-z]:/", raw):
        raw = raw[1:]
    return Path(raw).resolve()


def path_key(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def offset_at(text: str, line: int, character: int, encoding="utf-16") -> int:
    lines = text.splitlines(keepends=True)
    if line < 0 or character < 0:
        raise OCFError("negative document position")
    if line >= len(lines):
        return len(text)
    prefix = sum(map(len, lines[:line]))
    raw = lines[line].rstrip("\r\n")
    if encoding == "utf-8":
        return prefix + len(raw.encode("utf-8")[:character].decode("utf-8", "ignore"))
    if encoding == "utf-32":
        return prefix + min(character, len(raw))
    return prefix + len(raw.encode("utf-16-le")[: character * 2].decode("utf-16-le", "ignore"))


def position_at(text: str, offset: int, encoding="utf-16") -> dict:
    offset = min(max(offset, 0), len(text))
    line = text.count("\n", 0, offset)
    start = text.rfind("\n", 0, offset) + 1
    prefix = text[start:offset]
    count = (
        len(prefix)
        if encoding == "utf-32"
        else len(prefix.encode("utf-8"))
        if encoding == "utf-8"
        else len(prefix.encode("utf-16-le")) // 2
    )
    return {"line": line, "character": count}


@dataclass(frozen=True)
class Span:
    path: tuple
    value: str
    start: int
    end: int
    key: bool = False


@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    severity: str = "error"
    start: int = 0
    end: int = 1
    pointer: str = ""

    def json(self, text, encoding="utf-16"):
        return {
            **asdict(self),
            "range": {
                "start": position_at(text, self.start, encoding),
                "end": position_at(text, self.end, encoding),
            },
        }


def _plain_data(data):
    stack = [(data, 0, frozenset())]
    count = 0
    while stack:
        value, depth, ancestors = stack.pop()
        count += 1
        if count > MAX_NODES or depth > MAX_DEPTH:
            raise OCFError("document/alias expansion exceeds bounded authoring complexity")
        if isinstance(value, (dict, list)):
            if id(value) in ancestors:
                raise OCFError("cyclic YAML aliases cannot be validated as OCF JSON-shaped data")
            ancestors = ancestors | {id(value)}
            if isinstance(value, dict):
                if any(not isinstance(key, str) for key in value):
                    raise OCFError("OCF mapping keys must be strings")
                children = value.values()
            else:
                children = value
            stack.extend((child, depth + 1, ancestors) for child in children)
        elif isinstance(value, float) and not math.isfinite(value):
            raise OCFError("non-finite numbers are not valid OCF configuration")
        elif value is not None and not isinstance(value, (str, int, float, bool)):
            raise OCFError("OCF values must be JSON-compatible; quote dates and binary-like values")


class Document:
    def __init__(self, path: Path, text: str):
        self.path, self.text = path, text
        self.data = None
        self.spans = []
        self.diagnostics = []
        if len(text.encode("utf-8")) > MAX_BYTES:
            self.diagnostics.append(
                Diagnostic("ocf.document-size", "document exceeds 2 MiB authoring limit")
            )
            return
        try:
            # Bound the representation graph (including repeated merge aliases)
            # before PyYAML constructs/expands mappings.
            tree = yaml.compose(text, Loader=yaml.SafeLoader)
            self._spans(tree)
            if path.suffix.lower() == ".json":
                self.data = json.loads(
                    text,
                    parse_constant=lambda value: (_ for _ in ()).throw(
                        ValueError("non-finite JSON: " + value)
                    ),
                )
            else:
                self.data = yaml_safe_load(text)
            _plain_data(self.data)
        except (yaml.YAMLError, ValueError, OCFError, RecursionError) as exc:
            mark = getattr(exc, "problem_mark", None)
            at = getattr(mark, "index", getattr(exc, "pos", 0))
            message = getattr(exc, "problem", None) or str(exc)
            self.diagnostics.append(
                Diagnostic("ocf.parse", str(message)[:1000], start=at, end=min(at + 1, len(text)))
            )
            self.data = None

    def _spans(self, tree):
        stack = [(tree, (), 0, frozenset())]
        count = 0
        while stack:
            node, path, depth, ancestors = stack.pop()
            if node is None:
                continue
            count += 1
            if count > MAX_NODES or depth > MAX_DEPTH or id(node) in ancestors:
                raise OCFError("source structure exceeds authoring complexity limit")
            ancestors = ancestors | {id(node)}
            if isinstance(node, ScalarNode):
                start, end = node.start_mark.index, node.end_mark.index
                if node.style in ("'", '"'):
                    start, end = start + 1, max(start + 1, end - 1)
                self.spans.append(Span(path, node.value, start, end))
            elif isinstance(node, MappingNode):
                seen = set()
                for key, value in reversed(node.value):
                    if not isinstance(key, ScalarNode):
                        continue
                    child = (*path, key.value)
                    self.spans.append(
                        Span(
                            child,
                            key.value,
                            key.start_mark.index + (key.style in ("'", '"')),
                            key.end_mark.index - (key.style in ("'", '"')),
                            True,
                        )
                    )
                    if key.value in seen:
                        self.diagnostics.append(
                            Diagnostic(
                                "ocf.duplicate-key",
                                f"duplicate mapping key {key.value!r}",
                                start=key.start_mark.index,
                                end=key.end_mark.index,
                            )
                        )
                    seen.add(key.value)
                    stack.append((value, child, depth + 1, ancestors))
            elif isinstance(node, SequenceNode):
                stack.extend(
                    (child, (*path, index), depth + 1, ancestors)
                    for index, child in enumerate(node.value)
                )
        self.spans.sort(key=lambda span: (span.start, span.end))

    def span(self, path, *, key=False):
        while path:
            found = next(
                (item for item in self.spans if item.path == tuple(path) and item.key == key), None
            )
            if found:
                return found
            if not key:
                found = next(
                    (item for item in self.spans if item.path == tuple(path) and item.key), None
                )
                if found:
                    return found
            path = path[:-1]
        return Span((), "", 0, min(1, len(self.text)))

    def at(self, offset):
        return next((span for span in self.spans if span.start <= offset <= span.end), None)


def schema_name(path: Path, data, root: Path, associations=None):
    relative = path.relative_to(root).as_posix()
    for pattern, name in (associations or {}).items():
        if fnmatch.fnmatch(relative, pattern):
            if name not in {file.name for file in SCHEMAS_DIR.glob("*.schema.json")}:
                raise OCFError("schema associations must name a registered local OCF schema")
            return name
    routes = {
        "functions/": "function.schema.json",
        "function-content/bindings/": "function-binding.schema.json",
        "function-content/evidence/": "function-evidence.schema.json",
        "function-content/specifications/": "function-specification.schema.json",
        "function-content/decisions/": "function-decisions.schema.json",
        "audio/templates/sessions/": "session-template.schema.json",
        "audio/templates/pacing/": "session-pacing.schema.json",
        "audio/templates/stages/": "session-stage.schema.json",
        "audio/background/state-profiles/": "semantic-dsp-profile.schema.json",
        "audio/background/manifests/": "background-audio.schema.json",
        "audio/voices/profiles/": "voice-profile.schema.json",
        ".ocf-work/cache/voices/profiles/": "voice-profile.schema.json",
        "audio/voices/registry/": "community-voice.schema.json",
        "audio/manifests/": "audio-implementation.schema.json",
        "audio/scripts/": "timed-transcript.schema.json",
        "audio/session-plans/": "session-plan.schema.json",
        "audio/cues/profiles/": "cue-profile.schema.json",
        "brand/themes/": "theme.schema.json",
    }
    route_path = relative.casefold() if os.name == "nt" else relative
    if route_path.startswith("schemas/") and path.name.endswith(".schema.json"):
        return "json-schema"
    if route_path.startswith("audio/session-plans/") and path.name == "_shared.json":
        return None  # Generator metadata, not a per-function declaration.
    if route_path.startswith("locales/"):
        return (
            "locale-manifest.schema.json"
            if path.name == "manifest.yaml"
            else "locale-resource.schema.json"
        )
    for prefix, name in routes.items():
        if route_path.startswith(prefix):
            return name
    if not isinstance(data, dict):
        return None
    if data.get("$schema"):
        for file in SCHEMAS_DIR.glob("*.schema.json"):
            if validators._load_schema(file.name).get("$id") == data["$schema"]:
                return file.name
        raise OCFError("unknown schema URI; OCF authoring never fetches remote schemas")
    if {"canonical", "legacy"} <= data.keys():
        return "function.schema.json"
    if {"locale", "entries", "domain"} <= data.keys():
        return "locale-resource.schema.json"
    if {"locale", "resources", "language_name"} <= data.keys():
        return "locale-manifest.schema.json"
    if data.get("schema_version") == "2.0" and "mode" in data:
        return "narration-sources.schema.json"
    if {"recordings", "source_type"} <= data.keys():
        return "narration-package.schema.json"
    if "records" in data and "speaker" in data:
        return "voice-dataset.schema.json"
    if "palette" in data or (
        isinstance(data.get("extends"), str)
        and data["extends"].startswith("ocf-")
        and path.suffix == ".json"
    ):
        return "theme.schema.json"
    if "slots" in data and "sections" in data:
        return "session-template.schema.json"
    if "timeline" in data or ("sections" in data and "source" in data):
        return "timed-transcript.schema.json"
    if "narration_plan" in data or "default_session_template" in data:
        return "function-binding.schema.json"
    if any(key in data for key in ("output_headroom_db", "background_ducking", "limiter")):
        return "mix-profile.schema.json"
    return SCHEMAS.get(identifier_kind(str(data.get("id", ""))))


def identifier_kind(identifier):
    for prefix, kind in (
        ("OCF-CMD-", "command"),
        ("OCF-TPL-SESSION-", "template"),
        ("OCF-TPL-STAGE-", "stage"),
        ("OCF-PACING-", "pacing"),
        ("OCF-DSP-", "dsp"),
        ("OCF-VOICE-", "voice"),
        ("OCF-BG-", "background"),
        ("OCF-AUDIO-", "implementation"),
    ):
        if identifier.startswith(prefix):
            return kind
    return "function" if re.fullmatch(r"OCF-[A-Z]{3}-[0-9]{3}", identifier) else None


def reference_kind(span: Span, schema):
    path = span.path
    field = next((part for part in reversed(path) if isinstance(part, str)), "")
    if span.key:
        if len(path) > 1 and path[-2] == "entries" and schema == "session-pacing.schema.json":
            return "narration"
        return "function" if len(path) > 1 and path[-2] == "functions" else None
    if field in {"function_id", "incompatible_functions", "companions"}:
        return "function"
    if field in {
        "narration_key",
        "spoken_cue_key",
        "narration_resources",
        "evidence_keys",
        "source_narration_key",
        "source_narration_keys",
    } or (field == "key" and schema == "function-binding.schema.json"):
        return "narration"
    if field in {
        "title_key",
        "short_description_key",
        "purpose_key",
        "effect_key",
        "localization_key",
        "label_key",
        "display_cue_key",
        "usage_key",
        "explanation_key",
    }:
        return "locale-key"
    if field in {"session_templates", "default_session_template", "template"}:
        return "template"
    if field == "pacing_profile":
        return "pacing"
    if field in {"dsp_profile", "semantic_dsp_profile"}:
        return "dsp"
    if field in {"voice_profile", "default_voice", "voice"} or (
        field == "profile" and "voice" in path
    ):
        return "voice"
    if field in {"stage_template", "stage"}:
        return "stage"
    if field in {"artwork_theme"}:
        return "theme"
    if field == "extends":
        return next((kind for kind, name in SCHEMAS.items() if name == schema), None)
    if field == "preset":
        return "background"
    if field == "locale":
        return "locale"
    if field in {"command_id", "mode_ids", "command_ids"}:
        return "command"
    return None


@dataclass(frozen=True)
class Definition:
    name: str
    kind: str
    path: Path
    span: Span
    description: str
    locale: str | None = None


def schema_at(schema, path):
    """Read registered schema properties for completion; never validate or fetch."""
    root = schema
    node = schema
    for _depth in range(32):
        if not isinstance(node, dict):
            return {}
        if "$ref" in node:
            reference = node["$ref"]
            base, _separator, fragment = reference.partition("#")
            if base:
                name = base.rsplit("/", 1)[-1]
                if name not in {item.name for item in SCHEMAS_DIR.glob("*.schema.json")}:
                    return {}
                root = validators._load_schema(name)
            node = root
            for part in fragment.lstrip("/").split("/") if fragment else []:
                node = node.get(part.replace("~1", "/").replace("~0", "~"), {})
            continue
        if not path:
            return node
        part, path = path[0], path[1:]
        node = (
            node.get("items", {})
            if isinstance(part, int)
            else node.get("properties", {}).get(part, node.get("additionalProperties", {}))
        )
    return {}


class AuthoringService:
    def __init__(self, root: Path, *, associations=None):
        self.root = root.resolve()
        self.associations = associations or {}
        self.overlays = {}
        self._cache = {}
        self._signature = None
        self.documents = {}
        self.definitions = {}
        self._literal_sources = {}
        self.refreshes = 0
        self.last_index_seconds = 0.0
        self._catalog_cache = None

    def contained(self, path: Path):
        path = path.resolve()
        if not path.is_relative_to(self.root):
            raise OCFError("document/reference escapes the selected workspace")
        return path

    def path(self, uri):
        return self.contained(uri_path(uri))

    def update(self, uri, text):
        path = self.path(uri)
        previous = self.overlays.get(path_key(path))
        if previous is not None and previous[1] == text:
            return
        if previous is None and len(self.overlays) >= 100:
            raise OCFError("authoring is bounded to 100 open buffers per workspace")
        self.overlays[path_key(path)] = (path, text)
        self._signature = None

    def close(self, uri):
        path = self.path(uri)
        self.overlays.pop(path_key(path), None)
        self._cache.pop(path_key(path), None)
        self._signature = None

    def document(self, path):
        path = self.contained(path)
        key = path_key(path)
        if key in self.overlays:
            text = self.overlays[key][1]
            stamp = ("buffer", text)
        else:
            if path.stat().st_size > MAX_BYTES:
                raise OCFError("document exceeds 2 MiB authoring limit")
            stamp = (path.stat().st_mtime_ns, path.stat().st_size)
            text = None
        previous = self._cache.get(key)
        if previous and previous[0] == stamp:
            return previous[1]
        text = text if text is not None else path.read_text(encoding="utf-8")
        doc = Document(path, text)
        self._cache[key] = (stamp, doc)
        return doc

    def _files(self):
        files = set()
        for folder in SOURCE_FOLDERS:
            directory = self.root / folder
            files.update(
                path
                for path in directory.rglob("*")
                if path.suffix.lower() in {".yaml", ".yml", ".json"}
                and path.is_file()
                and path.resolve().is_relative_to(self.root)
            )
        private = self.root / ".ocf-work/cache/voices/profiles"
        files.update(
            path
            for path in private.glob("*.yaml")
            if path.is_file() and path.resolve().is_relative_to(self.root)
        )
        # Literal reference navigation only: no importing or executing these sources.
        for directory in (
            self.root / "scripts/ocf_tools",
            self.root / "scripts/tools",
            self.root / "tests",
        ):
            files.update(
                path
                for path in directory.glob("*.py")
                if path.is_file() and path.resolve().is_relative_to(self.root)
            )
        files.update(
            path
            for path, _text in self.overlays.values()
            if path.suffix.lower() in {".json", ".yaml", ".yml"}
        )
        if len(files) > MAX_FILES:
            raise OCFError("workspace exceeds 1500-file bounded authoring index")
        return sorted(files)

    def refresh(self):
        files = self._files()
        signature = tuple(
            (
                path_key(path),
                ("buffer", self.overlays[path_key(path)][1])
                if path_key(path) in self.overlays
                else (path.stat().st_mtime_ns, path.stat().st_size),
            )
            for path in files
        )
        if signature == self._signature:
            return
        start = perf_counter()
        documents, definitions, literals = {}, {}, {}
        for path in files:
            try:
                if path.suffix == ".py":
                    if path.stat().st_size <= MAX_BYTES:
                        literals[path] = path.read_text(encoding="utf-8")
                    continue
                doc = self.document(path)
                if not isinstance(doc.data, dict):
                    continue
                documents[path_key(path)] = doc
                name = schema_name(path, doc.data, self.root, self.associations)
                kind = next((kind for kind, schema in SCHEMAS.items() if schema == name), None)
                identifier = doc.data.get("id")
                if identifier and kind not in (None, "locale-key"):
                    description = (
                        doc.data.get("name")
                        or doc.data.get("title")
                        or doc.data.get("canonical", {}).get("name")
                        or str(identifier)
                    )
                    if kind == "function":
                        description += (
                            "\nCommand: "
                            + str(doc.data.get("canonical", {}).get("command", {}).get("primary"))
                            + "\n"
                            + str(doc.data.get("purpose", {}).get("summary", ""))
                        )
                    definitions.setdefault(str(identifier), []).append(
                        Definition(
                            str(identifier), kind, path, doc.span(("id",)), str(description)[:600]
                        )
                    )
                if name == "locale-resource.schema.json":
                    locale = str(doc.data.get("locale", ""))
                    for key, entry in (doc.data.get("entries") or {}).items():
                        description = (
                            entry
                            if isinstance(entry, str)
                            else entry.get("text", "")
                            if isinstance(entry, dict)
                            else ""
                        )
                        entry_kind = (
                            "narration" if doc.data.get("domain") == "narration" else "locale-key"
                        )
                        definitions.setdefault(key, []).append(
                            Definition(
                                key,
                                entry_kind,
                                path,
                                doc.span(("entries", key), key=True),
                                str(description)[:240],
                                locale,
                            )
                        )
                if name == "locale-manifest.schema.json" and doc.data.get("locale"):
                    locale = str(doc.data["locale"])
                    definitions.setdefault(locale, []).append(
                        Definition(
                            locale,
                            "locale",
                            path,
                            doc.span(("locale",)),
                            str(doc.data.get("language_name", locale)),
                            locale,
                        )
                    )
                for index, command in enumerate(
                    doc.data.get("commands", []) if name == "function.schema.json" else []
                ):
                    if isinstance(command, dict) and command.get("id"):
                        key = command["id"]
                        definitions.setdefault(key, []).append(
                            Definition(
                                key,
                                "command",
                                path,
                                doc.span(("commands", index, "id")),
                                f"{command.get('role')} / {command.get('designation')} — phrase remains in its canonical owner",
                            )
                        )
            except (OSError, UnicodeError, OCFError, AttributeError, TypeError, ValueError):
                continue
        self.documents, self.definitions, self._literal_sources = documents, definitions, literals
        live = {path_key(path) for path in files} | set(self.overlays)
        self._cache = {key: value for key, value in self._cache.items() if key in live}
        self._signature = signature
        self.refreshes += 1
        self.last_index_seconds = perf_counter() - start

    def lookup(self, kind, reference):
        self.refresh()
        definitions = [item for item in self.definitions.get(reference, []) if item.kind == kind]
        if definitions:
            return definitions[0].path
        path = Path(reference).expanduser()
        return self.contained(path if path.is_absolute() else self.root / path)

    def _reader(self):
        count = 0

        def read(path):
            nonlocal count
            count += 1
            if count > 32:
                raise OCFError("inheritance exceeds bounded 32-read authoring budget")
            doc = self.document(path)
            if doc.diagnostics or not isinstance(doc.data, dict):
                raise OCFError("inherited document is malformed or not an object")
            return doc.data

        return read

    def catalog(self):
        self.refresh()
        if self._catalog_cache and self._catalog_cache[0] == self._signature:
            return self._catalog_cache[1]
        locale_root = self.root / "locales"
        directories = {
            doc.path.parent
            for doc in self.documents.values()
            if doc.path.name == "manifest.yaml" and doc.path.parent.parent == locale_root
        }

        def exists(path):
            path = self.contained(path)
            return path_key(path) in self.overlays or path.is_file()

        # Reuse the pack loader's domain, filename, key, locale and duplicate rules.
        # The bounded index already limits the number and size of source documents.
        def reader(path):
            doc = self.document(path)
            if doc.diagnostics or not isinstance(doc.data, dict):
                raise OCFError("locale document is malformed or not an object")
            return doc.data

        catalog = LocaleCatalog(
            locale_root,
            reader=reader,
            exists=exists,
            directories=directories,
            function_records=self.records,
        )
        self._catalog_cache = (self._signature, catalog)
        return catalog

    def records(self):
        self.refresh()
        result = []
        for doc in self.documents.values():
            data = doc.data
            if schema_name(doc.path, data, self.root, self.associations) != "function.schema.json":
                continue
            canonical = data.get("canonical")
            lifecycle = data.get("lifecycle", {})
            if (
                not isinstance(canonical, dict)
                or not isinstance(canonical.get("command"), dict)
                or not isinstance(lifecycle, dict)
                or not isinstance(lifecycle.get("release", {}), dict)
            ):
                continue
            result.append(
                FunctionRecord(str(data.get("id", "")), str(data.get("slug", "")), doc.path, data)
            )
        return result

    def analyze(self, uri):
        path = self.path(uri)
        doc = self.document(path)
        diagnostics = list(doc.diagnostics)
        if path.relative_to(self.root).as_posix().startswith("audio/session-plans/"):
            diagnostics.append(
                Diagnostic(
                    "ocf.generated-document",
                    "Generated plan: use audio plan to regenerate; editor never rewrites it",
                    "info",
                )
            )
        if doc.diagnostics:
            return diagnostics
        try:
            schema = schema_name(path, doc.data, self.root, self.associations)
            if schema is None:
                return diagnostics
            if schema == "json-schema":
                validator_for(doc.data).check_schema(doc.data)
                return diagnostics
            data = doc.data
            reader = self._reader()
            if schema == "theme.schema.json":
                from .artwork import load_theme

                data = load_theme(str(path), reader=reader, lookup=self.lookup)
            elif schema in {"session-template.schema.json", "session-pacing.schema.json"}:
                from .session import load_pacing_profile, load_template

                loader = (
                    load_template
                    if schema == "session-template.schema.json"
                    else load_pacing_profile
                )
                data = loader(str(path), reader=reader, lookup=self.lookup)
            errors = validators.schema_errors(data, validators._load_schema(schema))
            for error in errors[:100]:
                span = doc.span(tuple(error.path))
                pointer = "/" + "/".join(
                    str(part).replace("~", "~0").replace("/", "~1") for part in error.path
                )
                diagnostics.append(
                    Diagnostic(
                        "ocf.schema." + str(error.validator),
                        error.message[:1500],
                        start=span.start,
                        end=span.end,
                        pointer=pointer,
                    )
                )
            if errors or not isinstance(data, dict):
                return diagnostics
            if schema == "session-template.schema.json":
                from .session import _pacing_value, load_pacing_profile

                pacing = (
                    load_pacing_profile(data["pacing_profile"], reader=reader, lookup=self.lookup)
                    if data.get("pacing_profile")
                    else None
                )
                for span in doc.spans:
                    if (
                        not span.key
                        and span.path
                        and (
                            span.path[-1] == "pacing_key"
                            or str(span.path[-1]).endswith("_pacing_key")
                        )
                    ):
                        try:
                            _pacing_value(
                                pacing,
                                span.value,
                                allow_negative=span.path[-1] == "gain_db_pacing_key",
                            )
                        except OCFError as exc:
                            diagnostics.append(
                                Diagnostic(
                                    "ocf.pacing-reference", str(exc), start=span.start, end=span.end
                                )
                            )
            if schema in {"locale-manifest.schema.json", "locale-resource.schema.json"}:
                diagnostics.extend(
                    Diagnostic("ocf.locale-pack", problem) for problem in self.catalog().problems
                )
                if schema == "locale-resource.schema.json":
                    for key, entry in data.get("entries", {}).items():
                        if not isinstance(entry, dict) or not entry.get("cue_template"):
                            continue
                        span = doc.span(("entries", key, "text"))
                        try:
                            self.catalog().resource(
                                key, data["locale"], domain=data["domain"], fallback=False
                            )
                        except OCFError as exc:
                            diagnostics.append(
                                Diagnostic(
                                    "ocf.cue-template", str(exc), start=span.start, end=span.end
                                )
                            )
            if schema == "function.schema.json":
                record = FunctionRecord(str(data["id"]), str(data["slug"]), path, data)
                result = validators.validate_command_rules(record)
                diagnostics.extend(
                    Diagnostic(issue.code, issue.message, issue.severity) for issue in result.issues
                )
                from .commands import localized_cue, validate_command_records
                from .lifecycle import validate_scope_descriptions

                diagnostics.extend(
                    Diagnostic("ocf.cue-authority", error)
                    for error in validate_command_records(record)
                )
                diagnostics.extend(
                    Diagnostic("ocf.lifecycle-authority", error)
                    for error in validate_scope_descriptions(record, self.catalog())
                )

                for command in record.command_records:
                    if command.data.get("spoken") is not None:
                        try:
                            localized_cue(
                                record, command, "en-US", catalog=self.catalog(), strict=True
                            )
                        except OCFError as exc:
                            diagnostics.append(Diagnostic("ocf.cue-authority", str(exc)))
            if schema == "timed-transcript.schema.json":
                result = validators.validate_timed_transcript(
                    data, path, self.catalog(), self.records()
                )
                for issue in result.issues:
                    if issue.code == "timed-schema":
                        continue
                    span = next(
                        (
                            item
                            for item in doc.spans
                            if item.value and repr(item.value) in issue.message
                        ),
                        Span((), "", 0, 1),
                    )
                    diagnostics.append(
                        Diagnostic(issue.code, issue.message, issue.severity, span.start, span.end)
                    )
            self.refresh()
            for span in doc.spans:
                kind = reference_kind(span, schema)
                if (
                    not kind
                    or span.value in ("", "null", "~")
                    or kind == "locale"
                    and schema == "locale-manifest.schema.json"
                ):
                    continue
                if schema == "timed-transcript.schema.json" and kind == "narration":
                    continue  # Existing strict locale validator is authoritative here.
                if span.path[-1] == "extends":
                    continue  # The existing inheritance loader already validates it.
                if kind == "locale":
                    # Requested regional locales can resolve through an installed
                    # same-language parent. Pack identities are checked by load_pack.
                    self.catalog().spoken_chain(span.value)
                    continue
                matches = [
                    item
                    for item in self.definitions.get(span.value, [])
                    if item.kind == kind or kind == "locale-key" and item.kind == "narration"
                ]
                if not matches:
                    diagnostics.append(
                        Diagnostic(
                            "ocf.unknown-reference",
                            f"unknown {kind} identifier {span.value!r}"
                            + (
                                "; external/private voice metadata may require local setup"
                                if kind == "voice"
                                else ""
                            ),
                            "warning" if kind == "voice" else "error",
                            span.start,
                            span.end,
                        )
                    )
        except (OCFError, SchemaError, OSError, ValueError, TypeError, RecursionError) as exc:
            diagnostics.append(Diagnostic("ocf.configuration", str(exc)[:1500]))
        return diagnostics[:100]

    def context(self, uri, offset):
        doc = self.document(self.path(uri))
        span = doc.at(offset)
        if span and len(span.path) >= 3 and span.path[0] == "entries" and span.path[-1] == "text":
            for match in re.finditer(
                r"(?<!\\)\{\{\s*([A-Za-z0-9_.-]*)", doc.text[span.start : span.end]
            ):
                start = span.start + match.start(1)
                end = span.start + match.end(1)
                if start <= offset <= end:
                    return doc, Span((*span.path, "$cue"), match.group(1), start, end)
        if span and (span.value or span.start == span.end):
            return doc, span
        line_start = doc.text.rfind("\n", 0, offset) + 1
        prefix = doc.text[line_start:offset]
        match = re.search(
            r'["\']?([A-Za-z_][A-Za-z0-9_-]*)["\']?\s*:\s*["\']?([A-Za-z0-9_.:/-]*)$', prefix
        )
        if match:
            return doc, Span(
                (match.group(1),), match.group(2), offset - len(match.group(2)), offset
            )
        match = next(
            (item for item in WORD.finditer(doc.text) if item.start() <= offset <= item.end()), None
        )
        return doc, Span(
            (),
            match.group() if match else "",
            match.start() if match else offset,
            match.end() if match else offset,
            True,
        )

    def completions(self, uri, offset):
        doc, span = self.context(uri, offset)
        self.refresh()
        if span.path and span.path[-1] == "$cue":
            from .cue_templates import choices

            entry = doc.data["entries"][span.path[1]]
            owner_id = entry.get("cue_template", {}).get("function_id")
            owner = next((record for record in self.records() if record.id == owner_id), None)
            rows = (
                [
                    {
                        "label": symbol,
                        "kind": "cue-symbol",
                        "description": "Strict complete reviewed cue from function YAML/localized binding",
                    }
                    for symbol in choices(owner)
                    if symbol.startswith(span.value)
                ]
                if owner
                else []
            )
            return doc, span, rows
        name = schema_name(doc.path, doc.data, self.root, self.associations)
        kind = reference_kind(span, name)
        prefix = doc.text[span.start : offset]
        if kind:
            rows = [
                {"label": key, "kind": item.kind, "description": item.description}
                for key, values in self.definitions.items()
                for item in values[:1]
                if item.kind == kind and key.casefold().startswith(prefix.casefold())
            ]
        else:
            schema = validators._load_schema(name) if name and name != "json-schema" else {}
            properties = schema_at(schema, span.path[:-1]).get("properties", {})
            field_schema = schema_at(schema, span.path)
            if not span.key and "enum" in field_schema:
                rows = [
                    {
                        "label": str(value),
                        "kind": "value",
                        "description": field_schema.get("description", ""),
                        "value": value,
                    }
                    for value in field_schema["enum"]
                    if str(value).casefold().startswith(prefix.casefold())
                ]
            else:
                rows = [
                    {"label": key, "kind": "property", "description": value.get("description", "")}
                    for key, value in properties.items()
                    if key.casefold().startswith(prefix.casefold())
                ]
        unique = {row["label"]: row for row in rows}
        return doc, span, [unique[key] for key in sorted(unique)[:1000]]

    def definitions_at(self, uri, offset):
        doc, span = self.context(uri, offset)
        self.refresh()
        if span.path and span.path[-1] == "$cue":
            from .cue_templates import select_command, value

            entry = doc.data["entries"][span.path[1]]
            owner_id = entry.get("cue_template", {}).get("function_id")
            owner = next((record for record in self.records() if record.id == owner_id), None)
            if owner is None:
                return doc, span, []
            try:
                text, _ = value(owner, span.value, doc.data["locale"], self.catalog())
                target = self.document(owner.path)
                if span.value == "function.title":
                    target_span = target.span(("canonical", "name"))
                else:
                    command = select_command(owner, span.value)
                    index = next(
                        i for i, row in enumerate(owner.data["commands"]) if row["id"] == command.id
                    )
                    target_span = target.span(("commands", index, "spoken"))
                    if ".variant." in span.value:
                        variant = span.value.split(".variant.", 1)[1]
                        if variant in command.data.get("spoken_variants", {}):
                            target_span = target.span(
                                ("commands", index, "spoken_variants", variant, "text")
                            )
                        else:
                            target_span = target.span(
                                ("commands", index, "localization", "spoken_variant_keys", variant)
                            )
                return (
                    doc,
                    span,
                    [
                        Definition(
                            span.value,
                            "cue-symbol",
                            owner.path,
                            target_span,
                            f"{owner.id}: {text} ({doc.data['locale']}; explicit reviewed cue)",
                        )
                    ],
                )
            except OCFError:
                return doc, span, []
        definitions = self.definitions.get(span.value, [])
        if not definitions and span.path and span.path[-1] in {"after", "event_id"}:
            definitions = [
                Definition(
                    span.value,
                    "local-event",
                    doc.path,
                    item,
                    "Local event identity; composed recording-marker migrations require separate review",
                )
                for item in doc.spans
                if item.value == span.value and item.path and item.path[-1] == "id" and not item.key
            ]
        if not definitions and span.path and span.path[-1] == "extends":
            name = schema_name(doc.path, doc.data, self.root, self.associations)
            kind = reference_kind(span, name)
            reference = (
                str(doc.path.parent / span.value)
                if kind == "theme" and Path(span.value).suffix == ".json"
                else span.value
            )
            try:
                parent = self.document(self.lookup(kind, reference))
                definitions = [
                    Definition(
                        str((parent.data or {}).get("id", span.value)),
                        kind or "configuration",
                        parent.path,
                        parent.span(("id",)),
                        "Inherited configuration",
                    )
                ]
            except (OCFError, OSError, AttributeError):
                pass
        locale = doc.data.get("locale") if isinstance(doc.data, dict) else None
        exact = [item for item in definitions if item.locale == locale] if locale else []
        return doc, span, exact or definitions

    def references(self, identifier, *, include_declarations=True):
        self.refresh()
        rows = []
        for doc in self.documents.values():
            for span in doc.spans:
                if span.value == identifier:
                    declaration = any(
                        item.path == doc.path and item.span == span
                        for item in self.definitions.get(identifier, [])
                    )
                    if include_declarations or not declaration:
                        rows.append((doc, span))
        pattern = re.compile(r"(?<![\w.-])" + re.escape(identifier) + r"(?![\w.-])")
        for path, text in self._literal_sources.items():
            for match in pattern.finditer(text):
                # No Python evaluation; only literal source navigation locations.
                rows.append(
                    (
                        SimpleNamespace(path=path, text=text),
                        Span((), identifier, match.start(), match.end()),
                    )
                )
        return rows

    def rename_preview(self, uri, position, proposed, *, offset=0, limit=200):
        _doc, span, definitions = self.definitions_at(uri, position)
        if not definitions:
            raise OCFError("identifier has no workspace definition")
        if any(item.kind == "local-event" for item in definitions):
            raise OCFError(
                "local/composed event migrations require composition-aware recording-marker review; automatic rename remains disabled"
            )
        if (
            not isinstance(proposed, str)
            or not proposed.strip()
            or len(proposed) > 200
            or any(ord(character) < 32 for character in proposed)
        ):
            raise OCFError("proposed name must be bounded printable text")
        if type(offset) is not int or type(limit) is not int or offset < 0 or not 1 <= limit <= 500:
            raise OCFError("preview pagination requires offset>=0 and limit 1..500")
        refs = self.references(span.value)
        return {
            "status": "PROPOSED — NOT IMPLEMENTED",
            "read_only": True,
            "old": span.value,
            "proposed": proposed,
            "automatic_rename": False,
            "reason": "Editorial/stable-ID changes require explicit human approval; no WorkspaceEdit or filesystem operation is produced",
            "collision": proposed in self.definitions,
            "total_references": len(refs),
            "next_offset": offset + limit if offset + limit < len(refs) else None,
            "references": [
                {"uri": doc.path.as_uri(), "start": item.start, "end": item.end}
                for doc, item in refs[offset : offset + limit]
            ],
            "reference_scope": "contained indexed configurations and literal Python references; dynamic constructors are not evaluated",
        }
