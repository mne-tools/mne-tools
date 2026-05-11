# Authors: The MNE-Tools contributors.
# License: BSD-3-Clause
# Copyright the MNE-Tools contributors.

import os
import subprocess
from argparse import SUPPRESS, ArgumentParser
from datetime import date

from helpers import check_release_version, get_contributor_names_emails


def main():
    parser = ArgumentParser(description="Generate `CITATION.cff`.")
    parser.add_argument(
        "project_root",
        type=str,
        default=SUPPRESS,
        help="The directory of the project to get the citation information for.",
    )
    parser.add_argument(
        "package_name",
        type=str,
        default=SUPPRESS,
        help="The name of the software package.",
    )
    parser.add_argument(
        "release_version",
        type=str,
        default=SUPPRESS,
        help="The major.minor.micro release version.",
    )
    parser.add_argument(
        "code_doi",
        type=str,
        default=SUPPRESS,
        help="The DOI for the package's code, e.g., on Zenodo.",
    )
    parser.add_argument(
        "keywords",
        type=str,
        default=SUPPRESS,
        help="A list of comma-separated keywords describing the software.",
    )
    parser.add_argument(
        "--compound_surnames",
        type=str,
        default=None,
        help=(
            "Comma-separated compound surnames to handle when parsing author names in "
            "from git's shortlog."
        ),
    )
    parser.add_argument(
        "--release_date",
        type=str,
        default=str(date.today()),
        help=(
            "The release date in format 'YYYY-MM-DD'. If not specified, the current "
            "date will be used."
        ),
    )
    parser.add_argument(
        "--preferred_citation",
        type=str,
        default=None,
        help=(
            "The preferred citation for the software, in cff format. This should be "
            "a YAML string that can be directly included in the `CITATION.cff` file."
        ),
    )

    args = parser.parse_args()
    # Required args
    project_root = args.project_root
    package_name = args.package_name
    release_version = args.release_version
    code_doi = args.code_doi
    keywords = args.keywords
    # Optional args
    compound_surnames = args.compound_surnames
    release_date = args.release_date
    preferred_citation = args.preferred_citation

    # Check the release version format
    check_release_version(release_version)

    # Parse the git shortlog to get the list of authors
    names_emails = get_contributor_names_emails(
        repo_dir=project_root, compound_surnames=compound_surnames
    )

    # Format author list
    # TODO: someday would be nice to include ORCiD identifiers too
    authors = [
        f"  - family-names: {last}\n    given-names: {first}"
        if first
        else f"  - name: {last}"
        for (first, last, _) in names_emails
    ]
    authors = "\n".join(authors)

    # Get the commit info
    commit = subprocess.run(
        ["git", "-C", project_root, "log", "-1", "--pretty=%H"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    # Get the message to include
    if preferred_citation is None:
        message = (
            "If you use this software, please cite it using the following information."
        )
    else:
        message = (
            "If you use this software, please cite both the software itself, and the "
            "paper listed in the preferred-citation field."
        )

    # Wrap multi-word keywords in quotes and form a bulleted list
    keywords = [kw.strip() for kw in keywords.split(",")]
    keywords = (f'"{kw}"' if " " in kw else kw for kw in keywords)
    keywords = "\n".join(f"  - {kw}" for kw in keywords)

    # Assemble the CFF string
    citation_cff = f"""\
cff-version: 1.2.0
title: "{package_name}"
message: "{message}"
version: {release_version}
date-released: "{release_date}"
commit: {commit}
doi: {code_doi}
keywords:
{keywords}
authors:
{authors}
"""
    if preferred_citation is not None:
        citation_cff += f"preferred-citation:\n{preferred_citation}\n"

    # Write to file
    with open(
        os.path.join(project_root, "CITATION.cff"), "w", encoding="utf-8"
    ) as cff_file:
        cff_file.write(citation_cff)


if __name__ == "__main__":
    main()
