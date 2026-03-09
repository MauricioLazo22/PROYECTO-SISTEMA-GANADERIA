# interfaz/login.py
import tkinter as tk
from tkinter import ttk, messagebox
from base_datos import Database

class LoginDialog(tk.Toplevel):
    def __init__(self, parent, db: Database):
        super().__init__(parent)
        self.db = db
        self.title("Inicio de sesión")
        self.geometry("320x180")
        self.resizable(False, False)
        self.grab_set()
        self.user = None

        frame = ttk.Frame(self, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Usuario:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.entry_user = ttk.Entry(frame, width=25)
        self.entry_user.grid(row=0, column=1, pady=5)

        ttk.Label(frame, text="Contraseña:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.entry_pwd = ttk.Entry(frame, width=25, show="*")
        self.entry_pwd.grid(row=1, column=1, pady=5)

        ttk.Button(frame, text="Ingresar", command=self._do_login).grid(
            row=2, column=0, columnspan=2, pady=12
        )

        self.entry_user.focus()

    def _do_login(self):
        u = self.entry_user.get().strip()
        p = self.entry_pwd.get().strip()
        if not u or not p:
            messagebox.showwarning("Atención", "Complete usuario y contraseña", parent=self)
            return

        user = self.db.authenticate_user(u, p)
        if user is None:
            messagebox.showerror("Error", "Credenciales inválidas", parent=self)
            return

        self.user = user
        self.destroy()
