# ADR-007: Bill as a printable HTML page plus a PDF, shared through the phone's share sheet

- **Date:** 2026-11-27 · **Status:** Accepted
- **Context:** the buyer should get the GST bill on WhatsApp. WhatsApp click-to-chat links can only pre-fill text; they
  cannot attach a file. The real WhatsApp Business API needs Meta approval (days to weeks).
- **Decision:** an HTML bill with print styles (Save as PDF on any device) and a server-made PDF (`fpdf2`, pure
  Python). On phones, the "Share bill" button uses the browser's share sheet to send the PDF to WhatsApp; elsewhere
  it downloads. Khata reminders use a text-only WhatsApp link.
- **Consequences:** works today with no approvals. The owner taps Send in WhatsApp himself (no automatic sending),
  which also keeps a human in the loop.
