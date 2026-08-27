#!/bin/bash
# Download and set up the MNE-C "minimal commands": the handful of MNE-C and
# FreeSurfer binaries (mne_process_raw, mne_surf2bem, mri_average, mkheadsurf, ...)
# that MNE-Python shells out to in some tests and tutorials.
#
# Binaries are only built for Linux x86_64 and macOS x86_64 (Intel), so on every
# other platform this is a no-op and callers can invoke it unconditionally.
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

# Bump the ?version= when uploading new binaries: the CI cache keys used by
# actions/setup-minimal-commands hash this file, so changing a URL invalidates them.
case "${_MINIMAL_CMDS_PLATFORM}" in
	Linux/x86_64)
		_MINIMAL_CMDS_URL="https://osf.io/download/g7dzs?version=7"
		;;
	Darwin/x86_64)
		_MINIMAL_CMDS_URL="https://osf.io/download/rjcz4?version=2"
		;;
	*)
		echo "No MNE-C minimal commands exist for ${_MINIMAL_CMDS_PLATFORM}, doing nothing."
		return 0 2>/dev/null || exit 0
		;;
esac

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
	# The tarball has a single "minimal_cmds" top-level directory
	curl -L --retry 5 --retry-connrefused "${_MINIMAL_CMDS_URL}" \
		| tar xz -C "$(dirname "${MNE_ROOT}")"
fi

if [ "$(uname -s)" == "Linux" ]; then
	# mkheadsurf and friends are tcsh scripts
	if ! command -v tcsh > /dev/null; then
		echo "tcsh not found, installing..."
		sudo apt-get install -yq tcsh
	fi
	# no trailing ":" -- that would put the current directory on the search path
	_minimal_cmds_set LD_LIBRARY_PATH "${MNE_ROOT}/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
	_minimal_cmds_set NEUROMAG2FT_ROOT "${MNE_ROOT}/bin"
	_minimal_cmds_set FREESURFER_HOME "${MNE_ROOT}"
else
	# The macOS binaries link against /usr/X11/lib/lib{X11,Xp,Xt,...}, so X11 is
	# needed even to run `--version`. XQuartz is pinned to 2.7.11 because later
	# releases dropped libXp. It lives outside MNE_ROOT and so is not covered by
	# caching MNE_ROOT, hence the separate existence check.
	if [ ! -d /opt/X11/lib ]; then
		echo "Installing XQuartz..."
		set -x
		curl -L --retry 5 --retry-connrefused -o "${TMPDIR:-/tmp}/XQuartz.dmg" https://github.com/XQuartz/XQuartz/releases/download/XQuartz-2.7.11/XQuartz-2.7.11.dmg
		sudo hdiutil attach "${TMPDIR:-/tmp}/XQuartz.dmg"
		sudo installer -package /Volumes/XQuartz-2.7.11/XQuartz.pkg -target /
		sudo hdiutil detach /Volumes/XQuartz-2.7.11
		rm -f "${TMPDIR:-/tmp}/XQuartz.dmg"
		set +x
	fi
	# /usr is not writable on SIP-enabled macOS, so /usr/X11 cannot be symlinked to
	# /opt/X11, and DYLD_LIBRARY_PATH is not enough on its own either: macOS strips
	# DYLD_* when it launches the (SIP-protected) system bash, so it does not survive
	# from one CI step to the next. Repoint the install names instead -- this is
	# idempotent, and it lands inside MNE_ROOT so it gets cached with it.
	for _MINIMAL_CMDS_EXE in "${MNE_ROOT}"/bin/*; do
		otool -L "${_MINIMAL_CMDS_EXE}" \
			| awk '/\/usr\/X11\/lib\//{print $1}' \
			| while read -r _MINIMAL_CMDS_LIB; do
				install_name_tool -change "${_MINIMAL_CMDS_LIB}" \
					"/opt/X11/lib/$(basename "${_MINIMAL_CMDS_LIB}")" \
					"${_MINIMAL_CMDS_EXE}"
			done
	done
	_minimal_cmds_set DYLD_LIBRARY_PATH "${MNE_ROOT}/lib:/opt/X11/lib${DYLD_LIBRARY_PATH:+:${DYLD_LIBRARY_PATH}}"
fi

unset -f _minimal_cmds_set
unset _MINIMAL_CMDS_PLATFORM _MINIMAL_CMDS_URL _MINIMAL_CMDS_EXE

echo "If one of the following fails, you should update the cache + download of the minimal commands:"
set -x
which mne_process_raw
mne_process_raw --version
which mne_surf2bem
mne_surf2bem --version
which mri_average
mri_average --version
if [ "$(uname -s)" == "Linux" ]; then
	which mkheadsurf
	mkheadsurf --version
fi
set +x
