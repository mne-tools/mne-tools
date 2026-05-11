# Authors: The MNE-Tools contributors.
# License: BSD-3-Clause
# Copyright the MNE-Tools contributors.

import os
from argparse import SUPPRESS, ArgumentParser
from datetime import date

import tomllib

from helpers import check_release_version, get_contributor_names_emails


def main():
    parser = ArgumentParser(description="Generate `codemeta.json`.")
    parser.add_argument(
        "project_root",
        type=str,
        default=SUPPRESS,
        help="The directory of the project to get the codemeta information for.",
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
        "package_description",
        type=str,
        default=SUPPRESS,
        help="A brief description of the software package.",
    )
    parser.add_argument(
        "license_url",
        type=str,
        default=SUPPRESS,
        help="A URL to the software license.",
    )
    parser.add_argument(
        "repo_url",
        type=str,
        default=SUPPRESS,
        help="URL of the repository the codemeta is being generated for.",
    )
    parser.add_argument(
        "keywords",
        type=str,
        default=SUPPRESS,
        help="A list of comma-separated keywords describing the software.",
    )
    parser.add_argument(
        "date_created",
        type=str,
        default=SUPPRESS,
        help="The date the software was originally created, in format 'YYYY-MM-DD'.",
    )
    parser.add_argument(
        "date_published",
        type=str,
        default=SUPPRESS,
        help="The date the software was originally published, in format 'YYYY-MM-DD'.",
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
        "--date_modified",
        type=str,
        default=str(date.today()),
        help=(
            "The release date of the current version in format 'YYYY-MM-DD'. If not "
            "specified, the current date will be used."
        ),
    )
    parser.add_argument(
        "--publication_doi",
        type=str,
        default=None,
        help="The DOI for the package's published paper.",
    )
    parser.add_argument(
        "--programming_languages",
        type=str,
        default="Python",
        help="Comma-separated programming languages the software is written in.",
    )
    parser.add_argument(
        "--operating_systems",
        type=str,
        default="Linux,Windows,macOS",
        help="Comma-separated operating systems the software can run on.",
    )
    parser.add_argument(
        "--application_category",
        type=str,
        default="Neuroscience",
        help="The category to which the software belongs.",
    )

    args = parser.parse_args()
    # Required args
    project_root = args.project_root
    package_name = args.package_name
    release_version = args.release_version
    package_description = args.package_description
    license_url = args.license_url
    repo_url = args.repo_url
    keywords = args.keywords
    date_created = args.date_created
    date_published = args.date_published
    # Optional args
    compound_surnames = args.compound_surnames
    date_modified = args.date_modified
    publication_doi = args.publication_doi
    programming_languages = args.programming_languages
    operating_systems = args.operating_systems
    application_category = args.application_category

    # Check the release version format
    check_release_version(release_version)

    # Parse the git shortlog to get the list of authors
    names_emails = get_contributor_names_emails(
        repo_dir=project_root, compound_surnames=compound_surnames
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
    if keywords is not None:
        keywords = [kw.strip() for kw in keywords.split(",")]
        keywords = '",\n        "'.join(keywords)

    # Format programming languages
    programming_languages = [lang.strip() for lang in programming_languages.split(",")]
    programming_languages = '",\n        "'.join(programming_languages)

    # Format operating systems
    operating_systems = [sys.strip() for sys in operating_systems.split(",")]
    operating_systems = '",\n        "'.join(operating_systems)

    # Get dependencies and format
    with open(os.path.join(project_root, "pyproject.toml"), "r", encoding="utf-8") as f:
        pyproject = tomllib.loads(f.read())
    dependencies = [f"python{pyproject['project']['requires-python']}"]
    dependencies.extend(pyproject["project"]["dependencies"])
    dependencies = '",\n        "'.join(dependencies)

    # Assemble the codemeta JSON
    codemeta = f"""{{
    "@context": "https://doi.org/10.5063/schema/codemeta-2.0",
    "@type": "SoftwareSourceCode",
    "license": "{license_url}",
    "codeRepository": "git+{repo_url}.git",
    "dateCreated": "{date_created}",
    "datePublished": "{date_published}",
    "dateModified": "{date_modified}",
    "downloadUrl": "{repo_url}/archive/v{release_version}.zip",
    "issueTracker": "{repo_url}/issues",
    "name": "{package_name}",
    "version": "{release_version}",
    "description": "{package_description}",
    "applicationCategory": "{application_category}",
    "developmentStatus": "active",
    """
    if publication_doi is not None:
        codemeta += f'"referencePublication": "{publication_doi}"'
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
