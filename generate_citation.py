# Authors: The MNE-Tools contributors.
# License: BSD-3-Clause
# Copyright the MNE-Tools contributors.

import os
import subprocess
from argparse import SUPPRESS, ArgumentParser
from datetime import date

import yaml

from helpers import (
    check_date_format,
    check_release_version,
    get_contributor_names_emails,
    read_extended_metadata,
    read_pyproject,
)


def main():
    parser = ArgumentParser(description="Generate `CITATION.cff`.")
    parser.add_argument(
        "project-root",
        type=str,
        default=SUPPRESS,
        help="The directory of the project to get the citation information for.",
    )
    parser.add_argument(
        "release-version",
        type=str,
        default=SUPPRESS,
        help="The major.minor.micro release version.",
    )
    parser.add_argument(
        "--release-date",
        type=str,
        default="",
        help=(
            "The release date of the current version in format 'YYYY-MM-DD'. If not "
            "specified, the current date will be used."
        ),
    )

    args = parser.parse_args()
    # Required args
    project_root = getattr(args, "project-root")
    release_version = getattr(args, "release-version")
    # Optional args
    release_date = args.release_date

    # Check the release version format
    check_release_version(release_version)

    # Check the release date format
    if release_date == "":
        release_date = str(date.today())
    else:
        check_date_format(release_date)

    # Read the package metadata
    pyproject = read_pyproject(project_root=project_root)
    extended_metadata = read_extended_metadata(
        os.path.join(project_root, ".extended_metadata.yaml")
    )

    # Parse the git shortlog to get the list of authors
    names_emails = get_contributor_names_emails(
        repo_dir=project_root,
        compound_surnames=extended_metadata.get("compound_surnames"),
    )

    # Format author list
    # TODO: someday would be nice to include ORCiD identifiers too
    authors = [
        {"family-names": last, "given-names": first} if first else {"name": last}
        for (first, last, _) in names_emails
    ]

    # Get the commit info
    commit = subprocess.run(
        ["git", "-C", project_root, "log", "-1", "--pretty=%H"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    # Get the message to include
    if extended_metadata.get("preferred_citation") is None:
        message = (
            "If you use this software, please cite it using the following information."
        )
    else:
        message = (
            "If you use this software, please cite both the software itself, and the "
            "paper listed in the preferred-citation field."
        )

    # Strip the keywords
    keywords = [kw.strip() for kw in pyproject["project"]["keywords"]]

    # Assemble the CFF string
    cff_contents = {
        "cff-version": "1.2.0",
        "title": extended_metadata["package_name"],
        "message": message,
        "version": release_version,
        "date-released": release_date,
        "commit": commit,
        "doi": extended_metadata["code_doi"],
        "keywords": keywords,
        "authors": authors,
    }
    if extended_metadata.get("preferred_citation") is not None:
        cff_contents["preferred-citation"] = extended_metadata["preferred_citation"]
    citation_cff = yaml.dump(
        cff_contents, sort_keys=False, allow_unicode=True, width=float("inf")
    )

    # Write to file
    with open(
        os.path.join(project_root, "CITATION.cff"), "w", encoding="utf-8"
    ) as cff_file:
        cff_file.write(citation_cff)


if __name__ == "__main__":
    main()
