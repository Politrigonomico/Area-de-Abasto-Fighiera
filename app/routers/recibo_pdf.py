import os
import sys
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
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

def _numero_recibo_vigente(db: Session, pago) -> int:
    from app.models.numero_recibo import NumeroRecibo

    # 1. Si el pago ya tiene un recibo asignado Y ES MAYOR A CERO, devolvemos ese mismo número
    if pago.comprobante and pago.comprobante.isdigit() and int(pago.comprobante) > 0:
        return int(pago.comprobante)

    # 2. Si no tiene número (o si quedó trabado en 000000), buscamos el contador en la DB
    contador = db.query(NumeroRecibo).filter(NumeroRecibo.id == 1).first()

    # Si la tabla está vacía, creamos el registro inicial
    if not contador:
        contador = NumeroRecibo(id=1, ultimo=0)
        db.add(contador)
        db.flush()

    # 3. Sumamos 1 al último número emitido
    contador.ultimo += 1

    # 4. Guardamos el nuevo número en el pago para futuras reimpresiones
    pago.comprobante = str(contador.ultimo).zfill(6)
    
    # Guardamos los cambios
    db.commit()

    return contador.ultimo

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

    return texto + (f' CON {centavos:02d}' if centavos else ' CON 00')

def _dibujar_recibo(c: canvas.Canvas, x0: float, y0: float,
                    ancho: float, alto: float,
                    datos: dict, etiqueta: str, logo_path: str):

    margen = 5 * mm
    xi = x0 + margen
    xa = x0 + ancho - margen

    # Borde exterior
    c.setStrokeColor(GRIS_BORDE)
    c.setLineWidth(0.8)
    c.rect(x0, y0, ancho, alto)

    # ENCABEZADO
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

    c.setFont('Helvetica', 7.5) # Letra un poco más grande
    c.setFillColor(NEGRO)
    
    # DATOS ACTUALIZADOS
    inst = [
        'San Martín 1075 - S2126 AFG Fighiera',
        'Tel. 3402533508',
        'Provincia de Santa Fe',
        'E-mail: areaabastofighiera@hotmail.com',
    ]
    ty = enc_y + enc_h - 4.5 * mm
    for linea in inst:
        c.drawString(xi + 22 * mm, ty, linea)
        ty -= 3.8 * mm

    cx = x0 + ancho * 0.55
    c.setStrokeColor(GRIS_BORDE)
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
    c.line(x0, enc_y, x0 + ancho, enc_y)

    # CUERPO
    FS = 10.5 # Fuente más legible
    c.setFont('Helvetica', FS)
    c.setFillColor(NEGRO)

    def linea_punteada(y, desde, hasta=xa):
        c.setStrokeColor(AZUL_LINEA)
        c.setLineWidth(0.35)
        c.setDash([1, 2])
        c.line(desde, y, hasta, y)
        c.setDash([])

    cy = enc_y - 9 * mm
    c.drawString(xi, cy, 'El Señor:')
    c.drawString(xi + 18 * mm, cy, datos['razon_social'][:60])
    linea_punteada(cy, xi + 16 * mm)

    cy = enc_y - 17 * mm
    c.drawString(xi, cy, 'en calle')
    c.drawString(xi + 16 * mm, cy, datos.get('domicilio', '')[:40])
    c.drawRightString(xa, cy, 'Ha satisfecho la')
    linea_punteada(cy, xi + 14 * mm, xa - 30 * mm)

    cy = enc_y - 25 * mm
    en_letras = _numero_a_letras(datos['total'])
    c.drawString(xi, cy, 'suma de Pesos')
    c.drawString(xi + 28 * mm, cy, en_letras[:70])
    linea_punteada(cy, xi + 26 * mm)

    cy = enc_y - 33 * mm
    c.drawString(xi, cy, 'Por concepto de')
    c.drawString(xi + 30 * mm, cy, datos.get('concept', '')[:55])
    linea_punteada(cy, xi + 28 * mm)

    cy = enc_y - 41 * mm
    c.drawString(xi, cy, datos.get('periodos_str', '')[:78])
    linea_punteada(cy, xi + 15 * mm)

    # PIE (Caja y Firmas)
    caja_y = y0 + 13 * mm
    caja_h = 12 * mm
    caja_w = 48 * mm
    c.setStrokeColor(GRIS_BORDE)
    c.setDash([])
    c.rect(xi, caja_y, caja_w, caja_h)
    
    c.setFont('Helvetica', 8)
    c.setFillColor(AZUL_TITULO)
    c.drawString(xi + 2 * mm, caja_y + caja_h - 3 * mm, 'SON $')
    
    c.setFont('Helvetica-Bold', 13)
    c.setFillColor(NEGRO)
    monto_str = '{:,.2f}'.format(datos['total']).replace(',', 'X').replace('.', ',').replace('X', '.')
    c.drawCentredString(xi + caja_w / 2, caja_y + 3.5 * mm, '$ ' + monto_str)

    firma_y = y0 + 16 * mm
    cx_sello = x0 + ancho * 0.55
    c.line(cx_sello - 15 * mm, firma_y, cx_sello + 15 * mm, firma_y)
    c.setFont('Helvetica', 8)
    c.drawCentredString(cx_sello, firma_y - 3.5 * mm, 'Sello')

    cx_firma = x0 + ancho * 0.85
    c.line(cx_firma - 15 * mm, firma_y, cx_firma + 15 * mm, firma_y)
    c.drawCentredString(cx_firma, firma_y - 3.5 * mm, 'Firma')

    c.setFont('Helvetica', 9)
    c.drawString(xi, y0 + 5 * mm, 'Recibido en Fighiera, el    ' + datos.get('fecha_str', ''))

@router.get("/triplicado/{pago_id}")
def recibo_triplicado(pago_id: int, db: Session = Depends(get_db)):
    from app.models.transaccion  import Transaccion
    from app.models.abastecedor  import Abastecedor
    from app.models.pago_detalle import PagoDetalle

    pago = db.get(Transaccion, pago_id)
    if not pago or pago.tipo != 'pago':
        raise HTTPException(404, "Pago no encontrado")

    ab       = db.get(Abastecedor, pago.abastecedor_id)
    detalles = db.query(PagoDetalle).filter_by(pago_id=pago_id).all()
    cargos   = [db.get(Transaccion, d.cargo_id) for d in detalles if db.get(Transaccion, d.cargo_id)]

    periodos_sorted = sorted(set(c.periodo for c in cargos if c.periodo))
    periodos_str = 'Periodos: ' + ', '.join(periodos_sorted) if periodos_sorted else ''
    concepto     = f'Cuota Abasto - {len(periodos_sorted)} periodo(s)' if periodos_sorted else (pago.descripcion or 'Pago Abasto')

    meses_es  = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
                 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
    fecha_str = f"{pago.fecha.day} de {meses_es[pago.fecha.month - 1]} de {pago.fecha.year}"

    datos = {
        'numero':       _numero_recibo_vigente(db, pago),
        'razon_social': f"{ab.razon_social}  -  Tit: {ab.titular}",
        'domicilio':    ab.domicilio or '',
        'concept':      concepto,
        'periodos_str': periodos_str,
        'total':        float(pago.importe),
        'fecha_str':    fecha_str,
    }

    logo_path = _ruta_logo()
    buffer    = BytesIO()
    W, H      = A4
    c = canvas.Canvas(buffer, pagesize=A4)

    # AJUSTE DE MÁRGENES PARA EVITAR RECORTE SUPERIOR
    margen_superior = 12 * mm 
    margen_inferior = 8 * mm
    espacio_util    = H - margen_superior - margen_inferior
    franja_h        = espacio_util / 3
    margen_ext      = 8 * mm
    recibo_w        = W - 2 * margen_ext

    for i, etiqueta in enumerate(['ORIGINAL', 'DUPLICADO', 'TRIPLICADO']):
        # Se calcula la posición Y empezando más abajo del borde de la hoja
        y_base = H - margen_superior - (i + 1) * franja_h
        alto   = franja_h - 2 * mm
        _dibujar_recibo(c, margen_ext, y_base + 1 * mm, recibo_w, alto, datos, etiqueta, logo_path)
        
        if i < 2:
            c.setStrokeColor(colors.HexColor('#bbbbbb'))
            c.setDash([4, 5])
            c.line(0, y_base, W, y_base)
            c.setDash([])

    c.save()
    buffer.seek(0)
    return StreamingResponse(buffer, media_type='application/pdf')