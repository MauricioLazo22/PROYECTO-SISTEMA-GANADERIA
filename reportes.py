
"""
reportes.py
Generación de reportes en PDF para el sistema ganadero.
Usa reportlab para crear reportes visuales con tablas y encabezados.
"""

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from datetime import date
from configuracion import AppConfig, logger
from base_datos import Database


def generar_reporte_produccion_pdf(db: Database, path: str) -> str:
    """
    Genera un reporte PDF con los registros de producción láctea.
    """
    records = db.get_milk_records()
    doc = SimpleDocTemplate(path, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("SISTEMA DE GESTIÓN GANADERA", styles["Title"]))
    story.append(Paragraph(f"Reporte de Producción Láctea - {date.today().isoformat()}", styles["Heading2"]))
    story.append(Spacer(1, 12))

    data = [["ID", "Fecha", "TAG", "Nombre", "Litros", "Calidad", "Observaciones"]]
    for r in records:
        data.append([
            str(r["id"]), r["fecha"], r["tag"], r["name"],
            f'{r["litros"]:.2f}', r["calidad"] or "-", r["observaciones"] or "-"
        ])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#3498DB")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey])
    ]))
    story.append(table)

    story.append(Spacer(1, 20))
    story.append(Paragraph(f"Versión del sistema: {AppConfig.VERSION}", styles["Normal"]))

    doc.build(story)
    logger.info("Reporte PDF generado: %s", path)
    return path
