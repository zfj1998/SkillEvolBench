# Release Checklist for v2.1.0

1. Merge `develop` into the release branch.
2. Resolve any conflicts without dropping release hotfixes.
3. Run the authentication regression tests.
4. Set the final release version to `2.1.0`.
5. Update the changelog entry so it reflects the release, not the old hotfix tag or the dev placeholder.

Auth-specific reminder:
- The 2.0.1 hotfix added rate-limiting behavior after an incident review.
- The 2.1 line added `remember_me` support for longer-lived tokens.
- Release code needs both.
