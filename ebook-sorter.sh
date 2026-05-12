#!/bin/sh
set -e

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

[ $# -lt 2 ] && usage

CMD="$1"
shift

VOLUMES=""
ARGS=""

for arg in "$@"; do
    case "$arg" in
        -o=*|--output-dir=*)
            dir="${arg#*=}"
            real="$(realpath "$dir")"
            mkdir -p "$real"
            VOLUMES="$VOLUMES -v $real:/output"
            ARGS="$ARGS ${arg%%=*}=/output"
            ;;
        -o|--output-dir)
            ARGS="$ARGS $arg"
            ;;
        /*)
            if [ -e "$arg" ]; then
                real="$(realpath "$arg")"
                if [ -d "$real" ]; then
                    VOLUMES="$VOLUMES -v $real:/data/$(basename "$real")"
                    ARGS="$ARGS /data/$(basename "$real")"
                else
                    dir="$(dirname "$real")"
                    VOLUMES="$VOLUMES -v $dir:/data/$(basename "$dir")"
                    ARGS="$ARGS /data/$(basename "$dir")/$(basename "$real")"
                fi
            else
                ARGS="$ARGS $arg"
            fi
            ;;
        *)
            if [ -e "$arg" ]; then
                real="$(realpath "$arg")"
                if [ -d "$real" ]; then
                    VOLUMES="$VOLUMES -v $real:/data/$(basename "$real")"
                    ARGS="$ARGS /data/$(basename "$real")"
                else
                    dir="$(dirname "$real")"
                    VOLUMES="$VOLUMES -v $dir:/data/$(basename "$dir")"
                    ARGS="$ARGS /data/$(basename "$dir")/$(basename "$real")"
                fi
            else
                ARGS="$ARGS $arg"
            fi
            ;;
    esac
done

# shellcheck disable=SC2086
exec docker run --rm \
    -e PUID="$PUID" \
    -e PGID="$PGID" \
    $VOLUMES \
    "$IMAGE" \
    "$CMD" $ARGS
