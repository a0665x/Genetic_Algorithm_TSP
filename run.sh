#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

APP_PORT="${PORT:-8000}"
APP_URL="http://127.0.0.1:${APP_PORT}"

stage() {
  printf '\n==> %s\n' "$*"
}

show_url() {
  printf '\n✓ Dispatch Lab is ready\n'
  printf '  URL: %s\n\n' "$APP_URL"
}

stage 'Checking Docker Compose'
if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  printf 'Docker Compose is required (docker compose or docker-compose).\n' >&2
  exit 1
fi

usage() {
  cat <<'EOF'
Usage: ./run.sh [command]

Commands:
  start, up       Build when needed and start in the background (default)
  --rebuild       Rebuild without cache, then recreate and start
  stop            Stop containers without removing them
  down_up         Remove and recreate the stack
  restart         Restart the running application container
  status          Show container and health status
  logs            Follow application logs
  test            Run the Python test suite in an isolated container
  down            Stop and remove the stack
  help            Show this help

Set PORT to change the host port, for example: PORT=8080 ./run.sh start
EOF
}

command_name="${1:-start}"

case "$command_name" in
  start|up)
    stage '[1/2] Building the image if needed'
    "${COMPOSE[@]}" build
    stage '[2/2] Starting the application'
    "${COMPOSE[@]}" up --detach --remove-orphans
    show_url
    ;;
  --rebuild|rebuild)
    stage '[1/3] Rebuilding the image without cache'
    "${COMPOSE[@]}" build --no-cache --pull
    stage '[2/3] Recreating the application container'
    "${COMPOSE[@]}" up --detach --force-recreate --remove-orphans
    stage '[3/3] Startup complete'
    show_url
    ;;
  stop)
    stage 'Stopping the application (container is kept)'
    "${COMPOSE[@]}" stop
    stage 'Application stopped'
    ;;
  down_up|down-up)
    stage '[1/3] Removing the existing stack'
    "${COMPOSE[@]}" down --remove-orphans
    stage '[2/3] Building the image if needed'
    "${COMPOSE[@]}" build
    stage '[3/3] Starting a fresh stack'
    "${COMPOSE[@]}" up --detach --remove-orphans
    show_url
    ;;
  restart)
    stage '[1/2] Restarting the application container'
    "${COMPOSE[@]}" restart app
    stage '[2/2] Restart complete'
    show_url
    ;;
  status|ps)
    stage 'Showing container and health status'
    "${COMPOSE[@]}" ps
    printf '\nURL when running: %s\n' "$APP_URL"
    ;;
  logs)
    stage 'Following application logs (press Ctrl+C to stop)'
    "${COMPOSE[@]}" logs --follow --tail=200 app
    ;;
  test)
    stage '[1/2] Starting an isolated test container'
    "${COMPOSE[@]}" run --rm --no-deps \
      --volume "$ROOT_DIR:/workspace:ro" --workdir /workspace \
      app python -m unittest discover -s tests -v
    stage '[2/2] All tests passed'
    ;;
  down)
    stage 'Stopping and removing the application stack'
    "${COMPOSE[@]}" down --remove-orphans
    stage 'Application stack removed'
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    printf 'Unknown command: %s\n\n' "$command_name" >&2
    usage >&2
    exit 2
    ;;
esac
