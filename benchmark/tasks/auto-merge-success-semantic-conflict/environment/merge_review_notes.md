# Merge Review Notes

Background:
- The onboarding team added email validation for the self-serve registration flow.
- The SMS team added phone validation for invite-based registration.
- Git reported a clean merge because the functions landed in different parts of the same file.

What people are seeing:
- Registration now rejects obviously valid emails.
- Phone validation still appears to work in some paths.

Suspicion:
- This may be a post-merge semantic collision rather than a parser or import problem.
