# Fix the blank GraphQL profile fields

The profile service is in `/root/task`. The frontend team says the profile page renders blank name and email values, but the GraphQL endpoint still returns HTTP 200 and the response shape looks normal.

Please fix the underlying issue in place under `/root/task`:
- `userName` and `emailAddress` should come back with real values
- schema and query behavior should stay aligned
- do not work around this in the frontend query layer

Start here:
- `/root/task/schema.graphql`
- `/root/task/app.py`
- `/root/task/resolvers/user_resolver.py`
- `/root/task/models/user.py`
- `/root/task/frontend/queries.graphql`

Keep the project under `/root/task`. Do not replace the GraphQL flow with a stubbed response.

Deliverable note: no standalone output file is required. The required artifacts are the edited GraphQL schema/resolver/model files under `/root/task`; the verifier checks the existing GraphQL JSON response fields `userName` and `emailAddress`.
