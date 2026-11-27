import pytest
from pydantic import TypeAdapter, ValidationError

from app.domain.changes import AddLine, Change, ChangeLine, PieceResult, RemoveLine, SetField


def test_parses_mixed_changes():
    result = PieceResult.model_validate({
        "intent": "order_changes",
        "customer": {"name_as_spoken": "Kerala Fancy", "city": "Palakkad"},
        "changes": [
            {"op": "add_line", "item_code": "PRP", "name_as_spoken": "print palazzo", "quantity_total": 24},
            {"op": "change_line", "item_code": "CRT", "sizes": {"S": 12}},
            {"op": "remove_line", "item_code": "KPT"},
            {"op": "set_field", "field": "transport", "value": "KPN"},
        ],
    })
    assert [type(c) for c in result.changes] == [AddLine, ChangeLine, RemoveLine, SetField]
    assert result.customer.match == "new"
    assert result.customer.confidence == "high"


def test_negative_quantity_rejected():
    with pytest.raises(ValidationError):
        AddLine(op="add_line", item_code="CRT", name_as_spoken="crop top", sizes={"M": -2})


def test_unknown_op_rejected():
    with pytest.raises(ValidationError):
        TypeAdapter(Change).validate_python({"op": "delete_everything", "item_code": "CRT"})


def test_payment_set_field():
    change = SetField(op="set_field", field="payment", value="credit")
    assert change.field == "payment" and change.value == "credit"


def test_piece_result_json_schema_exists():
    assert PieceResult.model_json_schema()["title"] == "PieceResult"


def test_customer_match_rejects_free_text():
    from app.domain.changes import CustomerRef
    with pytest.raises(ValidationError):
        CustomerRef(name_as_spoken="Kerala Fancy", match="existing-ish")
