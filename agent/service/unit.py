"""Служба systemd пользователя для приватного сервиса (spec FR-15, plan D-14).

Без sudo: `~/.config/systemd/user/day30-llm.service`, `Restart=on-failure`.
Без linger служба живёт, пока владелец в системе (ворота 0, A-6).

  текст(python, корень, память) -> содержимое unit-файла
  установить(...) / systemctl(действие) / статус() -> dict
"""

from __future__ import annotations

import os
import subprocess
from typing import Any

ИМЯ = "day30-llm.service"


def путь_unit() -> str:
    return os.path.join(os.path.expanduser("~"), ".config", "systemd", "user", ИМЯ)


def текст(python: str, корень: str, память: str) -> str:
    return (
        "[Unit]\n"
        "Description=День 30: приватный AI-сервис (шлюз перед Ollama, loc-rag-docs)\n"
        "After=network-online.target\n\n"
        "[Service]\n"
        f"WorkingDirectory={корень}\n"
        f"Environment=MEMORY_DIR={память}\n"
        "Environment=PYTHONIOENCODING=utf-8\n"
        f"ExecStart={python} {os.path.join(корень, 'service.py')}\n"
        "Restart=on-failure\n"
        "RestartSec=3\n\n"
        "[Install]\n"
        "WantedBy=default.target\n"
    )


def systemctl(*аргументы: str) -> subprocess.CompletedProcess:
    return subprocess.run(["systemctl", "--user", *аргументы], capture_output=True, text=True, timeout=60)


def установить(python: str, корень: str, память: str) -> str:
    путь = путь_unit()
    os.makedirs(os.path.dirname(путь), exist_ok=True)
    with open(путь, "w", encoding="utf-8") as f:
        f.write(текст(python, корень, память))
    systemctl("daemon-reload")
    return путь


def статус() -> dict[str, Any]:
    готово = systemctl("show", ИМЯ, "-p", "ActiveState", "-p", "SubState", "-p", "MainPID", "-p", "NRestarts",
                       "-p", "ActiveEnterTimestamp", "-p", "LoadState")
    поля = dict(с.split("=", 1) for с in готово.stdout.splitlines() if "=" in с)
    return {"установлена": поля.get("LoadState") == "loaded", "состояние": поля.get("ActiveState", ""),
            "подсостояние": поля.get("SubState", ""), "pid": int(поля.get("MainPID") or 0),
            "перезапусков": int(поля.get("NRestarts") or 0), "с": поля.get("ActiveEnterTimestamp", "")}
