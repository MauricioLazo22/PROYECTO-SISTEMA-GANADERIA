
"""
servicios.py
Capa de servicios intermedios para la aplicación ganadera.
Encapsula funciones de negocio como exportaciones, estadísticas
y consultas combinadas entre tablas.
"""

import csv
from datetime import date, timedelta
from typing import Optional, List, Dict, Any
from configuracion import AppConfig, logger
from base_datos import Database, DatabaseException


def exportar_produccion_csv(db: Database, path: str,
                            cow_id: Optional[int] = None,
                            fecha_from: Optional[str] = None,
                            fecha_to: Optional[str] = None) -> int:
    """
    Exporta registros de producción láctea a un archivo CSV.
    Devuelve el número de registros exportados.
    """
    records = db.get_milk_records(cow_id=cow_id, fecha_from=fecha_from, fecha_to=fecha_to)
    try:
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(["ID", "Fecha", "TAG", "Nombre", "Litros", "Calidad", "Observaciones"])
            for r in records:
                writer.writerow([
                    r["id"], r["fecha"], r["tag"], r["name"],
                    f'{r["litros"]:.2f}', r["calidad"] or "", r["observaciones"] or ""
                ])
        logger.info("CSV exportado: %s (%d registros)", path, len(records))
        return len(records)
    except Exception as e:
        logger.exception("Error exportando CSV")
        raise DatabaseException(str(e))


def calcular_estadisticas_generales(db: Database) -> Dict[str, Any]:
    """
    Retorna estadísticas globales del sistema: total de vacas, registros,
    producción acumulada y top vacas productoras.
    """
    cows = db.get_all_cows()
    all_records = db.get_milk_records()

    total_cows = len(cows)
    total_records = len(all_records)

    if total_records == 0:
        return {
            "total_cows": total_cows,
            "total_records": 0,
            "total_production": 0.0,
            "avg_production": 0.0,
            "top_cows": []
        }

    total_production = sum(r["litros"] for r in all_records)
    avg_production = total_production / total_records

    cow_production: Dict[int, Dict[str, Any]] = {}
    for r in all_records:
        cid = r["cow_id"]
        cow_production.setdefault(cid, {"litros": 0, "tag": r["tag"], "name": r["name"], "count": 0})
        cow_production[cid]["litros"] += r["litros"]
        cow_production[cid]["count"] += 1

    top_cows = sorted(cow_production.values(), key=lambda x: x["litros"], reverse=True)[:3]
    logger.info("Estadísticas globales calculadas")

    return {
        "total_cows": total_cows,
        "total_records": total_records,
        "total_production": round(total_production, 2),
        "avg_production": round(avg_production, 2),
        "top_cows": top_cows
    }
