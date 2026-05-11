# Authors: The MNE-Tools contributors.
# License: BSD-3-Clause
# Copyright the MNE-Tools contributors.

import logging
import os
import subprocess

from packaging.requirements import Requirement
from tomlkit.toml_file import TOMLFile

logger = logging.getLogger(__name__)

MODULE_NAME_MAPPING = {"scikit-learn": "sklearn", "lazy-loader": "lazy_loader"}


def check_release_version(version: str) -> None:
    """Check the release version is in the expected 'X.Y.Z' format.

    Parameters
    ----------
    version : str
        The release version.
    """
    bad_version_msg = (
        "`release_version` expects the format 'X.Y.Z', where X, Y, and Z are integers."
        f"Got {version}"
    )
    try:
        split_version = list(map(int, version.split(".")))
    except ValueError as error:
        raise ValueError(bad_version_msg) from error
    if len(split_version) != 3:
        raise ValueError(bad_version_msg)


def get_contributor_names_emails(
    repo_dir: str, compound_surnames: str | None
) -> list[tuple[str, str, str]]:
    """Extract names and emails for contributors to a git repository.

    Parameters
    ----------
    repo_dir : str
        Directory of the repository to get information for.
    compound_surnames : str | None
        Comma-separated compound surnames to handle when parsing author names.

    Returns
    -------
    names_emails : list of tuple of str
        Tuples for each contributor consisting of `(first name, last name, email)`.
    """
    if compound_surnames is None:
        compound_surnames = []
    else:
        compound_surnames = [s.strip() for s in compound_surnames.split(",")]

    git_shortlog = (
        subprocess.run(
            ["git", "-C", repo_dir, "shortlog", "-nse"],
            capture_output=True,
            text=True,
            check=True,
        )
        .stdout.strip()
        .split("\n")
    )

    names_emails = [
        parse_name_email(name_blob=line, compound_surnames=compound_surnames)
        for line in git_shortlog
        if "[bot]" not in line
    ]

    return names_emails


def parse_name_email(
    name_blob: str, compound_surnames: list[str]
) -> tuple[str, str, str]:
    """Split name blobs from `git shortlog -nse` into first/last/email.

    Parameters
    ----------
    name_blob : str
        The output of a single line of `git shortlog -nse`.
    compound_surnames : list of str
        Compound surnames to handle when parsing author names.

    Returns
    -------
    name_email : tuple of (str, str, str)
        A tuple of (first name, last name, email).
    """
    _, name_and_email = name_blob.strip().split("\t")  # remove commit count

    name, email = name_and_email.split(" <")
    email = email.strip(">")
    email = "" if "noreply" in email else email  # ignore "noreply" emails
    name = " ".join(name.split("."))  # remove periods from initials

    # handle compound surnames
    for compound_surname in compound_surnames:
        if name.endswith(compound_surname):
            ix = name.index(compound_surname)
            first = name[:ix].strip()
            last = compound_surname
            return (first, last, email)

    # handle non-compound surnames
    name_elements = name.split()
    if len(name_elements) == 1:  # mononyms / usernames
        first = ""
        last = name
    else:
        first = " ".join(name_elements[:-1])
        last = name_elements[-1]

    return (first, last, email)


def get_deps_to_check(project_root: str, groups: list[str]) -> list[str]:
    """Get the dependencies whose versions should be checked from `pyproject.toml`.

    Always includes the core dependencies in the `[project]` table and the Python
    version.

    Parameters
    ----------
    project_root : str
        The directory of the project to check the environment of.
    groups : list of str
        Names of additional groups in `pyproject.toml`'s `[dependency-groups]` whose
        versions should be checked.

    Returns
    -------
    check_deps : list of str
        The dependencies whose versions should be checked.
    """
    pyproject = TOMLFile(os.path.join(project_root, "pyproject.toml"))
    pyproject_data = pyproject.read()
    check_deps = [
        [f"python {pyproject_data['project']['requires-python']}"]
        + pyproject_data["project"]["dependencies"]
    ]
    check_deps += [pyproject_data["dependency-groups"][group] for group in groups]
    logger.info(
        "Checking the versions in the environment for the following dependencies: %s",
        ", ".join(check_deps),
    )

    return check_deps


def get_min_pinned_ver(req: str) -> tuple[str, str | None]:
    """Get the minimum pinned version from a dependency specification.

    Parameters
    ----------
    req : str
        The dependency specification.

    Returns
    -------
    name : str
        The name of the module.
    min_ver : str or None
        The minimum pinned version of the module, or None if not specified.
    """
    req = Requirement(req)
    name = req.name
    spec = req.specifier
    if len(spec) == 0:
        return name, None  # no min version specified
    ge_specs = [this_spec for this_spec in spec if this_spec.operator == ">="]
    if len(ge_specs) != 1:
        raise ValueError(
            f"Expected exactly 1 '>=' specifier in `pyproject.toml` for module {name} "
            f"with version specifications, but found {len(ge_specs)}"
            f"{': ' + ', '.join([str(ge_spec) for ge_spec in ge_specs]) if len(ge_specs) > 0 else ''}."  # noqa: E501
        )  # can't use \ to break f-string statements until python 3.12

    return name, ge_specs[0].version


def get_bad_deps_message(bads: list[str], bads_reason: str) -> str:
    """Format a message about bad deps (e.g., missing, wrong version), if any.

    Parameters
    ----------
    bads : list of str
        The names of the bad dependencies to report.
    bads_reason : str
        The reason why the dependencies are bad.

    Returns
    -------
    message : str
        A message reporting the bad dependencies and the reason, or an empty string
        if there are no bad dependencies.
    """
    if len(bads) == 0:
        return ""
    return f"The following module(s) {bads_reason}:\n" + "\n".join(bads)


def raise_bad_deps_messages(bad_messages: list[str]):
    """Raise a `RuntimeError` if there are any bad messages to report.

    Parameters
    ----------
    bad_messages : list of str
        The messages to report about bad dependencies. Only non-empty messages are
        included.
    """
    bad_messages = [message for message in bad_messages if message != ""]
    if len(bad_messages) > 0:
        raise RuntimeError("\n\n".join(bad_messages))
