#!/usr/bin/env python
from pathlib import Path

from yaml import safe_load

with open(Path(__file__).parent / "teams.yaml") as fid:
    doc = safe_load(fid)

# mapping from permission roles to what we call them in the team names
mapping = {
    "admin": "admins",
    "maintain": "maintainers",
    "read": "readers",
    "triage": "triagers",
    "write": "collaborators",
}
rev_mapping = {v: k for k, v in mapping.items()}

# teams granting org membership only, no permissions:
org_only_teams = {
    "Auxiliary",  # for e.g. billing purposes
    "MNE-Python Emeriti",
}

# multi-repo teams:
multi_repo_teams = {
    "MNE-BIDS Maintainers",  # MNE-BIDS and MNE-BIDS-app
    "MNE-bot",
    "MNE-CPP Admins",
}

# other exceptions from our standard team naming convention (`Repo-Name mapping[role]`):
role_exceptions = {
    "MNE-bot": "maintain",
}


for entry in doc:
    perms = entry.get("permissions", [])
    # ZERO-REPO TEAMS
    if len(perms) == 0:
        assert entry["name"] in org_only_teams, (
            f"team {entry['name']} has no associated repo permissions"
        )
    # SINGLE-REPO TEAMS
    elif len(perms) == 1:
        p = perms[0]
        expected = f"{p['repo']} {mapping[p['role']]}"
        if entry["name"] in role_exceptions:
            # TODO update as needed when we actually have single-repo exceptions
            pass
        else:
            # make sure our naming convention is followed
            assert entry["name"].lower() == expected, (
                f"team name: expected {expected}, got {entry['name']}"
            )
    # MULTI-REPO TEAMS
    else:
        nominal_role = entry["name"].rsplit(" ", maxsplit=1)[-1]
        alleged_role = rev_mapping.get(nominal_role.lower())
        if entry["name"] in role_exceptions:
            alleged_role = role_exceptions[entry["name"]]
        else:
            assert alleged_role, (
                f"team name claims role {nominal_role}, "
                f"expected one of {sorted(rev_mapping)}"
            )
        for perm in perms:
            assert perm["role"] == alleged_role, (
                f"team {entry['name']} "
                f"has {perm['role']} role "
                f"on repo {perm['repo']} "
                f"(expected {alleged_role})"
            )
