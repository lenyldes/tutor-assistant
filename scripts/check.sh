#!/usr/bin/env bash
set -uo pipefail

# Единая точка входа для обязательных проверок на изолированном Compose-проекте.
cd "$(dirname "$0")/.." || exit 1
export COMPOSE_PROJECT_NAME="tutor_checks_$$"
export POSTGRES_USER=tutor
export POSTGRES_PASSWORD=tutor
export POSTGRES_DB=tutor_test
export POSTGRES_PORT=0

CHECK_LOG=$(mktemp) || exit 1

cleanup() {
    local status=$?
    trap - EXIT
    if ! docker compose down -v --remove-orphans >"${CHECK_LOG}" 2>&1; then
        printf 'ОШИБКА: очистка проверочного Compose-проекта\n' >&2
        tail -n 30 "${CHECK_LOG}" >&2
        status=1
    fi
    rm -f "${CHECK_LOG}"
    exit "${status}"
}

run_check() {
    local name="$1"
    shift
    if "$@" >"${CHECK_LOG}" 2>&1; then
        return 0
    fi
    printf 'ОШИБКА: %s\n' "${name}" >&2
    tail -n 40 "${CHECK_LOG}" >&2
    return 1
}

if ! docker info >"${CHECK_LOG}" 2>&1; then
    printf 'ОШИБКА: нет доступа к Docker API\n' >&2
    tail -n 5 "${CHECK_LOG}" >&2
    rm -f "${CHECK_LOG}"
    exit 1
fi

trap cleanup EXIT
trap 'exit 130' INT TERM

run_check 'сборка тестового образа' docker compose build --quiet test || exit 1
run_check 'Ruff и лимит символов' \
    docker compose run --rm -T --no-deps test sh -c \
    'ruff check . && ruff format --check . && python3 scripts/check_limits.py' || exit 1
run_check 'запуск тестовой PostgreSQL' docker compose up -d --wait db || exit 1
run_check 'миграции Alembic' docker compose run --rm -T test alembic upgrade head || exit 1
run_check 'pytest' docker compose run --rm -T test pytest -q --tb=short || exit 1

printf 'Все проверки пройдены.\n'
