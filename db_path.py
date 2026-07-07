"""
Ruta de la base de datos. En Railway, si hay un volumen persistente montado
(RAILWAY_VOLUME_MOUNT_PATH), la DB vive ahi para sobrevivir redeploys.
En local, vive junto al codigo como siempre.
"""
import os
import shutil
from pathlib import Path

_BUNDLED_DB = Path(__file__).parent / "productos.db"
_VOLUME_DIR = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH")

if _VOLUME_DIR:
    DB_PATH = Path(_VOLUME_DIR) / "productos.db"
    if not DB_PATH.exists() and _BUNDLED_DB.exists():
        shutil.copy(_BUNDLED_DB, DB_PATH)
else:
    DB_PATH = _BUNDLED_DB
