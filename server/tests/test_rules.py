"""T-050: rule engine driven by shared YAML vectors in rules/tests/."""

import copy

import pytest

from app.core.config import RULES_DIR, load_yaml
from app.rules.engine import Beneficiary, DoseGiven, Visit, compute_tasks, load_ruleset, open_tasks

CASES = [
    pytest.param(case, id=f"{path.stem}:{case['name']}")
    for path in sorted((RULES_DIR / "tests").glob("*.yaml"))
    for case in load_yaml(path)["cases"]
]


@pytest.mark.parametrize("case", CASES)
def test_shared_vectors(case):
    tasks = compute_tasks(
        [Beneficiary(**b) for b in case["beneficiaries"]],
        [Visit(**v) for v in case.get("visits", [])],
        [DoseGiven(**d) for d in case.get("doses", [])],
        today=case["today"],
    )
    by_id = {t.rule_id: t for t in tasks}
    for exp in case.get("expect", []):
        assert exp["rule_id"] in by_id, f"missing task {exp['rule_id']}"
        task = by_id[exp["rule_id"]]
        for key, value in exp.items():
            assert getattr(task, key) == value, f"{exp['rule_id']}.{key}"
    for rid in case.get("absent", []):
        assert rid not in by_id, f"unexpected task {rid}"


def test_every_rule_file_is_sourced_and_has_status():
    for name in ("hbnc.yaml", "hbyc.yaml", "uip.yaml", "anc.yaml", "validation.yaml"):
        rule = load_yaml(RULES_DIR / name)
        assert rule.get("source"), name
        assert rule.get("status") in ("draft", "clinician_reviewed"), name


def test_anc_disabled_until_verified():
    assert "ANC" not in {r["programme"] for r in load_ruleset()}


def test_unreviewed_rules_are_marked_advisory():
    from datetime import date

    tasks = compute_tasks([Beneficiary("nb", "newborn", date(2026, 11, 8), "home")], [], [],
                          today=date(2026, 11, 8))
    assert tasks and all(t.advisory for t in tasks)


def test_reasons_in_both_languages():
    from datetime import date

    (t,) = [t for t in compute_tasks([Beneficiary("nb", "newborn", date(2026, 11, 8), "home")],
                                     [], [], today=date(2026, 11, 8)) if t.rule_id == "hbnc_d1"]
    assert "day 1" in t.reason_en and "दिन 1" in t.reason_hi


def test_open_tasks_sorted_by_priority():
    from datetime import date

    bens = [Beneficiary("a", "newborn", date(2026, 11, 8), "institution"),
            Beneficiary("b", "child", date(2026, 2, 7))]
    tasks = open_tasks(compute_tasks(bens, [], [], today=date(2026, 11, 12)))
    ranks = [t.rank for t in tasks]
    assert ranks == sorted(ranks)
    assert tasks[0].status == "overdue"


def test_feature_flags_switch_vaccines():
    from datetime import date

    rules = copy.deepcopy(load_ruleset())
    uip = next(r for r in rules if r["programme"] == "UIP")
    uip["features"].update(je=True, rota=False)
    ids = {t.rule_id for t in compute_tasks([Beneficiary("c", "child", date(2026, 9, 1))], [], [],
                                            today=date(2026, 10, 13), rules=rules)}
    assert {"je1", "je2"} <= ids
    assert not ids & {"rota1", "rota2", "rota3"}


def test_day_numbering_switch():
    from datetime import date

    rules = copy.deepcopy(load_ruleset())
    hbnc = next(r for r in rules if r["programme"] == "HBNC")
    hbnc["day_numbering"] = "birth_is_day_0"
    tasks = compute_tasks([Beneficiary("nb", "newborn", date(2026, 11, 8), "institution")], [], [],
                          today=date(2026, 11, 8), rules=rules)
    d3 = next(t for t in tasks if t.rule_id == "hbnc_d3")
    assert d3.due_date == date(2026, 11, 11)
