#!/usr/bin/env bash
# Установка и запуск neurocomment как systemd-сервиса.
# Запускать на VPS из корня проекта: sudo bash deploy/install-systemd.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_NAME="neurocomment"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
RUN_USER="${SUDO_USER:-root}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Запустите скрипт с sudo: sudo bash deploy/install-systemd.sh"
  exit 1
fi

if [[ ! -f "${PROJECT_DIR}/.env" ]]; then
  echo "Файл .env не найден: ${PROJECT_DIR}/.env"
  echo "Скопируйте .env.example и заполните переменные."
  exit 1
fi

if [[ ! -f "${PROJECT_DIR}/app/main.py" ]]; then
  echo "Не найден app/main.py в ${PROJECT_DIR}"
  exit 1
fi

# Подставляем реальный путь проекта и пользователя
sed \
  -e "s|WorkingDirectory=.*|WorkingDirectory=${PROJECT_DIR}|" \
  -e "s|EnvironmentFile=-.*|EnvironmentFile=-${PROJECT_DIR}/.env|" \
  -e "s|^User=.*|User=${RUN_USER}|" \
  -e "s|^Group=.*|Group=${RUN_USER}|" \
  "${PROJECT_DIR}/deploy/neurocomment.service" > "${SERVICE_FILE}"

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"

echo ""
echo "Сервис установлен: ${SERVICE_FILE}"
echo "Статус:  systemctl status ${SERVICE_NAME}"
echo "Логи:    journalctl -u ${SERVICE_NAME} -f"
echo "Стоп:    systemctl stop ${SERVICE_NAME}"
echo "Рестарт: systemctl restart ${SERVICE_NAME}"
