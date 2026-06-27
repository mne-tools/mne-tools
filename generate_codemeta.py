# Authors: The MNE-Tools contributors.
# License: BSD-3-Clause
# Copyright the MNE-Tools contributors.

import json
import os
from argparse import SUPPRESS, ArgumentParser
from datetime import date

from helpers import (
    check_date_format,
    check_release_version,
    get_contributor_names_emails,
    read_extended_metadata,
    read_pyproject,
)


def main():
    parser = ArgumentParser(description="Generate `codemeta.json`.")
    parser.add_argument(
        "project-root",
        type=str,
        default=SUPPRESS,
        help="The directory of the project to get the codemeta information for.",
    )
    parser.add_argument(
        "release-version",
        type=str,
        default=SUPPRESS,
        help="The major.minor.micro release version.",
    )
    parser.add_argument(
        "--date-modified",
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
    date_modified = args.date_modified

    # Check the release version format
    check_release_version(release_version)

    # Check the date modified format
    if date_modified == "":
        date_modified = str(date.today())
    else:
        check_date_format(date_modified)

    # Read the package metadata
    pyproject = read_pyproject(project_root=project_root)
    classifiers = pyproject["project"].get("classifiers", [])
    extended_metadata = read_extended_metadata(
        os.path.join(project_root, ".extended_metadata.yaml")
    )

    # Parse the git shortlog to get the list of authors
    names_emails = get_contributor_names_emails(
        repo_dir=project_root,
        compound_surnames=extended_metadata.get("compound_surnames"),
    )

    # Format author list
    authors = [
        {"@type": "Person", "email": email, "givenName": first, "familyName": last}
        for (first, last, email) in names_emails
    ]

    # Format keywords
    keywords = [kw.strip() for kw in pyproject["project"]["keywords"]]

    # Format programming languages
    programming_languages = [
        lang for lang in classifiers if lang.startswith("Programming Language")
    ]
    programming_languages = list(
        {lang.split("::")[1].strip() for lang in programming_languages}
    )

    # Format operating systems
    operating_systems = [
        opsys for opsys in classifiers if opsys.startswith("Operating System")
    ]
    operating_systems = {opsys.split("::")[-1].strip() for opsys in operating_systems}

    # Get dependencies and format
    dependencies = [f"python {pyproject['project']['requires-python']}"]
    dependencies.extend(pyproject["project"]["dependencies"])

    # Get repo url
    repo_url = pyproject["project"]["urls"].get("Source Code")
    if repo_url is None:
        repo_url = pyproject["project"]["urls"]["Repository"]
    repo_url = repo_url.rstrip("/")

    # Assemble the codemeta JSON
    codemeta_contents = {
        "@context": "https://doi.org/10.5063/schema/codemeta-2.0",
        "@type": "SoftwareSourceCode",
        "license": f"https://spdx.org/licenses/{pyproject['project']['license']}",
        "codeRepository": f"git+{repo_url}.git",
        "dateCreated": extended_metadata["date_created"],
        "datePublished": extended_metadata["date_published"],
        "dateModified": date_modified,
        "downloadUrl": f"{repo_url}/archive/v{release_version}.zip",
        "issueTracker": f"{repo_url}/issues",
        "name": extended_metadata["package_name"],
        "version": release_version,
        "description": pyproject["project"]["description"],
        "applicationCategory": extended_metadata["application_category"],
        "developmentStatus": "active",
    }
    if extended_metadata.get("preferred_citation") is not None:
        codemeta_contents["referencePublication"] = extended_metadata[
            "preferred_citation"
        ]["doi"]
    codemeta_contents["keywords"] = keywords
    codemeta_contents["programmingLanguage"] = programming_languages
    codemeta_contents["operatingSystem"] = list(operating_systems)
    codemeta_contents["softwareRequirements"] = dependencies
    codemeta_contents["author"] = authors
    codemeta = json.dumps(codemeta_contents, indent=4)
    codemeta += "\n"

    # Write to file
    with open(
        os.path.join(project_root, "codemeta.json"), "w", encoding="utf-8"
    ) as codemeta_file:
        codemeta_file.write(codemeta)


if __name__ == "__main__":
    main()
