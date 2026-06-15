from typing import cast

import yaml

from oh_my_field.domain.models import CapabilityManifest, StrictModel
from oh_my_field.domain.portability.models import (
    RUNTIME_SKILL_SCHEMA_VERSION,
    PortabilityManifest,
    YamlValue,
)


def bundle_readme(portability: PortabilityManifest) -> str:
    return "\n".join(
        [
            f"# {portability.capability}",
            "",
            "## Portability",
            f"- Source: {portability.source.runtime}/{portability.source.model}",
            f"- Target: {portability.target.runtime}/{portability.target.model}",
            f"- Transfer: {', '.join(portability.adaptation.transfer_type)}",
            "",
            "## OMF Import Required",
            "Runtime skill files are projections for agent discovery. The",
            "canonical capability is this OMF package, and target runtimes must",
            "import it before attempting a target run.",
            "",
            "```bash",
            _import_command(
                portability.target.runtime,
                portability.target.model,
            ),
            f"omf card {portability.capability}",
            (
                f"omf capability validate {portability.capability} "
                f"--target {portability.target.runtime}"
            ),
            "```",
            "",
        ],
    )


def base_instructions(manifest: CapabilityManifest) -> str:
    return "\n".join(
        [
            f"# {manifest.name}",
            "",
            manifest.description,
            "",
            "## Use",
            f"- Goal: {manifest.normalized_goal}",
            "- Apply the context policy before acting.",
            "- Run the harness before accepting the result.",
            "- Record target-specific failures as new evidence.",
            "",
        ],
    )


def compact_instructions(manifest: CapabilityManifest) -> str:
    required_context = ", ".join(manifest.context.required) or "the required context"
    required_checks = ", ".join(manifest.harness.required_checks) or "the harness"
    return "\n".join(
        [
            f"# {manifest.name} compact",
            "",
            manifest.description,
            "",
            "## Compact Procedure",
            f"- Use only {required_context} unless the harness fails.",
            "- Prefer direct steps and avoid exploratory branching.",
            f"- Verify with {required_checks} before accepting the result.",
            "- Escalate to human review when target tools or context are missing.",
            "",
        ],
    )


def model_notes_file(portability: PortabilityManifest) -> str:
    target_model = (portability.target.model or "model").replace("/", "_")
    return f"model_notes.{target_model}.md"


def model_notes(portability: PortabilityManifest) -> str:
    return "\n".join(
        [
            "# Model Transfer Notes",
            "",
            f"- Source model: {portability.source.model or 'not recorded'}",
            f"- Target model: {portability.target.model or 'not recorded'}",
            f"- Transfer type: {', '.join(portability.adaptation.transfer_type)}",
            "- Use compact instructions before expanding optional context.",
            "- Run target eval before treating the import as validated.",
            "",
        ],
    )


def compressed_context_pack(
    manifest: CapabilityManifest,
    portability: PortabilityManifest,
) -> str:
    required = "\n".join(f"- {item}" for item in manifest.context.required)
    optional = "\n".join(f"- {item}" for item in manifest.context.optional)
    budget = portability.compatibility.context_budget
    source_tokens = None if budget is None else budget.source_tokens
    target_tokens = None if budget is None else budget.target_tokens
    return "\n".join(
        [
            "# Compressed Context Pack",
            "",
            f"- Source token budget: {source_tokens or 'not recorded'}",
            f"- Target token budget: {target_tokens or 'not recorded'}",
            "- Include required context first.",
            "- Drop optional context when the target budget is smaller.",
            "",
            "## Required",
            required or "- No required context recorded.",
            "",
            "## Optional",
            optional or "- No optional context recorded.",
            "",
        ],
    )


def runtime_memory(manifest: CapabilityManifest) -> str:
    return "\n".join(
        [
            f"# {manifest.name}",
            "",
            "Use this imported OMF capability package as guidance for this project.",
            "Do not treat OMF as the agent runtime; use the local agent normally.",
            "",
            "## Capability",
            manifest.description,
            "",
        ],
    )


def claude_memory(manifest: CapabilityManifest) -> str:
    control = manifest.workflow_control
    allowed = _join_or(control.allowed_tools, "inherit from runtime")
    disallowed = _join_or(control.disallowed_tools, "none")
    return "\n".join(
        [
            f"# {manifest.name}",
            "",
            "Project memory for an imported OMF capability package.",
            "Use this guidance when the current task matches the capability.",
            "",
            "## Capability",
            manifest.description,
            "",
            "## When To Use",
            f"- {manifest.normalized_goal}",
            "",
            "## Tool Use Policy",
            f"- Allowed tools: {allowed}.",
            f"- Disallowed tools: {disallowed}.",
            "- Request approval before write, destructive, or external commands.",
            "",
            "## Instructions",
            "- Read capability.md before acting.",
            "- Follow checks.md before marking the result complete.",
            "- Preserve target-specific failures as OMF evidence.",
            "",
            "## Completion Criteria",
            _bullets(manifest.harness.required_checks, "Harness checks pass."),
            "- No unrelated changes.",
            "",
        ],
    )


def skill_markdown(manifest: CapabilityManifest) -> str:
    return "\n".join(
        [
            f"# {manifest.name}",
            "",
            "## Trigger",
            f"Use this skill when the task matches: {manifest.normalized_goal}.",
            "",
            "## OMF Import Required",
            "Before treating this projection as an executable capability, import",
            "the canonical OMF package into the target project:",
            "",
            "```bash",
            (
                "omf capability import <package.omfcap.tar.gz> "
                "--runtime <runtime> --project <project> --validate"
            ),
            f"omf card {manifest.name}",
            "```",
            "",
            "## Inputs",
            _bullets(manifest.inputs, "No specific inputs recorded."),
            "",
            "## Context Policy",
            "",
            "### Required",
            _bullets(manifest.context.required, "No required context recorded."),
            "",
            "### Forbidden",
            _bullets(manifest.context.forbidden, "No forbidden context recorded."),
            "",
            "## Procedure",
            "1. Load the required context before acting.",
            "2. Identify the smallest relevant surface for the goal.",
            "3. Make the minimal change or output that satisfies the goal.",
            "4. Run the harness checks before accepting the result.",
            "5. Record unresolved failures as evidence.",
            "",
            "## Completion Criteria",
            _bullets(manifest.harness.required_checks, "Harness checks pass."),
            "- No unrelated changes.",
            "- Attach a regression case if the failure was novel.",
            "",
        ],
    )


def agent_skill_markdown(manifest: CapabilityManifest) -> str:
    frontmatter = yaml.safe_dump(
        {"name": manifest.name, "description": manifest.description},
        sort_keys=False,
    ).strip()
    return "\n".join(
        [
            "---",
            frontmatter,
            "---",
            "",
            skill_markdown(manifest),
        ],
    )


def launcher_frontmatter_fields(
    manifest: CapabilityManifest,
    *,
    target_runtime: str,
) -> dict[str, YamlValue]:
    return {
        "name": manifest.name,
        "description": manifest.description,
        "omf_managed": True,
        "omf_schema": RUNTIME_SKILL_SCHEMA_VERSION,
        "capability_name": manifest.name,
        "runtime": target_runtime,
        "execution_mode": "omf_managed",
        "direct_execution_allowed": False,
    }


def launcher_skill_markdown(
    manifest: CapabilityManifest,
    *,
    target_runtime: str,
) -> str:
    frontmatter = yaml.safe_dump(
        launcher_frontmatter_fields(manifest, target_runtime=target_runtime),
        sort_keys=False,
    ).strip()
    return "\n".join(
        [
            "---",
            frontmatter,
            "---",
            "",
            launcher_body_markdown(manifest, target_runtime=target_runtime),
        ],
    )


def launcher_body_markdown(
    manifest: CapabilityManifest,
    *,
    target_runtime: str,
) -> str:
    name = manifest.name
    return "\n".join(
        [
            f"# OMF Capability Launcher: {name}",
            "",
            "This is not a standalone skill. It is the entrypoint for an",
            "OMF-managed capability; the capability body stays in the OMF",
            "package and registry, not in this file.",
            "",
            "## Required Behavior",
            "",
            "When this skill is selected, do not implement the task from this",
            "file. Import the canonical OMF package into this target project",
            "and enter the OMF lifecycle first:",
            "",
            "```bash",
            _import_command(target_runtime, "<model>"),
            f"omf card {name}",
            f"omf inspect import {name} --target {target_runtime} --model <model>",
            (
                f"omf capability remap {name} --target {target_runtime} "
                "--model <model> --map source=target"
            ),
            f"omf capability validate {name} --target {target_runtime}",
            (
                f"omf session start --runtime {target_runtime} "
                '--model <model> --goal "<goal>"'
            ),
            "```",
            "",
            "Record the work through OMF session events, then finish with",
            "`omf session finish` and `omf session materialize` so the run",
            "leaves evidence.",
            "",
            "## Inspect",
            "",
            "The capability goal and context policy are metadata, not direct",
            "instructions. Inspect them through OMF instead of skill files:",
            "",
            "```bash",
            f"omf card {name}",
            "```",
            "",
            "## Completion Condition",
            "",
            "The task is complete only when OMF has recorded:",
            "",
            "- materialized evidence for this run,",
            "- an OMF import record for the canonical package,",
            f"- a target validation report for `{target_runtime}`,",
            "- harness results for the required checks.",
            "",
            "## Forbidden Behavior",
            "",
            "- Do not execute the capability goal directly from skill files.",
            "- Do not treat copying runtime projection files as an OMF import.",
            "- Do not skip OMF harness execution.",
            "- Do not claim success without OMF evidence and a validation report.",
            "- Do not modify the capability bundle manually.",
            "",
        ],
    )


def odysseus_launcher_skill_markdown(manifest: CapabilityManifest) -> str:
    frontmatter = yaml.safe_dump(
        {
            **launcher_frontmatter_fields(manifest, target_runtime="odysseus"),
            "version": manifest.version,
            "category": "omf",
            "tags": ["omf", "capability"],
            "status": "published",
            "confidence": 1.0,
            "source": "imported",
        },
        sort_keys=False,
    ).strip()
    return "\n".join(
        [
            "---",
            frontmatter,
            "---",
            "",
            launcher_body_markdown(manifest, target_runtime="odysseus"),
        ],
    )


def odysseus_skill_markdown(manifest: CapabilityManifest) -> str:
    frontmatter = yaml.safe_dump(
        {
            "name": manifest.name,
            "description": manifest.description,
            "version": manifest.version,
            "category": "omf",
            "tags": ["omf", "capability"],
            "status": "published",
            "confidence": 1.0,
            "source": "imported",
        },
        sort_keys=False,
    ).strip()
    return "\n".join(
        [
            "---",
            frontmatter,
            "---",
            "",
            f"# {manifest.name}",
            "",
            "## When to Use",
            "",
            f"Use this skill when the task matches: {manifest.normalized_goal}.",
            "",
            "## Procedure",
            "",
            "1. Import the canonical OMF package with `omf capability import`.",
            "2. Load the required context before acting.",
            "3. Identify the smallest relevant surface for the goal.",
            "4. Make the minimal change or output that satisfies the goal.",
            "5. Run the harness checks before accepting the result.",
            "6. Record unresolved failures as OMF evidence.",
            "",
            "## Pitfalls",
            "",
            "- Do not treat OMF as the agent runtime; use Odysseus normally.",
            "- Do not read forbidden context or run risky tools without approval.",
            "",
            "## Verification",
            "",
            _bullets(manifest.harness.required_checks, "Harness checks pass."),
            "- No unrelated changes.",
            "",
            "## Context Policy",
            "",
            "### Required",
            _bullets(manifest.context.required, "No required context recorded."),
            "",
            "### Forbidden",
            _bullets(manifest.context.forbidden, "No forbidden context recorded."),
            "",
        ],
    )


def codex_agents_markdown(manifest: CapabilityManifest) -> str:
    control = manifest.workflow_control
    approvals = _join_or(control.approval_required_actions, "none")
    goal = manifest.normalized_goal
    return "\n".join(
        [
            f"# {manifest.name}",
            "",
            "Repository instructions for an imported OMF capability. Use the local",
            "agent runtime normally; OMF is not the runtime.",
            "",
            "## Activation",
            f"- Apply this capability when the task matches: {goal}.",
            "",
            "## Capability",
            manifest.description,
            "",
            "## Verification",
            "Run the harness checks before accepting a result:",
            _bullets(manifest.harness.required_checks, "No required checks recorded."),
            "",
            "## Safety Boundary",
            f"- Network policy: {control.network_policy}.",
            f"- Commands needing approval: {approvals}.",
            "- Do not read forbidden context:",
            _bullets(manifest.context.forbidden, "No forbidden context recorded."),
            "",
        ],
    )


def _bullets(values: tuple[str, ...], empty: str) -> str:
    if not values:
        return f"- {empty}"
    return "\n".join(f"- {value}" for value in values)


def _import_command(target_runtime: str, target_model: str | None) -> str:
    model = target_model or "<model>"
    return (
        "omf capability import <package.omfcap.tar.gz> "
        f"--runtime {target_runtime} --model {model} --project <project> --validate"
    )


def _join_or(values: tuple[str, ...], empty: str) -> str:
    return ", ".join(values) or empty


def examples_markdown(manifest: CapabilityManifest) -> str:
    return "\n".join(
        [
            "# Examples",
            "",
            "## Success",
            f"- A target run satisfies `{manifest.normalized_goal}` and passes checks.",
            "",
            "## Failure",
            "- Missing context, unavailable tools, or failed checks require evidence.",
            "",
        ],
    )


def harness_markdown(manifest: CapabilityManifest) -> str:
    checks = "\n".join(f"- {check}" for check in manifest.harness.required_checks)
    return f"# Harness\n\n{checks or '- No required checks recorded.'}\n"


def context_markdown(manifest: CapabilityManifest) -> str:
    required = "\n".join(f"- {item}" for item in manifest.context.required)
    forbidden = "\n".join(f"- {item}" for item in manifest.context.forbidden)
    return (
        "# Context Policy\n\n"
        "## Required\n"
        f"{required or '- No required context recorded.'}\n\n"
        "## Forbidden\n"
        f"{forbidden or '- No forbidden context recorded.'}\n"
    )


def yaml_dump(model: StrictModel) -> str:
    data = cast("dict[str, YamlValue]", model.model_dump(mode="json"))
    yaml_text: str = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    return yaml_text
