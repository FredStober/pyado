# Implementation plan


## API inconsistencies

These are known inconsistencies in the current API surface that should be
fixed before the OOP layer is considered stable.

## Raw layer gaps

These areas have no raw-layer coverage.  Endpoints and suggested module
names are listed; detailed implementation specs need to be written before
work begins.

## Lower priority

### Audit Log

| Operation | ADO endpoint |
|---|---|
| Query audit log | `GET {org}/_apis/audit/auditlog` |
| List audit streams | `GET {org}/_apis/audit/streams` |
| Create audit stream | `POST {org}/_apis/audit/streams` |

---

### Releases (Release Management)

Classic release pipelines live on a separate `vsrm.dev.azure.com` host.
Suggested module: `raw/pipelines/release.py`.

| Operation | ADO endpoint |
|---|---|
| List releases | `GET {org}/{project}/_apis/release/releases` |
| Get release | `GET {org}/{project}/_apis/release/releases/{id}` |
| Create release | `POST {org}/{project}/_apis/release/releases` |
| Update release environment | `PATCH {org}/{project}/_apis/release/releases/{id}/environments/{envId}` |
| List release definitions | `GET {org}/{project}/_apis/release/definitions` |

---

### Test Plans / Test Runs

Suggested modules: `raw/boards/test_plan.py`, `raw/boards/test_run.py`.

| Operation | ADO endpoint |
|---|---|
| List test plans | `GET {org}/{project}/_apis/testplan/plans` |
| Get test plan | `GET {org}/{project}/_apis/testplan/plans/{id}` |
| List test suites | `GET {org}/{project}/_apis/testplan/plans/{id}/suites` |
| List test cases | `GET {org}/{project}/_apis/testplan/plans/{id}/suites/{suiteId}/testcase` |
| List test runs | `GET {org}/{project}/_apis/test/runs` |
| Get test run | `GET {org}/{project}/_apis/test/runs/{id}` |
| List test results | `GET {org}/{project}/_apis/test/runs/{id}/results` |

---
