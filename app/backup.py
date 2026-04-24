import os
import shutil
import threading
import schedule
import time
from datetime import datetime

def get_db_path() -> str:
    """Obtiene la ruta de la base de datos según el entorno."""
    import sys
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), 'abasto.db')
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'abasto.db')

def get_backup_dir() -> str:
    """Carpeta de backups junto al ejecutable o en el proyecto."""
    import sys
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
        base = os.path.join(base, '..')
    carpeta = os.path.join(base, 'backups')
    os.makedirs(carpeta, exist_ok=True)
    return carpeta

def hacer_backup(motivo: str = "programado") -> str | None:
    """
    Copia la base de datos a la carpeta backups/.
    El archivo se llama abasto_YYYY-MM-DD_{motivo}.db
    Si ya existe uno del mismo día y motivo, lo reemplaza.
    Retorna la ruta del backup creado o None si falló.
    """
    try:
        db_path     = get_db_path()
        backup_dir  = get_backup_dir()
        hoy         = datetime.now().strftime('%Y-%m-%d')
        nombre      = f"abasto_{hoy}_{motivo}.db"
        destino     = os.path.join(backup_dir, nombre)

        if not os.path.exists(db_path):
            return None

        shutil.copy2(db_path, destino)
        limpiar_backups_viejos(backup_dir)
        return destino
    except Exception as e:
        print(f"Error en backup: {e}")
        return None

def limpiar_backups_viejos(backup_dir: str, mantener: int = 30):
    """
    Mantiene solo los últimos N backups de cada tipo.
    Borra los más viejos automáticamente.
    """
    try:
        archivos = sorted([
            f for f in os.listdir(backup_dir) if f.endswith('.db')
        ])
        if len(archivos) > mantener:
            para_borrar = archivos[:len(archivos) - mantener]
            for f in para_borrar:
                os.remove(os.path.join(backup_dir, f))
    except Exception as e:
        print(f"Error limpiando backups: {e}")

def iniciar_scheduler():
    """
    Corre el scheduler en un hilo separado.
    Programa backup automático a las 8:00 AM de lunes a viernes.
    """
    schedule.every().monday.at("08:00").do(hacer_backup, motivo="automatico")
    schedule.every().tuesday.at("08:00").do(hacer_backup, motivo="automatico")
    schedule.every().wednesday.at("08:00").do(hacer_backup, motivo="automatico")
    schedule.every().thursday.at("08:00").do(hacer_backup, motivo="automatico")
    schedule.every().friday.at("08:00").do(hacer_backup, motivo="automatico")

    def loop():
        while True:
            schedule.run_pending()
            time.sleep(30)

    t = threading.Thread(target=loop, daemon=True)
    t.start()