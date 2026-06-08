"""Tests for pyado.raw._core — _setup_session."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

from unittest.mock import MagicMock

import pytest
import requests
import requests.auth

from pyado.raw._core import _BearerAuth, _setup_session

_BEARER_TOKEN = "my-token"


class TestSetupSession:
    def test_pat_sets_http_basic_auth(self) -> None:
        session = requests.Session()
        result = _setup_session(session, pat="my-pat")
        assert result is session
        assert isinstance(result.auth, requests.auth.HTTPBasicAuth)
        assert result.auth.password == "my-pat"  # pragma: allowlist secret

    def test_bearer_token_sets_bearer_auth(self) -> None:
        session = requests.Session()
        result = _setup_session(session, bearer_token=_BEARER_TOKEN)
        assert result is session
        assert isinstance(result.auth, _BearerAuth)

    def test_azure_credentials_sets_bearer_auth(self) -> None:
        session = requests.Session()
        credential = MagicMock()
        token_result = MagicMock()
        token_result.token = "azure-token"
        credential.get_token.return_value = token_result
        result = _setup_session(session, azure_credentials=credential)
        assert result is session
        assert isinstance(result.auth, _BearerAuth)
        credential.get_token.assert_called_once()

    def test_no_token_leaves_session_unconfigured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("AZURE_DEVOPS_EXT_PAT", raising=False)
        session = requests.Session()
        result = _setup_session(session)
        assert result is session
        assert result.auth is None

    def test_env_pat_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AZURE_DEVOPS_EXT_PAT", "env-pat")
        session = requests.Session()
        result = _setup_session(session)
        assert isinstance(result.auth, requests.auth.HTTPBasicAuth)
        assert result.auth.password == "env-pat"  # pragma: allowlist secret

    def test_sets_trust_env_false(self) -> None:
        session = requests.Session()
        session.trust_env = True
        _setup_session(session, pat="my-pat")
        assert session.trust_env is False
