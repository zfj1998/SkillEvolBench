# Metro Market Merge

`population.csv` comes from a planning export and uses long-form city names.

`gdp_data.csv` comes from an economics feed that includes abbreviations, non-breaking spaces, punctuation variants, and duplicate city rows from different source candidates.

The current merge logic only handles light whitespace cleanup, so abbreviations like `NYC` still fail to align with the planning dataset.
