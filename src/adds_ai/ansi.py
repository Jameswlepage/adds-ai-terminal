CSI = b"\x1b["


def clear() -> bytes:
    return CSI + b"2J" + CSI + b"H"


def move(row: int, col: int) -> bytes:
    return CSI + f"{row};{col}H".encode()


def rev(on: bool) -> bytes:
    return CSI + (b"7m" if on else b"0m")


def hide_cursor() -> bytes:
    return CSI + b"?25l"


def show_cursor() -> bytes:
    return CSI + b"?25h"


def clear_eol() -> bytes:
    return CSI + b"K"


def reset() -> bytes:
    return CSI + b"0m"
