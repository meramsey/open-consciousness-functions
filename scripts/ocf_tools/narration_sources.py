"""Deterministic, source-neutral narration selection; no implicit speaker replacement."""

from __future__ import annotations

import hashlib
import io
import json
import wave
from copy import deepcopy
from pathlib import Path, PureWindowsPath

from .indexes import load_yaml_file
from .locale import document_locale, iter_events, normalize_tag, resolve_document
from .narration_pacing import plan_event_pacing
from .utils import OCFError, sha256_of_file
from .validators import _load_schema, validate_against_schema


def text_fingerprint(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _contexts(doc):
    result = {}

    def visit(node, stage=None, role=None):
        for event in node.get("timeline", []):
            if "id" in event:
                result[event["id"]] = (stage, role)
        for section in node.get("sections", []):
            visit(section, section["id"], section.get("role"))

    visit(doc)
    return result


def _safe_source(root, name):
    relative = Path(name)
    if (
        relative.is_absolute()
        or PureWindowsPath(name).root
        or PureWindowsPath(name).drive
        or "\\" in name
        or ".." in relative.parts
    ):
        raise OCFError(
            "recording source must be a portable relative path inside its manifest directory"
        )
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise OCFError(f"recording source is missing or escapes manifest directory: {name}")
    return path


class SourceResolver:
    """Resolve before synthesis; prepared audio uses the common recording cache."""

    def __init__(self, doc, reference, *, locale=None, mode=None, default_voice=None):
        self.path = None if isinstance(reference, dict) else Path(reference).expanduser().resolve()
        self.root = self.path.parent if self.path else None
        self.config = (
            deepcopy(reference) if isinstance(reference, dict) else load_yaml_file(self.path)
        )
        if self.path is None and self.config.get("recordings"):
            raise OCFError("recordings require a file-backed source manifest")
        errors = validate_against_schema(self.config, _load_schema("narration-sources.schema.json"))
        if errors:
            raise OCFError("narration sources: " + " | ".join(errors))
        # JSON values must remain finite even when a YAML parser accepted .nan.
        try:
            json.dumps(self.config, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise OCFError("narration sources require finite JSON-compatible values") from exc
        self.locale = normalize_tag(locale or document_locale(doc))
        if normalize_tag(self.config["locale"]) != self.locale:
            raise OCFError("narration source locale does not match session locale")
        self.mode = mode or self.config["mode"]
        if self.mode not in ("tts", "recording", "hybrid", "silence"):
            raise OCFError("narration source mode must be tts, recording, hybrid or silence")
        if self.mode == "hybrid" and "fallback" not in self.config:
            raise OCFError("hybrid narration requires an explicit fallback policy")
        self.default_voice = (
            default_voice or self.config.get("default_voice") or doc.get("voice_profile")
        )
        self.channels = self.config.get("output_channels", 1)
        self.contexts = _contexts(doc)
        self.doc = doc
        self.events = {event["id"]: event for event in iter_events(doc)}
        self.catalog = self.config.get("recordings", {})
        if self.config.get("session_stem"):
            if (
                self.mode != "recording"
                or self.catalog
                or any(
                    self.config.get(key)
                    for key in (
                        "events",
                        "resources",
                        "stages",
                        "functions",
                        "speaker_processing",
                        "speaker_gain_db",
                        "stage_gain_db",
                    )
                )
            ):
                raise OCFError(
                    "a complete marked stem requires recorded-only mode and cannot combine per-cue source/gain overrides"
                )
            from .narration_stems import plan_stem

            planned = plan_stem(doc, self.config["session_stem"], self.root, locale=self.locale)
            self.rows = {row["event_id"]: row for row in planned["narration_source"]["events"]}
            self.report = {
                **planned["narration_source"],
                "id": self.config["id"],
                "schema_version": "2.0",
                "manifest_sha256": sha256_of_file(self.path),
                "output_channels": self.channels,
            }
            return
        for identifier, entry in self.catalog.items():
            target = entry["target"]
            if target.get("event_id") and target["event_id"] not in self.events:
                raise OCFError(f"recording {identifier}: unknown narration event ID")
            if target.get("unit_index") and target.get("event_id") in self.events:
                pacing = plan_event_pacing(doc, self.events[target["event_id"]])
                if not pacing or target["unit_index"] > len(pacing["units"]):
                    raise OCFError(f"recording {identifier}: unknown semantic unit index")
            if normalize_tag(entry["locale"]) != self.locale:
                raise OCFError(f"recording {identifier}: locale mismatch")
            path = _safe_source(self.root, entry["file"])
            if sha256_of_file(path) != entry["sha256"]:
                raise OCFError(f"recording {identifier}: checksum mismatch; no TTS fallback")
        for key in self.config.get("events", {}):
            if key not in self.events:
                raise OCFError(f"unknown narration event override: {key}")
        stages = {stage for stage, _ in self.contexts.values() if stage}
        if set(self.config.get("stages", {})) - stages:
            raise OCFError("unknown narration stage override")
        self.rows = {}
        for event in self.events.values():
            self.rows[event["id"]] = self._event(event)
        speakers = {
            row["speaker"]
            for event in self.rows.values()
            for row in event.get("units", [event])
            if row.get("speaker") and row["source"] != "silence"
        }
        if self.config.get("speaker_consistency") == "require-single" and len(speakers) > 1:
            raise OCFError(
                "speaker consistency requires a single declared speaker; selected: "
                + ", ".join(sorted(speakers))
            )
        if self.config.get("speaker_consistency") == "require-single" and any(
            row["source"] != "silence" and not row.get("speaker")
            for event in self.rows.values()
            for row in event.get("units", [event])
        ):
            raise OCFError(
                "speaker consistency requires an explicit declared speaker for every spoken source"
            )
        self.report = {
            "schema_version": "2.0",
            "id": self.config["id"],
            "mode": self.mode,
            "manifest_sha256": sha256_of_file(self.path)
            if self.path
            else text_fingerprint(json.dumps(self.config, sort_keys=True)),
            "locale": self.locale,
            "fallback": self.config.get("fallback", "error"),
            "speakers": sorted(speakers),
            "speaker_consistency": self.config.get("speaker_consistency", "report"),
            "output_channels": self.channels,
            "events": list(self.rows.values()),
            "content_verification": "text fingerprints bind declarations; no speech recognition or approval inferred",
        }

    def _choice(self, event):
        stage, _role = self.contexts.get(event["id"], (None, None))
        if event["id"] in self.config.get("events", {}):
            return deepcopy(self.config["events"][event["id"]]), "events"
        if event.get("voice", {}).get("profile"):
            return {"source": "tts", "voice": event["voice"]["profile"]}, "event-voice"
        for category, key in (
            ("events", event["id"]),
            ("resources", event.get("narration_key")),
            ("stages", stage),
            ("functions", self.doc.get("function_id")),
        ):
            choice = self.config.get(category, {}).get(key)
            if choice:
                return deepcopy(choice), category
        return {}, "automatic"

    def _matches(self, event, unit_index=None):
        stage, _role = self.contexts.get(event["id"], (None, None))
        context = {
            "event_id": event["id"],
            "narration_key": event.get("narration_key"),
            "function_id": self.doc.get("function_id"),
            "stage_id": stage,
            "unit_index": unit_index,
        }
        found = []
        for identifier, entry in self.catalog.items():
            target = entry["target"]
            if target.get("unit_index") != unit_index:
                continue
            if all(context.get(key) == value for key, value in target.items()):
                # Explicit semantic identity wins over broad reusable scope.
                score = sum(
                    {
                        "unit_index": 32,
                        "event_id": 16,
                        "function_id": 8,
                        "narration_key": 4,
                        "stage_id": 2,
                    }[key]
                    for key in target
                )
                found.append((score, identifier))
        found.sort(reverse=True)
        if len(found) > 1 and found[0][0] == found[1][0]:
            raise OCFError(f"ambiguous recordings for {event['id']}; use an explicit recording_id")
        return found[0][1] if found else None

    def _row(self, event, text, choice, scope, unit_index=None):
        requested = choice.get("source")
        recording_id = choice.get("recording_id") if unit_index is None else None
        if recording_id and requested != "recording":
            raise OCFError("recording_id requires source=recording")
        if not requested and self.mode in ("recording", "hybrid"):
            recording_id = self._matches(event, unit_index)
        source = requested or ("recording" if recording_id else "tts")
        if self.mode == "silence" or source == "silence":
            if text.strip():
                raise OCFError("silence narration cannot suppress required spoken text")
            source = "silence"
        if self.mode == "recording" and source == "tts":
            raise OCFError(
                f"recorded-only narration is missing recording for {event['id']}"
                + (f" unit {unit_index}" if unit_index else "")
            )
        if (
            self.mode == "hybrid"
            and source == "tts"
            and not requested
            and self.config["fallback"] != "tts"
        ):
            raise OCFError(f"hybrid fallback=error: missing recording for {event['id']}")
        stage, role = self.contexts.get(event["id"], (None, None))
        row = {
            "event_id": event["id"],
            "narration_key": event.get("narration_key"),
            "function_id": self.doc.get("function_id"),
            "locale": self.locale,
            "role": role or event.get("semantic"),
            "stage_id": stage,
            "unit_index": unit_index,
            "source": source,
            "selection_scope": scope,
            "text_sha256": text_fingerprint(text),
            "fallback_reason": "recording-unavailable-explicit-tts-fallback"
            if self.mode == "hybrid" and source == "tts" and not requested
            else None,
        }
        if source == "recording":
            if not recording_id:
                recording_id = self._matches(event, unit_index)
            if recording_id not in self.catalog:
                raise OCFError(f"selected recording is missing for {event['id']}; no TTS fallback")
            entry = self.catalog[recording_id]
            if entry["text_sha256"] != row["text_sha256"]:
                raise OCFError(
                    f"recording {recording_id}: source text fingerprint mismatch; review stale recording"
                )
            if entry["target"].get("narration_key") and entry["target"][
                "narration_key"
            ] != event.get("narration_key"):
                raise OCFError("selected recording narration resource mismatch")
            row.update(
                recording_id=recording_id,
                recording=deepcopy(entry),
                speaker=entry["speaker"],
                text_compatibility="fingerprint-match-not-transcript-verification",
            )
        else:
            row.update(
                voice=choice.get("voice") or self.default_voice,
                speaker=choice.get("speaker")
                or choice.get("voice")
                or (
                    self.default_voice
                    if isinstance(self.default_voice, str)
                    else (self.default_voice or {}).get("id")
                ),
                text_compatibility="canonical-tts-text",
            )
        row["gain_db"] = (
            choice.get("gain_db", 0)
            + self.config.get("speaker_gain_db", {}).get(row.get("speaker"), 0)
            + self.config.get("stage_gain_db", {}).get(stage, 0)
            + (row.get("recording") or {}).get("gain_db", 0)
            + (event.get("voice", {}).get("gain_db") or 0)
        )
        row["processing"] = {
            **self.config.get("speaker_processing", {}).get(row.get("speaker"), {}),
            **(row.get("recording") or {}).get("processing", {}),
            **choice.get("processing", {}),
        }
        voice_controls = event.get("voice", {})
        if set(voice_controls) - {"profile", "rate", "gain_db"}:
            raise OCFError("unsupported per-event voice control")
        row["rate_scale"] = choice.get("rate_scale") or voice_controls.get("rate") or 1.0
        if not isinstance(row["rate_scale"], (int, float)) or not 0.5 <= row["rate_scale"] <= 2:
            raise OCFError("event narration rate must be 0.5..2")
        if not -60 <= row["gain_db"] <= 24:
            raise OCFError("combined narration gain must be -60..24 dB")
        return row

    def _event(self, event):
        text = event.get("text", "")
        if not text.strip():
            return {
                "event_id": event["id"],
                "source": "silence",
                "speaker": None,
                "intentional_nonspoken_event": True,
            }
        choice, scope = self._choice(event)
        pacing = plan_event_pacing(self.doc, event)
        unit_ids = (
            [self._matches(event, i + 1) for i, _ in enumerate(pacing["units"])] if pacing else []
        )
        # A partial unit collection must not displace an available complete take.
        unit_matches = any(unit_ids) and (all(unit_ids) or self._matches(event) is None)
        if unit_matches and not choice:
            units = [
                self._row(event, unit["text"], {}, "semantic-unit", i + 1)
                for i, unit in enumerate(pacing["units"])
            ]
            return {
                "event_id": event["id"],
                "source": "hybrid-units",
                "units": units,
                "pacing_profile": pacing["profile_id"],
            }
        return self._row(event, text, choice, scope)

    def prepare(self, row, *, sample_rate):
        from .recording_audio import process_recording

        entry = row["recording"]
        processing = dict(row.get("processing") or {})
        # Gain is applied once by the shared source-neutral renderer after preparation.
        data, report = process_recording(
            _safe_source(self.root, entry["file"]),
            sample_rate=sample_rate,
            channels=self.channels,
            processing=processing,
            expected_sha256=entry["sha256"],
        )
        if entry.get("segment"):
            segment = entry["segment"]
            with wave.open(io.BytesIO(data)) as reader:
                start = round(segment["start_s"] * sample_rate)
                end = round(segment["end_s"] * sample_rate)
                if not 0 <= start < end <= reader.getnframes():
                    raise OCFError(
                        "recording segment markers are empty, reversed or beyond decoded audio"
                    )
                reader.setpos(start)
                frames = reader.readframes(end - start)
            output = io.BytesIO()
            with wave.open(output, "wb") as writer:
                writer.setparams((self.channels, 2, sample_rate, 0, "NONE", "not compressed"))
                writer.writeframes(frames)
            data = output.getvalue()
            report = {
                **report,
                "selected_segment": {
                    **segment,
                    "start_frame": start,
                    "end_frame": end,
                    "duration_s": (end - start) / sample_rate,
                    "sha256": hashlib.sha256(data).hexdigest(),
                },
                "segment_processing_order": "prepare original file, then select explicit frame markers",
            }
        return data, report


def preview_sources(document, reference, *, locale=None, mode=None, default_voice=None):
    target = locale or document_locale(document)
    resolved = resolve_document(document, target, strict=True)
    return SourceResolver(
        resolved, reference, locale=target, mode=mode, default_voice=default_voice
    ).report
