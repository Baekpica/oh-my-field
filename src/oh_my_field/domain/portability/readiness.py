from oh_my_field.domain.portability.models import (
    DEFAULT_MODEL_PROFILES,
    PORTABILITY_REQUIRED_PASS_RATE,
    CapabilityTier,
    ModelClass,
    ModelProfile,
    PortabilityContextBudget,
    PortabilityManifest,
    PortabilityModelDelta,
    PortabilityReadiness,
    PortabilitySource,
    PortabilityTarget,
    ReadinessFactor,
)

LOCAL_MODEL_MARKERS = ("mini", "small", "local", "qwen", "7b", "13b", "27b")
FRONTIER_MODEL_MARKERS = ("gpt-5", "opus", "sonnet", "gemini-2", "frontier")
CLASS_RANK: dict[ModelClass, int] = {"local": 1, "standard": 2, "frontier": 3}
TIER_RANK: dict[CapabilityTier, int] = {"low": 1, "medium": 2, "high": 3}
MODEL_DOWNGRADE_FACTOR_THRESHOLD = -0.1
MODEL_UNKNOWN_DELTA = -0.1
MODEL_FRONTIER_TO_LOCAL_DELTA = -0.25
MODEL_FRONTIER_TO_STANDARD_DELTA = -0.15
MODEL_GENERIC_DOWNGRADE_DELTA = -0.1
MODEL_SAME_PROFILE_DELTA = -0.03
MODEL_FRONTIER_TO_FRONTIER_DELTA = -0.05
MODEL_GENERIC_TRANSFER_DELTA = -0.08


def transfer_type(
    *,
    source: PortabilitySource,
    target: PortabilityTarget,
) -> tuple[str, ...]:
    values: list[str] = []
    if source.runtime != target.runtime:
        values.append("cross_runtime")
    if source.model != target.model:
        values.append("model_transfer")
    if source.project != target.project:
        values.append("project_transfer")
    return tuple(values or ("same_environment",))


def compression_required(context_budget: PortabilityContextBudget) -> bool:
    return (
        context_budget.source_tokens is not None
        and context_budget.target_tokens is not None
        and context_budget.target_tokens < context_budget.source_tokens
    )


def portability_readiness(
    *,
    portability: PortabilityManifest,
    unavailable_tools: tuple[str, ...],
) -> PortabilityReadiness:
    source = portability.source
    target = portability.target
    factors: list[ReadinessFactor] = []
    score = 1.0
    if source.runtime != target.runtime:
        score -= 0.05
        factors.append(
            ReadinessFactor(
                name="cross_runtime",
                delta=-0.05,
                reason=f"{source.runtime} → {target.runtime}",
            ),
        )
    if source.model != target.model:
        model_delta_value = _model_transfer_delta(source.model, target.model)
        score += model_delta_value
        factors.append(
            ReadinessFactor(
                name=(
                    "model_downgrade"
                    if model_delta_value <= MODEL_DOWNGRADE_FACTOR_THRESHOLD
                    else "model_transfer"
                ),
                delta=model_delta_value,
                reason=f"{source.model or 'unknown'} → {target.model or 'unknown'}",
            ),
        )
    if source.project != target.project:
        score -= 0.05
        factors.append(
            ReadinessFactor(
                name="project_transfer",
                delta=-0.05,
                reason=f"{source.project} → {target.project or 'unknown'}",
            ),
        )
    if portability.compatibility.compression_required:
        score -= 0.1
        factors.append(
            ReadinessFactor(
                name="context_compression",
                delta=-0.1,
                reason="target context budget smaller than source",
            ),
        )
    _ = unavailable_tools
    return PortabilityReadiness(
        score=max(0.0, round(score, 2)),
        required_pass_rate=PORTABILITY_REQUIRED_PASS_RATE,
        factors=tuple(factors),
    )



def _model_transfer_delta(source: str | None, target: str | None) -> float:
    if source is None or target is None:
        delta = MODEL_UNKNOWN_DELTA
    else:
        source_profile = _model_profile(source)
        target_profile = _model_profile(target)
        downgrade = _profile_rank(target_profile) < _profile_rank(source_profile)
        if (
            downgrade
            and source_profile.model_class == "frontier"
            and target_profile.model_class == "local"
        ):
            delta = MODEL_FRONTIER_TO_LOCAL_DELTA
        elif (
            downgrade
            and source_profile.model_class == "frontier"
            and target_profile.model_class == "standard"
        ):
            delta = MODEL_FRONTIER_TO_STANDARD_DELTA
        elif downgrade:
            delta = MODEL_GENERIC_DOWNGRADE_DELTA
        elif source_profile == target_profile:
            delta = MODEL_SAME_PROFILE_DELTA
        elif (
            source_profile.model_class == "frontier"
            and target_profile.model_class == "frontier"
        ):
            delta = MODEL_FRONTIER_TO_FRONTIER_DELTA
        else:
            delta = MODEL_GENERIC_TRANSFER_DELTA
    return delta

def model_delta(portability: PortabilityManifest) -> PortabilityModelDelta:
    source_model = portability.source.model
    target_model = portability.target.model
    return PortabilityModelDelta(
        source_model=source_model,
        target_model=target_model,
        model_changed=source_model != target_model,
        transfer_type=portability.adaptation.transfer_type,
        source_profile=None if source_model is None else _model_profile(source_model),
        target_profile=None if target_model is None else _model_profile(target_model),
        downgrade=model_downgrade(portability),
    )


def model_downgrade(portability: PortabilityManifest) -> bool:
    source = portability.source.model
    target = portability.target.model
    if source is None or target is None or source == target:
        return False
    return _profile_rank(_model_profile(target)) < _profile_rank(_model_profile(source))


def _model_profile(model: str) -> ModelProfile:
    profile = DEFAULT_MODEL_PROFILES.get(model.casefold())
    if profile is not None:
        return profile
    return _infer_model_profile(model)


def _infer_model_profile(model: str) -> ModelProfile:
    name = model.casefold()
    if any(marker in name for marker in LOCAL_MODEL_MARKERS):
        return ModelProfile(model_class="local", tool_use="medium", reasoning="medium")
    if any(marker in name for marker in FRONTIER_MODEL_MARKERS):
        return ModelProfile(model_class="frontier", tool_use="high", reasoning="high")
    return ModelProfile()


def _profile_rank(profile: ModelProfile) -> tuple[int, int, int]:
    return (
        CLASS_RANK[profile.model_class],
        TIER_RANK[profile.reasoning],
        TIER_RANK[profile.tool_use],
    )


def context_remap_required(portability: PortabilityManifest) -> bool:
    return (
        portability.target.project is not None
        and portability.target.project != portability.source.project
    )
