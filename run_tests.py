#!/usr/bin/env python3
"""Безопасный единый запуск автоматических тестов Дня 30.

Запускать из корня проекта:

    .venv/bin/python -B run_tests.py

Runner переносит только отслеживаемые Git файлы во временный каталог, поэтому
корневой .env, рабочая память, документы и другие локальные данные не читаются
тестируемым кодом и его дочерними процессами. Живые проверки из ``tests.py``
остаются пропущенными: этот runner не принимает флаг ``--живые``.
"""

from __future__ import annotations

import os
import argparse
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile


МОДУЛИ = (
    "tests",
    "test_gateway_validation",
    "test_telegram_offset",
    "test_telegram_reliability",
    "test_telegram_security",
)

_БЕЗОПАСНОЕ_ОКРУЖЕНИЕ = {
    "PATH", "HOME", "USER", "LOGNAME", "SHELL", "LANG", "LC_ALL", "LC_CTYPE",
    "TZ", "TERM", "COLORTERM",
}


def _окружение_git() -> dict[str, str]:
    окружение = {
        ключ: значение for ключ, значение in os.environ.items()
        if ключ.upper() in {"PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE", "TZ"}
    }
    окружение.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull})
    return окружение


def _отслеживаемые(корень: Path) -> list[Path]:
    """Возвращает пути из индекса Git, не просматривая неотслеживаемые файлы."""
    результат = subprocess.run(
        ["git", "ls-files", "-z", "--cached"],
        cwd=корень,
        env=_окружение_git(),
        check=True,
        stdout=subprocess.PIPE,
    )
    пути = []
    for сырой in результат.stdout.split(b"\0"):
        if not сырой:
            continue
        относительный = Path(os.fsdecode(сырой))
        if относительный.is_absolute() or ".." in относительный.parts:
            raise RuntimeError(f"Небезопасный путь в индексе Git: {относительный}")
        if any(часть == ".env" or (часть.startswith(".env.") and часть != ".env.example")
               for часть in относительный.parts):
            continue
        пути.append(относительный)
    return пути


def _копировать(корень: Path, снимок: Path) -> None:
    пути = _отслеживаемые(корень)
    # Проверяем весь набор до первого копирования. Ссылка способна замаскировать
    # неотслеживаемый .env под безопасным именем, поэтому в снимке их нет вовсе.
    for относительный in пути:
        источник = корень / относительный
        if источник.is_symlink():
            raise RuntimeError(f"Отслеживаемые ссылки запрещены в тестовом снимке: {относительный}")
        if not источник.is_file():
            raise RuntimeError(f"Отслеживаемый файл отсутствует: {относительный}")

    for относительный in пути:
        источник = корень / относительный
        назначение = снимок / относительный
        назначение.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(источник, назначение)

    # До первого коммита runner ещё не находится в индексе.
    runner = Path(__file__).resolve()
    shutil.copy2(runner, снимок / runner.name)

    # load_dotenv() ищет файл вверх по дереву. Пустая синтетическая граница не
    # позволяет ему дойти до случайного /tmp/.env или родительского каталога.
    (снимок / ".env").write_text("# synthetic empty test environment\n", encoding="utf-8")


def _окружение(временный: Path, предохранитель: Path) -> dict[str, str]:
    """Убирает унаследованные секреты и направляет состояние в temp."""
    окружение = {
        ключ: значение
        for ключ, значение in os.environ.items()
        if ключ.upper() in _БЕЗОПАСНОЕ_ОКРУЖЕНИЕ
    }
    окружение.update({
        "PYTHONPATH": str(предохранитель),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "TMPDIR": str(временный / "tmp"),
        "MEMORY_DIR": str(временный / "memory"),
        "RAG_DIR": str(временный / "rag"),
        "DOCS_DIR": str(временный / "docs"),
        "REPORTS_DIR": str(временный / "reports"),
        "SCHEDULER_DB": str(временный / "memory" / "scheduler.db"),
        "HF_HOME": str(временный / "huggingface"),
        "XDG_CACHE_HOME": str(временный / "cache"),
        "HF_HUB_OFFLINE": "1",
        "OLLAMA_HOST": "127.0.0.1:9",
        "OLLAMA_URL": "http://127.0.0.1:9",
        "TRACKER_MOCK_TOKEN": "synthetic-mock-token",
        "TRACKER_MOCK_ORG": "synthetic-mock-org",
        "NO_PROXY": "*",
    })
    for каталог in ("tmp", "memory", "rag", "docs", "reports", "huggingface", "cache"):
        (временный / каталог).mkdir(parents=True, exist_ok=True)
    return окружение


_ПРЕДОХРАНИТЕЛЬ = r'''"""Сетевой предохранитель только для безопасного test runner."""
import ipaddress
import os
import socket
import subprocess

_настоящий_getaddrinfo = socket.getaddrinfo
_настоящий_connect = socket.socket.connect
_настоящий_connect_ex = socket.socket.connect_ex
_настоящий_create_connection = socket.create_connection
_настоящий_popen_init = subprocess.Popen.__init__
_служебные_порты = {8443, 11434, 11435, 11436}
_каталог_guard = os.path.dirname(os.path.abspath(__file__))
os.environ["DAY30_TEST_GUARD"] = "1"

def _адрес(адрес):
    if not isinstance(адрес, tuple) or len(адрес) < 2:
        return
    хост, порт = адрес[0], адрес[1]
    if isinstance(хост, bytes):
        хост = хост.decode("ascii", "strict")
    if хост == "localhost":
        локальный = True
    else:
        try:
            локальный = ipaddress.ip_address(хост).is_loopback
        except ValueError:
            локальный = False
    if not локальный:
        raise OSError("Внешняя сеть запрещена безопасным test runner")
    if isinstance(порт, int) and порт in _служебные_порты:
        raise OSError("Подключение к локальной production-службе запрещено test runner")

def getaddrinfo(host, *args, **kwargs):
    if host not in (None, "localhost", b"localhost"):
        try:
            значение = host.decode("ascii", "strict") if isinstance(host, bytes) else host
            if not ipaddress.ip_address(значение).is_loopback:
                raise OSError("DNS внешнего адреса запрещён безопасным test runner")
        except ValueError:
            raise OSError("DNS внешнего адреса запрещён безопасным test runner") from None
    return _настоящий_getaddrinfo(host, *args, **kwargs)

def connect(self, address):
    _адрес(address)
    return _настоящий_connect(self, address)

def connect_ex(self, address):
    _адрес(address)
    return _настоящий_connect_ex(self, address)

def create_connection(address, *args, **kwargs):
    _адрес(address)
    return _настоящий_create_connection(address, *args, **kwargs)

def popen_init(self, *args, **kwargs):
    # Некоторые MCP-библиотеки передают процессу узкий env={...}. Без явного
    # PYTHONPATH такой Python-потомок потерял бы сетевой предохранитель.
    env = kwargs.get("env")
    if env is not None:
        env = dict(env)
        прежний = env.get("PYTHONPATH", "")
        части = [часть for часть in прежний.split(os.pathsep) if часть]
        if _каталог_guard not in части:
            части.insert(0, _каталог_guard)
        env["PYTHONPATH"] = os.pathsep.join(части)
        kwargs["env"] = env
    return _настоящий_popen_init(self, *args, **kwargs)

socket.getaddrinfo = getaddrinfo
socket.socket.connect = connect
socket.socket.connect_ex = connect_ex
socket.create_connection = create_connection
subprocess.Popen.__init__ = popen_init
'''


def _аргументы(argv: list[str] | None = None) -> argparse.Namespace:
    разбор = argparse.ArgumentParser(description="Безопасный запуск пяти автоматических модулей Day-30")
    разбор.add_argument("-q", "--quiet", action="store_true", help="показывать только итог unittest")
    return разбор.parse_args(argv)


def _дождаться(команда: list[str], снимок: Path, окружение: dict[str, str], таймаут: int = 900) -> int:
    процесс = subprocess.Popen(команда, cwd=снимок, env=окружение, start_new_session=True)
    try:
        return процесс.wait(timeout=таймаут)
    except subprocess.TimeoutExpired:
        print(f"Тесты не завершились за {таймаут} с", file=sys.stderr)
        os.killpg(процесс.pid, signal.SIGTERM)
        try:
            процесс.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(процесс.pid, signal.SIGKILL)
            процесс.wait()
        return 124
    except BaseException:
        os.killpg(процесс.pid, signal.SIGTERM)
        try:
            процесс.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(процесс.pid, signal.SIGKILL)
            процесс.wait()
        raise


def main(argv: list[str] | None = None) -> int:
    аргументы = _аргументы(argv)
    корень = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="day30-safe-tests-") as temp:
        временный = Path(temp)
        снимок = временный / "project"
        снимок.mkdir()
        _копировать(корень, снимок)

        предохранитель = временный / "guard"
        предохранитель.mkdir()
        (предохранитель / "sitecustomize.py").write_text(_ПРЕДОХРАНИТЕЛЬ, encoding="utf-8")

        команда = [sys.executable, "-B", "-m", "unittest"]
        if аргументы.quiet:
            команда.append("-q")
        команда.extend(МОДУЛИ)
        return _дождаться(команда, снимок, _окружение(временный, предохранитель))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
