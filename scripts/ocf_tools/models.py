"""Typed models for OCF function records.

The YAML files remain the canonical source of truth; these dataclasses provide
typed accessors and consistent structural guarantees to validators, the CLI,
wizards, and index generators. JSON Schema validation happens separately.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DOMAINS = (
    "foundation",
    "cognition",
    "emotion",
    "communication",
    "body",
    "performance",
    "sensory",
    "sleep",
    "lifestyle",
    "emergency",
    "automation",
    "experimental",
)

COMMAND_REVIEW_STATES = ("pending", "approved", "needs-review", "review-required", "superseded")
REIMPLEMENTATION_STATES = ("planned", "draft", "in-progress", "complete", "released")
COMPATIBILITY_STATES = (
    "unchanged",
    "alias-listed",
    "bridge-trainable",
    "canonical-first",
    "legacy-first",
    "none",
)


@dataclass
class Source:
    type: str
    title: str
    locator: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class FunctionCommand:
    """Structured command identity with a reference to its authoritative phrase."""

    id: str
    function_id: str
    phrase_ref: dict[str, str]
    role: str
    designation: str
    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FunctionCommand:
        return cls(
            id=str(data["id"]),
            function_id=str(data["function_id"]),
            phrase_ref=dict(data["phrase_ref"]),
            role=str(data["role"]),
            designation=str(data["designation"]),
            data=dict(data),
        )

    @property
    def procedure(self) -> dict[str, Any] | None:
        value = self.data.get("procedure")
        return dict(value) if isinstance(value, dict) else None

    @property
    def relationships(self) -> dict[str, list[str]]:
        value = self.data.get("relationships")
        return dict(value) if isinstance(value, dict) else {}

    @property
    def localization(self) -> dict[str, str]:
        value = self.data.get("localization")
        return dict(value) if isinstance(value, dict) else {}

    @property
    def documentation(self) -> dict[str, Any]:
        value = self.data.get("documentation")
        return dict(value) if isinstance(value, dict) else {}


@dataclass
class FunctionRecord:
    """A parsed OCF function record plus its source path."""

    id: str
    slug: str
    path: Path
    data: dict[str, Any] = field(default_factory=dict)

    # -- convenience accessors ----------------------------------------------
    @property
    def canonical_name(self) -> str:
        return str(self.data.get("canonical", {}).get("name", ""))

    @property
    def canonical_command(self) -> str | None:
        return self.data.get("canonical", {}).get("command", {}).get("primary")

    @property
    def command_modes(self) -> list[str]:
        return list(self.data.get("canonical", {}).get("command", {}).get("modes", []))

    @property
    def command_records(self) -> list[FunctionCommand]:
        """Structured commands, if migrated; legacy command accessors stay unchanged."""
        values = self.data.get("commands")
        if not isinstance(values, list):
            return []
        return [
            FunctionCommand.from_dict(item)
            for item in values
            if isinstance(item, dict)
            and isinstance(item.get("phrase_ref"), dict)
            and all(name in item for name in ("id", "function_id", "role", "designation"))
        ]

    @property
    def legacy_name(self) -> str:
        return str(self.data.get("legacy", {}).get("name", ""))

    @property
    def legacy_commands(self) -> list[str]:
        return list(self.data.get("legacy", {}).get("commands", []))

    @property
    def command_status(self) -> str:
        return str(self.data.get("legacy", {}).get("command_status", ""))

    @property
    def source_availability(self) -> str:
        return str(self.data.get("legacy", {}).get("source_availability", ""))

    @property
    def reimplementation_status(self) -> str:
        return str(self.data.get("ocf", {}).get("reimplementation_status", ""))

    @property
    def command_review(self) -> str:
        return str(self.data.get("ocf", {}).get("command_review", ""))

    @property
    def documentation(self) -> dict[str, str]:
        value = self.data.get("documentation")
        return dict(value) if isinstance(value, dict) else {}

    @property
    def compatibility(self) -> str:
        state = self.data.get("compatibility", {}).get("state")
        if state:
            return str(state)
        return "unchanged" if self.command_status == "unchanged" else "alias-listed"

    @property
    def primary_domain(self) -> str:
        return str(self.data.get("classification", {}).get("primary_domain", ""))

    @property
    def secondary_domains(self) -> list[str]:
        return list(self.data.get("classification", {}).get("secondary_domains", []))

    @property
    def persistence(self) -> str:
        return str(self.data.get("lifecycle", {}).get("persistence", ""))

    @property
    def activation(self) -> str:
        return str(self.data.get("lifecycle", {}).get("activation", ""))

    @property
    def release_required(self) -> bool:
        return bool(self.data.get("lifecycle", {}).get("release", {}).get("required", False))

    @property
    def release_command(self) -> str | None:
        return self.data.get("lifecycle", {}).get("release", {}).get("command")

    @property
    def purpose_summary(self) -> str:
        return str(self.data.get("purpose", {}).get("summary", ""))

    @property
    def safety_level(self) -> str:
        return str(self.data.get("safety", {}).get("level", "general"))

    @property
    def safety_notes(self) -> list[str]:
        return list(self.data.get("safety", {}).get("notes", []))

    @property
    def evidence_state(self) -> str:
        return str(self.data.get("status", {}).get("evidence", ""))

    @property
    def maturity(self) -> str:
        return str(self.data.get("status", {}).get("maturity", ""))

    @property
    def audio_script_status(self) -> str:
        return str(self.data.get("audio", {}).get("script_status", ""))

    @property
    def audio_implementation_status(self) -> str:
        return str(self.data.get("audio", {}).get("implementation_status", ""))

    @property
    def background_strategy(self) -> str:
        return str(self.data.get("audio", {}).get("background_audio", {}).get("strategy", ""))

    @property
    def background_preset(self) -> str | None:
        return self.data.get("audio", {}).get("background_audio", {}).get("preset")

    @property
    def sources(self) -> list[Source]:
        out = []
        for item in self.data.get("sources", []):
            out.append(
                Source(
                    type=str(item.get("type", "")),
                    title=str(item.get("title", "")),
                    locator=item.get("locator"),
                    url=item.get("url"),
                )
            )
        return out

    def spoken_words(self) -> list[tuple[str, int]]:
        """Return (text, spoken-word-count) for the canonical command plus modes.

        Commas separate spoken words; hyphens do not split words.
        """
        result: list[tuple[str, int]] = []
        for text in [self.canonical_command] + self.command_modes:
            if not text:
                continue
            normalized = text.replace(",", " ").strip()
            count = len([w for w in normalized.split() if w])
            result.append((text, count))
        return result

    def to_dict(self) -> dict[str, Any]:
        return self.data


def function_from_dict(data: dict[str, Any], path: Path) -> FunctionRecord:
    """Build a FunctionRecord from parsed YAML, raising on missing id/slug."""
    if not data.get("id") or not data.get("slug"):
        raise ValueError(f"Function record missing 'id' or 'slug': {path}")
    return FunctionRecord(id=str(data["id"]), slug=str(data["slug"]), path=path, data=data)
