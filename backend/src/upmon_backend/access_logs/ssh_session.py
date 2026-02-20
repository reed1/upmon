import asyncio
import logging
import random
import socket
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("upmon_backend.access_logs")

RELAY_SCRIPT_PATH = Path(__file__).parent / "relay_script.py"
READY_TIMEOUT = 10


@dataclass
class SSHSession:
    site_key: str
    process: asyncio.subprocess.Process
    local_port: int
    remote_port: int

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.local_port}"

    def is_alive(self) -> bool:
        return self.process.returncode is None


def _find_free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _random_remote_port() -> int:
    return random.randint(49152, 65535)


class SSHSessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, SSHSession] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    async def _get_lock(self, site_key: str) -> asyncio.Lock:
        async with self._global_lock:
            if site_key not in self._locks:
                self._locks[site_key] = asyncio.Lock()
            return self._locks[site_key]

    async def get_session(self, site_key: str, ssh_host: str, db_path: str) -> SSHSession:
        existing = self._sessions.get(site_key)
        if existing and existing.is_alive():
            return existing

        lock = await self._get_lock(site_key)
        async with lock:
            existing = self._sessions.get(site_key)
            if existing and existing.is_alive():
                return existing

            return await self._spawn(site_key, ssh_host, db_path)

    async def _spawn(self, site_key: str, ssh_host: str, db_path: str) -> SSHSession:
        local_port = _find_free_local_port()
        remote_port = _random_remote_port()

        from .relay_script import SCRIPT

        proc = await asyncio.create_subprocess_exec(
            "ssh",
            "-L",
            f"{local_port}:127.0.0.1:{remote_port}",
            "-o",
            "ExitOnForwardFailure=yes",
            "-o",
            "StrictHostKeyChecking=accept-new",
            ssh_host,
            "python3",
            "-u",
            "-",
            str(remote_port),
            db_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        proc.stdin.write(SCRIPT.encode())
        proc.stdin.close()

        try:
            line = await asyncio.wait_for(proc.stdout.readline(), timeout=READY_TIMEOUT)
        except asyncio.TimeoutError:
            proc.kill()
            stderr = await proc.stderr.read()
            raise RuntimeError(
                f"Relay for {site_key} failed to start within {READY_TIMEOUT}s. "
                f"stderr: {stderr.decode(errors='replace')}"
            )

        decoded = line.decode().strip()
        if not decoded.startswith("RELAY_READY"):
            proc.kill()
            stderr = await proc.stderr.read()
            raise RuntimeError(
                f"Unexpected relay output for {site_key}: {decoded!r}. " f"stderr: {stderr.decode(errors='replace')}"
            )

        session = SSHSession(
            site_key=site_key,
            process=proc,
            local_port=local_port,
            remote_port=remote_port,
        )
        self._sessions[site_key] = session
        logger.info(
            "SSH relay started for %s (local:%d → remote:%d)",
            site_key,
            local_port,
            remote_port,
        )
        return session

    def clear_session(self, site_key: str) -> None:
        session = self._sessions.pop(site_key, None)
        if session and session.is_alive():
            session.process.kill()

    async def close_all(self) -> None:
        for key in list(self._sessions):
            session = self._sessions.pop(key)
            if session.is_alive():
                session.process.kill()
                await session.process.wait()
        logger.info("All SSH relay sessions closed")
