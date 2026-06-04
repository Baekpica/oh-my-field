from oh_my_field.domain.portability.models import PortabilityTarget


def target_slug(target: PortabilityTarget) -> str:
    model = target.model.replace("/", "_") if target.model else "model_unspecified"
    return f"{target.runtime}-{model}"


def runtime_profile(target: PortabilityTarget) -> str:
    if target.model is None:
        return target.runtime
    return f"{target.runtime}:{target.model}"
