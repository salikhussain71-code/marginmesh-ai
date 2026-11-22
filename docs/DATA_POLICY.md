# Data policy

- This repository contains **only synthetic, fictional data** (`data/sample`).
- Do not commit real purchase orders, invoices, costing sheets, bank details or buyer names.
  `.gitignore` excludes `private/` and `real_data/` as a safety net.
- Real documents must only be processed with the owner's written permission, locally, and should
  be anonymised first.
- The tool does not send data to any external service. There is no telemetry.
- The optional API has no authentication; run it on `127.0.0.1` only.
