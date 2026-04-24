from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from app.database import get_db
from app.models import Abastecedor
from app.services.cobro_service import get_saldo_abastecedor
import os
import sys
from reportlab.platypus import Image as RLImage

router = APIRouter(prefix="/reportes", tags=["Reportes"])

# Paleta de colores
AZUL_OSCURO  = colors.HexColor('#1a3a5c')
AZUL_MEDIO   = colors.HexColor('#2563a8')
AZUL_CLARO   = colors.HexColor('#dbeafe')
AZUL_BORDE   = colors.HexColor('#93c5fd')
VERDE_OSCURO = colors.HexColor('#166534')
VERDE_MEDIO  = colors.HexColor('#16a34a')
VERDE_CLARO  = colors.HexColor('#dcfce7')
VERDE_BORDE  = colors.HexColor('#86efac')
ROJO_TEXTO   = colors.HexColor('#dc2626')
ROJO_CLARO   = colors.HexColor('#fee2e2')
GRIS_FONDO   = colors.HexColor('#f8fafc')
GRIS_BORDE   = colors.HexColor('#e2e8f0')
GRIS_TEXTO   = colors.HexColor('#64748b')
NEGRO_TEXTO  = colors.HexColor('#1e293b')
BLANCO       = colors.white
AMARILLO_CLARO = colors.HexColor('#fefce8')
AMARILLO_BORDE = colors.HexColor('#fde047')

@router.get("/mensual/{periodo}")
def informe_mensual(periodo: str, db: Session = Depends(get_db)):
    from app.models.abastecedor_categoria import AbastecedorCategoria
    abastecedores = db.query(Abastecedor).filter_by(estado='activo').all()
    deudores = []
    for ab in abastecedores:
        estado = get_saldo_abastecedor(db, ab.id)
        if estado["saldo"] > 0:
            relaciones = db.query(AbastecedorCategoria).filter_by(
                abastecedor_id=ab.id
            ).all()
            codigos = "+".join(sorted(r.categoria.codigo for r in relaciones)) if relaciones else "—"
            deudores.append({
                "id":              ab.id,
                "razon_social":    ab.razon_social,
                "titular":         ab.titular,
                "telefono":        ab.telefono_principal,
                "categoria":       codigos,
                "meses_adeudados": estado["meses_adeudados"],
                "periodos":        estado["periodos_deudores"],
                "deuda_total":     estado["saldo"],
            })
    deudores.sort(key=lambda x: x["meses_adeudados"], reverse=True)
    return {"periodo": periodo, "deudores": deudores}

@router.get("/exportar-pdf/{periodo}")
def exportar_pdf(periodo: str, db: Session = Depends(get_db)):
    abastecedores = db.query(Abastecedor).filter_by(estado='activo').all()

    filas_deudores = []
    filas_al_dia   = []
    total_deuda    = 0.0

    for ab in abastecedores:
        estado = get_saldo_abastecedor(db, ab.id)
        saldo  = estado["saldo"]
        meses  = estado["meses_adeudados"]

        # Obtener todas las categorías del abastecedor
        from app.models.abastecedor_categoria import AbastecedorCategoria
        relaciones = db.query(AbastecedorCategoria).filter_by(
            abastecedor_id=ab.id
        ).all()
        codigos = "+".join(sorted(r.categoria.codigo for r in relaciones)) if relaciones else "—"

        if saldo > 0:
            total_deuda += saldo
            filas_deudores.append({
                "razon_social": ab.razon_social,
                "titular":      ab.titular,
                "telefono":     ab.telefono_principal or "—",
                "categoria":    codigos,
                "meses":        meses,
                "periodos":     ", ".join(estado["periodos_deudores"]),
                "saldo":        saldo,
            })
        else:
            filas_al_dia.append({
                "razon_social": ab.razon_social,
                "titular":      ab.titular,
                "categoria":    codigos,
            })

    filas_deudores.sort(key=lambda x: x["meses"], reverse=True)
    # Ruta del logo
    if getattr(sys, 'frozen', False):
        logo_path = os.path.join(sys._MEIPASS, 'static', 'img', 'logo.png')
    else:
        logo_path = os.path.join('static', 'img', 'logo.png')
    buffer = BytesIO()
    doc    = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=12*mm, bottomMargin=12*mm
    )

    # ── Estilos de texto ─────────────────────────────────────
    def estilo(nombre, **kwargs):
        base = {
            'fontName': 'Helvetica',
            'fontSize': 10,
            'textColor': NEGRO_TEXTO,
            'leading': 14,
        }
        base.update(kwargs)
        return ParagraphStyle(nombre, **base)

    s_titulo_header = estilo('th', fontSize=20, fontName='Helvetica-Bold',
                             textColor=BLANCO, leading=24)
    s_sub_header    = estilo('sh', fontSize=10, textColor=colors.HexColor('#93c5fd'), leading=13)
    s_fecha_header  = estilo('fh', fontSize=9, textColor=colors.HexColor('#7dd3fc'),
                             alignment=TA_RIGHT, leading=13)
    s_seccion       = estilo('sc', fontSize=12, fontName='Helvetica-Bold',
                             textColor=AZUL_OSCURO, leading=16)
    s_cab_azul      = estilo('ca', fontSize=9, fontName='Helvetica-Bold',
                             textColor=BLANCO, leading=12)
    s_cab_verde     = estilo('cv', fontSize=9, fontName='Helvetica-Bold',
                             textColor=BLANCO, leading=12)
    s_celda         = estilo('ce', fontSize=9, textColor=NEGRO_TEXTO, leading=12)
    s_celda_rojo    = estilo('cr', fontSize=9, fontName='Helvetica-Bold',
                             textColor=ROJO_TEXTO, leading=12, alignment=TA_RIGHT)
    s_celda_centro  = estilo('cc', fontSize=9, textColor=NEGRO_TEXTO,
                             leading=12, alignment=TA_CENTER)
    s_metrica_num   = estilo('mn', fontSize=22, fontName='Helvetica-Bold',
                             textColor=NEGRO_TEXTO, alignment=TA_CENTER, leading=26)
    s_metrica_lbl   = estilo('ml', fontSize=8, textColor=GRIS_TEXTO,
                             alignment=TA_CENTER, leading=11)
    s_pie           = estilo('pi', fontSize=8, textColor=GRIS_TEXTO, alignment=TA_CENTER)
    s_vacio         = estilo('va', fontSize=9, textColor=GRIS_TEXTO,
                             alignment=TA_CENTER, leading=12)

    try:
        anio, mes = periodo.split('-')
        meses_nombres = ['','Enero','Febrero','Marzo','Abril','Mayo','Junio',
                         'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
        periodo_legible = f"{meses_nombres[int(mes)]} {anio}"
    except:
        periodo_legible = periodo

    elementos = []

    # ── Encabezado azul oscuro ───────────────────────────────
    logo_cell = []
    if os.path.exists(logo_path):
        logo_img = RLImage(logo_path, width=14*mm, height=14*mm)
        logo_cell = [logo_img]

    enc_izq = Table([[
        logo_cell[0] if logo_cell else Paragraph('', estilo('x')),
        Paragraph(f"<b>Comuna de Fighiera</b><br/><font size=9 color='#93c5fd'>Área de Abasto</font>",
            estilo('th', fontSize=16, fontName='Helvetica-Bold', textColor=BLANCO, leading=20))
    ]], colWidths=[18*mm, 82*mm])
    enc_izq.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 0),
        ('LEFTPADDING', (1,0), (1,0), 8),
    ]))

    enc_der = Table([[
        Paragraph(f"Informe mensual<br/>{periodo_legible}",
            estilo('pl', fontSize=13, fontName='Helvetica-Bold',
            textColor=BLANCO, alignment=TA_RIGHT, leading=18)),
    ]], colWidths=[75*mm])
    enc_der.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 0),
    ]))

    enc_data = [[enc_izq, enc_der]]
    enc_table = Table(enc_data, colWidths=[100*mm, 75*mm])
    enc_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), AZUL_OSCURO),
        ('PADDING',    (0,0), (-1,-1), 14),
        ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elementos.append(enc_table)
    elementos.append(Spacer(1, 4*mm))
    sub_data = [[
        Paragraph("Sistema de Abasto", estilo('sub2', fontSize=9,
            textColor=GRIS_TEXTO, leading=12)),
        Paragraph(f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            estilo('gen', fontSize=9, textColor=GRIS_TEXTO,
            alignment=TA_RIGHT, leading=12)),
    ]]
    sub_table = Table(sub_data, colWidths=[100*mm, 75*mm])
    sub_table.setStyle(TableStyle([
        ('PADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    elementos.append(sub_table)
    elementos.append(Spacer(1, 4*mm))

    # ── Métricas ─────────────────────────────────────────────
    total_activos = len(abastecedores)
    cant_deudores = len(filas_deudores)
    cant_al_dia   = len(filas_al_dia)

    def metrica_card(numero, label, color_num=NEGRO_TEXTO, bg=GRIS_FONDO, borde=GRIS_BORDE):
        s_num = estilo(f'mn_{label}', fontSize=22, fontName='Helvetica-Bold',
                       textColor=color_num, alignment=TA_CENTER, leading=26)
        s_lbl = estilo(f'ml_{label}', fontSize=8, textColor=GRIS_TEXTO,
                       alignment=TA_CENTER, leading=11)
        t = Table([
            [Paragraph(str(numero), s_num)],
            [Paragraph(label, s_lbl)],
        ], colWidths=[43*mm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), bg),
            ('PADDING',    (0,0), (-1,-1), 8),
            ('TOPPADDING', (0,0), (0,0), 10),
            ('BOX',        (0,0), (-1,-1), 1, borde),
            ('ROUNDEDCORNERS', [5]),
        ]))
        return t

    metricas_row = [[
        metrica_card(total_activos, "Abastecedores activos"),
        metrica_card(cant_al_dia,   "Al día",
                     color_num=VERDE_MEDIO, bg=VERDE_CLARO, borde=VERDE_BORDE),
        metrica_card(cant_deudores, "Con deuda",
                     color_num=ROJO_TEXTO, bg=ROJO_CLARO,
                     borde=colors.HexColor('#fca5a5')),
        metrica_card(f"${total_deuda:,.0f}", "Deuda total acumulada",
                     color_num=ROJO_TEXTO, bg=ROJO_CLARO,
                     borde=colors.HexColor('#fca5a5')),
    ]]
    metricas_table = Table(metricas_row, colWidths=[43*mm]*4,
                           spaceBefore=0, spaceAfter=0)
    metricas_table.setStyle(TableStyle([
        ('PADDING',  (0,0), (-1,-1), 3),
        ('VALIGN',   (0,0), (-1,-1), 'TOP'),
    ]))
    elementos.append(metricas_table)
    elementos.append(Spacer(1, 6*mm))

    # ── Sección deudores ─────────────────────────────────────
    elementos.append(
        HRFlowable(width="100%", thickness=2, color=AZUL_MEDIO,
                   spaceAfter=4, spaceBefore=2)
    )
    elementos.append(Paragraph("Abastecedores con deuda", s_seccion))
    elementos.append(Spacer(1, 2*mm))

    if filas_deudores:
        cab = [
            Paragraph('Razón social',      s_cab_azul),
            Paragraph('Titular',           s_cab_azul),
            Paragraph('Teléfono',          s_cab_azul),
            Paragraph('Cat.',              s_cab_azul),
            Paragraph('Meses',             s_cab_azul),
            Paragraph('Períodos adeudados',s_cab_azul),
            Paragraph('Saldo',             s_cab_azul),
        ]
        filas = [cab]
        for i, f in enumerate(filas_deudores):
            bg = BLANCO if i % 2 == 0 else AZUL_CLARO
            filas.append([
                Paragraph(f["razon_social"], s_celda),
                Paragraph(f["titular"],      s_celda),
                Paragraph(f["telefono"],     s_celda),
                Paragraph(f["categoria"],    s_celda_centro),
                Paragraph(str(f["meses"]),   s_celda_centro),
                Paragraph(f["periodos"],     s_celda),
                Paragraph(f'${f["saldo"]:,.0f}', s_celda_rojo),
            ])

        t = Table(filas, colWidths=[42*mm, 30*mm, 24*mm, 14*mm, 16*mm, 34*mm, 20*mm],
                  repeatRows=1)
        estilo_t = TableStyle([
            # Cabecera
            ('BACKGROUND', (0,0), (-1,0), AZUL_MEDIO),
            ('TEXTCOLOR',  (0,0), (-1,0), BLANCO),
            ('TOPPADDING', (0,0), (-1,0), 7),
            ('BOTTOMPADDING', (0,0), (-1,0), 7),
            # Filas
            ('PADDING',    (0,1), (-1,-1), 5),
            ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
            # Bordes
            ('LINEBELOW',  (0,0), (-1,0), 0.5, AZUL_OSCURO),
            ('LINEBELOW',  (0,1), (-1,-1), 0.3, AZUL_BORDE),
            ('BOX',        (0,0), (-1,-1), 0.5, AZUL_BORDE),
        ])
        # Filas alternas
        for i in range(1, len(filas)):
            bg = BLANCO if i % 2 == 1 else AZUL_CLARO
            estilo_t.add('BACKGROUND', (0,i), (-1,i), bg)

        t.setStyle(estilo_t)
        elementos.append(t)
    else:
        caja = Table([[Paragraph("Sin deudores en este período.", s_vacio)]],
                     colWidths=[175*mm])
        caja.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), VERDE_CLARO),
            ('PADDING',    (0,0), (-1,-1), 12),
            ('BOX',        (0,0), (-1,-1), 0.5, VERDE_BORDE),
        ]))
        elementos.append(caja)

    elementos.append(Spacer(1, 6*mm))

    # ── Sección al día ───────────────────────────────────────
    elementos.append(
        HRFlowable(width="100%", thickness=2, color=VERDE_MEDIO,
                   spaceAfter=4, spaceBefore=2)
    )
    elementos.append(Paragraph("Abastecedores al día", s_seccion))
    elementos.append(Spacer(1, 2*mm))

    if filas_al_dia:
        cab_dia = [
            Paragraph('Razón social', s_cab_verde),
            Paragraph('Titular',      s_cab_verde),
            Paragraph('Categoría',    s_cab_verde),
        ]
        filas_d = [cab_dia]
        for i, f in enumerate(filas_al_dia):
            filas_d.append([
                Paragraph(f["razon_social"], s_celda),
                Paragraph(f["titular"],      s_celda),
                Paragraph(f["categoria"],    s_celda_centro),
            ])

        t2 = Table(filas_d, colWidths=[85*mm, 70*mm, 20*mm], repeatRows=1)
        estilo_t2 = TableStyle([
            ('BACKGROUND', (0,0), (-1,0), VERDE_MEDIO),
            ('TEXTCOLOR',  (0,0), (-1,0), BLANCO),
            ('TOPPADDING', (0,0), (-1,0), 7),
            ('BOTTOMPADDING', (0,0), (-1,0), 7),
            ('PADDING',    (0,1), (-1,-1), 5),
            ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
            ('LINEBELOW',  (0,0), (-1,0), 0.5, VERDE_OSCURO),
            ('LINEBELOW',  (0,1), (-1,-1), 0.3, VERDE_BORDE),
            ('BOX',        (0,0), (-1,-1), 0.5, VERDE_BORDE),
        ])
        for i in range(1, len(filas_d)):
            bg = BLANCO if i % 2 == 1 else VERDE_CLARO
            estilo_t2.add('BACKGROUND', (0,i), (-1,i), bg)

        t2.setStyle(estilo_t2)
        elementos.append(t2)
    else:
        caja2 = Table([[Paragraph("Sin abastecedores al día.", s_vacio)]],
                      colWidths=[175*mm])
        caja2.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), AMARILLO_CLARO),
            ('PADDING',    (0,0), (-1,-1), 12),
            ('BOX',        (0,0), (-1,-1), 0.5, AMARILLO_BORDE),
        ]))
        elementos.append(caja2)

    # ── Pie ──────────────────────────────────────────────────
    elementos.append(Spacer(1, 8*mm))
    elementos.append(HRFlowable(width="100%", thickness=0.5, color=GRIS_BORDE))
    elementos.append(Spacer(1, 2*mm))
    elementos.append(Paragraph(
        f"Sistema de Abasto — Comuna de Fighiera  •  "
        f"Generado el {datetime.now().strftime('%d/%m/%Y a las %H:%M')}",
        s_pie
    ))

    doc.build(elementos)
    buffer.seek(0)

    filename = f"informe-abasto-{periodo}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"}
    )