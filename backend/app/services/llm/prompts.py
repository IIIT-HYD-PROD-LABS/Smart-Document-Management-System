"""Document-type-specific extraction prompts for LLM-based data extraction."""

from __future__ import annotations

# Base system prompt shared by ALL document categories.
# Instructs the LLM on output format, confidence scoring, and summary expectations.
BASE_SYSTEM_PROMPT = (
    "You are a document data extraction assistant. "
    "Your job is to extract structured information from the provided document text.\n\n"
    "Rules:\n"
    "1. Extract all dates (in ISO 8601 format when possible), monetary amounts "
    "(with currency symbol or code), party/entity names, and key terms.\n"
    "2. For each extracted field, estimate a confidence score between 0.0 and 1.0 "
    "based on how clearly the information appears in the text.\n"
    "3. Provide a one-paragraph summary of the document's purpose and key details.\n"
    "4. If a field type has no matches in the document, return an empty list for it.\n"
    "5. Prefer precision over recall -- only extract values you are confident about.\n"
)

# Category-specific hints that tell the LLM what fields to focus on
# for each document type.
CATEGORY_HINTS: dict[str, str] = {
    "invoices": (
        "This is an INVOICE document. Focus on extracting:\n"
        "- Invoice number / reference number\n"
        "- Invoice date and due date\n"
        "- Vendor/seller name and address\n"
        "- Buyer/customer name and address\n"
        "- Line items with descriptions, quantities, unit prices\n"
        "- Subtotal, tax amount (GST/CGST/SGST/IGST if Indian), total amount\n"
        "- Payment terms and bank details\n"
        "- GSTIN / PAN / TAN numbers if present\n"
    ),
    "bills": (
        "This is a BILL or UTILITY BILL document. Focus on extracting:\n"
        "- Bill number / account number / consumer number\n"
        "- Billing period (start date and end date)\n"
        "- Due date and bill date\n"
        "- Service provider name (electricity board, telecom, water, gas)\n"
        "- Customer name and service address\n"
        "- Previous balance, current charges, total amount due\n"
        "- Usage/consumption details (units, kWh, etc.)\n"
        "- Late payment penalty if mentioned\n"
    ),
    "tax": (
        "This is a TAX document (return, assessment, or certificate). Focus on extracting:\n"
        "- PAN number, GSTIN, TAN\n"
        "- Assessment year / financial year\n"
        "- Taxpayer name and address\n"
        "- Gross income / total income / taxable income\n"
        "- Tax computed, TDS deducted, advance tax paid\n"
        "- Refund amount or tax payable\n"
        "- Form number (ITR-1, ITR-2, Form 16, Form 26AS, etc.)\n"
        "- Filing date and acknowledgement number\n"
    ),
    "bank": (
        "This is a BANK document (statement, passbook, or letter). Focus on extracting:\n"
        "- Bank name and branch\n"
        "- Account number and IFSC code\n"
        "- Account holder name\n"
        "- Statement period (start date and end date)\n"
        "- Opening balance and closing balance\n"
        "- Individual transactions: date, description, debit/credit, running balance\n"
        "- Total debits and total credits for the period\n"
        "- Interest earned or charges applied\n"
    ),
    "tickets": (
        "This is a TICKET document (travel, event, or support). Focus on extracting:\n"
        "- Ticket/booking/PNR number\n"
        "- Passenger/attendee name(s)\n"
        "- Event or journey details (route, venue, showtime)\n"
        "- Date and time of travel/event\n"
        "- Departure and arrival locations (for travel)\n"
        "- Seat/berth/class information\n"
        "- Fare/price and any taxes or fees\n"
        "- Booking platform or operator name\n"
    ),
    "upi": (
        "This is a UPI PAYMENT document (receipt, screenshot, or statement). Focus on extracting:\n"
        "- UPI transaction ID / reference number\n"
        "- Transaction date and time\n"
        "- Sender name and UPI ID (VPA)\n"
        "- Receiver/payee name and UPI ID (VPA)\n"
        "- Transaction amount\n"
        "- Payment status (success, failed, pending)\n"
        "- Remarks/note if present\n"
        "- Bank name or UPI app used\n"
    ),
}

# Fallback hint for unknown or unsupported categories.
_GENERIC_HINT = (
    "This document's category is not specifically recognized. Extract:\n"
    "- All dates mentioned in the document\n"
    "- All monetary amounts with currency\n"
    "- All person names, organization names, and entity names\n"
    "- Key terms, reference numbers, and identifiers\n"
    "- Any structured data (tables, lists) present\n"
)


def get_extraction_prompt(category: str) -> str:
    """Return the full system prompt for a given document category.

    Combines the base system prompt with category-specific extraction hints.
    Falls back to a generic hint for unknown categories.

    Args:
        category: Document category string (e.g. "invoices", "tax", "bills").

    Returns:
        Complete system prompt string for the LLM.
    """
    hint = CATEGORY_HINTS.get(category, _GENERIC_HINT)
    return BASE_SYSTEM_PROMPT + "\n" + hint
