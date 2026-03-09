#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
base_datos.py
Capa de acceso a datos (SQLite) para el sistema ganadero.
Contiene la clase Database y las operaciones CRUD sobre vacas, registros
de leche, usuarios, auditoría y backups.
"""

import sqlite3
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Tuple
import shutil
import os
import hashlib
import secrets
import binascii
import json  # lo tenías en el original, lo dejamos

from configuracion import AppConfig, logger
from modelos import Cow, MilkRecord, User


# ========================================================================
# EXCEPCIONES
# ========================================================================

class DatabaseException(Exception):
    """Excepción personalizada para errores de base de datos."""
    pass


# ========================================================================
# CLASE PRINCIPAL DE BASE DE DATOS
# ========================================================================

class Database:
    def __init__(self, file: str = AppConfig.DB_FILE):
        self.file = file
        try:
            self.conn = sqlite3.connect(file, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            # Habilitar foreign keys
            cur = self.conn.cursor()
            cur.execute("PRAGMA foreign_keys = ON;")         # ya lo tenías
            cur.execute("PRAGMA journal_mode = WAL;")        # escritura concurrente y menos bloqueos
            cur.execute("PRAGMA synchronous = NORMAL;")      # balance seguridad/velocidad
            cur.execute("PRAGMA cache_size = -20000;")       # ~20 MB de cache en RAM (negativo = KB)
            cur.execute("PRAGMA temp_store = MEMORY;")       # temp en RAM
            cur.execute("PRAGMA busy_timeout = 5000;")       # reintenta 5s si la DB está ocupada
            self.conn.commit()
            self._create_tables()
            self._create_indexes()
            logger.info(f"DB inicializada: {file}")
        except sqlite3.Error as e:
            logger.exception("Error al inicializar DB")
            raise DatabaseException(str(e))

    # ------------------------------------------------------------------
    # CREACIÓN DE TABLAS
    # ------------------------------------------------------------------
    def _create_tables(self):
        cur = self.conn.cursor()
        # cows
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tag TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                breed TEXT,
                dob TEXT,
                notes TEXT,
                active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # milk_records
        cur.execute("""
            CREATE TABLE IF NOT EXISTS milk_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cow_id INTEGER NOT NULL,
                fecha TEXT NOT NULL,
                litros REAL NOT NULL CHECK(litros >= 0),
                calidad TEXT,
                observaciones TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(cow_id) REFERENCES cows(id) ON DELETE CASCADE ON UPDATE CASCADE
            );
        """)
        # audit_log
        cur.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                operation TEXT NOT NULL,
                record_id INTEGER,
                details TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # users (gestión de usuarios y contraseñas)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # reports (metadatos de exportaciones / backups)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                path TEXT NOT NULL,
                user_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
            );
        """)
        self.conn.commit()

    # ------------------------------------------------------------------
    # ÍNDICES
    # ------------------------------------------------------------------
    def _create_indexes(self):
        cur = self.conn.cursor()
        # Cows
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_cow_tag ON cows(tag);")
        # Índice parcial: buscamos casi siempre vacas activas
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cows_active_tag ON cows(tag) WHERE active=1;")

        # Milk records
        # 🔥 el patrón más habitual es filtrar por cow_id y por rango de fecha
        cur.execute("CREATE INDEX IF NOT EXISTS idx_milk_cow_fecha ON milk_records(cow_id, fecha);")
        # Para listados por fecha (consultas globales)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_milk_fecha_id ON milk_records(fecha, id);")

        # Users
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username);")

        self.conn.commit()

        # ayuda al optimizador con estadísticas
        try:
            cur.execute("ANALYZE;")
        except sqlite3.Error:
            pass

    # ------------------------------------------------------------------
    # AUDITORÍA
    # ------------------------------------------------------------------
    def _log_audit(self, table: str, operation: str, record_id: Optional[int], details: str = ""):
        try:
            cur = self.conn.cursor()
            cur.execute(
                "INSERT INTO audit_log(table_name, operation, record_id, details) VALUES(?,?,?,?)",
                (table, operation, record_id, details)
            )
            self.conn.commit()
        except sqlite3.Error:
            logger.exception("Error registrando auditoría (se ignora)")

    # ========================================================================
    # COWS CRUD
    # ========================================================================
    def add_cow(self, cow: Cow) -> int:
        valid, msg = cow.validate()
        if not valid:
            raise DatabaseException(msg)
        try:
            cur = self.conn.cursor()
            cur.execute(
                "INSERT INTO cows(tag, name, breed, dob, notes) VALUES(?,?,?,?,?)",
                (cow.tag, cow.name, cow.breed, cow.dob, cow.notes)
            )
            self.conn.commit()
            cow_id = cur.lastrowid
            self._log_audit("cows", "INSERT", cow_id, f"TAG:{cow.tag}")
            return cow_id
        except sqlite3.IntegrityError as e:
            logger.error("Integrity error al agregar vaca: %s", e)
            raise DatabaseException("TAG ya existe")
        except sqlite3.Error as e:
            logger.exception("Error al agregar vaca")
            raise DatabaseException(str(e))

    def update_cow(self, cow: Cow) -> bool:
        valid, msg = cow.validate()
        if not valid:
            raise DatabaseException(msg)
        try:
            cur = self.conn.cursor()
            cur.execute("""
                UPDATE cows SET tag=?, name=?, breed=?, dob=?, notes=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
            """, (cow.tag, cow.name, cow.breed, cow.dob, cow.notes, cow.id))
            self.conn.commit()
            self._log_audit("cows", "UPDATE", cow.id, f"TAG:{cow.tag}")
            return True
        except sqlite3.Error:
            logger.exception("Error actualizando vaca")
            raise DatabaseException("Error actualizando vaca")

    def delete_cow(self, cow_id: int) -> bool:
        try:
            cur = self.conn.cursor()
            # borrado lógico (active=0) como en tu original
            cur.execute("UPDATE cows SET active=0, updated_at=CURRENT_TIMESTAMP WHERE id=?", (cow_id,))
            self.conn.commit()
            self._log_audit("cows", "DELETE", cow_id)
            return True
        except sqlite3.Error:
            logger.exception("Error eliminando vaca")
            raise DatabaseException("Error eliminando vaca")

    def get_cow(self, cow_id: int) -> Optional[sqlite3.Row]:
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT * FROM cows WHERE id=? AND active=1", (cow_id,))
            return cur.fetchone()
        except sqlite3.Error:
            logger.exception("Error obteniendo vaca")
            return None

    def get_all_cows(self, include_inactive: bool = False) -> List[sqlite3.Row]:
        try:
            cur = self.conn.cursor()
            if include_inactive:
                cur.execute("SELECT * FROM cows ORDER BY tag")
            else:
                cur.execute("SELECT * FROM cows WHERE active=1 ORDER BY tag")
            return cur.fetchall()
        except sqlite3.Error:
            logger.exception("Error listando vacas")
            return []

    # ========================================================================
    # MILK RECORDS CRUD
    # ========================================================================
    def add_milk_record(self, record: MilkRecord) -> int:
        valid, msg = record.validate()
        if not valid:
            raise DatabaseException(msg)
        try:
            cur = self.conn.cursor()
            cur.execute("""
                INSERT INTO milk_records(cow_id, fecha, litros, calidad, observaciones)
                VALUES(?,?,?,?,?)
            """, (record.cow_id, record.fecha, record.litros, record.calidad, record.observaciones))
            self.conn.commit()
            rid = cur.lastrowid
            self._log_audit("milk_records", "INSERT", rid, f"Cow:{record.cow_id},L:{record.litros}")
            return rid
        except sqlite3.Error:
            logger.exception("Error añadiendo registro de leche")
            raise DatabaseException("Error añadiendo registro de leche")

    def update_milk_record(self, record: MilkRecord) -> bool:
        valid, msg = record.validate()
        if not valid:
            raise DatabaseException(msg)
        try:
            cur = self.conn.cursor()
            cur.execute("""
                UPDATE milk_records SET fecha=?, litros=?, calidad=?, observaciones=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
            """, (record.fecha, record.litros, record.calidad, record.observaciones, record.id))
            self.conn.commit()
            self._log_audit("milk_records", "UPDATE", record.id)
            return True
        except sqlite3.Error:
            logger.exception("Error actualizando registro de leche")
            raise DatabaseException("Error actualizando registro de leche")

    def delete_milk_record(self, rec_id: int) -> bool:
        try:
            cur = self.conn.cursor()
            cur.execute("DELETE FROM milk_records WHERE id=?", (rec_id,))
            self.conn.commit()
            self._log_audit("milk_records", "DELETE", rec_id)
            return True
        except sqlite3.Error:
            logger.exception("Error eliminando registro de leche")
            raise DatabaseException("Error eliminando registro de leche")

    def get_milk_records(self,
                        cow_id: Optional[int] = None,
                        fecha_from: Optional[str] = None,
                        fecha_to: Optional[str] = None,
                        limit: Optional[int] = None,
                        offset: int = 0) -> List[sqlite3.Row]:
        try:
            cur = self.conn.cursor()
            query = [
                "SELECT mr.*, c.tag, c.name",
                "FROM milk_records mr",
                "JOIN cows c ON mr.cow_id = c.id",
                "WHERE c.active=1"
            ]
            params: List[Any] = []

            if cow_id:
                query.append("AND mr.cow_id=?")
                params.append(cow_id)
            if fecha_from:
                query.append("AND mr.fecha>=?")
                params.append(fecha_from)
            if fecha_to:
                query.append("AND mr.fecha<=?")
                params.append(fecha_to)

            # usar el índice (cow_id,fecha) con orden compatible
            query.append("ORDER BY mr.fecha DESC, mr.id DESC")

            if limit is not None:
                query.append("LIMIT ? OFFSET ?")
                params.extend([int(limit), int(offset)])

            cur.execute(" ".join(query), params)
            return cur.fetchall()
        except sqlite3.Error:
            logger.exception("Error obteniendo registros de leche")
            return []
        
    def count_milk_records(self,
                        cow_id: Optional[int] = None,
                        fecha_from: Optional[str] = None,
                        fecha_to: Optional[str] = None) -> int:
        try:
            cur = self.conn.cursor()
            query = [
                "SELECT COUNT(1)",
                "FROM milk_records mr",
                "JOIN cows c ON mr.cow_id = c.id",
                "WHERE c.active=1"
            ]
            params: List[Any] = []

            if cow_id:
                query.append("AND mr.cow_id=?")
                params.append(cow_id)
            if fecha_from:
                query.append("AND mr.fecha>=?")
                params.append(fecha_from)
            if fecha_to:
                query.append("AND mr.fecha<=?")
                params.append(fecha_to)

            cur.execute(" ".join(query), params)
            r = cur.fetchone()
            return int(r[0]) if r else 0
        except sqlite3.Error:
            logger.exception("Error contando registros de leche")
            return 0

    
    # ========================================================================
    # ESTADÍSTICAS / REPORTES / BACKUP
    # ========================================================================
    def get_production_stats(self, cow_id: int, days: int = 30) -> Dict[str, Any]:
        try:
            fecha_from = (date.today() - timedelta(days=days)).isoformat()
            cur = self.conn.cursor()
            cur.execute("""
                SELECT COUNT(*) as total_records,
                       AVG(litros) as avg_liters,
                       MAX(litros) as max_liters,
                       MIN(litros) as min_liters,
                       SUM(litros) as total_liters
                FROM milk_records
                WHERE cow_id=? AND fecha>=?
            """, (cow_id, fecha_from))
            r = cur.fetchone()
            return {
                'total_records': r['total_records'] or 0,
                'avg_liters': round(r['avg_liters'] or 0, 2),
                'max_liters': r['max_liters'] or 0,
                'min_liters': r['min_liters'] or 0,
                'total_liters': round(r['total_liters'] or 0, 2),
                'period_days': days
            }
        except sqlite3.Error:
            logger.exception("Error calculando estadísticas")
            return {}

    def backup(self, backup_dir: str = AppConfig.BACKUP_DIR, user_id: Optional[int] = None) -> str:
        Path(backup_dir).mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"{backup_dir}/leche_backup_{timestamp}.db"
        try:
            shutil.copy2(self.file, backup_file)
            self._log_audit("backup", "CREATE", None, backup_file)
            # registrar report
            cur = self.conn.cursor()
            cur.execute(
                "INSERT INTO reports(name, path, user_id) VALUES(?,?,?)",
                (f"backup_{timestamp}", backup_file, user_id)
            )
            self.conn.commit()
            return backup_file
        except Exception:
            logger.exception("Error creando backup")
            raise DatabaseException("Error creando backup")

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass

    # ========================================================================
    # USERS (SEGURIDAD)
    # ========================================================================
    @staticmethod
    def _hash_password(password: str, salt: Optional[bytes] = None) -> Tuple[str, str]:
        if salt is None:
            salt = secrets.token_bytes(16)
        # PBKDF2 HMAC SHA256
        dk = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            AppConfig.PWD_ITERATIONS
        )
        return binascii.hexlify(dk).decode('ascii'), binascii.hexlify(salt).decode('ascii')

    def add_user(self, username: str, password: str, role: str = "user") -> int:
        if not username or not password:
            raise DatabaseException("Usuario y contraseña obligatorios")
        h, s = self._hash_password(password)
        try:
            cur = self.conn.cursor()
            cur.execute(
                "INSERT INTO users(username, password_hash, salt, role) VALUES(?,?,?,?)",
                (username, h, s, role)
            )
            self.conn.commit()
            uid = cur.lastrowid
            self._log_audit("users", "INSERT", uid, username)
            return uid
        except sqlite3.IntegrityError:
            raise DatabaseException("Nombre de usuario ya existe")
        except sqlite3.Error:
            logger.exception("Error creando usuario")
            raise DatabaseException("Error creando usuario")

    def authenticate_user(self, username: str, password: str) -> Optional[sqlite3.Row]:
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT * FROM users WHERE username=? AND active=1", (username,))
            user = cur.fetchone()
            if not user:
                return None
            stored_hash = user["password_hash"]
            salt = binascii.unhexlify(user["salt"].encode('ascii'))
            computed_hash, _ = self._hash_password(password, salt)
            if computed_hash == stored_hash:
                return user
            return None
        except sqlite3.Error:
            logger.exception("Error autenticando usuario")
            return None

    def get_user(self, user_id: int) -> Optional[sqlite3.Row]:
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT id, username, role, active, created_at FROM users WHERE id=?", (user_id,))
            return cur.fetchone()
        except sqlite3.Error:
            logger.exception("Error obteniendo usuario")
            return None

    def list_users(self) -> List[sqlite3.Row]:
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT id, username, role, active, created_at FROM users ORDER BY username")
            return cur.fetchall()
        except sqlite3.Error:
            logger.exception("Error listando usuarios")
            return []

    def update_user_password(self, user_id: int, new_password: str) -> bool:
        if not new_password:
            raise DatabaseException("Contraseña vacía")
        h, s = self._hash_password(new_password)
        try:
            cur = self.conn.cursor()
            cur.execute("UPDATE users SET password_hash=?, salt=? WHERE id=?", (h, s, user_id))
            self.conn.commit()
            self._log_audit("users", "UPDATE_PWD", user_id)
            return True
        except sqlite3.Error:
            logger.exception("Error actualizando contraseña")
            raise DatabaseException("Error actualizando contraseña")

    def delete_user(self, user_id: int) -> bool:
        try:
            cur = self.conn.cursor()
            cur.execute("UPDATE users SET active=0 WHERE id=?", (user_id,))
            self.conn.commit()
            self._log_audit("users", "DELETE", user_id)
            return True
        except sqlite3.Error:
            logger.exception("Error eliminando usuario")
            raise DatabaseException("Error eliminando usuario")
        
    def restore(self, backup_file: str):
        """
        Restaura la base de datos desde un archivo de backup (.db)
        Sobrescribe el archivo actual y reabre la conexión.
        """
        try:
            self.conn.close()
        except Exception:
            pass

        # copiar el backup sobre la base actual
        shutil.copy2(backup_file, self.file)

        # volver a abrir
        self.conn = sqlite3.connect(self.file, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")
        logger.info("Base de datos restaurada desde %s", backup_file)

