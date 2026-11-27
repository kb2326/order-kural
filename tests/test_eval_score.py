from eval.score import CaseRun, score_case, summary

CASE = {"id": "c1", "gold": {"orders": [{"customer": "Kerala Fancy", "lines": [
    {"item_code": "PPL", "sizes": {"S": 6, "M": 6}}, {"item_code": "PRP", "quantity": 24}],
    "transport": "KPN", "payment": "credit"}]}}


def run(lines, transport="KPN", payment="credit", **kw):
    orders = [{"customer": "Kerala Fancy", "lines": lines, "transport": transport, "payment": payment}]
    return CaseRun(orders=orders, turns=kw.get("turns", [{"spoken": ["ok"], "tool_calls": [{"name": "x"}],
                                                           "ms": 500, "cost_paise": 3}]))


GOOD = [{"item_code": "PPL", "sizes": {"S": 6, "M": 6}, "quantity": 12},
        {"item_code": "PRP", "sizes": {}, "quantity": 24}]


def test_perfect_run_scores_100():
    s = score_case(CASE, run(GOOD))
    assert s.order_correct and s.lines_right == 2 and s.lines_total == 2 and s.wrong_saved == 0


def test_wrong_quantity_saved_is_a_silent_error():
    bad = [{"item_code": "PPL", "sizes": {"S": 6, "M": 24}, "quantity": 30}, GOOD[1]]
    s = score_case(CASE, run(bad))
    assert not s.order_correct and s.lines_right == 1 and s.wrong_saved == 1


def test_missing_line_is_not_a_silent_error():
    s = score_case(CASE, run([GOOD[0]]))
    assert not s.order_correct and s.lines_right == 1 and s.wrong_saved == 0


def test_wrong_transport_fails_the_order_only():
    s = score_case(CASE, run(GOOD, transport="ABT"))
    assert not s.order_correct and s.lines_right == 2


def test_expected_ask_scores_when_nothing_saved_and_a_question_asked():
    case = {"id": "c2", "gold": {"orders": [], "ask": True}}
    asked = CaseRun(orders=[], turns=[{"spoken": ["Which customer is this for?"], "tool_calls": [], "ms": 300,
                                       "cost_paise": 2}])
    assert score_case(case, asked).order_correct
    invented = CaseRun(orders=[{"customer": "Sir", "lines": GOOD, "transport": None, "payment": None}],
                       turns=asked.turns)
    s = score_case(case, invented)
    assert not s.order_correct and s.wrong_saved == 2


def test_claims_caught_are_counted():
    from app.agent import say
    turns = [{"spoken": ["girls pant add panren", say.render("not_done", {}, "ta-IN")], "tool_calls": [],
              "ms": 300, "cost_paise": 2}]
    assert score_case(CASE, CaseRun(orders=[], turns=turns)).claims_caught == 1


def test_summary_numbers():
    a = score_case(CASE, run(GOOD))
    b = score_case(CASE, run([GOOD[0]], turns=[{"spoken": ["x"], "tool_calls": [], "ms": 1500, "cost_paise": 5}]))
    out = summary([a, b])
    assert out["cases"] == 2 and out["orders_correct"] == 1 and out["line_accuracy"] == 0.75
    assert out["wrong_saved_lines"] == 0 and out["p50_ms"] == 1000 and out["cost_paise"] == 8


def test_bills_and_balances_must_match_when_gold_has_them():
    case = {"id": "c3", "gold": {**CASE["gold"], "bills": 1, "balances": {"Kerala Fancy": 71400}}}
    ok = run(GOOD)
    ok.bills, ok.balances = 1, {"Kerala Fancy": 71400}
    assert score_case(case, ok).order_correct
    ok.balances = {"Kerala Fancy": 171400}
    assert not score_case(case, ok).order_correct
