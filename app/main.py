import atexit
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader
from app.database import init_db, get_db
from app.routers import categorias, abastecedores, transacciones, parametros, reportes
from app.backup import hacer_backup, iniciar_scheduler
from app.routers import recibo_pdf


app = FastAPI(title="Sistema de Abasto", version="1.0.0")

app.mount("/static", StaticFiles(directory="static"), name="static")

jinja_env = Environment(loader=FileSystemLoader("app/templates"))

def render(template_name: str, context: dict):
    template = jinja_env.get_template(template_name)
    return HTMLResponse(template.render(**context))

app.include_router(categorias.router)
app.include_router(abastecedores.router)
app.include_router(transacciones.router)
app.include_router(parametros.router)
app.include_router(reportes.router)
app.include_router(recibo_pdf.router)

@app.on_event("startup")
def startup():
    init_db()
    hacer_backup(motivo="inicio")      # Backup al arrancar
    iniciar_scheduler()                # Activa el backup automático 8AM

@app.on_event("shutdown")
def shutdown():
    hacer_backup(motivo="cierre")      # Backup al cerrar

# ── Páginas HTML ──────────────────────────────────────────
@app.get("/")
def dashboard(request: Request):
    return render("dashboard.html", {"active": "dashboard"})

@app.get("/categorias-page")
def categorias_page(request: Request):
    return render("categorias/lista.html", {"active": "categorias"})

@app.get("/abastecedores")
def abastecedores_page(request: Request):
    return render("abastecedores/lista.html", {"active": "abastecedores"})

@app.get("/abastecedores/{id}/detalle")
def abastecedor_detalle(id: int, request: Request):
    return render("abastecedores/detalle.html", {
        "active": "abastecedores",
        "abastecedor_id": id
    })

@app.get("/reportes/mensual")
def reporte_mensual(request: Request):
    return render("reportes/mensual.html", {"active": "reportes"})

@app.get("/parametros")
def parametros_page(request: Request):
    return render("parametros.html", {"active": "parametros"})

@app.get("/recibo")
def recibo_page(request: Request):
    return render("recibo.html", {})

@app.get("/recibo/datos/{pago_id}")
def recibo_datos(pago_id: int, db=Depends(get_db)):
    from app.routers.transacciones import datos_recibo
    return datos_recibo(pago_id, db)