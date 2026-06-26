"""Ponto de entrada do centralizador local de workers."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from seller_workers.gui import iniciar_gui


def main() -> None:
    iniciar_gui()


if __name__ == "__main__":
    main()
