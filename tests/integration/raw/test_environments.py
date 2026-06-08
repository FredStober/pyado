"""Integration tests for pipeline environment endpoints."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from pyado import raw
from tests.integration.raw._support import console


def test_environments_read(project_api_call: raw.ApiCall) -> None:
    """List environments, checks, and deployments."""
    console.print("\n=== ENVIRONMENTS (read) ===")

    envs = list(raw.iter_environments(project_api_call))
    assert envs == raw.list_environments(project_api_call)
    if envs:
        env = envs[0]
        env_api_call = raw.get_environment_api_call(project_api_call, env.id)
        raw.get_environment(project_api_call, env.id)
        checks = list(raw.iter_environment_checks(project_api_call, env.id))
        assert checks == raw.list_environment_checks(project_api_call, env.id)
        if env_api_call:
            deployments = list(raw.iter_environment_deployments(env_api_call))
            assert deployments == raw.list_environment_deployments(env_api_call)
