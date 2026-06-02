"""Higher-level Azure DevOps abstractions.

Design rules for this package
------------------------------
* **Construct request models from primitive args.**  High-layer functions
  accept plain Python values (strings, ints, enums) and build the Pydantic
  request models required by the corresponding raw function.

* **Wrap pagination.**  Where an ADO endpoint returns paged results, the
  high-layer function owns the loop and yields individual items.

* **Orchestrate multi-step operations.**  When achieving a goal requires
  more than one API call (e.g. look up a ref then push a commit), that
  sequence lives here, not in raw.

* **Names express intent, not HTTP verbs.**  A high-layer function may be
  named differently from the raw function it wraps when a more descriptive
  name improves clarity (e.g. ``push_commits`` wraps ``post_push``,
  ``add_pr_reviewer`` wraps ``put_pr_reviewer``).

* **Delegate all HTTP to raw.**  High-layer functions never call
  ``api_call.get / post / patch / put / delete`` directly.

* **No re-exports of raw symbols.**  Every public name in ``high/__init__``
  must be a function defined in this package.  Raw models and functions are
  imported for internal use only.
"""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

__all__ = [
    "add_artifact_link",
    "add_file",
    "add_pr_reviewer",
    "add_work_item_attachment",
    "add_work_item_tag",
    "approve_pipeline",
    "create_branch",
    "create_pr",
    "create_pr_thread",
    "create_work_item",
    "delete_branch",
    "delete_file",
    "edit_file",
    "get_file_content_at_branch",
    "get_file_content_at_commit",
    "get_last_commit_touching_file",
    "get_pr_labels",
    "get_work_item_tags",
    "iter_build_work_item_ids",
    "iter_commit_diff",
    "iter_open_prs",
    "iter_pending_approvals",
    "iter_pr_work_item_ids",
    "iter_work_item_details",
    "make_commit",
    "push_commits",
    "remove_work_item_tag",
    "rename_file",
    "reply_to_pr_thread",
    "send_job_event",
    "send_job_feed",
    "set_pr_reviewer_vote",
    "start_build",
    "update_timeline_records",
    "update_variable_group",
    "update_work_item",
]

from pyado.high.build import (
    approve_pipeline as approve_pipeline,
)
from pyado.high.build import (
    iter_build_work_item_ids as iter_build_work_item_ids,
)
from pyado.high.build import (
    iter_pending_approvals as iter_pending_approvals,
)
from pyado.high.build import (
    send_job_event as send_job_event,
)
from pyado.high.build import (
    send_job_feed as send_job_feed,
)
from pyado.high.build import (
    start_build as start_build,
)
from pyado.high.build import (
    update_timeline_records as update_timeline_records,
)
from pyado.high.git import (
    add_file as add_file,
)
from pyado.high.git import (
    create_branch as create_branch,
)
from pyado.high.git import (
    delete_branch as delete_branch,
)
from pyado.high.git import (
    delete_file as delete_file,
)
from pyado.high.git import (
    edit_file as edit_file,
)
from pyado.high.git import (
    get_file_content_at_branch as get_file_content_at_branch,
)
from pyado.high.git import (
    get_file_content_at_commit as get_file_content_at_commit,
)
from pyado.high.git import (
    get_last_commit_touching_file as get_last_commit_touching_file,
)
from pyado.high.git import (
    iter_commit_diff as iter_commit_diff,
)
from pyado.high.git import (
    make_commit as make_commit,
)
from pyado.high.git import (
    push_commits as push_commits,
)
from pyado.high.git import (
    rename_file as rename_file,
)
from pyado.high.pull_request import (
    add_pr_reviewer as add_pr_reviewer,
)
from pyado.high.pull_request import (
    create_pr as create_pr,
)
from pyado.high.pull_request import (
    create_pr_thread as create_pr_thread,
)
from pyado.high.pull_request import (
    get_pr_labels as get_pr_labels,
)
from pyado.high.pull_request import (
    iter_open_prs as iter_open_prs,
)
from pyado.high.pull_request import (
    iter_pr_work_item_ids as iter_pr_work_item_ids,
)
from pyado.high.pull_request import (
    reply_to_pr_thread as reply_to_pr_thread,
)
from pyado.high.pull_request import (
    set_pr_reviewer_vote as set_pr_reviewer_vote,
)
from pyado.high.variable_group import (
    update_variable_group as update_variable_group,
)
from pyado.high.work_item import (
    add_artifact_link as add_artifact_link,
)
from pyado.high.work_item import (
    add_work_item_attachment as add_work_item_attachment,
)
from pyado.high.work_item import (
    add_work_item_tag as add_work_item_tag,
)
from pyado.high.work_item import (
    create_work_item as create_work_item,
)
from pyado.high.work_item import (
    get_work_item_tags as get_work_item_tags,
)
from pyado.high.work_item import (
    iter_work_item_details as iter_work_item_details,
)
from pyado.high.work_item import (
    remove_work_item_tag as remove_work_item_tag,
)
from pyado.high.work_item import (
    update_work_item as update_work_item,
)
