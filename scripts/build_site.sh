#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dist_dir="${repo_dir}/dist"
map_python="${MAP_PYTHON:-python}"

if [[ -d "${dist_dir}" ]]; then
  find "${dist_dir}" -mindepth 1 -delete
fi
mkdir -p "${dist_dir}"

cd "${repo_dir}"
"${map_python}" code/build_phase_zero_map.py --output-dir "${dist_dir}"
"${map_python}" -m unittest discover -s code/tests -v
"${map_python}" scripts/validate_site.py "${dist_dir}"
