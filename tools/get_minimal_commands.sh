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
		_MINIMAL_CMDS_SHA256="7751ee38914a4e97e3c613d094ef6259c3de1925a5b617a84cdfd87241429487"
		;;
	Darwin/x86_64)
		_MINIMAL_CMDS_ASSET="macos-x86_64"
		_MINIMAL_CMDS_SHA256="e5b36837cf301166c543fcabf10ddaafd3582ca0dc1bf4c7e8fddb9c603667d4"
		;;
	Darwin/arm64)
		_MINIMAL_CMDS_ASSET="macos-arm64"
		_MINIMAL_CMDS_SHA256="a19058b60efcd28836f97628b9fc62f4974a358f4ab7f9c75ccf5771951be664"
		;;
	MINGW*/x86_64 | MSYS*/x86_64 | CYGWIN*/x86_64)
		_MINIMAL_CMDS_ASSET="windows-x86_64"
		_MINIMAL_CMDS_SHA256="f9d0328df2e77be7e75fa2f7ba61593d99edda09a6ef4acf352d28e984b04135"
		;;
	*)
		echo "No MNE-C minimal commands exist for ${_MINIMAL_CMDS_PLATFORM}, doing nothing."
		return 0 2>/dev/null || exit 0
		;;
esac
_MINIMAL_CMDS_URL="https://github.com/mne-tools/mne-data/releases/download/${_MINIMAL_CMDS_TAG}/minimal_cmds-${_MINIMAL_CMDS_ASSET}.tar.gz"

# Native (non-MSYS) form of a path. The MNE-C binaries are native executables that
# read MNE_ROOT to locate share/mne, and the CI PATH directives want native paths
# too, so under Git Bash the /c/... form used by the shell operations below is not
# usable by either. A no-op everywhere except Windows.
_minimal_cmds_native() {
	if command -v cygpath > /dev/null; then
		cygpath -w "$1"
	else
		printf '%s' "$1"
	fi
}

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

_MINIMAL_CMDS_NATIVE_ROOT="$(_minimal_cmds_native "${MINIMAL_CMDS_ROOT}")"
_MINIMAL_CMDS_NATIVE_BIN="$(_minimal_cmds_native "${MINIMAL_CMDS_ROOT}/bin")"
_minimal_cmds_set MNE_ROOT "${_MINIMAL_CMDS_NATIVE_ROOT}"
# The shell operations below need the MSYS form, so they use MINIMAL_CMDS_ROOT
export PATH="${MINIMAL_CMDS_ROOT}/bin:$PATH"
if [ "${GITHUB_ACTIONS}" == "true" ]; then
	echo "${_MINIMAL_CMDS_NATIVE_BIN}" >> "$GITHUB_PATH"
elif [ "${AZURE_CI}" == "true" ]; then
	# prependpath rather than overwriting PATH: assigning $PATH wholesale would hand
	# Azure an MSYS-style value and corrupt PATH for every later task
	echo "##vso[task.prependpath]${_MINIMAL_CMDS_NATIVE_BIN}"
elif [ "${CIRCLECI}" == "true" ]; then
	echo "export PATH=${MINIMAL_CMDS_ROOT}/bin:\$PATH" | tee -a "$BASH_ENV"
fi

if [ -d "${MINIMAL_CMDS_ROOT}" ]; then
	echo "Minimal commands already present in ${MINIMAL_CMDS_ROOT}, not downloading."
else
	echo "Downloading minimal commands for ${_MINIMAL_CMDS_PLATFORM} to ${MINIMAL_CMDS_ROOT} ..."
	mkdir -p "$(dirname "${MINIMAL_CMDS_ROOT}")"
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
	tar xzf "${_MINIMAL_CMDS_TGZ}" -C "$(dirname "${MINIMAL_CMDS_ROOT}")"
	# MSYS resolves "foo" and "foo.exe" to the same file, so when tar unlinks the
	# path for an extensionless entry it deletes a same-named .exe extracted
	# earlier. The Windows bundle pairs each of mne_do_forward_solution and
	# mne_setup_source_space with a /bin/sh script the .exe runs, and whichever of
	# the pair comes second in the archive wins -- so mne_do_forward_solution.exe
	# was silently disappearing (mne-python#14234). Re-extracting just the
	# executables afterwards restores them without touching the scripts, since the
	# unlink for a name that already ends in .exe gets no such magic. No-op where
	# the bundle has no .exe entries.
	_MINIMAL_CMDS_EXES="$(tar tzf "${_MINIMAL_CMDS_TGZ}" | grep -E '\.exe$' || true)"
	if [ -n "${_MINIMAL_CMDS_EXES}" ]; then
		# deliberate word splitting: these member names contain no spaces
		# shellcheck disable=SC2086
		tar xzf "${_MINIMAL_CMDS_TGZ}" -C "$(dirname "${MINIMAL_CMDS_ROOT}")" ${_MINIMAL_CMDS_EXES}
	fi
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
if [ -e "${MINIMAL_CMDS_ROOT}/bin/mkheadsurf" ]; then
	# The FreeSurfer helpers are tcsh scripts
	if ! command -v tcsh > /dev/null; then
		echo "tcsh not found, installing..."
		sudo apt-get install -yq tcsh
	fi
	_minimal_cmds_set FREESURFER_HOME "${_MINIMAL_CMDS_NATIVE_ROOT}"
fi
if [ -e "${MINIMAL_CMDS_ROOT}/bin/neuromag2ft" ]; then
	_minimal_cmds_set NEUROMAG2FT_ROOT "${_MINIMAL_CMDS_NATIVE_BIN}"
fi

unset -f _minimal_cmds_set _minimal_cmds_sha256 _minimal_cmds_native
unset _MINIMAL_CMDS_PLATFORM _MINIMAL_CMDS_URL _MINIMAL_CMDS_ASSET _MINIMAL_CMDS_TAG \
	_MINIMAL_CMDS_SHA256 _MINIMAL_CMDS_TMP _MINIMAL_CMDS_TGZ _MINIMAL_CMDS_GOT \
	_MINIMAL_CMDS_NATIVE_ROOT _MINIMAL_CMDS_NATIVE_BIN _MINIMAL_CMDS_EXES

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
