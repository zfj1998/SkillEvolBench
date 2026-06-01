This fixture models a report-audit helper that compares an internal draft against a
published version. The starter can detect text changes but does not yet reason about
whether those edits distort the underlying data context, even though the pipeline now
has a separate numeric-evidence helper for that purpose.
