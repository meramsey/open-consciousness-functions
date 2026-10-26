"""Create portable indexes for an already verified private audio package."""

from __future__ import annotations

import html
import json
import os
from pathlib import Path
from urllib.parse import quote

from .indexes import load_function_by_id
from .listener_packages import verify_package
from .paths import work_root
from .utils import OCFError, read_json_object, write_text_atomic


def build_private_collection_index(
    package: str | Path, output: str | Path, *, progress: str | Path | None = None
) -> dict:
    package = Path(package).expanduser().resolve()
    output = Path(output).expanduser().resolve()
    if not package.is_relative_to(work_root().resolve()) or not output.is_relative_to(
        work_root().resolve()
    ):
        raise OCFError("private collection indexes must remain inside the OCF workspace")
    if output == package or output.is_relative_to(package):
        raise OCFError("collection indexes must be outside the immutable package directory")
    package_receipt = verify_package(package)
    package_prefix = Path(os.path.relpath(package, output)).as_posix()
    edition_ids = {(row["version"], row["function_id"]) for row in package_receipt["sessions"]}
    versions = {version for version, _ in edition_ids}
    if len(versions) != 1:
        raise OCFError("one portable index can describe only one complete-session edition")
    version = next(iter(versions))
    tracks = []
    for row in package_receipt["sessions"]:
        function_id = row["function_id"]
        manifest = read_json_object(package / function_id / "manifest.json")
        record = load_function_by_id(function_id)
        if record is None:
            raise OCFError(f"unknown function in verified private package: {function_id}")
        mp3 = manifest.get("artifacts", {}).get("mp3", {})
        if mp3.get("codec") != "mp3" or not mp3.get("path"):
            raise OCFError(f"verified package is missing MP3 metadata for {function_id}")
        relative = Path(function_id) / mp3["path"]
        path = package / relative
        if not path.is_file():
            raise OCFError(f"verified MP3 path is missing for {function_id}")
        title = record.canonical_name or manifest.get("title", function_id)
        tracks.append(
            {
                "function_id": function_id,
                "title": title,
                "activation_cue": record.canonical_command or "",
                "category": (record.data.get("classification") or {}).get(
                    "primary_domain", "unknown"
                ),
                "duration_seconds": mp3["duration_seconds"],
                "voice": manifest.get("edition", {}).get("voice_profile_id", ""),
                "background_variant": manifest.get("edition", {}).get("background_variant", ""),
                "edition": version,
                "flac": f"{function_id}/{manifest['artifacts']['flac']['path']}",
                "mp3": relative.as_posix(),
                "status": "verified",
                "technical_verification": "verified-package",
                "human_listening_approval": manifest.get("human_listening_approval"),
                "publication_authorization": manifest.get("publication_approval", False),
            }
        )
    tracks.sort(key=lambda row: row["function_id"])
    statuses = {row["function_id"]: row for row in tracks}
    if progress:
        for row in read_json_object(Path(progress)).get("functions", []):
            statuses.setdefault(
                row["function_id"],
                {
                    "function_id": row["function_id"],
                    "title": row.get("title", row["function_id"]),
                    "status": row.get("status", "PENDING").lower(),
                    "technical_verification": row.get("technical_verification", "PENDING"),
                    "human_listening_approval": row.get("human_listening", "PENDING"),
                    "publication_authorization": "NOT_AUTHORIZED",
                },
            )
    dashboard = {
        "schema_version": "1.0",
        "edition": version,
        "publication_authorized": False,
        "verified_count": len(tracks),
        "status_count": len(statuses),
        "tracks": tracks,
        "functions": list(statuses.values()),
    }
    existing = output / "dashboard.json"
    if existing.is_file():
        previous = read_json_object(existing)
        if previous.get("edition") != version:
            raise OCFError("refusing to overwrite collection indexes for a different edition")
    playlist = ["#EXTM3U"]
    for row in tracks:
        playlist.extend(
            [
                f"#EXTINF:{int(round(row['duration_seconds']))},{row['title']}",
                f"{package_prefix}/{row['mp3']}",
            ]
        )
    rows = [
        "| ID | Function | Activation cue | Category | Duration | Voice | Background | Edition | FLAC | MP3 | Verification | Listening | Publication |",
        "| --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in tracks:
        mm, ss = divmod(int(row["duration_seconds"]), 60)
        rows.append(
            f"| {row['function_id']} | {row['title']} | {row['activation_cue']} | {row['category']} | {mm}:{ss:02} | {row['voice']} | {row['background_variant']} | {row['edition']} | [FLAC]({quote(package_prefix + '/' + row['flac'])}) | [MP3]({quote(package_prefix + '/' + row['mp3'])}) | Verified | Pending | Not authorized |"
        )
    headers = (
        "ID",
        "Function",
        "Activation cue",
        "Category",
        "Duration",
        "Voice",
        "Background",
        "Edition",
        "Files",
        "Technical",
        "Listening",
        "Publication",
    )
    links = [
        '<!doctype html><html><head><meta charset="utf-8"><title>Private OCF listening collection</title></head><body>',
        "<h1>Private OCF listening collection</h1>",
        f"<p>Edition v{html.escape(version)} · {len(tracks)} verified tracks · private only</p>",
        "<table><thead><tr>"
        + "".join(f"<th>{html.escape(item)}</th>" for item in headers)
        + "</tr></thead><tbody>",
    ]
    for row in tracks:
        minutes, seconds = divmod(int(row["duration_seconds"]), 60)
        values = [
            html.escape(row["function_id"]),
            html.escape(row["title"]),
            html.escape(row["activation_cue"]),
            html.escape(row["category"]),
            f"{minutes}:{seconds:02}",
            html.escape(row["voice"]),
            html.escape(row["background_variant"]),
            html.escape(row["edition"]),
            f'<a href="{html.escape(package_prefix + "/" + row["flac"], quote=True)}">FLAC</a> · '
            f'<a href="{html.escape(package_prefix + "/" + row["mp3"], quote=True)}">MP3</a>',
            "Verified",
            "Pending",
            "Not authorized",
        ]
        links.append("<tr>" + "".join(f"<td>{item}</td>" for item in values) + "</tr>")
    links.append("</tbody></table>")
    unfinished = [
        row
        for row in dashboard["functions"]
        if row.get("technical_verification") != "verified-package"
    ]
    if unfinished:
        links.append("<h2>Not included as verified tracks</h2><ul>")
        links.extend(
            f"<li>{html.escape(row['function_id'])}: {html.escape(str(row.get('status', 'pending')))} — "
            f"{html.escape(str(row.get('technical_verification', 'pending')))}</li>"
            for row in unfinished
        )
        links.append("</ul>")
    links.append("</body></html>")
    output.mkdir(parents=True, exist_ok=True)
    write_text_atomic(
        output / "dashboard.json", json.dumps(dashboard, ensure_ascii=False, indent=2) + "\n"
    )
    write_text_atomic(output / "playlist.m3u", "\n".join(playlist) + "\n")
    write_text_atomic(
        output / "index.md", "# Private OCF listening collection\n\n" + "\n".join(rows) + "\n"
    )
    write_text_atomic(output / "index.html", "\n".join(links) + "\n")
    return dashboard
