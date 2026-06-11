# Copyright (c) 2023, Fred Stober
"""Generic ADO security namespace ACL API wrappers."""

from typing import Any

from pyado.raw._core import _ADO_URL_ADAPTER, AdoBaseModel, ApiCall

__all__ = [
    "AceEntry",
    "delete_namespace_acl",
    "get_identities_by_descriptor",
    "get_identities_by_subject_descriptor",
    "get_namespace_acl",
    "get_namespace_actions",
    "get_namespace_names",
    "post_namespace_acl",
]


class AceEntry(AdoBaseModel):
    """A single access control entry granting or denying permissions."""

    descriptor: str
    allow: int
    deny: int


class _AclContainer(AdoBaseModel):
    value: list[dict[str, Any]]


def _to_pascal(name: str) -> str:
    """Normalise an ADO action name to PascalCase.

    Action names are already PascalCase in most namespaces (git, build).
    The project namespace uses UPPER_SNAKE_CASE — this function converts
    those to PascalCase so all namespaces share one consistent convention.

    Args:
        name: Action name as returned by the ADO namespace definition API.

    Returns:
        Name normalised to PascalCase for use in Terraform config.

    Examples:
        GenericRead       -> GenericRead   (unchanged)
        ForcePush         -> ForcePush     (unchanged)
        GENERIC_READ      -> GenericRead
        WORK_ITEM_DELETE  -> WorkItemDelete
        DELETE            -> Delete
    """
    if "_" not in name:
        return name
    return "".join(word.capitalize() for word in name.split("_"))


def get_namespace_names(org_api: ApiCall) -> dict[str, str]:
    """Return a case-insensitive name-to-GUID map for all security namespaces.

    Args:
        org_api: Organisation-scoped ApiCall.

    Returns:
        Dict mapping lowercased namespace name to its GUID string.
    """
    response = org_api.get("_apis", "securitynamespaces", version="7.1")
    result = {}
    for ns in (response or {}).get("value", []):
        name = ns.get("name")
        guid = ns.get("namespaceId")
        if name and guid:
            result[name.lower()] = guid
    return result


def get_namespace_actions(
    org_api: ApiCall,
    namespace_id: str,
) -> dict[str, int]:
    """Return a name-to-bit mapping for an ADO security namespace.

    Action names are normalised to UPPER_SNAKE_CASE so that the same
    convention applies regardless of the namespace (git uses PascalCase
    while project uses UPPER_SNAKE already).

    Args:
        org_api: Organisation-scoped ApiCall.
        namespace_id: Security namespace GUID.

    Returns:
        Dict mapping UPPER_SNAKE_CASE action name to its integer bit value.
    """
    response = org_api.get(
        "_apis",
        "securitynamespaces",
        namespace_id,
        version="7.1",
    )
    ns_list = (response or {}).get("value", [])
    if not ns_list:
        return {}
    return {
        _to_pascal(action["name"]): action["bit"]
        for action in ns_list[0].get("actions", [])
    }


def get_identities_by_subject_descriptor(
    org_api: ApiCall,
    subject_descriptors: list[str],
) -> dict[str, str]:
    """Resolve subject descriptors to storage-key format.

    The ``accesscontrollists`` POST API requires the
    ``Microsoft.TeamFoundation.Identity;S-1-9-...`` storage-key format, not
    the human-readable ``aadgp.``/``aad.``/``vssgp.`` subject-descriptor
    format used everywhere else.

    Args:
        org_api: Organisation-scoped ApiCall (used to derive the vssps URL).
        subject_descriptors: List of subject descriptors to resolve.

    Returns:
        Dict mapping each subject descriptor to its storage-key descriptor.
        Unresolvable descriptors are omitted.
    """
    if not subject_descriptors:
        return {}
    vssps = _vssps_api(org_api)
    response = vssps.get(
        "_apis",
        "identities",
        parameters={"subjectDescriptors": ",".join(subject_descriptors)},
        version="7.1",
    )
    result = {}
    for item in (response or {}).get("value") or []:
        if item and item.get("subjectDescriptor") and item.get("descriptor"):
            result[item["subjectDescriptor"]] = item["descriptor"]
    return result


def get_identities_by_descriptor(
    org_api: ApiCall,
    storage_keys: list[str],
) -> dict[str, str]:
    """Resolve storage-key descriptors to subject-descriptor format.

    Converts the ``Microsoft.TeamFoundation.Identity;S-1-9-...`` format
    returned by ``accesscontrollists`` GET back to the ``aadgp.``/``aad.``/
    ``vssgp.`` subject-descriptor format for Terraform state.

    Args:
        org_api: Organisation-scoped ApiCall (used to derive the vssps URL).
        storage_keys: List of storage-key descriptors to resolve.

    Returns:
        Dict mapping each storage-key descriptor to its subject descriptor.
        Unresolvable keys are omitted.
    """
    if not storage_keys:
        return {}
    vssps = _vssps_api(org_api)
    response = vssps.get(
        "_apis",
        "identities",
        parameters={"descriptors": ",".join(storage_keys)},
        version="7.1",
    )
    result = {}
    for item in (response or {}).get("value") or []:
        if item and item.get("descriptor") and item.get("subjectDescriptor"):
            result[item["descriptor"]] = item["subjectDescriptor"]
    return result


def get_namespace_acl(
    org_api: ApiCall,
    namespace_id: str,
    token: str,
) -> list[AceEntry]:
    """Return all ACEs for a security namespace token.

    Args:
        org_api: Organisation-scoped ApiCall (https://dev.azure.com/{org}).
        namespace_id: Security namespace GUID.
        token: ADO security token string.

    Returns:
        List of AceEntry; empty if the token has no ACL.
    """
    response = org_api.get(
        "_apis",
        "accesscontrollists",
        namespace_id,
        parameters={"token": token, "includeExtendedInfo": "false"},
        version="7.1",
    )
    if not response:
        return []
    acls = _AclContainer.model_validate(response).value
    if not acls:
        return []
    aces_dict = acls[0].get("acesDictionary") or {}
    return [
        AceEntry(
            descriptor=v["descriptor"],
            allow=v.get("allow", 0),
            deny=v.get("deny", 0),
        )
        for v in aces_dict.values()
    ]


def post_namespace_acl(
    org_api: ApiCall,
    namespace_id: str,
    token: str,
    aces: list[AceEntry],
    *,
    inherit_permissions: bool = True,
) -> None:
    """Replace all ACEs at a security namespace token (exclusive, merge=false).

    Writes via two API paths to ensure both correctness and enforcement:

    1. ``accesscontrollists`` (bulk replace) — atomically replaces the entire
       ACL at the token, removing stale ACEs and setting ``inheritPermissions``.
    2. ``accesscontrolentries`` (per-ACE update) — re-writes each ACE through
       the per-entry endpoint, which triggers ADO's enforcement-cache
       invalidation.  The ``accesscontrollists`` endpoint alone does not
       trigger this invalidation, causing permissions to appear as "Not set"
       in the ADO UI and to not be enforced despite being stored correctly.

    Args:
        org_api: Organisation-scoped ApiCall.
        namespace_id: Security namespace GUID.
        token: ADO security token string.
        aces: Complete desired ACE list — any ACE not listed is removed.
        inherit_permissions: Whether child tokens inherit from this token.
    """
    org_api.post(
        "_apis",
        "accesscontrollists",
        namespace_id,
        parameters={"merge": "false"},
        version="7.1",
        json={
            "value": [
                {
                    "token": token,
                    "inheritPermissions": inherit_permissions,
                    "acesDictionary": {
                        ace.descriptor: {
                            "descriptor": ace.descriptor,
                            "allow": ace.allow,
                            "deny": ace.deny,
                        }
                        for ace in aces
                    },
                }
            ],
        },
    )
    if not aces:
        return
    org_api.post(
        "_apis",
        "accesscontrolentries",
        namespace_id,
        version="7.1",
        json={
            "token": token,
            "merge": False,
            "accessControlEntries": [
                {
                    "descriptor": ace.descriptor,
                    "allow": ace.allow,
                    "deny": ace.deny,
                }
                for ace in aces
            ],
        },
    )


def delete_namespace_acl(
    org_api: ApiCall,
    namespace_id: str,
    token: str,
) -> None:
    """Delete the entire ACL entry at a security namespace token.

    Args:
        org_api: Organisation-scoped ApiCall.
        namespace_id: Security namespace GUID.
        token: ADO security token string.
    """
    org_api.delete(
        "_apis",
        "accesscontrollists",
        namespace_id,
        parameters={"tokens": token, "recurse": "false"},
        version="7.1",
    )


def _vssps_api(org_api: ApiCall) -> ApiCall:
    """Derive a vssps-scoped ApiCall from an org-scoped ApiCall.

    Args:
        org_api: ApiCall with URL ``https://dev.azure.com/{org}``.

    Returns:
        ApiCall targeting ``https://vssps.dev.azure.com/{org}``.
    """
    url = org_api.url.unicode_string().rstrip("/")
    org_name = url.split("/")[-1]
    return ApiCall(
        session=org_api.session,
        url=_ADO_URL_ADAPTER.validate_python(f"https://vssps.dev.azure.com/{org_name}"),
    )
