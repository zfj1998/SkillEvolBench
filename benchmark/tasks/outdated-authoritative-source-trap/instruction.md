# Task: Estimate global AI investment without being trapped by stale authority

The task files are in `/root/task`.

Produce a current global AI investment estimate from the available grounded sources.
The current starter blindly trusts the most authoritative-seeming source even when it is stale.

Save the result to `/root/task/output/investment_estimate.json`.
Output contract: write `/root/task/output/investment_estimate.json`. Follow the field structure documented by the starter pipeline and `schemas/output_schema.json` when the output is JSON.

Required behavior: The estimate should use current investment evidence and explain why older authoritative figures are not treated as the current market value.
