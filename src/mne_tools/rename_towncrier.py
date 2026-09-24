# Authors: The MNE-Tools contributors.
# License: BSD-3-Clause
# Copyright the MNE-Tools contributors.

# Adapted from action-towncrier-changelog
import json
import logging
import os
import re
import subprocess
from argparse import SUPPRESS, ArgumentParser

from github import Github

from mne_tools.helpers import read_pyproject

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Add PR numbers to towncrier files on pull request events.

    Expects `pyproject.toml` to have a `[tool.towncrier]` section, and looks for
    modified rst files matching the towncrier types.
    """
    parser = ArgumentParser(description="Add PR numbers to towncrier files.")
    parser.add_argument(
        "project-root",
        type=str,
        default=SUPPRESS,
        help="The directory of the project to add PR numbers to.",
    )

    args = parser.parse_args()
    project_root = getattr(args, "project-root")

    # Get event info
    event_name = os.getenv("GITHUB_EVENT_NAME")
    if not event_name.startswith("pull_request"):
        logger.info("No-op for `%s` event. Expected `pull_request` event.", event_name)
        return
    with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as fin:
        event = json.load(fin)
    pr_num = event["number"]
    base_repo_name = event["pull_request"]["base"]["repo"]["full_name"]

    # Get towncrier settings
    pyproject = read_pyproject(project_root)
    if "tool" not in pyproject or "towncrier" not in pyproject["tool"]:
        raise RuntimeError("No `[tool.towncrier]` section found in `pyproject.toml`.")
    tc_config = pyproject["tool"]["towncrier"]
    tc_types = [ent["directory"] for ent in tc_config["type"]]

    # Get modified files
    gh = Github(os.environ.get("GITHUB_TOKEN"))
    base_repo = gh.get_repo(base_repo_name)
    pr = base_repo.get_pull(pr_num)
    modified_files = [f.filename for f in pr.get_files()]

    # Get files that potentially match the types and rename them
    directory = tc_config["directory"]
    if not directory.endswith("/"):
        directory += "/"
    types_re = "|".join(re.escape(tc_type) for tc_type in tc_types)
    file_re = re.compile(rf"^{re.escape(directory)}({types_re})(\.\d+)?\.rst$")
    found_stubs = [f for f in modified_files if file_re.match(f)]
    for stub in found_stubs:
        fro = stub
        to = file_re.sub(rf"{directory}{pr_num}.\1\2.rst", fro)
        logger.info("Renaming %s to %s", fro, to)
        subprocess.check_call(["mv", fro, to])


if __name__ == "__main__":
    main()
