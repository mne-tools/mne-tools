# Authors: The MNE-Tools contributors.
# License: BSD-3-Clause
# Copyright the MNE-Tools contributors.

import logging
import os
from argparse import SUPPRESS, ArgumentParser

from packaging.specifiers import Specifier
from packaging.version import Version
from tomlkit.toml_file import TOMLFile

from mne_tools.helpers import (
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

    # Check that the versions in the lockfile match the minimum versions in pyproject
    # For modules, uv's `lowest-direct` option will resolve to the lowest
    # major.minor.micro version, even if a micro version isn't specified. E.g., if
    # `pyproject.toml` asks for numpy >= 1.26, the lockfile will have 1.26.0.
    # However, the non-lowest micro version of a module may be selected for
    # compatibility reasons. E.g., if `pyproject.toml` asks for pandas >= 2.2 and numpy
    # >= 2.0, pandas 2.2.2 will be placed in the lockfile, as that was the first version
    # to support numpy 2.0. Non-lowest micro versions of modules may also not be used if
    # they were yanked.
    # Therefore, if the micro version of a module isn't specified in `pyproject.toml`,
    # we don't check the micro version of the module in the environment.
    bad_missing = []
    bad_version = []
    for dep in check_deps:
        mod_name, pyproject_ver = get_min_pinned_ver(dep)
        if pyproject_ver is None:
            continue  # no min version specified, so no check needed
        pyproject_ver = Version(pyproject_ver)
        name = IMPORT_MODULE_NAME_MAPPING.get(mod_name, mod_name)

        if name not in lockfile_modules.keys():
            bad_missing.append(name)
            continue
        lockfile_ver = lockfile_modules[name]
        lockfile_ver = Version(lockfile_ver)

        # Discard micro info from lockfile version if it's not specified in pyproject
        if len(pyproject_ver.release) == 2:
            lockfile_ver = Version(f"{lockfile_ver.major}.{lockfile_ver.minor}")

        if lockfile_ver != pyproject_ver:
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
