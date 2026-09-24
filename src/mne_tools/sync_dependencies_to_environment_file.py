# Authors: The MNE-Tools contributors.
# License: BSD-3-Clause
# Copyright the MNE-Tools contributors.

import logging
from argparse import SUPPRESS, ArgumentParser
from pathlib import Path

from packaging.requirements import Requirement, SpecifierSet

from mne_tools.helpers import read_pyproject, split_optional_args

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    parser = ArgumentParser(
        description=(
            "Sync dependency information from `pyproject.toml` to `environment.yml`."
        )
    )
    parser.add_argument(
        "project-root",
        type=str,
        default=SUPPRESS,
        help="The directory of the project to sync the dependency information for.",
    )
    parser.add_argument(
        "--extras",
        type=str,
        default="",
        help=(
            "Comma-separated names of extra dependencies in `pyproject.toml`'s "
            "`[project.optional-dependencies]` that should be included in "
            "`environment.yml`."
        ),
    )
    parser.add_argument(
        "--additional-dependencies",
        type=str,
        default="",
        help=(
            "Comma-separated names of additional dependencies that are not included in "
            "`pyproject.toml`, but which should be included in `environment.yml`."
        ),
    )
    parser.add_argument(
        "--channels",
        type=str,
        default="conda-forge",
        help="Comma-separated names of channels to include in `environment.yml`.",
    )
    parser.add_argument(
        "--pip-dependencies",
        type=str,
        default="",
        help=(
            "Comma-separated names of dependencies which should be installed via pip. "
            "The should be dependencies already included as core dependencies, in "
            "`extras`, or in `additional_dependencies`. Dependencies specified with "
            "extras or markers will be automatically included as pip dependencies."
        ),
    )
    parser.add_argument(
        "--requirements-overrides",
        type=str,
        default="",
        help=(
            "Comma-separated dependencies parseable by "
            "`packaging.requirements.Requirement`, which will override the information "
            "for those same dependencies as specified in `pyproject.toml`. "
            "Pip-to-conda name mapping can be provided using `->`, e.g., "
            "`mne->mne-base` will add `mne-base` instead of `mne` to "
            "`environment.yml`. Existing requirements will be carried over, unless "
            "overridden explicitly, e.g., if `mne>=1.6` is the dependency in "
            "`pyproject.toml`, `mne->mne-base>=1.10` will put `mne-base>=1.10` in "
            "`environment.yml`."
        ),
    )

    args = parser.parse_args()
    # Required args
    project_root = getattr(args, "project-root")
    # Optional args
    extras = split_optional_args(args.extras)
    additional_dependencies = split_optional_args(args.additional_dependencies)
    channels = split_optional_args(args.channels)
    if len(channels) == 0:
        raise ValueError("At least one channel must be specified in `channels`.")
    pip_dependencies = split_optional_args(args.pip_dependencies)
    requirements_overrides = split_optional_args(args.requirements_overrides)

    # Get the `pyproject.toml` dependency info
    pyproject = read_pyproject(project_root=project_root)
    deps = pyproject["project"]["dependencies"]
    for extra in extras:
        deps.extend(pyproject["project"]["optional-dependencies"][extra])
    deps = [Requirement(dep) for dep in deps]  # parse deps to handle extras and markers

    # Remove recursive dependencies
    deps = [dep for dep in deps if dep.name != pyproject["project"]["name"]]

    # Parse requirement overrides
    overrides = dict()
    dep_names = [dep.name for dep in deps]
    for req in requirements_overrides:
        if "->" in req:  # handle requirement renaming
            split_reqs = req.split("->")  # expected form is `pyproj_name->env_req`
            if len(split_reqs) != 2:
                raise ValueError(
                    f"Invalid requirement override with name mapping: {req}. Expected "
                    "format is '<pyproject.toml name> -> <environment.yml name>'."
                )
            pyproj_req, env_req = Requirement(split_reqs[0]), Requirement(split_reqs[1])
            _check_pyproj_dep_present(pyproj_req.name, dep_names)
            pyproj_dep = deps[dep_names.index(pyproj_req.name)]
            # Carry over specifiers/extras/markers if not overridden
            for attr, empty in zip(
                ["specifier", "extras", "marker"], [SpecifierSet(), dict(), None]
            ):
                if getattr(env_req, attr) == empty and getattr(pyproj_dep, attr):
                    setattr(env_req, attr, getattr(pyproj_dep, attr))
            overrides[pyproj_req.name] = env_req
        else:  # else use override directly
            req = Requirement(req)
            _check_pyproj_dep_present(req.name, dep_names)
            overrides[req.name] = req

    # Override dependency info
    for idx, dep in enumerate(deps):
        if dep.name in overrides:
            deps[idx] = overrides[dep.name]

    # Add additional dependencies
    deps.extend(Requirement(dep) for dep in additional_dependencies)

    # Check and remove duplicate dependencies
    seen = dict()
    for dep in deps:
        if dep.name in seen:
            if dep != seen[dep.name]:
                raise ValueError(
                    "There are conflicting specifications for the dependency "
                    f"{dep.name}: {dep} vs. {seen[dep.name]}"
                )
        else:
            seen[dep.name] = dep
    deps = seen  # keep as dict for convenience, now that duplicates are handled

    # Isolate pip dependencies (specified, and those with extras or markers)
    pip_deps = dict()
    for dep in pip_dependencies:
        if dep not in deps.keys():
            raise ValueError(
                f"Dependency {dep} is specified as a pip dependency, but it does not "
                "appear in the existing dependencies."
            )
    for name, req in deps.items():
        if name in pip_dependencies or req.extras or req.marker:
            pip_deps[name] = req
    conda_deps = {name: req for name, req in deps.items() if name not in pip_deps}

    # Construct the `environment.yml` content
    env_contents = f"""\
# THIS FILE IS AUTO-GENERATED BY MNE-TOOLS AND WILL BE OVERWRITTEN
name: {pyproject["project"]["name"]}
channels:
"""
    for channel in channels:
        env_contents += f"  - {channel}\n"
    env_contents += f"""\
dependencies:
  - python {pyproject["project"]["requires-python"].replace(" ", "")}
"""
    conda_deps = dict(sorted(conda_deps.items(), key=lambda item: item[0].lower()))
    for req in conda_deps.values():
        env_contents += (
            f"  - {req.name}{' ' + str(req.specifier) if req.specifier else ''}\n"
        )
    if pip_deps:
        env_contents += "  - pip:\n"
        for req in pip_deps.values():
            env_contents += f"      - {req}\n"

    # Save the `environment.yml` file
    with open(
        Path(project_root) / "environment.yml", "w", encoding="utf-8"
    ) as env_file:
        env_file.write(env_contents)


def _check_pyproj_dep_present(check: str, deps: list[str]) -> None:
    if check not in deps:
        raise ValueError(
            f"Dependency '{check}' in `requirements_overrides` is not specified in "
            "`pyproject.toml`."
        )


if __name__ == "__main__":
    main()
