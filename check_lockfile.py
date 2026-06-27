# Authors: The MNE-Tools contributors.
# License: BSD-3-Clause
# Copyright the MNE-Tools contributors.

import logging
import os
from argparse import SUPPRESS, ArgumentParser

from packaging.specifiers import Specifier
from packaging.version import Version
from tomlkit.toml_file import TOMLFile

from helpers import (
    IMPORT_MODULE_NAME_MAPPING,
    get_bad_deps_message,
    get_deps_to_check,
    get_min_pinned_ver,
    raise_bad_deps_messages,
    split_optional_args,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Note: This script is meant to work with a uv lockfile and an 'old' environment, i.e.,
# looks for module versions in the lockfile pinned to the minimum versions in
# pyproject.toml


def main():
    parser = ArgumentParser(
        description=(
            "Check that the 'old' environment lockfile installed has the expected "
            "versions of dependencies."
        )
    )
    parser.add_argument(
        "project-root",
        type=str,
        default=SUPPRESS,
        help="The directory of the project to check the lockfile of.",
    )
    parser.add_argument(
        "lockfile-path",
        type=str,
        default=SUPPRESS,
        help=(
            "The path to the lockfile of the old environment to check, relative to the "
            "project root.",
        ),
    )
    parser.add_argument(
        "--groups",
        type=str,
        default="",
        help=(
            "Comma-separated names of additional groups in `pyproject.toml`'s "
            "`[dependency-groups]` whose versions should be checked."
        ),
    )

    args = parser.parse_args()
    # Required args
    project_root = getattr(args, "project-root")
    lockfile_path = getattr(args, "lockfile-path")
    # Optional args
    groups = split_optional_args(args.groups)

    # Get dependencies to check from pyproject.toml
    check_deps = get_deps_to_check(project_root=project_root, groups=groups)

    # Get 'old' lockfile pins for dependencies
    lockfile = TOMLFile(os.path.join(project_root, lockfile_path))
    lockfile_data = lockfile.read()
    python_spec = Specifier(lockfile_data["requires-python"])
    if python_spec.operator != ">=":
        raise ValueError(
            "Expected the Python version specifier in the lockfile to be a '>=' "
            f"specifier, but found {python_spec.operator}."
        )
    lockfile_modules = {"python": python_spec.version}
    lockfile_modules.update(
        {mod["name"]: mod["version"] for mod in lockfile_data["packages"]}
    )

    # Check that the versions in the lockfile match the min versions in pyproject.toml
    bad_missing = []
    bad_version = []
    for dep in check_deps:
        mod_name, pyproject_ver = get_min_pinned_ver(dep)
        if pyproject_ver is None:
            continue  # no min version specified, so no check needed
        name = IMPORT_MODULE_NAME_MAPPING.get(mod_name, mod_name)

        if name not in lockfile_modules.keys():
            bad_missing.append(name)
            continue
        lockfile_ver = lockfile_modules[name]

        if Version(lockfile_ver) != Version(pyproject_ver):
            bad_version.append(
                f"lower pin on {name} in `pyproject.toml` is {pyproject_ver}, but the "
                f"lockfile has {lockfile_ver}"
            )

    # Format bad messages and raise if there are any bads
    bad_missing = get_bad_deps_message(bad_missing, "are missing from the lockfile")
    bad_version = get_bad_deps_message(
        bad_version, "have incorrect versions in the lockfile"
    )
    raise_bad_deps_messages([bad_missing, bad_version])


if __name__ == "__main__":
    main()
