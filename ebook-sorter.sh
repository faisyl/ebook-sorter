#!/usr/bin/env bash
set -euo pipefail

IMAGE="${EBOOK_SORTER_IMAGE:-ghcr.io/faisyl/ebook-sorter:latest}"
PUID="${PUID:-$(id -u)}"
PGID="${PGID:-$(id -g)}"

usage() {
    echo "Usage: $(basename "$0") <command> <source-path> [options...]"
    echo ""
    echo "Commands: scan, organize, find-isbn, identify, interactive"
    echo ""
    echo "Examples:"
    echo "  $(basename "$0") scan /path/to/ebooks --sidecar"
    echo "  $(basename "$0") organize /path/to/ebooks -o /path/to/library --sidecar"
    echo "  $(basename "$0") find-isbn /path/to/book.pdf"
    echo "  $(basename "$0") identify /path/to/book.epub"
    echo ""
    echo "Environment:"
    echo "  PUID                  User ID for file ownership (default: current user)"
    echo "  PGID                  Group ID for file ownership (default: current group)"
    echo "  EBOOK_SORTER_IMAGE    Docker image (default: $IMAGE)"
    exit 1
}

[[ $# -lt 2 ]] && usage

CMD="$1"
shift

VOLUMES=()
ARGS=()
NEXT_IS_OUTPUT=false

for arg in "$@"; do
    if $NEXT_IS_OUTPUT; then
        NEXT_IS_OUTPUT=false
        real="$(realpath "$arg")"
        mkdir -p "$real"
        VOLUMES+=(-v "$real:/output")
        ARGS+=("/output")
        continue
    fi

    case "$arg" in
        -o=*|--output-dir=*)
            dir="${arg#*=}"
            real="$(realpath "$dir")"
            mkdir -p "$real"
            VOLUMES+=(-v "$real:/output")
            ARGS+=("${arg%%=*}=/output")
            ;;
        -o|--output-dir)
            ARGS+=("$arg")
            NEXT_IS_OUTPUT=true
            ;;
        *)
            if [[ -e "$arg" ]]; then
                real="$(realpath "$arg")"
                base="$(basename "$real")"
                if [[ -d "$real" ]]; then
                    VOLUMES+=(-v "$real:/data/$base")
                    ARGS+=("/data/$base")
                else
                    dir="$(dirname "$real")"
                    dirbase="$(basename "$dir")"
                    VOLUMES+=(-v "$dir:/data/$dirbase")
                    ARGS+=("/data/$dirbase/$base")
                fi
            else
                ARGS+=("$arg")
            fi
            ;;
    esac
done

exec docker run --rm \
    -e PUID="$PUID" \
    -e PGID="$PGID" \
    "${VOLUMES[@]}" \
    "$IMAGE" \
    "$CMD" "${ARGS[@]}"
