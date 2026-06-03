from oh_my_field.execution import assess_command_risk


def test_assess_command_risk_classifies_representative_patterns() -> None:
    assert assess_command_risk("rm -rf build").categories == ("destructive",)
    assert assess_command_risk("curl https://example.test").categories == (
        "external_call",
    )
    assert assess_command_risk("cat .env").categories == ("credential_access",)


def test_assess_command_risk_honors_required_category_policy() -> None:
    risk = assess_command_risk(
        "touch output.txt",
        approval_required_categories=("destructive",),
    )

    assert risk.categories == ("write",)
    assert not risk.approval_required
