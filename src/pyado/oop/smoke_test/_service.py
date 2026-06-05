"""Smoke tests for AzureDevOpsService."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import sys

from pyado.oop import AzureDevOpsService
from pyado.oop.smoke_test._runner import console, run


def _test_service(org_url: str, token: str) -> AzureDevOpsService:
    console.print("\n=== AzureDevOpsService ===")
    svc = run(
        "AzureDevOpsService(org, pat)",
        lambda: AzureDevOpsService(org=org_url, pat=token),
    )
    if svc is None:
        console.print("  [red]Cannot continue — service construction failed.[/red]")
        sys.exit(1)
    run("svc.org (property)", lambda: svc.org)
    run("svc.api_call (property)", lambda: svc.api_call)
    run("svc.oop_api (property)", lambda: svc.oop_api)
    run("svc.refresh()", svc.refresh)
    return svc
