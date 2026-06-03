# Alternatives to pyado

There are several ways to work with the Azure DevOps REST API from Python.
This page gives an honest overview so you can choose what is right for your
project.

---

## Microsoft's official `azure-devops` package

The [`azure-devops`][azure-devops-pkg] package is the officially supported
Python client from Microsoft. It is auto-generated from the REST API OpenAPI
spec and covers the full surface area of the API. If you need an endpoint that
pyado does not yet cover, or if Microsoft-maintained support is a firm
requirement, it is worth a look.

**Where it shows its auto-generated origins:**

- Models are largely untyped — fields are annotated as `object`, so IDEs
  cannot offer meaningful completion or catch mistakes at write time.
- Optional fields are not always distinguished from required ones in the
  type signatures.
- Pagination is inconsistent: some list methods return all pages
  automatically, others require manual iteration with continuation tokens,
  and the pattern differs by endpoint family.
- Docstrings describe wire-format field names rather than intent, which
  makes it harder to understand what a parameter actually controls.

These are not criticisms of the team — they are inherent trade-offs of
generating a client from a large, heterogeneous API spec. The generated
client is a faithful reflection of the API; it just leaves more work for
the caller.

---

## Calling the REST API directly

Some teams skip any client library and issue raw `requests` calls with
manually constructed headers, URL templates, and JSON payloads.

This is completely reasonable for one-off scripts or when you only need a
single endpoint. It becomes painful at scale: every caller reimplements
auth, retry logic, pagination, and dict-based access with no safety net.

---

## pyado

pyado is hand-written rather than generated. Every function is authored
explicitly, which makes the library smaller in scope but more deliberate in
design.

**What pyado focuses on:**

- Every function returns a [Pydantic] model — fields are typed, optional
  fields are marked `... | None`, and bad inputs are caught before any HTTP
  request is made.
- Authentication, retries, and content-type negotiation are centralised in
  one place; callers never touch them.
- Paginated endpoints are plain Python generators — iterate with a `for`
  loop and pagination happens automatically.
- A two-layer architecture (`raw` for one-function-per-endpoint, `high` for
  payload construction and multi-step helpers) keeps concerns separated and
  makes the library easy to extend.

**Honest limitations:**

- pyado covers the endpoints the authors needed; there will be gaps. Check
  the [API reference] before committing to it if you need an obscure endpoint.
- It is not backed by Microsoft and does not track the OpenAPI spec
  automatically, so new API features require manual additions.
- The project is young and the API is not yet stable across minor versions.

---

## Summary table

| | `azure-devops` | raw `requests` | pyado |
|---|:---:|:---:|:---:|
| Official Microsoft support | ✓ | — | — |
| Full API coverage | ✓ | ✓ | partial |
| Typed return values | — | — | ✓ |
| IDE completion on models | — | — | ✓ |
| Automatic pagination | partial | — | ✓ |
| Auth handled for you | ✓ | — | ✓ |
| No external dependencies | — | — | — |

[azure-devops-pkg]: https://pypi.org/project/azure-devops/
[pydantic]: https://docs.pydantic.dev/
[api reference]: https://pyado.readthedocs.io/
