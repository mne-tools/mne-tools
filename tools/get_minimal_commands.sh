#!/bin/bash
# Download and set up the MNE-C "minimal commands": the MNE-C binaries and the
# FreeSurfer utilities (mne_process_raw, mne_surf2bem, mri_watershed, mkheadsurf,
# ...) that MNE-Python shells out to in some tests and tutorials.
#
# The bundles are built from https://github.com/mne-tools/mne-c and published as
# release assets on mne-tools/mne-data. Platforms without a bundle are a no-op, so
# callers can invoke this unconditionally.
#
# The script can either be run (`bash get_minimal_commands.sh`) or sourced
# (`source get_minimal_commands.sh`, which additionally leaves the variables set in
# the calling shell). On GitHub Actions, Azure Pipelines and CircleCI the variables
# are persisted for the remaining steps of the job either way.
#
# Environment variables:
#   MINIMAL_CMDS_ROOT  install directory (default: ~/minimal_cmds). An existing
#                      directory is reused rather than re-downloaded, which is what
#                      makes caching it in CI work.

set -eo pipefail

MINIMAL_CMDS_ROOT="${MINIMAL_CMDS_ROOT:-${HOME}/minimal_cmds}"
_MINIMAL_CMDS_PLATFORM="$(uname -s)/$(uname -m)"

# Bump the tag and the checksums when publishing a new bundle. The CI cache keys
# used by actions/setup-minimal-commands hash this file, so editing either one
# invalidates them. The checksums are what the GitHub API reports as each asset's
# digest:
#
#   gh release view <tag> --repo mne-tools/mne-data \
#       --json assets --jq '.assets[] | "\(.digest)  \(.name)"'
_MINIMAL_CMDS_TAG="minimal-cmds-1.0"
case "${_MINIMAL_CMDS_PLATFORM}" in
	Linux/x86_64)
		_MINIMAL_CMDS_ASSET="linux-x86_64"
		_MINIMAL_CMDS_SHA256="e89d584a39f032339383c51e29fcec0b27c36f0f53010936c23d41f3cff705a7"
		;;
	Darwin/x86_64)
		_MINIMAL_CMDS_ASSET="macos-x86_64"
		_MINIMAL_CMDS_SHA256="e22d1271a09ee278fbb834229d1bec0ba9273a9126b5d3f9aa52ae39ee287476"
		;;
	Darwin/arm64)
		_MINIMAL_CMDS_ASSET="macos-arm64"
		_MINIMAL_CMDS_SHA256="977c07e19d1777c62537e52abffd7236a11f1c4c0c46d876695ef962b34e400a"
		;;
	MINGW*/x86_64 | MSYS*/x86_64 | CYGWIN*/x86_64)
		_MINIMAL_CMDS_ASSET="windows-x86_64"
		_MINIMAL_CMDS_SHA256="e9d2db5e6e95e2f02ce90d67bad88f6bfa4b42fda3638e42e1c2b7f94d3f8898"
		;;
	*)
		echo "No MNE-C minimal commands exist for ${_MINIMAL_CMDS_PLATFORM}, doing nothing."
		return 0 2>/dev/null || exit 0
		;;
esac
_MINIMAL_CMDS_URL="https://github.com/mne-tools/mne-data/releases/download/${_MINIMAL_CMDS_TAG}/minimal_cmds-${_MINIMAL_CMDS_ASSET}.tar.gz"

# sha256sum on Linux and in Git Bash, shasum on macOS
_minimal_cmds_sha256() {
	if command -v sha256sum > /dev/null; then
		sha256sum "$1" | cut -d' ' -f1
	else
		shasum -a 256 "$1" | cut -d' ' -f1
	fi
}

# Set a variable both here and for the remaining steps of the CI job
_minimal_cmds_set() {
	export "${1}=${2}"
	if [ "${GITHUB_ACTIONS}" == "true" ]; then
		echo "${1}=${2}" | tee -a "$GITHUB_ENV"
	elif [ "${AZURE_CI}" == "true" ]; then
		echo "##vso[task.setvariable variable=${1}]${2}"
	elif [ "${CIRCLECI}" == "true" ]; then
		echo "export ${1}=${2}" | tee -a "$BASH_ENV"
	fi
}

_minimal_cmds_set MNE_ROOT "${MINIMAL_CMDS_ROOT}"
export PATH="${MNE_ROOT}/bin:$PATH"
if [ "${GITHUB_ACTIONS}" == "true" ]; then
	echo "${MNE_ROOT}/bin" >> "$GITHUB_PATH"
elif [ "${AZURE_CI}" == "true" ]; then
	echo "##vso[task.setvariable variable=PATH]${PATH}"
elif [ "${CIRCLECI}" == "true" ]; then
	echo "export PATH=${MNE_ROOT}/bin:\$PATH" | tee -a "$BASH_ENV"
fi

if [ -d "${MNE_ROOT}" ]; then
	echo "Minimal commands already present in ${MNE_ROOT}, not downloading."
else
	echo "Downloading minimal commands for ${_MINIMAL_CMDS_PLATFORM} to ${MNE_ROOT} ..."
	mkdir -p "$(dirname "${MNE_ROOT}")"
	# Downloaded to a file rather than piped straight into tar so that it can be
	# checksummed before anything is unpacked and put on PATH. A cache hit skips
	# this entirely, so the check covers the download, not the CI cache.
	_MINIMAL_CMDS_TMP="$(mktemp -d)"
	_MINIMAL_CMDS_TGZ="${_MINIMAL_CMDS_TMP}/minimal_cmds.tar.gz"
	curl -fL --retry 5 --retry-connrefused -o "${_MINIMAL_CMDS_TGZ}" "${_MINIMAL_CMDS_URL}"
	_MINIMAL_CMDS_GOT="$(_minimal_cmds_sha256 "${_MINIMAL_CMDS_TGZ}")"
	if [ "${_MINIMAL_CMDS_GOT}" != "${_MINIMAL_CMDS_SHA256}" ]; then
		echo "Checksum mismatch for ${_MINIMAL_CMDS_URL}"
		echo "  expected ${_MINIMAL_CMDS_SHA256}"
		echo "  got      ${_MINIMAL_CMDS_GOT}"
		rm -rf "${_MINIMAL_CMDS_TMP}"
		return 1 2>/dev/null || exit 1
	fi
	# The tarball has a single "minimal_cmds" top-level directory
	tar xzf "${_MINIMAL_CMDS_TGZ}" -C "$(dirname "${MNE_ROOT}")"
	rm -rf "${_MINIMAL_CMDS_TMP}"
fi

# No library search path is set on any platform, deliberately. The Linux binaries
# carry DT_RUNPATH=$ORIGIN/../lib and the macOS ones link only against system
# libraries, so it is unnecessary; and it would be actively harmful, because it is
# exported for the rest of the CI job and the dynamic loader resolves it by leaf
# name for *every* process. On Linux MNE_ROOT/lib would shadow the system libz and
# libgomp; on macOS an earlier version of this script put /opt/X11/lib on
# DYLD_LIBRARY_PATH and shadowed the system OpenGL, which broke mne-python's 3D
# tests (mne-python#14230).
if [ -d "${MNE_ROOT}/bin" ] && [ -e "${MNE_ROOT}/bin/mkheadsurf" ]; then
	# The FreeSurfer helpers are tcsh scripts
	if ! command -v tcsh > /dev/null; then
		echo "tcsh not found, installing..."
		sudo apt-get install -yq tcsh
	fi
	_minimal_cmds_set FREESURFER_HOME "${MNE_ROOT}"
fi
if [ -e "${MNE_ROOT}/bin/neuromag2ft" ]; then
	_minimal_cmds_set NEUROMAG2FT_ROOT "${MNE_ROOT}/bin"
fi

unset -f _minimal_cmds_set _minimal_cmds_sha256
unset _MINIMAL_CMDS_PLATFORM _MINIMAL_CMDS_URL _MINIMAL_CMDS_ASSET _MINIMAL_CMDS_TAG \
	_MINIMAL_CMDS_SHA256 _MINIMAL_CMDS_TMP _MINIMAL_CMDS_TGZ _MINIMAL_CMDS_GOT

echo "If one of the following fails, you should update the cache + download of the minimal commands:"
set -x
which mne_process_raw
mne_process_raw --version
which mne_surf2bem
mne_surf2bem --version
if [ -n "${FREESURFER_HOME}" ]; then
	which mri_average
	mri_average --version
	which mkheadsurf
	mkheadsurf --version
fi
set +x
