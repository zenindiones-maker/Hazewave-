from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class GenreProductionProfile:
    genre_id: str
    display_name: str
    principles: tuple[str, ...]
    topologies: tuple[str, ...]
    anti_assumptions: tuple[str, ...]
    default_parameter_values: Mapping[str, float]
    fixed_preset: bool = False
    human_refinement_required: bool = True
    schema: str = "GenreProductionProfile/v1"

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["principles"] = list(self.principles)
        value["topologies"] = list(self.topologies)
        value["anti_assumptions"] = list(self.anti_assumptions)
        value["default_parameter_values"] = dict(self.default_parameter_values)
        return value


@dataclass(frozen=True)
class ListeningConcept:
    term: str
    evidence_candidates: tuple[str, ...]
    possible_causes: tuple[str, ...]
    candidate_capabilities: tuple[str, ...]
    numeric_truth: bool = False
    automatic_action: bool = False
    schema: str = "ListeningConcept/v1"


@dataclass(frozen=True)
class ListeningHypothesis:
    term: str
    evidence: Mapping[str, Any]
    context: Mapping[str, Any]
    reference_features: Mapping[str, Any]
    candidate_capabilities: tuple[str, ...]
    rationale: str
    automatic_action: bool = False
    artistic_truth_claimed: bool = False
    schema: str = "ListeningHypothesis/v1"


@dataclass(frozen=True)
class MusicProductionBrief:
    brief_id: str
    intent: str
    genre_id: str
    source_kind: str
    desired_character: tuple[str, ...]
    delivery_context: str
    schema: str = "MusicProductionBrief/v1"

    def __post_init__(self) -> None:
        for value in (
            self.brief_id,
            self.intent,
            self.genre_id,
            self.source_kind,
            self.delivery_context,
        ):
            if not str(value or "").strip():
                raise ValueError("MUSIC_PRODUCTION_BRIEF_INVALID")


@dataclass(frozen=True)
class ProductionStrategy:
    brief_id: str
    intent: str
    genre_id: str
    ordered_capabilities: tuple[str, ...]
    constraints: tuple[str, ...]
    rationale: tuple[str, ...]
    fixed_preset: bool = False
    grants_execution_authority: bool = False
    requires_snapshot: bool = True
    requires_post_analysis: bool = True
    schema: str = "ProductionStrategy/v1"


class MusicProductionKnowledgeRegistry:
    def __init__(self, profiles: tuple[GenreProductionProfile, ...]) -> None:
        self._profiles: dict[str, GenreProductionProfile] = {}
        for profile in profiles:
            if profile.genre_id in self._profiles:
                raise ValueError("GENRE_PROFILE_DUPLICATE_ID")
            self._profiles[profile.genre_id] = profile

    @classmethod
    def default(cls) -> "MusicProductionKnowledgeRegistry":
        profiles = (
            GenreProductionProfile(
                genre_id="dub-reggae",
                display_name="Dub / Reggae",
                principles=(
                    "Treat space as arrangement, not decoration.",
                    "Protect drum and bass focus and bass preservation before effect density.",
                    "Use send-based delay as a performable instrument when the brief calls for it.",
                    "Treat feedback riding and automation as performance, not a static preset.",
                    "Use filtered repeats to control buildup while preserving musical motion.",
                    "Make pre/post-fader routing a deliberate pre/post decision.",
                ),
                topologies=(
                    "send-based delay return",
                    "parallel spatial return",
                    "feedback riding automation lane",
                    "filtered repeats return",
                    "pre/post send topology selected from arrangement intent",
                    "space as arrangement through mutes, drops and returns",
                ),
                anti_assumptions=(
                    "Do not assume every dub mix needs maximal feedback.",
                    "Do not thin bass automatically to make effects audible.",
                    "Do not hardcode one delay plug-in or timing.",
                ),
                default_parameter_values={},
            ),
            GenreProductionProfile(
                genre_id="hip-hop",
                display_name="Hip-Hop",
                principles=(
                    "Preserve intentional low-end relationship between kick, bass and sample.",
                    "Treat vocal placement, transient shape and sample texture as context dependent.",
                ),
                topologies=(
                    "vocal subgroup and parallel dynamics where justified",
                    "drum and low-end buses with explicit headroom",
                ),
                anti_assumptions=(
                    "Do not equate loudness with impact.",
                    "Do not force one vocal chain across styles or eras.",
                ),
                default_parameter_values={},
            ),
            GenreProductionProfile(
                genre_id="rock",
                display_name="Rock",
                principles=(
                    "Preserve performance dynamics and phase relationships before corrective processing.",
                    "Evaluate guitar, bass, drums and vocal masking in arrangement context.",
                ),
                topologies=(
                    "instrument buses with phase-aware routing",
                    "parallel dynamics only when it serves the performance",
                ),
                anti_assumptions=(
                    "Do not assume distorted sources need additional saturation.",
                    "Do not quantize or flatten dynamics by default.",
                ),
                default_parameter_values={},
            ),
            GenreProductionProfile(
                genre_id="psychedelic",
                display_name="Psychedelic",
                principles=(
                    "Use movement, contrast and spatial transformation as arrangement devices.",
                    "Keep experimental processing bounded and recallable.",
                ),
                topologies=(
                    "modulated spatial returns",
                    "automation-driven transitions",
                    "parallel character processing",
                ),
                anti_assumptions=(
                    "Do not confuse randomness with psychedelic intent.",
                    "Do not sacrifice center stability without a reason.",
                ),
                default_parameter_values={},
            ),
            GenreProductionProfile(
                genre_id="electronic",
                display_name="Electronic",
                principles=(
                    "Balance transient design, sub-energy, synthesis layers and automation density.",
                    "Treat sound design and mix decisions as coupled but independently reversible.",
                ),
                topologies=(
                    "synthesis and resampling layers",
                    "sidechain topology selected from musical intent",
                    "automation buses for macro movement",
                ),
                anti_assumptions=(
                    "Do not assume four-on-the-floor or aggressive limiting.",
                    "Do not use sidechain compression merely because of genre label.",
                ),
                default_parameter_values={},
            ),
            GenreProductionProfile(
                genre_id="ambient",
                display_name="Ambient",
                principles=(
                    "Evaluate long-term dynamics, depth, density and spectral accumulation.",
                    "Preserve silence, decay and contrast as musical material.",
                ),
                topologies=(
                    "long-tail spatial returns",
                    "layered depth planes",
                    "slow automation with bounded feedback",
                ),
                anti_assumptions=(
                    "Do not assume ambient means uniformly quiet or washed out.",
                    "Do not remove transients automatically.",
                ),
                default_parameter_values={},
            ),
            GenreProductionProfile(
                genre_id="cinematic",
                display_name="Cinematic",
                principles=(
                    "Coordinate orchestration, dialogue or focal elements, dynamics and delivery headroom.",
                    "Use automation and perspective to support narrative hierarchy.",
                ),
                topologies=(
                    "stem-oriented buses",
                    "dialogue or focal-element priority routing",
                    "delivery-context master path",
                ),
                anti_assumptions=(
                    "Do not force trailer-style loudness or orchestration.",
                    "Do not treat VMAF or loudness as narrative quality.",
                ),
                default_parameter_values={},
            ),
            GenreProductionProfile(
                genre_id="brazilian-contexts",
                display_name="Brazilian Music Contexts",
                principles=(
                    "Treat Brazilian music as multiple traditions and contemporary practices, not one preset.",
                    "Preserve groove, articulation, language, percussion relationships and regional context.",
                ),
                topologies=(
                    "rhythm-section routing selected per repertoire",
                    "percussion-aware transient and spatial management",
                ),
                anti_assumptions=(
                    "Do not collapse samba, funk, trap, MPB, reggae, rock or regional forms into one sound.",
                    "Do not impose imported genre stereotypes over session evidence.",
                ),
                default_parameter_values={},
            ),
        )
        return cls(profiles)

    def genre_profile(self, genre_id: str) -> GenreProductionProfile:
        try:
            return self._profiles[genre_id]
        except KeyError as exc:
            raise ValueError(f"GENRE_PROFILE_NOT_FOUND:{genre_id}") from exc

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema": "MusicProductionKnowledge/v1",
            "authority": "NONE",
            "grants_execution_authority": False,
            "genre_profiles": [
                self._profiles[key].to_dict()
                for key in sorted(self._profiles)
            ],
        }


class ListeningReasoningEngine:
    def __init__(self, concepts: tuple[ListeningConcept, ...]) -> None:
        self._concepts = {item.term: item for item in concepts}

    @staticmethod
    def _concept(
        term: str,
        evidence: tuple[str, ...],
        causes: tuple[str, ...],
        capabilities: tuple[str, ...],
    ) -> ListeningConcept:
        return ListeningConcept(
            term=term,
            evidence_candidates=evidence,
            possible_causes=causes,
            candidate_capabilities=capabilities,
        )

    @classmethod
    def default(cls) -> "ListeningReasoningEngine":
        spectral = ("spectral_distribution", "reference_delta", "section_energy")
        spatial = ("stereo_correlation", "side_energy_ratio", "mono_compatibility")
        dynamics = ("crest_factor", "loudness_range", "transient_density")
        concepts = (
            cls._concept("mud", spectral, ("low-mid accumulation", "masking", "arrangement density"), ("mix.eq", "mix.balance", "arrangement.structure")),
            cls._concept("harshness", spectral, ("upper-mid excess", "distortion", "source tone"), ("mix.eq", "mix.dynamics", "mix.saturation")),
            cls._concept("boxiness", spectral, ("midrange resonance", "room coloration"), ("mix.eq", "audio.edit")),
            cls._concept("nasality", spectral, ("narrow mid resonance", "performance or mic tone"), ("mix.eq", "mix.automation")),
            cls._concept("sibilance", spectral + dynamics, ("vocal consonant energy", "compression interaction"), ("mix.dynamics", "mix.eq", "mix.automation")),
            cls._concept("boom", spectral, ("low resonance", "room mode", "arrangement overlap"), ("mix.eq", "mix.balance")),
            cls._concept("thinness", spectral, ("missing body", "phase cancellation", "arrangement gap"), ("mix.eq", "mix.balance", "audio.align")),
            cls._concept("masking", spectral, ("overlapping sources", "arrangement density"), ("mix.balance", "mix.eq", "arrangement.structure")),
            cls._concept("depth", spatial + spectral, ("level hierarchy", "early/late energy", "spectral contrast"), ("mix.spatial", "mix.reverb", "mix.delay")),
            cls._concept("width", spatial, ("panning", "decorrelation", "phase relationship"), ("mix.spatial", "mix.balance")),
            cls._concept("punch", dynamics, ("transient-to-body relationship", "timing", "dynamic contrast"), ("mix.dynamics", "audio.align", "mix.gainstage")),
            cls._concept("density", dynamics + spectral, ("layer count", "sustain", "compression"), ("arrangement.structure", "mix.dynamics", "mix.balance")),
            cls._concept("air", spectral, ("high-frequency extension", "noise", "vocal texture"), ("mix.eq", "mix.saturation")),
            cls._concept("warmth", spectral, ("spectral tilt", "harmonic coloration", "source balance"), ("mix.eq", "mix.saturation", "mix.balance")),
            cls._concept("brightness", spectral, ("spectral tilt", "transient content"), ("mix.eq", "mix.balance")),
            cls._concept("darkness", spectral, ("spectral tilt", "source or filter choice"), ("mix.eq", "mix.balance")),
            cls._concept("glue", dynamics, ("shared dynamics", "bus interaction", "arrangement cohesion"), ("mix.dynamics", "master.process")),
            cls._concept("movement", dynamics + spatial, ("automation", "modulation", "performance"), ("mix.automation", "mix.spatial", "mix.delay")),
            cls._concept("contrast", dynamics + spectral, ("section-to-section difference", "automation", "arrangement"), ("arrangement.structure", "mix.automation")),
            cls._concept("clarity", spectral + spatial, ("masking", "level hierarchy", "phase relationship"), ("mix.balance", "mix.eq", "audio.align")),
        )
        return cls(concepts)

    def concept(self, term: str) -> ListeningConcept:
        key = str(term or "").strip().casefold()
        try:
            return self._concepts[key]
        except KeyError as exc:
            raise ValueError(f"LISTENING_CONCEPT_NOT_FOUND:{term}") from exc

    def hypothesize(
        self,
        *,
        term: str,
        evidence: Mapping[str, Any],
        context: Mapping[str, Any],
        reference_features: Mapping[str, Any],
    ) -> ListeningHypothesis:
        concept = self.concept(term)
        return ListeningHypothesis(
            term=concept.term,
            evidence=dict(evidence),
            context=dict(context),
            reference_features=dict(reference_features),
            candidate_capabilities=concept.candidate_capabilities,
            rationale=(
                "Perceptual language is treated as a hypothesis. Measurements, "
                "source context, reference features and human preference must be "
                "considered together before any bounded mutation is planned."
            ),
        )


class MusicProductionPlanner:
    _INTENT_CAPABILITIES = {
        "CLEAN_TRANSPARENT": (
            "session.inspect",
            "mix.gainstage",
            "mix.balance",
            "mix.eq",
            "audio.analyze",
            "audio.compare",
        ),
        "COLORED_CHARACTER": (
            "session.inspect",
            "mix.gainstage",
            "mix.balance",
            "mix.eq",
            "mix.saturation",
            "mix.automation",
            "audio.analyze",
            "audio.compare",
        ),
        "DUB_SEND_FX": (
            "session.inspect",
            "routing.bus",
            "routing.send",
            "mix.delay",
            "mix.eq",
            "mix.automation",
            "audio.analyze",
            "audio.compare",
        ),
        "DYNAMIC_CONTROL": (
            "session.inspect",
            "mix.gainstage",
            "mix.dynamics",
            "mix.automation",
            "audio.analyze",
            "audio.compare",
        ),
        "MIX_BUS_MASTER": (
            "session.inspect",
            "audio.analyze",
            "audio.compare",
            "master.prepare",
            "master.process",
            "master.render",
        ),
    }

    def __init__(self, *, registry: MusicProductionKnowledgeRegistry) -> None:
        self.registry = registry

    def plan(self, brief: MusicProductionBrief) -> ProductionStrategy:
        profile = self.registry.genre_profile(brief.genre_id)
        capabilities = self._INTENT_CAPABILITIES.get(brief.intent)
        if capabilities is None:
            raise ValueError(f"MUSIC_PRODUCTION_INTENT_UNSUPPORTED:{brief.intent}")

        constraints = (
            "Bind mutations to the current project snapshot/state count.",
            "Use only capability-authorized subordinate tools.",
            "Do not turn genre profile into fixed parameter values.",
            "Separate technical gates from creative judgment.",
            f"Respect delivery context: {brief.delivery_context}.",
        ) + profile.anti_assumptions

        rationale = (
            f"Intent {brief.intent} determines the bounded capability surface.",
            f"Genre context {profile.display_name} contributes principles, not a preset.",
            f"Source kind {brief.source_kind} and desired character {', '.join(brief.desired_character) or 'unspecified'} remain session-specific evidence.",
        ) + profile.principles[:2]

        return ProductionStrategy(
            brief_id=brief.brief_id,
            intent=brief.intent,
            genre_id=brief.genre_id,
            ordered_capabilities=capabilities,
            constraints=constraints,
            rationale=rationale,
        )
