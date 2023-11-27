"""Module to interact with Azure DevOps pull requests."""
from typing import Iterator
from typing import Literal
from typing import Optional
from typing import TypeAlias

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic.networks import AnyUrl

from pyado.api_call import ApiCall
from pyado.api_call import get_test_api_call
from pyado.repository import RepositoryId
from pyado.work_item import WorkItemId


PullRequestId: TypeAlias = int
PullRequestIteration: TypeAlias = int
PullRequestStatusState: TypeAlias = Literal[
    "error", "failed", "notApplicable", "notSet", "pending", "succeeded"
]


def get_pr_api_call(
    project_api_call: ApiCall, repository_id: RepositoryId, pr_id: PullRequestId
) -> ApiCall:
    """Get pull request API call."""
    return project_api_call.build_call(
        "git",
        "repositories",
        repository_id,
        "pullRequests",
        pr_id,
    )


def iter_pr_work_item_ids(pr_api_call: ApiCall) -> Iterator[WorkItemId]:
    """Get work items linked to the PR."""
    max_results = 100
    response = pr_api_call.get(
        "workitems",
        parameters={"$top": max_results},
        version="6.0",
    )
    for entry in response["value"]:
        yield int(entry["id"])


class PullRequestComment(BaseModel):
    """Type for storing a pull request comment."""

    model_config = ConfigDict(populate_by_name=True)

    comment_type: int = Field(alias="commentType")
    content: str
    parent_comment_id: int = Field(alias="parentCommentId")


class PullRequestCommentHolder(BaseModel):
    """Type for storing pull request comment information."""

    status: int
    comments: list[PullRequestComment]


def create_pr_comments(
    pr_api_call: ApiCall, pr_comments_info: PullRequestCommentHolder
) -> None:
    """Create comments on a PR.

    Reference: https://github.com/MicrosoftDocs/vsts-rest-api-specs/blob/master
    /specification/git/7.1/httpExamples/pullRequestThreads/
    POST__git_repositories__repositoryId__pullRequests__pullRequestId__threads
    .json
    """
    pr_api_call.post(
        "threads",
        version="7.1-preview.1",
        json=pr_comments_info.model_dump(mode="json"),
    )


class PullRequestStatusContext(BaseModel):
    """Type for storing pull request status context information."""

    name: str
    genre: str


class PullRequestStatusInfo(BaseModel):
    """Type for storing pull request status information."""

    model_config = ConfigDict(populate_by_name=True)

    context: PullRequestStatusContext
    description: Optional[str] = None
    iteration_id: PullRequestIteration = Field(alias="iterationId")
    state: PullRequestStatusState
    target_url: Optional[AnyUrl] = Field(default=None, alias="targetUrl")


def create_pr_status_flag(
    pr_api_call: ApiCall, pr_status_info: PullRequestStatusInfo
) -> None:
    """Create a status item on the PR.

    Reference: https://github.com/MicrosoftDocs/vsts-rest-api-specs/blob/master
    /specification/git/7.1/httpExamples/pullRequestStatuses/
    POST_git_pullRequestStatuses_statusIterationInBody.json
    """
    pr_status_payload = pr_status_info.model_dump(
        mode="json", by_alias=True, exclude_none=True
    )
    pr_api_call.post("statuses", version="7.1", json=pr_status_payload)


def test() -> None:
    """Function to test the functions."""
    test_api_call, test_config = get_test_api_call()
    pr_api_call = get_pr_api_call(
        test_api_call, test_config["repository_id"], test_config["pr_id"]
    )

    # Test PR comments
    comment = PullRequestComment(
        commentType=1,
        parentCommentId=0,
        content="TEST",
    )
    create_pr_comments(
        pr_api_call, PullRequestCommentHolder(status=1, comments=[comment])
    )
    # Test PR status flags
    status = PullRequestStatusInfo(
        description="Test 1",
        iterationId=4,
        context=PullRequestStatusContext(genre="test", name="test"),
        state="pending",
        targetUrl=AnyUrl("https://google.com"),
    )
    create_pr_status_flag(pr_api_call, status)


if __name__ == "__main__":
    test()
