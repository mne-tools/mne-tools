import subprocess


def check_release_version(version: str) -> None:
    """Check the release version is in the expected 'X.Y.Z' format.

    Parameters
    ----------
    version : str
        The release version.
    """
    bad_version_msg = (
        "`release_version` expects the format 'X.Y.Z', where X, Y, and Z are integers."
        f"Got {version}"
    )
    try:
        split_version = list(map(int, version.split(".")))
    except ValueError as error:
        raise ValueError(bad_version_msg) from error
    if len(split_version) != 3:
        raise ValueError(bad_version_msg)


def get_contributor_names_emails(
    repo_dir: str, compound_surnames: str | None
) -> list[tuple[str, str, str]]:
    """Extract names and emails for contributors to a git repository.

    Parameters
    ----------
    repo_dir : str
        Directory of the repository to get information for.
    compound_surnames : str | None
        Comma-separated compound surnames to handle when parsing author names.

    Returns
    -------
    names_emails : list of tuple of str
        Tuples for each contributor consisting of `(first name, last name, email)`.
    """
    if compound_surnames is None:
        compound_surnames = []
    else:
        compound_surnames = [s.strip() for s in compound_surnames.split(",")]

    git_shortlog = (
        subprocess.run(
            ["git", "-C", repo_dir, "shortlog", "-nse"],
            capture_output=True,
            text=True,
            check=True,
        )
        .stdout.strip()
        .split("\n")
    )

    names_emails = [
        parse_name_email(name_blob=line, compound_surnames=compound_surnames)
        for line in git_shortlog
        if "[bot]" not in line
    ]

    return names_emails


def parse_name_email(
    name_blob: str, compound_surnames: list[str]
) -> tuple[str, str, str]:
    """Split name blobs from `git shortlog -nse` into first/last/email.

    Parameters
    ----------
    name_blob : str
        The output of a single line of `git shortlog -nse`.
    compound_surnames : list of str
        Compound surnames to handle when parsing author names.

    Returns
    -------
    name_email : tuple of (str, str, str)
        A tuple of (first name, last name, email).
    """
    _, name_and_email = name_blob.strip().split("\t")  # remove commit count

    name, email = name_and_email.split(" <")
    email = email.strip(">")
    email = "" if "noreply" in email else email  # ignore "noreply" emails
    name = " ".join(name.split("."))  # remove periods from initials

    # handle compound surnames
    for compound_surname in compound_surnames:
        if name.endswith(compound_surname):
            ix = name.index(compound_surname)
            first = name[:ix].strip()
            last = compound_surname
            return (first, last, email)

    # handle non-compound surnames
    name_elements = name.split()
    if len(name_elements) == 1:  # mononyms / usernames
        first = ""
        last = name
    else:
        first = " ".join(name_elements[:-1])
        last = name_elements[-1]

    return (first, last, email)
