"""The AI's output contract: what one voice piece asks to change.

The AI never computes money. It only says which customer and which change; code applies it.
"""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, NonNegativeInt, PositiveInt


class AddLine(BaseModel):
    op: Literal["add_line"]
    item_code: str | None = None
    name_as_spoken: str
    sizes: dict[str, NonNegativeInt] = {}
    quantity_total: NonNegativeInt | None = None
    rate_spoken: PositiveInt | None = None  # whole rupees, only if the speaker said a rate


class ChangeLine(BaseModel):
    op: Literal["change_line"]
    item_code: str
    sizes: dict[str, NonNegativeInt] | None = None
    quantity_total: NonNegativeInt | None = None
    rate_spoken: PositiveInt | None = None


class RemoveLine(BaseModel):
    op: Literal["remove_line"]
    item_code: str


class SetField(BaseModel):
    op: Literal["set_field"]
    field: Literal["transport", "payment", "city", "gstin", "state"]
    value: str


Change = Annotated[AddLine | ChangeLine | RemoveLine | SetField, Field(discriminator="op")]


class CustomerRef(BaseModel):
    """Who the piece is for. A forwarded customer note often never says the shop's name: then name is None."""
    name_as_spoken: str | None = None
    city: str | None = None
    match: Literal["new", "existing"] = "new"
    order_id: int | None = None  # the open order the AI picked, when match is "existing"
    confidence: Literal["high", "low"] = "high"

    @property
    def said(self) -> bool:
        return bool(self.order_id or (self.name_as_spoken and self.name_as_spoken.strip()))


class PieceResult(BaseModel):
    intent: Literal["order_changes", "bill_order", "mark_shipped", "record_payment", "unclear"]
    customer: CustomerRef | None
    changes: list[Change] = []
    amount: PositiveInt | None = None
    uncertain: list[str] = []
