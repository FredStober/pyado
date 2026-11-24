# Implementation plan


## API inconsistencies

These are known inconsistencies in the current API surface that should be
fixed before the OOP layer is considered stable.

### Timeline session: bugs and wrong documentation

Found by probing a live organisation (`experiments/probe_all.py`; evidence and
the measurements are in `experiments/ADO_TIMELINE_API.md`, section numbers
below refer to it).  Ordered by risk.

Status legend: **DONE** = changed in code or docs; **PARTLY** = only part of the
item is done (the text says which); **OPEN** = nothing done.  `ruff`, `mypy` and
`ty` pass on `src/` and `tests/`; **the new and changed tests have not been run
yet** (pytest was deliberately not executed), so every DONE below means
"written and type-checked", not "verified by a test run".

**Code**

1. **`TimelineSession.record_id` ignores the parent** (12.3 G1, confirmed live).
   `create_task("Run", under=job1)` and then `create_task("Run", under=job2)`
   derive the *same* id, so ADO upserts one record: it keeps the first parent
   and nothing appears under `job2`.  `key` defaults to `name`, so the default
   is the trap.  Fix: include the parent id in the uuid5 input
   (`f"{build_id}/{parent_id}/{key}#{attempt}"`), or require an explicit key
   when the name is not unique under the parent; add a test with two parents.
   Note that changing the derivation changes existing ids, so a stateless
   writer that restarts across the upgrade re-creates its records.
   **Status: DONE for the default key.**  `create_job` / `create_task` now
   default the key to `f"{parent_id}/{name}"`, so the same name under two
   parents is two records, and existing explicit keys keep their ids.  An
   explicit key is still the whole identity, which `record_id`'s docstring
   warns about.  `record_id()` itself still ignores the parent (it only maps a
   key to an id).  Consequence: a writer that relied on the old default (the
   name alone) creates new records after the upgrade.  Tests: `TestIdPitfalls`.
2. **The id has no job attempt** (G2).  After a stage or job retry the old job
   id leaves the root timeline; a key that does not change re-attaches to a
   record parented under the dead job.  Measured: records written into
   attempt 1 move into the attempt-1 sub-timeline and are not drawn; writing
   the same ids again under the new job creates records under the new job.
   Fix: document that the key must contain `SYSTEM_JOBATTEMPT`, or offer
   `TimelineSession.for_attempt(n)` that mixes it in.
   **Status: PARTLY.**  Documented as a pitfall in `record_id`, `create_*`, the
   class docstring and `AGENT.md` / `usage.md` (put `SYSTEM_JOBATTEMPT` into
   the key; the sub-timeline of the earlier attempt can now be read, item 7).
   Not done: `for_attempt(n)` or an automatic attempt in the id, and no test
   with a retry between two sessions.  Note that the default key now contains
   the parent id, and a retry gives the job a new id, so default-key records
   follow the new job; only explicit keys still hit the trap.
3. **`JobEventResult` has no `skipped`** (`raw/pipelines/pipeline.py`).
   `TaskCompleted` with `skipped` returns 204 and completes the task as
   `skipped` with the job `succeeded` (the pipeline continues).  Add
   `SKIPPED = "skipped"` and let `TimelineSession.complete` take a result
   instead of `succeeded: bool`.
   **Status: DONE.**  `JobEventResult.SKIPPED` added;
   `TimelineSession.complete(step, result=...)` takes it (`succeeded` stays for
   compatibility and is ignored when `result` is given).  The enum and
   `post_job_event` docstrings describe the three outcomes.
4. **`_create` hard-codes `ref_name="CmdLine1"`, no `order`** (G4).  Every
   created record is green and unordered.  The portal reads colour from the
   `refName`: a name starting with `JobExtension` (exact case) or no name
   gives grey (`system-task`), anything else green (`success`).  Proposed
   `Icon` enum, `icon=` / `ref_name=` / `order=` parameters and `set_icon`
   are in section 12.5.  Measured constants: `order` `0` or negative sorts
   first, `2147483646` last, `null` lands between `1` and `2`.
   **Status: DONE.**  `StatusIcon` (`COLOURED` / `GREY`), `RecordOrder` (`FIRST`,
   `LAST`), `icon=` and `order=` on `create_job` / `create_task`; `icon` also
   accepts any `refName` string.  `set_icon()` was **removed**: ADO ignores a changed
   `refName` (measured), so the colour is a creation-time choice.  The colour rule is
   documented as measured, with the open caveat that for a *running* Job only a
   missing `refName` made it grey and the stage-card colour of a dynamic Job was
   not measured.  Not done from section 12.5 of the experiments document:
   `Icon.of()` and a session-wide default icon.
5. **`_check_new_id` is dead code and misses native records** (G3).  It runs
   only outside `batch()`, needs a full timeline GET per create, can fire only
   on a uuid5 collision, and its "native" test (`task` or `identifier` set)
   misses `Initialize job` / `Finalize Job`.  Remove it, or replace it by one
   cached timeline read per session.
   **Status: DONE (kept, not removed).**  The guard now reads the timeline once
   per session (cached) and treats a record with a task definition, an
   `identifier` or a `worker_name` as native.  It still fires only for an id
   that collides with a native record, which the default derivation never
   produces, so it is a safety net.  Records that appear after the first read
   are not in the cached set.
6. **`append_log` reads the whole timeline before every append** (G3).  Cache
   the log id per record after the first lookup.
   **Status: DONE.**  The log id is cached per record; the first append reads
   the timeline, later ones do not.  `attach_log` fills the cache.
7. **No sub-timeline reader** (G5).  `raw.iter_timeline_records` always
   appends `timeline`, so the recipe `build_call.build_call("timeline", id)`
   requests `.../timeline/{id}/timeline`.  Add a `timeline_id` argument.
   Needed because retried attempts live only in sub-timelines (8.3).
   **Status: DONE.**  `raw.iter_timeline_records(call, timeline_id=None)` and
   `list_timeline_records(call, timeline_id=None)`.  Not done: a
   `Build`-level helper that follows `previous_attempts`, and a
   `TimelineSession` method to read or write a sub-timeline.
8. **One unknown record type makes every read fail** (G6).  `BuildRecordType`
   has no catch-all and `BuildLogInfo`, `BuildAttemptInfo`, `BuildIssue`,
   `TimelineReference` are `extra="forbid"`, so a single injected
   `type="X"` makes `list_timeline_records`, `resolve_task`, `find`,
   `native_phase` and `append_log` raise for the whole build.  Add an
   `OTHER` member with a lenient parser and relax the nested models to
   `extra="ignore"`.
   **Status: DONE.**  `BuildRecordType.OTHER` with a `_missing_` hook (the
   original string is not kept), and `BuildLogInfo`, `BuildRecordTypeInfo`,
   `BuildAttemptInfo`, `TimelineReference` ignore extra fields.  `BuildIssue`
   stays `forbid` on purpose: it is also the model `report_issues` sends, and
   the server never returns an unknown issue type (it stores it as `error`).
9. **`TimelineSession` must refuse to create a `Stage` record** (7.9).  A
   dynamic `Stage` record, in any state, makes the build's results page show
   "Build not found" and it stays broken after the build ends.  The public API
   only creates Jobs and Tasks today, but `raw.patch_timeline_records` and
   `_RecordWrite.type_name` accept it.  **Done**: `_RecordWrite` and the oop
   `update_timeline_records` raise; the raw `patch_timeline_records` only
   documents the hazard (it is a thin transport and may patch a native Stage).
   **Status: DONE.**  `_RecordWrite` rejects `Stage`, and
   `raw.patch_timeline_records` raises `AzureDevOpsSessionError` for a payload
   that contains one; the warning is in the `BuildRecordType` docstring.
10. **`create_job` allows `state=COMPLETED`** (G4c).  A completed Job under a
    native Phase is drawn as a task-like row and is not listed as a job; and
    `create_task(under=<Task>)` allows any depth although only two levels are
    drawn (the 3rd and 4th are stored, not shown).  Warn or refuse.

    **Status: DONE (warn, not refuse).**  `create_job(state=COMPLETED)` and a
    task whose parent is already a task of a task issue a `UserWarning`; the
    records are still written.
**Documentation and docstrings**

11. **"Raise the *agentless* job's `timeoutInMinutes`" is not what was
    measured** (`docs/AGENT.md:408`, `docs/usage.md:2121`,
    `timeline_session.py` lines 739-740 and 757).  Every token that was
    decoded belonged to an *agent* job (expiry = that job's timeout + 15 min,
    seven jobs, 1-60 min); an agentless job runs no script, so its own token
    was never read and which job's timeout governs a token used against an
    agentless task is untested.  Reword to: "the token expires at the issuing
    job's `timeoutInMinutes` + 15 min (measured on agent jobs)".
    **Status: DONE.**  Reworded in `AGENT.md`, `usage.md`, the module and
    `complete()` docstrings and the expiry error message: the measured rule is
    for the issuing (agent) job, and the agentless case is stated as not
    measured.
12. **"Records left in progress end as the job's result"**
    (`docs/AGENT.md:1362`) is wrong: they take the **build's** result when
    the build ends (`inProgress` becomes `completed` with the build's result,
    `pending` becomes `abandoned`).  Measured with a record under a succeeded
    job in a failed build: it ended `failed`.
    **Status: DONE.**  `AGENT.md` quirk 16, the class and `complete()`
    docstrings and `usage.md` now say the build's result.
13. **`report_issues` docstring** (`timeline_session.py:613`) says an empty
    list is ignored.  True for native and completed records; a dynamic record
    that is still `inProgress` is cleared by `[]`.  Also: issues of an unknown
    `type` are stored as `error` but appear in neither summary tab.
    **Status: DONE.**  The docstring now covers `[]` (clears only an
    `inProgress` virtual record), the non-recomputed counts and the unknown
    issue type that shows in neither tab.
14. **Removed API still documented**: `Build.get_distributed_task_session`,
    `Build.iter_stages`, `DistributedTaskSession`, `BuildStage` were removed in
    `8ddec85` (2026-06-11) and replaced by `TimelineSession`; they are still in
    `docs/usage.md` (lines 606 and 633), `docs/quick_reference.md` (339, 344)
    and `docs/AGENT.md` (325).
    **Status: DONE.**  Removed from `usage.md`, `quick_reference.md`,
    `AGENT.md`, `README.md` and one `build.py` docstring (it still named
    `BuildJob` / `BuildStage`).
15. **`JobEventResult` doc and the `complete()` docstring**: state that
    `TaskCompleted` resolves `taskId` too (a fabricated `taskId` with a real
    `jobId` returns 404 `No job found with identifier ...`), that an unknown
    event name is a silent 204, and that `skipped` is accepted.
    **Status: DONE.**  In `post_job_event`, `JobEventResult` and `complete()`.
16. **Add the portal facts users hit**: a dynamic Job is drawn (and listed on
    the stage card and in the Jobs tab) only under a native Phase; Task
    nesting is drawn two levels deep; `TaskCompleted` does not close child
    records; a PAT cannot complete an agentless task (HTTP 500) but can write
    records, feed and logs.

    **Status: DONE.**  In `patch_timeline_records`, `post_job_logs`, the
    `TimelineSession` class docstring, `AGENT.md` quirk 24 and `usage.md`.
**Tests to add**

17. Two parents with one key (item 1); a retry between two sessions (item 2);
    `complete(skipped)` against the fake (item 3); a timeline containing an
    unknown record type and an extra field in `log` (item 8); a Stage write is
    refused (item 9).
    **Status: PARTLY, written but not run.**  Written (in
    `tests/oop/test_timeline_session.py`, `tests/raw/test_build.py`,
    `tests/raw/test_pipeline.py`): two parents with the default and with an
    explicit key, `complete(skipped)`, an unknown record type and an extra field
    in `log` and `previousAttempts`, a refused Stage (oop layers; raw only passes it through), the sub-timeline
    URL, icon and order, the warnings, the log-id cache and the once-per-session
    native read.  Not written: a retry between two sessions (item 2).  Run
    `uv run pytest tests/raw tests/oop` before relying on any of it; the
    fake ADO in the OOP tests gained a sub-timeline route and has not been
    exercised.

## Raw layer gaps

These areas have no raw-layer coverage.  Endpoints and suggested module
names are listed; detailed implementation specs need to be written before
work begins.

## Pipeline lifecycle (create, preview, retry, clean up)

The experiments lab (`experiments/lab/lab.py`) builds, runs and removes
throwaway pipelines purely through REST.  Several of its calls have no pyado
counterpart, so anyone automating "create a pipeline from YAML" has to drop to
raw `ApiCall`.  These are the real gaps (verified against `src/pyado`).

Already covered, **do not duplicate**: `raw.post_push` / `Repository.push_commits`
(commit files and create the branch in one push), `Repository.create_branch` /
`delete_branch`, `raw.patch_pipeline_permission` (authorize an environment or
service connection), `raw.post_pipeline_run`, `Build.cancel`, `Build.retry`
(queues a *new build*, not a stage retry), `iter_environments`,
`iter_agent_queues`, `raw.iter_pipeline_definitions`.

Suggested modules: `raw/pipelines/build.py` (definitions, builds, leases, stages)
and `raw/pipelines/pipeline.py` (preview).

| Operation | ADO endpoint | Notes (measured in the lab) |
|---|---|---|
| **Create a YAML pipeline definition** | `POST {project}/_apis/build/definitions` | Body: `name`, `path`, `type: "build"`, `queue: {id}`, `process: {type: 2, yamlFilename}`, `repository: {id, name, type: "TfsGit", defaultBranch: "refs/heads/<b>", properties: {reportBuildStatus: "true"}}`, `triggers: []`.  `process.type=2` is what makes it a YAML pipeline.  The `queue` id is not discoverable from a name, the lab copied it from definition 1 (`GET build/definitions/1` → `queue.id`); `iter_agent_queues` should be the documented source |
| Delete a pipeline definition | `DELETE {project}/_apis/build/definitions/{id}` | Treat 404 as "already gone".  **Never delete a definition under a running build**: the build stays `cancelling` for 16–85 min (see below) |
| Get one definition | `GET {project}/_apis/build/definitions/{id}` | Only listing exists today |
| **Preview / compile YAML without running** | `POST {project}/_apis/pipelines/{id}/runs` with `previewRun: true` | Returns `finalYaml` (templates expanded); a template error is HTTP 400 with a message.  `PipelineRunRequest` has no `preview_run`; `PipelineRunInfo.final_yaml` already exists.  Body also takes `resources.repositories.self.refName` to choose the branch, which `PipelineRunRequest.resources` allows only as a raw dict |
| Delete a build | `DELETE {project}/_apis/build/builds/{id}` | Fails with HTTP 400 `TF900561` while retention leases exist and HTTP 403 while running.  Deleted builds still answer `GET` with `deleted: true`, so "gone" must be checked on that flag, not on a 404 |
| **List retention leases of a build** | `GET {project}/_apis/build/builds/{id}/leases` | Each lease has `leaseId`, `ownerId` (e.g. `Branch:<repo>:refs/heads/<b>`, `Pipeline:<id>`).  A *successful* run gets two; failed or canceled runs get none |
| **Delete retention leases** | `DELETE {project}/_apis/build/retention/leases?ids=1,2` | Needed before a successful build can be deleted.  Only remove leases whose owner you created |
| **Retry or cancel a single stage** | `PATCH {project}/_apis/build/builds/{id}/stages/{stageRefName}` | Body `{"state": "retry", "forceRetryAllJobs": true}`.  The retried stage and its dependents get **new record ids** and `attempt=2`; see the timeline reference |
| Cancel a build stuck in `cancelling` | `PATCH {project}/_apis/build/builds/{id}` `{"status": "cancelling"}` | `raw.patch_build` already sends this; document that sending it a second time completes a stuck build |

Suggested OOP surface (sketch, to be specified before work begins):

* `ProjectPipelines.create_pipeline(name, *, repository, yaml_path, branch,
  folder=None, queue=None, report_build_status=False) -> Pipeline` and
  `Pipeline.delete()`
* `Pipeline.preview(branch=None, template_parameters=None) -> str` (final YAML)
* `Build.delete()` that removes retention leases first (only when asked) and
  `Build.iter_leases()` / `Build.delete_leases()`
* `Build.retry_stage(stage, *, force_all_jobs=False)`

Related but already tracked elsewhere: the timeline-writing gaps
(`TimelineSession` has no `order`, icon colour, sub-timeline reads or typed
tree) are in the experiments repo's `ADO_TIMELINE_API.md`, section 12.

---

## Uploads, tests and coverage: what is still missing

State after the 2026-11 experiments (`experiments/ADO_TIMELINE_API.md`, section
18).  These raw functions exist and were run against a live organisation:
task summaries, test runs/results/attachments (write and read back), the
coverage *report*, container files, build artifacts, plan timelines, build
tags.  What a pyado user **cannot** do, or has never been checked:

| # | Gap | Evidence / why | What to do |
|---|-----|----------------|------------|
| 1 | ~~**The Code Coverage figures cannot be written**~~ | **done:** `raw.publish_code_coverage` / `post_code_coverage` / `post_file_coverage` / `FileCoverage` (the requests of `PublishCodeCoverageResults@2`, seen behind a proxy and replayed with a PAT; live test `test_publish_code_coverage_without_the_task`).  The figures need the per-file blob as well, and the build must run an agent job and end normally (then the service finalises them).  **Files** stays empty even for the real task. | Nothing more to build; see `docs/usage.md`. |
| 2 | **The Environments tab** is neither written nor tested | pyado has no environment *write* functions (`iter_environments` only reads) | Find out what fills the tab (environment deployment records) and add the calls, or document that only a deployment job fills it |
| 3 | **Linking a work item to a build** was never verified | `WorkItem` can build an ArtifactLink relation targeting a build (`oop/boards/_work_item.py`), and the Summary page shows "Related: N work items", but no experiment compared the two | Write the link, read the count on the Summary page, add the result to `docs/usage.md` |
| 4 | ~~**`TimelineSession` cannot create a `Phase` or `Checkpoint` record**~~ | **decided: no `create_phase` / `create_checkpoint`.**  The experiments document (7.4, 7.8) says both are accepted but have no tree row and their only visible effect is an issue in the Errors/Warnings tabs (breadcrumb = build number), which a Task issue already reaches.  The raw `patch_timeline_records` stays the way for the rare case. |
| 5 | **No OOP wrappers** for summaries, tests, coverage report, attachments and plan timelines | only `raw` exists; `CLAUDE.md` says endpoints with payload construction or multi-step logic get a helper and a method | e.g. `Build.add_summary`, `Build.create_test_run`, `Build.publish_coverage_report`, `Build.iter_test_results`, `Build.iter_plan_timelines` |
| 6 | **No pyado-only end-to-end run** | the checks mixed pyado with raw HTTP and the real tasks; `publish_coverage_report` and the read-side functions were each run alone | One script that fills every reachable tab on one build (tree via `TimelineSession`, summary, tests with a Bug link, report) and screenshots each tab; keep it as an integration test (`tests/integration/`) |
| 7 | **Integration tests for all the new raw functions** | only unit tests (mocks) exist, and a mock hid a real bug (a double-encoded path in `get_container_item_text`) | Add `tests/integration/raw/` modules for `attachment.py` and `test_results.py` (they need a running build or a build id from a fixture) |
| 8 | **Finished-build write boundary** | writes were accepted for 13 minutes after a build ended and refused (HTTP 400 "timeline is in a completed state") hours later; the edge is unknown | Measure it (a lane that writes at +1 h, +2 h ...) and put the number in the docstrings of the write functions |
| 9 | **Tests tab: things that cannot be filled** | tags have no route (`customFields` fails, a `tags` body is stored as nothing); iteration details and sub-results are stored but never shown; duration is derived from the two dates | Nothing to build.  Keep the warnings in `docs/usage.md`; revisit if ADO adds a route |

Facts that shaped the API and must stay documented (all measured):

* A `refName` can be set once, from `null`; a later change is answered 200 and
  ignored, so the icon is a creation-time choice (`set_icon` was removed).
* A run created `Completed` is rejected (HTTP 400): `TestRunCreate.state` is
  limited to `NotStarted` / `InProgress`.
* The container needs the **organisation** URL; a path with a space must not be
  pre-encoded (`requests` encodes it once).
* `task.logdetail` records live in a **second timeline** of the plan, which
  `iter_timeline_records` does not read.
* `post_build_tag` was renamed `put_build_tag` (it always sent PUT).

---

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
| ~~List test runs~~ | **done:** `iter_build_test_runs` / `list_build_test_runs` (by build) |
| ~~Get test run~~ | **done:** `get_test_run` |
| ~~List test results~~ | **done:** `list_test_results` / `get_test_result` (see "Uploads, tests and coverage" above) |
| List test runs of a project (not by build) | `GET {org}/{project}/_apis/test/runs` (`iter_build_test_runs` filters by build only) |

---

---

## Done in the 2026-11 follow-up

* `tests/integration/raw/test_build_tabs.py` (12 tests, run alone against the live org): summaries, test runs/results/attachments, container files, `publish_coverage_report`, coverage read, `patch_timeline_records`, plan timelines, tags.  Writes need a freshly finished build (a cancelled `onpremise` run), the `distributedtask` routes need the project **id** in the URL.
* `TestRunState.OTHER`: a deleted run is still listed with state `"255"`, which failed the whole listing.
* `get_build_container_id` falls back to the organisation's container list (`artifactUris`), so a build that published nothing still has an id.
* `EnvironmentDeploymentRecord` read `definition_name` from a field the API never sends; it now reads the nested `definition`, plus `plan_id`, `stage_name`, `job_name`, attempts, times and `build_id`.  Records are server-written only (405 on every write method).
* `SUMMARY_ATTACHMENT_TYPE` is now `DistributedTask.Core.Summary`, the spelling `##vso[task.uploadsummary]` writes.  The server compares the type name case-sensitively, so the old `Distributedtask.Core.Summary` (small `t`) was a different type that the agent never produced.  There is one constant and no second reader.
* Retry between two `TimelineSession`s is tested (default key follows the new job, an explicit key hits the old record).
* Summaries: `iter_build_summaries`, `put_record_summaries` (a `{name: markdown}` mapping to one record), `BuildAttachmentInfo.record_id` (parsed from the link) and `TimelineSession.add_summaries` / `iter_summaries`.  Measured on build 2410: a summary is identified by **record + name**; a repeated name on one record **replaces** the content, the same name on two records is two summaries, an empty body is accepted.
* Measured, no code: summaries cannot be deleted (405), only replaced.  The Extensions tab draws capital-T summaries, also those of a real `##vso[task.uploadsummary]`.  The Summary's "Related" counts work items resolved from the build's **commits**, not a work item linked to the build (ArtifactLink).
* Summary rendering measured (build 2414, 53 cases): GFM markdown + sanitized HTML subset; mermaid, math, footnotes, definition lists, `:emoji:` shortcodes and `data:` images are not rendered; nothing executes.  Details in `ADO_TIMELINE_API.md` §18.7 and `docs/usage.md`.
* `TimelineSession.for_attempt(n)` and `.attempt`: a session that mixes the job attempt into every derived id (`record_id`, `create_job`, `create_task`; an explicit `attempt=` still wins).  Attempt 1 derives the ids of a plain session (pinned by a test), the record's own `attempt` field stays 1, and the new session starts with empty caches.
* Measured: a summary can be put on a Stage, Phase, Job, Task or Checkpoint record and is drawn as a card; the browser requests every external address of a summary (http is upgraded to https) and loads real images without CORS headers.  The real request of `PublishCodeCoverageResults@2` is still unknown (needs a proxy on the agent).
* `TimelineSession.for_current_attempt(step)`: takes the attempt from the native job of a Task or Job, so an explicit key follows a retry without typing the number.  Without `key=` nothing is needed (the parent id is in the default key).
* Coverage figures: `get_test_results_api_call`, `post_code_coverage`, `post_file_coverage`, `publish_code_coverage`, `FileCoverage` (see `docs/usage.md`).  The earlier belief that this was impossible came from using the old `test/codecoverage` route.
* Coverage: the Files sub-tab and the Summary header are isolated.  Files fills (like the official task) when the build checked out the sources and every `FileCoverage.file_path` is the absolute agent path of a checked-out file; the "N % covered" in the Summary needs a test run in the build.  Live test `test_publish_code_coverage_without_the_task` pins the coverage-service store (`covered 3, notCovered 1`).
