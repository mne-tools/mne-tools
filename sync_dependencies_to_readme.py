# Authors: The MNE-Tools contributors.
# License: BSD-3-Clause
# Copyright the MNE-Tools contributors.

import difflib
import logging
import os
from argparse import SUPPRESS, ArgumentParser

import requests
from packaging.requirements import Requirement

from helpers import prettify_pins, read_pyproject, split_optional_args

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BEGIN = ".. ↓↓↓ BEGIN CORE DEPS LIST. DO NOT EDIT! HANDLED BY MNE-TOOLS ↓↓↓"
END = ".. ↑↑↑ END CORE DEPS LIST. DO NOT EDIT! HANDLED BY MNE-TOOLS ↑↑↑"


def main():
    parser = ArgumentParser(
        description="Sync dependency information from `pyproject.toml` to `README.rst`."
    )
    parser.add_argument(
        "project-root",
        type=str,
        default=SUPPRESS,
        help="The directory of the project to sync the dependency information for.",
    )
    parser.add_argument(
        "--ignore-upper-pins",
        type=str,
        default=None,
        help=(
            "A comma-separated list of packages for which to ignore upper pin "
            "constraints when listing dependencies.",
        ),
    )

    args = parser.parse_args()
    # Required args
    project_root = getattr(args, "project-root")
    # Optional args
    ignore_upper_pins = split_optional_args(args.ignore_upper_pins)

    # Get the dependency info
    pyproject = read_pyproject(project_root=project_root)
    core_deps = [f"python {pyproject['project']['requires-python']}"]
    core_deps.extend(pyproject["project"]["dependencies"])
    core_deps_pins = dict()
    for dep in core_deps:
        req = Requirement(dep)
        core_deps_pins[req.name] = prettify_pins(str(req.specifier))

    # Ignore upper pins when specified (e.g., when only important for devs)
    for dep in ignore_upper_pins:
        if dep in core_deps_pins:
            pin = core_deps_pins[dep]
            if " < " in pin:
                core_deps_pins[dep] = pin.split(" < ")[0]

    # Get dependency URLs
    core_deps_urls = {dep: None for dep in core_deps_pins.keys()}
    url_search_order = [
        "project_urls/homepage",
        "project_urls/documentation",
        "project_urls/repository",
        "project_urls/source code",
        "home_page",
        "docs_url",
        "project_url",
    ]
    for dep in core_deps_pins:
        if dep == "python":
            core_deps_urls[dep] = "https://www.python.org"
            continue

        logger.info("Querying pypi.org for %s metadata...", dep)
        dep_info = requests.get(
            f"https://pypi.org/pypi/{dep}/json",
            headers={"Accept": "application/json"},
            timeout=10,
        ).json()["info"]
        logger.info("OK")

        # Normalize project_urls keys to lowercase
        project_urls = {
            k.lower(): v for k, v in (dep_info.get("project_urls") or {}).items()
        }

        # Search for URL in priority order
        for url_path in url_search_order:
            if url_path.startswith("project_urls/"):
                url_key = url_path.split("/")[1]
                if url_key in project_urls:
                    core_deps_urls[dep] = project_urls[url_key]
                    break
            elif dep_info.get(url_path):
                core_deps_urls[dep] = dep_info[url_path]
                break
    if any(url is None for url in core_deps_urls.values()):
        logger.warning(
            "Could not find URLs for the following dependencies: %s",
            ", ".join([dep for dep, url in core_deps_urls.items() if url is None]),
        )

    # Construct the rST
    core_deps_bullets = []
    for key, url in core_deps_urls.items():
        if url is not None:
            core_deps_bullets.append(
                f"- `{key} <{url}>`__{core_deps_pins[key.lower()]}"
            )
        else:
            core_deps_bullets.append(f"- {key}{core_deps_pins[key.lower()]}")

    # Rewrite the README file
    readme_path = os.path.join(project_root, "README.rst")
    with open(readme_path, "r", encoding="utf-8") as f:
        readme = f.read()
    lines = readme.splitlines()
    out_lines = list()
    skip = False
    for line in lines:
        if line.strip() == BEGIN:
            skip = True
            out_lines.append(line)
            out_lines.extend(["", *core_deps_bullets, ""])
        if line.strip() == END:
            skip = False
        if not skip:
            out_lines.append(line)
    new = "\n".join(out_lines) + "\n"
    old = readme
    if new != old:
        diff = "\n".join(difflib.unified_diff(old.splitlines(), new.splitlines()))
        logger.info("Updating %s with diff:\n%s", readme_path, diff)
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(new)


if __name__ == "__main__":
    main()
