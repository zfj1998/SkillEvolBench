This fixture models a policy history reviewer that compares three sequential versions of
the same document. The starter already tries to compute two diff rounds and identify
rollbacks, but it still uses positional section pairing, so renumbering and inserted
sections blur the true change history.
