"""
configuracion.py
Configuración global de la aplicación: rutas, formatos, enums y logging.
Este archivo debe importarse antes que el resto para que el logger exista.
"""

import logging

class AppConfig:
    # archivo principal de la base de datos
    DB_FILE = "leche100.db"
    # carpeta donde se guardarán los backups
    BACKUP_DIR = "backups"
    # archivo de log
    LOG_FILE = "dairy_system.log"
    # versión de la app (la que muestras en la ventana)
    VERSION = "2.0.1"

    # validaciones de negocio
    MIN_LITERS = 0.0
    # se aumentó por si hay ordeñas por encierro (ajustable)
    MAX_LITERS = 1000.0

    # formatos de fecha
    DATE_FORMAT = "%Y-%m-%d"
    DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

    # seguridad (para hash de contraseñas)
    PWD_ITERATIONS = 120_000


from enum import Enum

class QualityLevel(Enum):
    EXCELENTE = "Excelente"
    BUENA = "Buena"
    MEDIA = "Media"
    BAJA = "Baja"


# -------------------------------------------------------------------------
# LOGGING
# -------------------------------------------------------------------------
# Creamos el logger aquí para que cualquier módulo lo pueda usar
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(AppConfig.LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("dairy_app")
