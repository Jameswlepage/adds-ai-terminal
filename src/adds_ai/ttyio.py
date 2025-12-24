import os
import termios
import tty


def open_tty(path: str) -> int:
    """Open a TTY in raw mode without becoming controlling terminal."""
    fd = os.open(path, os.O_RDWR | os.O_NOCTTY)
    tty.setraw(fd, when=termios.TCSANOW)
    return fd


def write_bytes(fd: int, data: bytes) -> None:
    os.write(fd, data)


def read_bytes(fd: int, n: int = 1) -> bytes:
    return os.read(fd, n)
