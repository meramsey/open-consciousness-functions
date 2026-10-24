"""Copy-only private bundles and shared, edition-independent guide attachment."""

from __future__ import annotations

import argparse
import json
import shutil
import unicodedata
from pathlib import Path, PureWindowsPath

from .artwork_content import function_artwork_content
from .audition_exports import _artifact, _source_artifact, _verify_export_identity
from .indexes import load_function_by_id
from .listening_guides import function_markdown, html_bytes, pdf_bytes
from .paths import (
    REPO_ROOT,
    publish_workspace_temp_directory,
    record_workspace_failure,
    work_root,
    workspace_temp_directory,
)
from .utils import OCFError, read_json_object, sha256_of_file, write_bytes_atomic, write_text_atomic


def _portable(value):
    if isinstance(value, dict):
        for item in value.values():
            _portable(item)
    elif isinstance(value, list):
        for item in value:
            _portable(item)
    elif isinstance(value, str) and (Path(value).is_absolute() or PureWindowsPath(value).drive):
        raise OCFError("absolute filesystem path in portable metadata")


def _filename_key(name):
    return unicodedata.normalize("NFC", name).casefold()


def _session_items(manifest):
    if (
        manifest.get("kind") != "private-audition-export"
        or manifest.get("publication_approval") is not False
    ):
        raise OCFError("only explicitly private audition exports can enter this bundle")
    _portable(manifest)
    _verify_export_identity(manifest, manifest.get("edition", {}))
    if manifest.get("locale") != "en-US":
        raise OCFError("conflicting edition/function/locale identity")
    text = manifest.get("listener_text") or {}
    if not all(fmt in text.get("artifacts", {}) for fmt in ("txt", "lrc", "srt", "vtt")):
        raise OCFError("missing measured listener transcripts")
    if not manifest.get("cover") or not text.get("timing_receipt"):
        raise OCFError("missing cover or timing provenance")
    return [manifest["artifacts"][fmt] for fmt in ("flac", "mp3")] + [
        manifest["cover"],
        *text["artifacts"].values(),
        text["timing_receipt"],
    ]


def attach_guides(stage: Path, function_ids, *, source: Path | None = None, locale="en-US"):
    """Attach only selected guides; cached bytes must match current authoritative content."""
    if locale != "en-US":
        raise OCFError(
            "listener guides currently support en-US only; no silent translation fallback"
        )
    documents = {
        "listening-guide.md": (REPO_ROOT / "docs/LISTENING_GUIDE.md").read_text(encoding="utf-8")
    }
    index = ["# Included function guides", "", "[General listening guide](listening-guide.md)", ""]
    for fid in sorted(set(function_ids)):
        record = load_function_by_id(fid)
        if record is None:
            raise OCFError(f"unknown guide function: {fid}")
        name = f"functions/{fid}.md"
        documents[name] = function_markdown(
            record, function_artwork_content(fid, locale, strict=False)
        )
        index.append(f"- [{fid}]({name})")
    artifacts = []
    for name, text in {**documents, "index.md": "\n".join(index) + "\n"}.items():
        for suffix, data in (
            (".md", text.encode("utf-8")),
            (".html", html_bytes(text)),
            (".pdf", pdf_bytes(text)),
        ):
            relative = Path(name).with_suffix(suffix)
            if source is not None and name != "index.md":
                cached = source / relative
                if not cached.is_file() or cached.read_bytes() != data:
                    raise OCFError(f"missing, corrupt or stale guide: {relative}")
                data = cached.read_bytes()
            target = stage / "guides" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            write_bytes_atomic(target, data, overwrite=False)
            artifacts.append(
                {
                    **_artifact(target),
                    "path": target.relative_to(stage).as_posix(),
                    "format": {
                        ".md": "text/markdown",
                        ".html": "text/html",
                        ".pdf": "application/pdf",
                    }[suffix],
                }
            )
    return artifacts


def verify_package(root: Path):
    """Verify every declared byte after relocation; reject path aliases and extra files."""
    document = read_json_object(root / "package.json")
    _portable(document)
    if (
        document.get("kind") != "private-listener-package"
        or document.get("publication_approval") is not False
    ):
        raise OCFError("not a private listener package")
    seen = set()
    receipts = {item["path"]: item for item in document["artifacts"]}
    for item in document["artifacts"]:
        name = item["path"]
        if _filename_key(name) in seen:
            raise OCFError("duplicate package filename")
        seen.add(_filename_key(name))
        _source_artifact(root, item)
    if not document.get("sessions"):
        raise OCFError("missing package sessions")
    session_ids = set()
    for session in document["sessions"]:
        fid = session["function_id"]
        if fid in session_ids:
            raise OCFError("duplicate session identity")
        session_ids.add(fid)
        name = f"{fid}/manifest.json"
        item = receipts.get(name)
        if item is None or item["sha256"] != session["source_manifest_sha256"]:
            raise OCFError("missing or conflicting session manifest receipt")
        manifest = read_json_object(_source_artifact(root, item))
        if manifest.get("function_id") != fid or manifest.get("version") != session["version"]:
            raise OCFError("conflicting session edition identity")
        for required in _session_items(manifest):
            included = receipts.get(f"{fid}/{required['path']}")
            if included is None or any(
                included[k] != required[k] for k in ("size_bytes", "sha256")
            ):
                raise OCFError("missing or conflicting session artifact receipt")
    guide_stems = ["listening-guide", "index", *(f"functions/{fid}" for fid in session_ids)]
    if any(
        f"guides/{stem}.{fmt}" not in receipts
        for stem in guide_stems
        for fmt in ("md", "pdf", "html")
    ):
        raise OCFError("missing package guides")
    actual = {_filename_key(p.relative_to(root).as_posix()) for p in root.rglob("*") if p.is_file()}
    if actual - {".ocf-owned"} != seen | {"package.json"}:
        raise OCFError("undeclared or missing package files")
    return document


def package_auditions(sources, output, *, guides=None, resume=False):
    """Bundle immutable verified exports without calling an encoder or changing metadata.

    This is deliberately private-only. Formal releases attach guides inside the
    existing release service, never by promoting a private package.
    """
    output = Path(output).expanduser().resolve()
    if not output.is_relative_to(work_root().resolve()):
        raise OCFError("private listener packages must remain inside the OCF workspace")
    inputs = []
    ids = set()
    for value in sources:
        source = Path(value).resolve()
        manifest_path = source / "manifest.json"
        manifest = read_json_object(manifest_path)
        items = _session_items(manifest)
        fid = manifest["function_id"]
        if fid in ids:
            raise OCFError("duplicate function in collection; use separate edition packages")
        ids.add(fid)
        names = [_filename_key(item["path"]) for item in items]
        if len(names) != len(set(names)):
            raise OCFError("duplicate source artifact filename")
        for item in items:
            _source_artifact(source, item)
            if Path(item["path"]).name in {"manifest.json", "package.json"}:
                raise OCFError("reserved source artifact filename")
        inputs.append((source, manifest, items, sha256_of_file(manifest_path)))
    if not inputs:
        raise OCFError("select at least one audition")
    identities = [
        {"function_id": m["function_id"], "version": m["version"], "source_manifest_sha256": digest}
        for _, m, _, digest in inputs
    ]
    if output.exists():
        if not resume:
            raise OCFError("refusing to overwrite an existing listener package")
        existing = verify_package(output)
        if existing["sessions"] != identities:
            raise OCFError("resume package belongs to different sources or editions")
        return existing
    stage = workspace_temp_directory(prefix="ocf-listener-package-")
    try:
        artifacts = attach_guides(stage, ids, source=Path(guides) if guides else None)
        for source, manifest, items, digest in inputs:
            folder = stage / manifest["function_id"]
            folder.mkdir()
            for item in items:
                original = _source_artifact(source, item)
                target = folder / item["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(original, target)
                _source_artifact(folder, item)
                artifacts.append(
                    {**_artifact(target), "path": target.relative_to(stage).as_posix()}
                )
            # Keep the complete portable edition/provenance manifest, not machine paths.
            target = folder / "manifest.json"
            shutil.copyfile(source / "manifest.json", target)
            if sha256_of_file(target) != digest:
                raise OCFError("source manifest changed during packaging")
            artifacts.append({**_artifact(target), "path": target.relative_to(stage).as_posix()})
        document = {
            "schema_version": "1.0",
            "kind": "private-listener-package",
            "status": "BETA / PRIVATE",
            "publication_approval": False,
            "human_listening_approval": None,
            "sessions": identities,
            "artifacts": artifacts,
            "audio_operation": "byte-for-byte copy; no reencoding or tag changes",
        }
        write_text_atomic(
            stage / "package.json", json.dumps(document, ensure_ascii=False, indent=2) + "\n"
        )
        verify_package(stage)
        output.parent.mkdir(parents=True, exist_ok=True)
        publish_workspace_temp_directory(stage, output)
        return document
    except BaseException as exc:
        record_workspace_failure(stage.name, f"listener packaging failed; retained {stage}: {exc}")
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sources", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--guides", type=Path, help="reuse a current generated guide directory")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    package_auditions(args.sources, args.output, guides=args.guides, resume=args.resume)
    print(args.output)


if __name__ == "__main__":
    main()
