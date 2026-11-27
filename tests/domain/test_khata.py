from app.domain.khata import balance


def e(id, kind, amount, reverses=None):
    return {"id": id, "kind": kind, "amount_paise": amount, "reverses": reverses}


def test_balance_bill_minus_payment():
    assert balance([e(1, "bill", 2655200), e(2, "payment", 1000000)]) == 1655200


def test_overpayment_gives_negative_balance():
    assert balance([e(1, "bill", 500000), e(2, "payment", 600000)]) == -100000


def test_reversal_cancels_its_entry():
    entries = [e(1, "bill", 500000), e(2, "payment", 200000), e(3, "reversal", 200000, reverses=2)]
    assert balance(entries) == 500000


def test_empty_khata_is_zero():
    assert balance([]) == 0
