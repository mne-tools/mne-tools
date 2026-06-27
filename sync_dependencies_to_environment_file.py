# Authors: The MNE-Tools contributors.
# License: BSD-3-Clause
# Copyright the MNE-Tools contributors.

from argparse import SUPPRESS, ArgumentParser
from pathlib import Path
from packaging.requirements import Requirement
import logging

from helpers import split_optional_args, read_pyproject, PIP_CONDA_MAPPING

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
        default=None,
        help=(
            "Comma-separated names of extra dependencies in `pyproject.toml`'s "
            "`[project.optional-dependencies]` that should be included in "
            "`environment.yml`."
        ),
    )
    parser.add_argument(
        "--additional-dependencies",
        type=str,
        default=None,
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
        default=None,
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
        default=None,
        help=(
            "Comma-separated dependencies parseable by "
            "`packaging.requirements.Requirement`, which will override the information "
            "for those same dependencies as specified in `pyproject.toml`."
        ),
    )

    args = parser.parse_args()
    # Required args
    project_root = args.project_root
    # Optional args
    extras = split_optional_args(args.extras)
    additional_dependencies = split_optional_args(args.additional_dependencies)
    channels = split_optional_args(args.channels)
    if len(channels) == 0:
        raise ValueError("At least one channel must be specified in `channels`.")
    pip_dependencies = split_optional_args(args.pip_dependencies)
    requirements_overrides = split_optional_args(args.requirements_overrides)
    requirements_overrides = [Requirement(req) for req in requirements_overrides]
    requirements_overrides = {req.name: req for req in requirements_overrides}

    # Get the `pyproject.toml` dependency info
    pyproject = read_pyproject(project_root=project_root)
    deps = pyproject["project"]["dependencies"]
    for extra in extras:
        deps.extend(pyproject["project"]["optional-dependencies"][extra])
    deps = [Requirement(dep) for dep in deps]  # parse deps to handle extras and markers

    # Remove recursive dependencies
    deps = [dep for dep in deps if dep.name != pyproject["project"]["name"]]

    # Override dependency info
    for dep in requirements_overrides.keys():
        if dep not in [d.name for d in deps]:
            raise ValueError(
                f"Dependency {dep} in `requirements_overrides` is not specified in "
                "`pyproject.toml`."
            )
    for idx, dep in enumerate(deps):
        if dep.name in requirements_overrides:
            deps[idx] = requirements_overrides[dep.name]

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

    # Map pip names to conda names
    mapped_reqs = {}
    for name, req in conda_deps.items():
        new_name = PIP_CONDA_MAPPING.get(name, name)
        if new_name == name:
            continue
        new_req = Requirement(str(req).replace(name, new_name, 1))
        mapped_reqs[name] = new_req
    conda_deps = {
        name: req for name, req in conda_deps.items() if name not in mapped_reqs
    }
    conda_deps.update({req.name: req for req in mapped_reqs.values()})

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


if __name__ == "__main__":
    main()
