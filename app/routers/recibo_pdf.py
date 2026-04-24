import os
import sys
from io import BytesIO

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas

from app.database import get_db

router = APIRouter(prefix="/recibo-pdf", tags=["Recibo PDF"])

AZUL_TITULO = colors.HexColor('#1a3a7c')
AZUL_LINEA  = colors.HexColor('#3a6fd8')
GRIS_BORDE  = colors.HexColor('#7a9ac0')
NEGRO       = colors.black


def _numero_formateado(n: int) -> str:
    return str(n).zfill(6)


def _ruta_logo() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, 'static', 'img', 'logo.png')
    candidatos = [
        os.path.join('static', 'img', 'logo.png'),
        os.path.join(os.path.dirname(__file__), '..', '..', 'static', 'img', 'logo.png'),
    ]
    for p in candidatos:
        if os.path.exists(p):
            return p
    return ''


def _numero_recibo_vigente(db: Session) -> int:
    return 0


def _numero_a_letras(monto: float) -> str:
    entero   = int(monto)
    centavos = round((monto - entero) * 100)
    unidades = ['', 'UN', 'DOS', 'TRES', 'CUATRO', 'CINCO', 'SEIS', 'SIETE', 'OCHO', 'NUEVE',
                'DIEZ', 'ONCE', 'DOCE', 'TRECE', 'CATORCE', 'QUINCE', 'DIECISEIS',
                'DIECISIETE', 'DIECIOCHO', 'DIECINUEVE']
    decenas  = ['', 'DIEZ', 'VEINTE', 'TREINTA', 'CUARENTA', 'CINCUENTA',
                'SESENTA', 'SETENTA', 'OCHENTA', 'NOVENTA']
    centenas = ['', 'CIENTO', 'DOSCIENTOS', 'TRESCIENTOS', 'CUATROCIENTOS', 'QUINIENTOS',
                'SEISCIENTOS', 'SETECIENTOS', 'OCHOCIENTOS', 'NOVECIENTOS']

    def _seg(n):
        if n == 0:   return ''
        if n == 100: return 'CIEN'
        if n < 20:   return unidades[n]
        if n < 100:
            d, u = divmod(n, 10)
            return decenas[d] + (' Y ' + unidades[u] if u else '')
        c2, r = divmod(n, 100)
        return centenas[c2] + (' ' + _seg(r) if r else '')

    if entero == 0:
        texto = 'CERO'
    elif entero < 1000:
        texto = _seg(entero)
    elif entero < 1_000_000:
        miles, r = divmod(entero, 1000)
        p = 'MIL' if miles == 1 else _seg(miles) + ' MIL'
        texto = p + (' ' + _seg(r) if r else '')
    else:
        mn, r = divmod(entero, 1_000_000)
        p = 'UN MILLON' if mn == 1 else _seg(mn) + ' MILLONES'
        texto = p + (' ' + _seg(r) if r else '')

    return texto + (f' CON {centavos:02d}/100' if centavos else ' CON 00/100')


def _dibujar_recibo(c: canvas.Canvas, x0: float, y0: float,
                    ancho: float, alto: float,
                    datos: dict, etiqueta: str, logo_path: str):

    margen = 5 * mm
    xi = x0 + margen
    xa = x0 + ancho - margen

    # Borde exterior principal
    c.setStrokeColor(GRIS_BORDE)
    c.setLineWidth(0.8)
    c.rect(x0, y0, ancho, alto)

    # ================= ENCABEZADO =================
    enc_h = 22 * mm
    enc_y = y0 + alto - enc_h
    c.setFillColor(colors.HexColor('#e8f0fb'))
    c.rect(x0, enc_y, ancho, enc_h, fill=1, stroke=0)

    if logo_path and os.path.exists(logo_path):
        try:
            c.drawImage(logo_path, xi, enc_y + 2 * mm,
                        width=18 * mm, height=18 * mm, preserveAspectRatio=True)
        except Exception:
            pass

    c.setFont('Helvetica', 7)
    c.setFillColor(NEGRO)
    inst = [
        'Andrade N 625 - S2126 AFG  Fighiera',
        'Tel. (03402) 470124 - Fax: 03402-470259',
        'Provincia de Santa Fe',
        'E-mail: comunafighiera@gmail.com',
        'secretariacomuna@gmail.com',
    ]
    ty = enc_y + enc_h - 4 * mm
    for linea in inst:
        c.drawString(xi + 22 * mm, ty, linea)
        ty -= 3.5 * mm

    cx = x0 + ancho * 0.55
    c.setStrokeColor(GRIS_BORDE)
    c.setLineWidth(0.5)
    c.line(cx, enc_y + 2 * mm, cx, enc_y + enc_h - 2 * mm)

    numero = _numero_formateado(datos['numero'])
    c.setFont('Helvetica-Bold', 14)
    c.setFillColor(AZUL_TITULO)
    c.drawString(cx + 5 * mm, enc_y + enc_h - 7 * mm, 'RECIBO   Nº   ' + numero)
    c.setFont('Helvetica-Bold', 11)
    c.drawString(cx + 5 * mm, enc_y + enc_h - 14 * mm, 'CONTROL ABASTO')

    c.setFont('Helvetica-Bold', 8)
    c.setFillColor(colors.HexColor('#444444'))
    c.drawRightString(xa, enc_y + 2 * mm, etiqueta)

    c.setStrokeColor(AZUL_LINEA)
    c.setLineWidth(0.6)
    c.line(x0, enc_y, x0 + ancho, enc_y)


    # ================= CUERPO (Letras grandes y alineadas) =================
    FS = 10
    c.setFont('Helvetica', FS)
    c.setFillColor(NEGRO)

    def linea_punteada(y, desde, hasta=xa):
        c.setStrokeColor(AZUL_LINEA)
        c.setLineWidth(0.35)
        c.setDash([1, 2])
        c.line(desde, y, hasta, y)
        c.setDash([])

    # 1. Señor
    cy = enc_y - 8 * mm
    c.drawString(xi, cy, 'El Señor:')
    c.drawString(xi + 18 * mm, cy, datos['razon_social'][:60])
    linea_punteada(cy, xi + 16 * mm)

    # 2. Calle
    cy = enc_y - 16 * mm
    c.drawString(xi, cy, 'en calle')
    c.drawString(xi + 16 * mm, cy, datos.get('domicilio', '')[:40])
    c.drawRightString(xa, cy, 'Ha satisfecho la')
    linea_punteada(cy, xi + 14 * mm, xa - 28 * mm)

    # 3. Suma
    cy = enc_y - 24 * mm
    en_letras = _numero_a_letras(datos['total'])
    c.drawString(xi, cy, 'suma de Pesos')
    c.drawString(xi + 28 * mm, cy, en_letras[:70])
    linea_punteada(cy, xi + 26 * mm)

    # 4. Concepto
    cy = enc_y - 32 * mm
    c.drawString(xi, cy, 'Por concepto de')
    c.drawString(xi + 30 * mm, cy, datos.get('concepto', '')[:55])
    linea_punteada(cy, xi + 28 * mm)

    # 5. Períodos
    cy = enc_y - 40 * mm
    c.drawString(xi, cy, datos.get('periodos_str', '')[:78])
    linea_punteada(cy, xi + c.stringWidth("Periodos: ", 'Helvetica', FS))


    # ================= PIE (Caja $ y Firmas ancladas abajo) =================
    # Caja Monto
    caja_y = y0 + 12 * mm
    caja_h = 12 * mm
    caja_w = 45 * mm
    c.setStrokeColor(GRIS_BORDE)
    c.setDash([])
    c.setLineWidth(0.8)
    c.rect(xi, caja_y, caja_w, caja_h)
    
    c.setFont('Helvetica', 8)
    c.setFillColor(AZUL_TITULO)
    c.drawString(xi + 2 * mm, caja_y + caja_h - 3 * mm, 'SON $')
    
    c.setFont('Helvetica-Bold', 12)
    c.setFillColor(NEGRO)
    monto_str = '{:,.2f}'.format(datos['total']).replace(',', 'X').replace('.', ',').replace('X', '.')
    c.drawCentredString(xi + caja_w / 2, caja_y + 3 * mm, '$ ' + monto_str)

    # Firmas
    firma_y = y0 + 15 * mm
    c.setStrokeColor(NEGRO)
    c.setLineWidth(0.5)

    cx_sello = x0 + ancho * 0.55
    c.line(cx_sello - 15 * mm, firma_y, cx_sello + 15 * mm, firma_y)
    c.setFont('Helvetica', 8)
    c.drawCentredString(cx_sello, firma_y - 3 * mm, 'Sello')

    cx_firma = x0 + ancho * 0.85
    c.line(cx_firma - 15 * mm, firma_y, cx_firma + 15 * mm, firma_y)
    c.drawCentredString(cx_firma, firma_y - 3 * mm, 'Firma')

    # Fecha de emisión
    c.setFont('Helvetica', 9)
    c.drawString(xi, y0 + 4 * mm, 'Recibido en Fighiera, el    ' + datos.get('fecha_str', ''))


@router.get("/triplicado/{pago_id}")
def recibo_triplicado(pago_id: int, db: Session = Depends(get_db)):
    from app.models.transaccion  import Transaccion
    from app.models.abastecedor  import Abastecedor
    from app.models.pago_detalle import PagoDetalle
    from fastapi import HTTPException

    pago = db.get(Transaccion, pago_id)
    if not pago or pago.tipo != 'pago':
        raise HTTPException(404, "Pago no encontrado")

    ab       = db.get(Abastecedor, pago.abastecedor_id)
    detalles = db.query(PagoDetalle).filter_by(pago_id=pago_id).all()
    cargos   = [db.get(Transaccion, d.cargo_id) for d in detalles
                if db.get(Transaccion, d.cargo_id)]

    periodos_sorted = sorted(set(c.periodo for c in cargos if c.periodo))
    if periodos_sorted:
        periodos_str = 'Periodos: ' + ', '.join(periodos_sorted)
        concepto     = 'Cuota Abasto - ' + str(len(periodos_sorted)) + ' periodo(s)'
    else:
        periodos_str = ''
        concepto     = pago.descripcion or 'Pago Abasto'

    numero    = _numero_recibo_vigente(db)
    fecha_obj = pago.fecha
    meses_es  = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
                 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
    fecha_str = (str(fecha_obj.day) + ' de ' + meses_es[fecha_obj.month - 1] +
                 ' de ' + str(fecha_obj.year))

    datos = {
        'numero':       numero,
        'razon_social': ab.razon_social + '  -  Tit: ' + ab.titular,
        'domicilio':    ab.domicilio or '',
        'concepto':     concepto,
        'periodos_str': periodos_str,
        'total':        float(pago.importe),
        'fecha_str':    fecha_str,
    }

    logo_path = _ruta_logo()
    buffer    = BytesIO()
    W, H      = A4

    c = canvas.Canvas(buffer, pagesize=A4)
    c.setTitle('Recibo Abasto N ' + _numero_formateado(numero))

    franja_h   = H / 3
    margen_ext = 8 * mm
    recibo_w   = W - 2 * margen_ext

    for i, etiqueta in enumerate(['ORIGINAL', 'DUPLICADO', 'TRIPLICADO']):
        y_base = H - (i + 1) * franja_h
        alto   = franja_h - 2 * mm
        _dibujar_recibo(c, margen_ext, y_base + 1 * mm, recibo_w, alto,
                        datos, etiqueta, logo_path)
        
        # Linea de corte entre recibos
        if i < 2:
            c.setStrokeColor(colors.HexColor('#bbbbbb'))
            c.setLineWidth(0.4)
            c.setDash([4, 5])
            c.line(0, y_base + 0.5 * mm, W, y_base + 0.5 * mm)
            c.setDash([])

    c.save()
    buffer.seek(0)

    filename = 'recibo-abasto-' + _numero_formateado(numero) + '-pago' + str(pago_id) + '.pdf'
    return StreamingResponse(
        buffer,
        media_type='application/pdf',
        headers={'Content-Disposition': 'inline; filename=' + filename}
    )