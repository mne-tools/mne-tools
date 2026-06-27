# Authors: The MNE-Tools contributors.
# License: BSD-3-Clause
# Copyright the MNE-Tools contributors.

import os
from argparse import SUPPRESS, ArgumentParser

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
        default=None,
        help=(
            "The release date of the current version in format 'YYYY-MM-DD'. If not "
            "specified, the current date will be used."
        ),
    )

    args = parser.parse_args()
    # Required args
    project_root = args.project_root
    release_version = args.release_version
    # Optional args
    date_modified = args.date_modified

    # Check the release version format
    check_release_version(release_version)

    # Check the date modified format
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
        f"""{{
           "@type":"Person",
           "email":"{email}",
           "givenName":"{first}",
           "familyName": "{last}"
        }}"""
        for (first, last, email) in names_emails
    ]
    authors = ",\n        ".join(authors)

    # Format keywords
    keywords = [kw.strip() for kw in pyproject["project"]["keywords"]]
    keywords = '",\n        "'.join(keywords)

    # Format programming languages
    programming_languages = [
        lang for lang in classifiers if lang.startswith("Programming Language")
    ]
    programming_languages = {
        lang.split("::")[1].strip() for lang in programming_languages
    }
    programming_languages = '",\n        "'.join(programming_languages)

    # Format operating systems
    operating_systems = [os for os in classifiers if os.startswith("Operating System")]
    operating_systems = {os.split("::")[-1].strip() for os in operating_systems}
    operating_systems = '",\n        "'.join(operating_systems)

    # Get dependencies and format
    dependencies = [f"python {pyproject['project']['requires-python']}"]
    dependencies.extend(pyproject["project"]["dependencies"])
    dependencies = '",\n        "'.join(dependencies)

    # Get repo url
    repo_url = pyproject["project"]["urls"].get("Source Code")
    if repo_url is None:
        repo_url = pyproject["project"]["urls"]["Repository"]
    repo_url = repo_url.rstrip("/")

    # Assemble the codemeta JSON
    codemeta = f"""{{
    "@context": "https://doi.org/10.5063/schema/codemeta-2.0",
    "@type": "SoftwareSourceCode",
    "license": "https://spdx.org/licenses/{pyproject["project"]["license"]}",
    "codeRepository": "git+{repo_url}.git",
    "dateCreated": "{extended_metadata["date_created"]}",
    "datePublished": "{extended_metadata["date_published"]}",
    "dateModified": "{date_modified}",
    "downloadUrl": "{repo_url}/archive/v{release_version}.zip",
    "issueTracker": "{repo_url}/issues",
    "name": "{extended_metadata["package_name"]}",
    "version": "{release_version}",
    "description": "{pyproject["project"]["description"]}",
    "applicationCategory": "{extended_metadata["application_category"]}",
    "developmentStatus": "active","""
    if extended_metadata.get("preferred_citation") is not None:
        codemeta += f'''
    "referencePublication": "{extended_metadata["preferred_citation"]["doi"]}",'''
    codemeta += f"""
    "keywords": [
        "{keywords}"
    ],
    "programmingLanguage": [
        "{programming_languages}"
    ],
    "operatingSystem": [
        "{operating_systems}"
    ],
    "softwareRequirements": [
        "{dependencies}"
    ],
    "author": [
        {authors}
    ]
}}
"""

    # Write to file
    with open(
        os.path.join(project_root, "codemeta.json"), "w", encoding="utf-8"
    ) as codemeta_file:
        codemeta_file.write(codemeta)


if __name__ == "__main__":
    main()
