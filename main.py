# main.py
from pathlib import Path
import tkinter as tk
from configuracion import AppConfig
from base_datos import Database
from interfaz.aplicacion import DairyManagementApp
from interfaz.login import LoginDialog

def main():
    # asegurar carpeta de backups
    Path(AppConfig.BACKUP_DIR).mkdir(exist_ok=True)

    # raíz oculta solo para mostrar el login
    root = tk.Tk()
    root.withdraw()

    db = Database()

    # si no hay usuarios, crear admin por defecto
    if not db.list_users():
        db.add_user("admin", "admin123", role="admin")

    # mostrar login
    dlg = LoginDialog(root, db)
    root.wait_window(dlg)

    if dlg.user is None:
        # cerró o falló
        db.close()
        return 0

    # ya tenemos usuario -> abrir app con ese usuario
    app = DairyManagementApp(user=dlg.user)
    app.mainloop()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
