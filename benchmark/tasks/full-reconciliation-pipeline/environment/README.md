# T6 Starter Notes

This task combines the whole family:

- fuzzy entity matching across three systems
- deep nested conflict reporting
- explicit source-priority resolution
- provenance tracking in the master output

Fixture twist:

- several overlapping records now have a missing email in one source
- names still vary (`Tom` / `Thomas`, `Rick` / `Richard`, initials)
- nested address / compensation conflicts still exist on a subset

The starter normalization layer is mostly in place, but the entity matcher still behaves
like an exact-email join and the conflict reporter only sees clusters that exact matching
already recovered.
