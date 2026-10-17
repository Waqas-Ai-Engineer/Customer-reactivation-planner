# Compliance notes (not legal advice)

This tool only plans messages; you send them. Before contacting past customers:

- Get and record consent where required (US TCPA for SMS, GDPR/ePrivacy in the EU/UK, CASL in Canada, CAN-SPAM for email).
- Always honour opt-outs: set `opted_out` to yes in your CSV as soon as someone replies STOP.
- Respect quiet hours and local rules; keep the cooldown setting sensible.
- Keep customer CSVs out of Git (`.gitignore` already excludes `my_*.csv`).
- Healthcare (HIPAA etc.): do not put diagnoses or treatment detail in messages.
