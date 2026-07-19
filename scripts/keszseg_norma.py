# -*- coding: utf-8 -*-
"""Kézi indítású névegyesítés — a gyűjtő ezt automatikusan is lefuttatja,
ez a script csak arra van, ha azonnal akarod futtatni.

Futtatás:  python scripts/keszseg_norma.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.adatbazis import keszsegnev_normalizalas  # noqa: E402

if __name__ == "__main__":
    n = keszsegnev_normalizalas()
    print(f"KESZ! {n} valtozat osszevonva.")
