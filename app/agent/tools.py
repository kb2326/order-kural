"""The tool menu shown to the LLM (OpenAI-style function JSON, which Sarvam and Pipecat both accept). The
descriptions are part of the prompt: they say when to use each tool."""
from __future__ import annotations

ITEM = {
    "type": "object",
    "properties": {
        "name_as_spoken": {"type": "string", "description": "Item name exactly as said, e.g. 'plain palazzo'"},
        "item_code": {"type": "string", "description": "Code from the item list, or empty if not sure"},
        "sizes": {"type": "object", "additionalProperties": {"type": "integer"},
                  "description": "Size label to quantity, e.g. {\"S\": 6, \"M\": 6} or {\"1-10 yrs\": 50}"},
        "quantity_total": {"type": "integer", "description": "Only when no sizes were said"},
        "rate_spoken": {"type": "integer", "description": "Rupees per piece, only if a rate was said"},
    },
    "required": ["name_as_spoken"],
}
CUSTOMER = {"type": "string", "description": "Shop name only, as said, e.g. 'Kerala Fancy'. Empty if not said."}


def _fn(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {"type": "function", "function": {"name": name, "description": description, "parameters": {
        "type": "object", "properties": properties, "required": required}}}


TOOL_SPECS = [
    _fn("find_customer", "Look up a customer by shop name (and city) before you are sure who is meant.",
        {"name": {"type": "string"}, "city": {"type": "string"}}, ["name"]),
    _fn("get_open_order", "Read what a customer has ordered so far.", {"customer": CUSTOMER}, ["customer"]),
    _fn("add_to_order", "Add items the owner said to a customer's order. Use for any new order or extra items. "
                        "If the same message names a transport or payment, pass them here too.",
        {"customer": CUSTOMER, "items": {"type": "array", "items": ITEM}, "city": {"type": "string"},
         "transport": {"type": "string", "description": "Carrier name, e.g. KPN, Girnar Transport"},
         "payment": {"type": "string", "enum": ["cash", "upi", "credit", "bank"]},
         "gstin": {"type": "string", "description": "Buyer's 15-character GSTIN, only if said"},
         "state": {"type": "string", "description": "Buyer's state, e.g. Kerala, only if said"}},
        ["customer", "items"]),
    _fn("change_line", "Change the quantity or sizes of an item already in the order.",
        {"customer": CUSTOMER, "item_code": {"type": "string"},
         "sizes": {"type": "object", "additionalProperties": {"type": "integer"}},
         "quantity_total": {"type": "integer"}}, ["customer", "item_code"]),
    _fn("remove_line", "Remove an item from the order.", {"customer": CUSTOMER, "item_code": {"type": "string"}},
        ["customer", "item_code"]),
    _fn("set_detail", "Set transport (a carrier name like KPN or Girnar Transport), payment (cash, upi, credit, "
                      "bank), the buyer's GSTIN, or the buyer's state (for the GST invoice).",
        {"customer": CUSTOMER, "field": {"type": "string", "enum": ["transport", "payment", "gstin", "state"]},
         "value": {"type": "string"}}, ["customer", "field", "value"]),
    _fn("bill_order", "The owner asked to bill / make the GST invoice for a customer's order.", {"customer": CUSTOMER},
        ["customer"]),
    _fn("record_payment", "A customer paid money (e.g. 'Kerala Fancy paid 10,000 by UPI').",
        {"customer": CUSTOMER, "amount_rupees": {"type": "integer"},
         "mode": {"type": "string", "enum": ["cash", "upi", "credit", "bank"]}},
        ["customer", "amount_rupees", "mode"]),
    _fn("mark_shipped", "The goods for a customer were sent (optionally by which transport).",
        {"customer": CUSTOMER, "transport": {"type": "string"}}, ["customer"]),
    _fn("ask_shop", "Answer a question about the shop: 'to_ship' = what is still to ship; 'customer' = a customer's "
                    "open order and balance; 'item_count' = how many of an item were ordered this week.",
        {"question": {"type": "string", "enum": ["to_ship", "customer", "item_count"]}, "customer": CUSTOMER,
         "item": {"type": "string"}}, ["question"]),
    _fn("confirm_pending", "The owner said sari / seri / haan / ok / howdu / correct to what is waiting. Call it "
                           "whenever he agrees; the code checks his words.", {}, []),
    _fn("discard_pending", "The owner said cancel / vendaam / nahi to what is waiting.", {}, []),
]
