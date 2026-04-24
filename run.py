import sys
import os

if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

if base_path not in sys.path:
    sys.path.insert(0, base_path)

os.chdir(base_path)

if getattr(sys, 'frozen', False):
    db_path = os.path.join(os.path.dirname(sys.executable), 'abasto.db')
else:
    db_path = os.path.join(base_path, 'abasto.db')

os.environ['DATABASE_URL'] = f'sqlite:///{db_path}'

import webbrowser
import threading
import time
import socket
import subprocess

def puerto_ocupado(puerto: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', puerto)) == 0

def liberar_puerto(puerto: int):
    """Mata cualquier proceso que esté usando el puerto."""
    try:
        resultado = subprocess.check_output(
            f'netstat -ano | findstr :{puerto}', shell=True
        ).decode()
        for linea in resultado.strip().split('\n'):
            partes = linea.strip().split()
            if partes and 'LISTENING' in linea:
                pid = partes[-1]
                subprocess.call(f'taskkill /F /PID {pid}', shell=True)
                time.sleep(0.5)
    except Exception:
        pass

def abrir_navegador():
    time.sleep(2)
    webbrowser.open('http://127.0.0.1:8000')

def crear_icono_bandeja(server):
    """Crea un ícono en la bandeja del sistema para cerrar el programa."""
    try:
        import pystray
        from PIL import Image, ImageDraw

        # Crear imagen simple para el ícono
        img = Image.new('RGB', (64, 64), color='#1a1a2e')
        draw = ImageDraw.Draw(img)
        draw.ellipse([8, 8, 56, 56], fill='#6c63ff')
        draw.text((20, 18), 'AB', fill='white')

        def abrir_app(icon, item):
            webbrowser.open('http://127.0.0.1:8000')

        def cerrar_app(icon, item):
            from app.backup import hacer_backup
            hacer_backup(motivo="cierre")
            icon.stop()
            server.should_exit = True
            os._exit(0)

        menu = pystray.Menu(
            pystray.MenuItem('Abrir Sistema de Abasto', abrir_app, default=True),
            pystray.MenuItem('Cerrar', cerrar_app)
        )

        icon = pystray.Icon('SistemaAbasto', img, 'Sistema de Abasto', menu)
        icon.run()
    except Exception as e:
        print(f"Error en bandeja: {e}")

def main():
    # Liberar el puerto si está ocupado
    if puerto_ocupado(8000):
        print("Puerto 8000 ocupado, liberando...")
        liberar_puerto(8000)
        time.sleep(1)

    # Si sigue ocupado, abrir el navegador con la instancia existente
    if puerto_ocupado(8000):
        webbrowser.open('http://127.0.0.1:8000')
        return

    import uvicorn
    config = uvicorn.Config(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        log_config=None,
        access_log=False,
    )
    server = uvicorn.Server(config)

    # Abrir navegador en hilo separado
    t_browser = threading.Thread(target=abrir_navegador, daemon=True)
    t_browser.start()

    # Ícono de bandeja en hilo separado
    t_tray = threading.Thread(target=crear_icono_bandeja, args=(server,), daemon=True)
    t_tray.start()

    server.run()

if __name__ == '__main__':
    main()