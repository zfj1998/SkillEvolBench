# Task: Turn the Sales Query Into a Valid Search Request

I need a report generated from the natural-language request in `/root/task/query.txt`.

The pipeline in `/root/task` is supposed to read the user query, infer the search parameters, validate them, normalize them into the API contract, call the sales search, and then summarize the result. Right now that flow is not reliable enough.

Start here:
- `/root/task/README.md`
- `/root/task/pipeline.py`
- `/root/task/query.txt`
- `/root/task/docs/crm-glossary.md`

What I need:
1. Extract the search intent from the user query.
2. Normalize the parameters into the API's expected shape: map `California` to `CA`, derive the previous full month as `2025-03-01` through `2025-03-31`, and preserve `amount`/`desc` sorting.
3. Validate them before the outbound call.
4. Produce the final summary report through the dictionary returned by `run_pipeline(...)`, and save your code changes under `/root/task`.

The returned report schema is `{ "count": int, "total_amount": number, "average_amount": number, "rows": [ ... ] }`; rows should be sorted by amount descending.

Do not move the project outside `/root/task`, and do not replace it with a stub.
