# T1 Starter Notes

This task models a realistic contact-unification pipeline:

- `crm.csv` is the external go-to-market address book.
- `hr.csv` is the internal employee directory with more formal names.
- `email_contacts.csv` is the marketing list with nicknames and abbreviated names.

Important fixture properties:

- Three specific contacts now require phone-assisted fuzzy reconciliation because one
  source is missing email:
  - `P002` (`Robert` / `Bob`)
  - `P006` (`James` / `Jim`)
  - `P041` (`Owen Roberts` / `O. Roberts`)
- Two different `John Smith` records intentionally exist and must remain separate.

The starter pipeline already has:

- source adapters
- an identity matcher
- a merge policy
- a merge audit

But the matching layer is still too conservative. It over-trusts exact identifiers and
does not correctly promote nickname/initial variants when email is missing in one source.
