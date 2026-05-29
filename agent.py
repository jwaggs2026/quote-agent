import os
import json
import anthropic
from dotenv import load_dotenv
from tools import lookup_vendor_quickbooks, draft_quote_email

load_dotenv()

client = anthropic.Anthropic()

SYSTEM_PROMPT = """You are a quote-requesting agent for Midstate.

You MUST always call both tools in this exact order:
1. Call lookup_vendor_quickbooks with the vendor name.
2. Immediately after receiving the result, call draft_quote_email using the rep_name and rep_email_address from step 1 along with the items list from the user message.

Do not stop after step 1. Do not produce any text response until both tools have been called and draft_quote_email has returned. After draft_quote_email returns, respond with a brief confirmation that the draft is ready."""

TOOL_DEFINITIONS = [
    {
        "name": "lookup_vendor_quickbooks",
        "description": "Call this tool with a vendor name from the form input to retrieve the vendor's rep name and email from QuickBooks before drafting the quote email.",
        "input_schema": {
            "type": "object",
            "properties": {
                "vendor_name": {
                    "type": "string",
                    "description": "The vendor name from the form input to look up in QuickBooks",
                }
            },
            "required": ["vendor_name"],
        },
    },
    {
        "name": "draft_quote_email",
        "description": "Call this tool with vendor contact information from lookup_vendor_quickbooks and the items list from the input form to draft a quote email.",
        "input_schema": {
            "type": "object",
            "properties": {
                "vendor_name": {"type": "string", "description": "The vendor name from the form input"},
                "rep_name": {"type": "string", "description": "The vendor rep name from lookup_vendor_quickbooks"},
                "email": {"type": "string", "description": "The rep email from lookup_vendor_quickbooks"},
                "items": {
                    "type": "array",
                    "description": "The list of line items from the input form",
                    "items": {
                        "type": "object",
                        "properties": {
                            "material": {"type": "string"},
                            "size": {"type": "string"},
                            "quantity": {"type": "string"},
                            "details": {"type": "string"},
                        },
                        "required": ["material", "size", "quantity"],
                    },
                },
            },
            "required": ["vendor_name", "rep_name", "email", "items"],
        },
    },
]

TOOL_DISPATCH = {
    "lookup_vendor_quickbooks": lookup_vendor_quickbooks,
    "draft_quote_email": draft_quote_email,
}


def run_agent(vendor_name: str, items: list) -> dict:
    """Run the agent loop and return the draft email dict."""
    lines = []
    for idx, item in enumerate(items, 1):
        parts = f"Material: {item['material']} | Size: {item['size']} | Qty: {item['quantity']}"
        if item.get("details"):
            parts += f" | Details: {item['details']}"
        lines.append(f"{idx}. {parts}")
    items_text = "\n".join(lines)

    messages = [
        {
            "role": "user",
            "content": (
                f"Please look up the vendor and draft a quote email for the following request:\n"
                f"Vendor: {vendor_name}\n\n"
                f"Line items:\n{items_text}"
            ),
        }
    ]

    draft = None

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                fn = TOOL_DISPATCH.get(block.name)
                if fn is None:
                    result = {"error": f"Tool '{block.name}' not available in this step"}
                else:
                    result = fn(**block.input)
                    if block.name == "draft_quote_email":
                        draft = result
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    }
                )
            messages.append({"role": "user", "content": tool_results})

    if draft is None:
        raise RuntimeError("Agent completed without calling draft_quote_email")

    return draft
