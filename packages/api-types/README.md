# @cmc/api-types

TypeScript types generated from the API's OpenAPI document. **Do not edit
`schema.d.ts` by hand** — it is regenerated and CI fails on any difference.

```
make openapi
```

## Why this exists

The frontend and the backend are separate deployments in separate languages.
Without a shared, checked artefact, a backend change that alters a response
shape breaks the frontend at runtime, in production, for users — and nothing in
either repository's tests notices, because each side is internally consistent.

Committing the generated file and failing CI on a diff turns that into a build
error on the pull request that caused it. It is contract testing for the cost
of one CI step.

Phase 0 has no product endpoints, so today this describes `/health` and
`/ready` and nothing else. That is the point: the pipeline is proven while the
contract is trivial, rather than introduced later when it matters and there is
pressure to skip it.
