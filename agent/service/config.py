"""Настройки приватного сервиса Дня 30.

Значения по умолчанию — `service.json` в корне проекта (в репозитории). Данные,
которые в репозиторий не идут, — ключи (только хэши), журнал запросов,
сертификаты и их закрытые ключи — живут в `$MEMORY_DIR/service/`, как остальная
память агента: тесты и стенд пишут в свои каталоги, а не в живые ключи.

  загрузить(путь="") -> Настройки
  каталог_данных() -> str        $MEMORY_DIR/service (создаётся)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

КОРЕНЬ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ФАЙЛ = "service.json"


@dataclass(frozen=True)
class Лимиты:
    запросов_в_минуту: int = 6
    очередь: int = 4
    вход_токенов: int = 3400
    ответ_токенов: int = 600
    окно: int = 4096
    тело_байт: int = 262144
    вопрос_символов: int = 1000
    таймаут_с: float = 600.0


@dataclass(frozen=True)
class Настройки:
    адрес: str = "0.0.0.0"
    порт: int = 8443
    подсети: tuple[str, ...] = ("127.0.0.0/8", "::1/128", "192.168.1.0/24", "172.17.0.0/16")
    модель: str = "loc-rag-docs"
    ollama: str = "http://127.0.0.1:11434"
    keep_alive: str = "30m"
    лимиты: Лимиты = field(default_factory=Лимиты)
    сертификат: dict[str, Any] = field(default_factory=dict)


def путь_настроек() -> str:
    return os.environ.get("SERVICE_CONFIG") or os.path.join(КОРЕНЬ, ФАЙЛ)


def загрузить(путь: str = "") -> Настройки:
    """Настройки из service.json; поля, которых в файле нет, — по умолчанию."""
    путь = путь or путь_настроек()
    with open(путь, encoding="utf-8") as f:
        данные = json.load(f)
    лимиты = Лимиты(**{к: в for к, в in (данные.get("лимиты") or {}).items() if к in Лимиты.__dataclass_fields__})
    return Настройки(
        адрес=str(данные.get("адрес", Настройки.адрес)),
        порт=int(данные.get("порт", Настройки.порт)),
        подсети=tuple(данные.get("подсети") or Настройки.подсети),
        модель=str(данные.get("модель", Настройки.модель)),
        ollama=str(данные.get("ollama", Настройки.ollama)).rstrip("/"),
        keep_alive=str(данные.get("keep_alive", Настройки.keep_alive)),
        лимиты=лимиты,
        сертификат=dict(данные.get("сертификат") or {}),
    )


def каталог_данных() -> str:
    """$MEMORY_DIR/service — ключи, журнал, сертификаты (вне репозитория)."""
    база = os.environ.get("MEMORY_DIR") or os.path.join(КОРЕНЬ, "memory")
    путь = os.path.join(база, "service")
    os.makedirs(путь, exist_ok=True)
    return путь
