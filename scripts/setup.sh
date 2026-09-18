#!/usr/bin/env bash
set -euo pipefail

package_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
workspace=$PWD
python_version=3.12
index_url=
wheelhouse=
offline=false
agents=()
all=false

while [ "$#" -gt 0 ]; do
    case "$1" in
        --workspace) workspace=$2; shift 2 ;;
        --agent) agents+=("$2"); shift 2 ;;
        --all) all=true; shift ;;
        --python) python_version=$2; shift 2 ;;
        --index-url) index_url=$2; shift 2 ;;
        --wheelhouse) wheelhouse=$2; shift 2 ;;
        --offline) offline=true; shift ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done

if ! command -v uv >/dev/null 2>&1; then
    echo "uv was not found; installing it from https://astral.sh/uv ..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

install_args=(--system-certs tool install --force --python "$python_version")
if [ -n "$index_url" ]; then
    install_args+=(--default-index "$index_url")
fi
if [ -n "$wheelhouse" ]; then
    install_args+=(--find-links "$wheelhouse")
fi
if [ "$offline" = true ]; then
    install_args+=(--offline)
fi
uv "${install_args[@]}" "$package_root"
export PATH="$(uv tool dir --bin):$PATH"

integrate_args=(integrate --workspace "$workspace")
doctor_args=(doctor --workspace "$workspace" --configured)
for agent in "${agents[@]}"; do
    integrate_args+=(--agent "$agent")
done
if [ "$all" = true ]; then
    integrate_args+=(--all)
fi
skillc "${integrate_args[@]}"
skillc "${doctor_args[@]}"
echo "skillc and z3-solver are installed; selected agents now run preflight at SessionStart."