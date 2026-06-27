# Authors: The MNE-Tools contributors.
# License: BSD-3-Clause
# Copyright the MNE-Tools contributors.

import logging
import os
import subprocess
from datetime import date

import tomllib
import yaml
from packaging.requirements import Requirement

logger = logging.getLogger(__name__)

MODULE_IMPORT_NAME_MAPPING = {"scikit-learn": "sklearn", "lazy-loader": "lazy_loader"}
IMPORT_MODULE_NAME_MAPPING = {
    value: key for key, value in MODULE_IMPORT_NAME_MAPPING.items()
}

PIP_CONDA_MAPPING = {"neo": "python-neo"}


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


def check_date_format(date_str: str) -> None:
    """Check the date string is in the 'YYYY-MM-DD' format.

    Parameters
    ----------
    date_str : str
        The date string to check.
    """
    try:
        date.fromisoformat(date_str)
    except ValueError as error:
        raise ValueError(
            f"`date_modified` expects the format 'YYYY-MM-DD'. Got {date_str}"
        ) from error


def read_pyproject(project_root: str) -> dict:
    """Read `pyproject.toml` file.

    Parameters
    ----------
    project_root : str
        The path to the project root directory.

    Returns
    -------
    pyproject : dict
        The `pyproject.toml` contents.
    """
    with open(os.path.join(project_root, "pyproject.toml"), "r", encoding="utf-8") as f:
        pyproject = tomllib.loads(f.read())

    return pyproject


def read_extended_metadata(metadata_path: str) -> dict:
    """Read extended package metadata from a yaml file.

    Parameters
    ----------
    metadata_path : str
        The path to the package metadata file.

    Returns
    -------
    metadata : dict
        The package metadata.
    """
    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = yaml.safe_load(f)

    return metadata


def get_contributor_names_emails(
    repo_dir: str, compound_surnames: list[str] | None
) -> list[tuple[str, str, str]]:
    """Extract names and emails for contributors to a git repository.

    Parameters
    ----------
    repo_dir : str
        Directory of the repository to get information for.
    compound_surnames : list of str | None
        List of compound surnames to handle when parsing author names.

    Returns
    -------
    names_emails : list of tuple of str
        Tuples for each contributor consisting of `(first name, last name, email)`.
    """
    if compound_surnames is None:
        compound_surnames = []
    else:
        compound_surnames = [s.strip() for s in compound_surnames]

    git_shortlog = (
        subprocess.run(
            ["git", "-C", repo_dir, "shortlog", "-nse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        .stdout.strip()
        .split("\n")
    )

    print(f"shortlog: {git_shortlog}")

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
    out = name_blob.strip().split("\t")  # remove commit count
    if len(out) != 2:
        print(f"name blob: {name_blob}")
        assert False
    name_and_email = out[1]

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
    pyproject_data = read_pyproject(project_root=project_root)
    check_deps = [f"python {pyproject_data['project']['requires-python']}"]
    check_deps.extend(pyproject_data["project"]["dependencies"])
    for group in groups:
        check_deps.extend(pyproject_data["dependency-groups"][group])
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


def prettify_pins(req: str | None) -> str:
    """Make a version specifier pin prettier.

    Parameters
    ----------
    req : str or None
        The dependency specification. If None, an empty string will be returned.

    Returns
    -------
    pretty_req : str
        The prettified dependency specification.
    """
    if req is None:
        return ""
    reqs = req.split(",")
    replacements = {
        "<=": " ≤ ",
        ">=": " ≥ ",
        "<": " < ",
        ">": " > ",
    }
    for old, new in replacements.items():
        reqs = [p.replace(old, new) for p in reqs]
    reqs = reversed(reqs)
    return ",".join(reqs)


def split_optional_args(arg: str | None, sep: str = ",") -> list[str]:
    """Split a string of optional arguments into a list.

    Parameters
    ----------
    arg : str | None
        The string of optional arguments. If None, an empty list will be returned.
    sep : str, optional (Default ",")
        The separator to use for splitting the string.

    Returns
    -------
    arg_list : list of str
        The list of optional arguments.
    """
    if arg is None:
        return []
    return [a.strip() for a in arg.split(sep)]
