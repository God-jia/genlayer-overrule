import json

RULES = [
    {
        "id": "H1",
        "title": "Harassment",
        "text": "Do not direct abusive, threatening or demeaning language at another person.",
    },
    {
        "id": "S2",
        "title": "Spam",
        "text": "Do not post repetitive promotional content that is unrelated to the topic.",
    },
]

CONTENT_URL = "https://example.com/post/1234"
REASON = "The post targets another member with insulting language about their appearance."


def _deploy(direct_deploy):
    return direct_deploy("contracts/overrule.py")


def _setup(contract, direct_vm, direct_alice, direct_bob):
    """Publish one rulebook per party and return (rulebook_id, alice_addr, bob_addr).

    Reading the platform back from the contract guarantees the address string
    matches exactly what the contract itself produced.
    """
    direct_vm.sender = direct_alice
    rulebook_id = contract.publish_rulebook("Community Guidelines v1", json.dumps(RULES))
    alice = json.loads(contract.get_rulebook(rulebook_id))["platform"]

    direct_vm.sender = direct_bob
    bob_rulebook = contract.publish_rulebook("Bob Rules v1", json.dumps(RULES))
    bob = json.loads(contract.get_rulebook(bob_rulebook))["platform"]

    return rulebook_id, alice, bob


def _issue(contract, direct_vm, direct_alice, rulebook_id, subject, cited=("H1",)):
    direct_vm.sender = direct_alice
    return contract.issue_decision(
        rulebook_id,
        subject,
        "MOD-1001",
        CONTENT_URL,
        json.dumps(list(cited)),
        "remove",
        REASON,
    )


def _mock_content(direct_vm, body):
    direct_vm.mock_web(r".*example\.com/post/1234.*", {"status": 200, "body": body})


def _mock_verdicts(direct_vm, payload):
    direct_vm.mock_llm(r".*content-moderation appeal court.*", json.dumps(payload))


def _appeal(contract, direct_vm, direct_bob, decision_id):
    direct_vm.sender = direct_bob
    contract.appeal(
        decision_id,
        "The post quoted a public news headline and did not address any member directly, "
        "so the cited rule does not cover it.",
        "[]",
    )


# --------------------------------------------------------------------- rulebooks


def test_publish_rulebook_and_read(direct_vm, direct_deploy, direct_alice):
    contract = _deploy(direct_deploy)
    direct_vm.sender = direct_alice

    rulebook_id = contract.publish_rulebook("Community Guidelines v1", json.dumps(RULES))
    assert rulebook_id == 0
    assert contract.total_rulebooks() == 1

    record = json.loads(contract.get_rulebook(rulebook_id))
    assert record["name"] == "Community Guidelines v1"
    assert record["rules"][0]["id"] == "H1"
    assert record["digest"].startswith("sha256:")


def test_publish_rejects_bad_rules_json(direct_vm, direct_deploy, direct_alice):
    contract = _deploy(direct_deploy)
    direct_vm.sender = direct_alice

    with direct_vm.expect_revert("must be a JSON array"):
        contract.publish_rulebook("Community Guidelines v1", "not json")


def test_publish_rejects_duplicate_rule_ids(direct_vm, direct_deploy, direct_alice):
    contract = _deploy(direct_deploy)
    direct_vm.sender = direct_alice

    duplicated = json.dumps([RULES[0], RULES[0]])
    with direct_vm.expect_revert("Duplicate rule id"):
        contract.publish_rulebook("Community Guidelines v1", duplicated)


def test_publish_rejects_short_rule_text(direct_vm, direct_deploy, direct_alice):
    contract = _deploy(direct_deploy)
    direct_vm.sender = direct_alice

    thin = json.dumps([{"id": "H1", "title": "Harassment", "text": "be nice"}])
    with direct_vm.expect_revert("Rule text must be"):
        contract.publish_rulebook("Community Guidelines v1", thin)


# --------------------------------------------------------------------- decisions


def test_issue_decision_only_by_publisher(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = _deploy(direct_deploy)
    rulebook_id, _alice, bob = _setup(contract, direct_vm, direct_alice, direct_bob)

    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("Only the rulebook publisher"):
        contract.issue_decision(
            rulebook_id, bob, "MOD-1001", CONTENT_URL, json.dumps(["H1"]), "remove", REASON
        )


def test_issue_decision_rejects_unknown_cited_rule(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = _deploy(direct_deploy)
    rulebook_id, _alice, bob = _setup(contract, direct_vm, direct_alice, direct_bob)

    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("not in the rulebook"):
        contract.issue_decision(
            rulebook_id, bob, "MOD-1001", CONTENT_URL, json.dumps(["Z9"]), "remove", REASON
        )


def test_issue_decision_rejects_self_target(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = _deploy(direct_deploy)
    rulebook_id, alice, _bob = _setup(contract, direct_vm, direct_alice, direct_bob)

    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("cannot issue a decision against itself"):
        contract.issue_decision(
            rulebook_id, alice, "MOD-1001", CONTENT_URL, json.dumps(["H1"]), "remove", REASON
        )


def test_issue_decision_records_and_counts(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = _deploy(direct_deploy)
    rulebook_id, alice, bob = _setup(contract, direct_vm, direct_alice, direct_bob)

    decision_id = _issue(contract, direct_vm, direct_alice, rulebook_id, bob)
    assert decision_id == 0
    assert contract.total_decisions() == 1

    record = json.loads(contract.get_decision(decision_id))
    assert record["status"] == "issued"
    assert record["subject"] == bob
    assert record["cited_rule_ids"] == ["H1"]
    assert record["outcome"] is None

    stats = json.loads(contract.get_platform_stats(alice))
    assert stats["issued"] == 1
    assert stats["adjudicated"] == 0


# ------------------------------------------------------------------------ appeal


def test_appeal_only_by_subject(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = _deploy(direct_deploy)
    rulebook_id, _alice, bob = _setup(contract, direct_vm, direct_alice, direct_bob)
    decision_id = _issue(contract, direct_vm, direct_alice, rulebook_id, bob)

    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("Only the subject"):
        contract.appeal(decision_id, "x" * 60, "[]")


def test_appeal_requires_short_argument(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = _deploy(direct_deploy)
    rulebook_id, _alice, bob = _setup(contract, direct_vm, direct_alice, direct_bob)
    decision_id = _issue(contract, direct_vm, direct_alice, rulebook_id, bob)

    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("Appeal argument must be"):
        contract.appeal(decision_id, "too short", "[]")


def test_appeal_twice_reverts(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = _deploy(direct_deploy)
    rulebook_id, _alice, bob = _setup(contract, direct_vm, direct_alice, direct_bob)
    decision_id = _issue(contract, direct_vm, direct_alice, rulebook_id, bob)

    _appeal(contract, direct_vm, direct_bob, decision_id)

    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("not open for appeal"):
        contract.appeal(decision_id, "y" * 60, "[]")


def test_adjudicate_requires_appeal(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = _deploy(direct_deploy)
    rulebook_id, _alice, bob = _setup(contract, direct_vm, direct_alice, direct_bob)
    decision_id = _issue(contract, direct_vm, direct_alice, rulebook_id, bob)

    with direct_vm.expect_revert("not under appeal"):
        contract.adjudicate(decision_id)


# ------------------------------------------------------------------- adjudication


def test_adjudicate_upheld(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = _deploy(direct_deploy)
    rulebook_id, alice, bob = _setup(contract, direct_vm, direct_alice, direct_bob)
    decision_id = _issue(contract, direct_vm, direct_alice, rulebook_id, bob)
    _appeal(contract, direct_vm, direct_bob, decision_id)

    _mock_content(direct_vm, "<html><body>You are pathetic and everyone hates you.</body></html>")
    _mock_verdicts(
        direct_vm,
        {
            "content_available": True,
            "rule_verdicts": [
                {"id": "H1", "verdict": "applied", "reason": "The post demeans a person."}
            ],
            "confidence": 91,
            "reasoning": "The content plainly targets a person with insulting language.",
        },
    )

    contract.adjudicate(decision_id)

    record = json.loads(contract.get_decision(decision_id))
    assert record["status"] == "adjudicated"
    assert record["outcome"]["result"] == "upheld"
    assert record["outcome"]["rule_verdicts"][0]["verdict"] == "applied"

    stats = json.loads(contract.get_platform_stats(alice))
    assert stats["adjudicated"] == 1
    assert stats["upheld"] == 1
    assert stats["overturned"] == 0


def test_adjudicate_overturned(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = _deploy(direct_deploy)
    rulebook_id, alice, bob = _setup(contract, direct_vm, direct_alice, direct_bob)
    decision_id = _issue(contract, direct_vm, direct_alice, rulebook_id, bob)
    _appeal(contract, direct_vm, direct_bob, decision_id)

    _mock_content(direct_vm, "<html><body>GenLayer shipped a new testnet release today.</body></html>")
    _mock_verdicts(
        direct_vm,
        {
            "content_available": True,
            "rule_verdicts": [
                {"id": "H1", "verdict": "misapplied", "reason": "No person is addressed."}
            ],
            "confidence": 84,
            "reasoning": "The rule prohibits harassment, and the post contains none.",
        },
    )

    contract.adjudicate(decision_id)

    record = json.loads(contract.get_decision(decision_id))
    assert record["outcome"]["result"] == "overturned"

    stats = json.loads(contract.get_platform_stats(alice))
    assert stats["overturned"] == 1
    assert stats["upheld"] == 0


def test_adjudicate_remanded_on_mixed_verdicts(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = _deploy(direct_deploy)
    rulebook_id, alice, bob = _setup(contract, direct_vm, direct_alice, direct_bob)
    decision_id = _issue(
        contract, direct_vm, direct_alice, rulebook_id, bob, cited=("H1", "S2")
    )
    _appeal(contract, direct_vm, direct_bob, decision_id)

    _mock_content(direct_vm, "<html><body>Buy my course! Also you are an idiot.</body></html>")
    _mock_verdicts(
        direct_vm,
        {
            "content_available": True,
            "rule_verdicts": [
                {"id": "H1", "verdict": "applied", "reason": "It insults a person."},
                {"id": "S2", "verdict": "unsupported", "reason": "It is not repetitive."},
            ],
            "confidence": 70,
            "reasoning": "One rule holds and one does not.",
        },
    )

    contract.adjudicate(decision_id)

    record = json.loads(contract.get_decision(decision_id))
    assert record["outcome"]["result"] == "remanded"
    assert len(record["outcome"]["rule_verdicts"]) == 2

    stats = json.loads(contract.get_platform_stats(alice))
    assert stats["remanded"] == 1


def test_adjudicate_remands_when_content_unavailable(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = _deploy(direct_deploy)
    rulebook_id, alice, bob = _setup(contract, direct_vm, direct_alice, direct_bob)
    decision_id = _issue(contract, direct_vm, direct_alice, rulebook_id, bob)
    _appeal(contract, direct_vm, direct_bob, decision_id)

    direct_vm.mock_web(
        r".*example\.com/post/1234.*", {"status": 404, "body": "gone"}
    )
    _mock_verdicts(
        direct_vm,
        {
            "content_available": False,
            "rule_verdicts": [
                {"id": "H1", "verdict": "applied", "reason": "Assumed from the report."}
            ],
            "confidence": 40,
            "reasoning": "The content could not be retrieved.",
        },
    )

    contract.adjudicate(decision_id)

    record = json.loads(contract.get_decision(decision_id))
    assert record["outcome"]["content_available"] is False
    assert record["outcome"]["result"] == "remanded"

    stats = json.loads(contract.get_platform_stats(alice))
    assert stats["remanded"] == 1


def test_adjudicate_twice_reverts(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = _deploy(direct_deploy)
    rulebook_id, _alice, bob = _setup(contract, direct_vm, direct_alice, direct_bob)
    decision_id = _issue(contract, direct_vm, direct_alice, rulebook_id, bob)
    _appeal(contract, direct_vm, direct_bob, decision_id)

    _mock_content(direct_vm, "<html><body>You are pathetic.</body></html>")
    _mock_verdicts(
        direct_vm,
        {
            "content_available": True,
            "rule_verdicts": [
                {"id": "H1", "verdict": "applied", "reason": "It demeans a person."}
            ],
            "confidence": 90,
            "reasoning": "Clear harassment.",
        },
    )

    contract.adjudicate(decision_id)

    with direct_vm.expect_revert("not under appeal"):
        contract.adjudicate(decision_id)


# ------------------------------------------------------------------------ views


def test_unknown_ids_revert(direct_vm, direct_deploy, direct_alice):
    contract = _deploy(direct_deploy)
    direct_vm.sender = direct_alice

    with direct_vm.expect_revert("Unknown rulebook id"):
        contract.get_rulebook(999)
    with direct_vm.expect_revert("Unknown decision id"):
        contract.get_decision(999)


def test_stats_start_at_zero(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = _deploy(direct_deploy)
    _rulebook_id, alice, _bob = _setup(contract, direct_vm, direct_alice, direct_bob)

    stats = json.loads(contract.get_platform_stats(alice))
    assert stats == {
        "issued": 0,
        "adjudicated": 0,
        "upheld": 0,
        "overturned": 0,
        "remanded": 0,
    }
