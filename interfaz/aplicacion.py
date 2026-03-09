
"""
interfaz/aplicacion.py
Interfaz gráfica (Tkinter) del sistema de gestión ganadera.
Este archivo es la misma parte de Tkinter que tenías en tu script original.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any
from pathlib import Path
import csv
import os
import sqlite3

# gráficos
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np

# estos vienen de los otros archivos que vamos a separar
from configuracion import AppConfig, QualityLevel, logger
from modelos import Cow, MilkRecord
from base_datos import Database, DatabaseException

# ========================================================================
# INTERFAZ GRÁFICA (Tkinter)
# ========================================================================

class ModernStyle:
    @staticmethod
    def configure(root):
        style = ttk.Style(root)
        try:
            style.theme_use('clam')
        except Exception:
            pass
        style.configure('Title.TLabel', font=('Arial', 12, 'bold'), foreground='#2C3E50')
        style.configure('Subtitle.TLabel', font=('Arial', 10), foreground='#34495E')
        style.configure('Success.TButton', background='#27AE60', foreground='white')
        style.configure('Danger.TButton', background='#E74C3C', foreground='white')
        style.configure('Primary.TButton', background='#3498DB', foreground='white')


class UserManagerDialog(tk.Toplevel):
    """Diálogo simple para administrar usuarios"""
    def __init__(self, parent, db: Database):
        super().__init__(parent)
        self.db = db
        self.title("Administración de Usuarios")
        self.geometry("600x400")
        self.resizable(False, False)
        self.grab_set()

        frame = ttk.Frame(self, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        # Lista de usuarios
        cols = ("id", "username", "role", "active", "created_at")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", height=12)
        for c in cols:
            self.tree.heading(c, text=c.capitalize())
            self.tree.column(c, width=100)
        self.tree.pack(fill=tk.BOTH, expand=True)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=8)
        ttk.Button(btn_frame, text="➕ Nuevo", command=self._create_user).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="🔑 Cambiar Contraseña", command=self._change_password).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="🗑️ Desactivar", command=self._deactivate_user).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cerrar", command=self.destroy).pack(side=tk.RIGHT, padx=5)

        self.refresh()

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for u in self.db.list_users():
            self.tree.insert("", tk.END, values=(u["id"], u["username"], u["role"], u["active"], u["created_at"]))

    def _create_user(self):
        import tkinter.simpledialog as simpledialog

        username = simpledialog.askstring("Nuevo Usuario", "Nombre de usuario:", parent=self)
        if not username:
            return

        pwd = simpledialog.askstring("Contraseña", f"Contraseña para {username}:", parent=self, show='*')
        if pwd is None or pwd == "":
            messagebox.showwarning("Atención", "Contraseña vacía", parent=self)
            return

        # 👉 Aquí pedimos el rol directamente
        role = simpledialog.askstring(
            "Rol de usuario",
            "Ingrese el rol (admin / tecnico / ordenador):",
            parent=self
        )

        # Si escribe algo distinto, dejamos 'user' por defecto
        if role not in ("admin", "tecnico", "ordenador"):
            role = "user"

        try:
            self.db.add_user(username, pwd, role=role)
            messagebox.showinfo("Éxito", f"Usuario '{username}' creado con rol '{role}'", parent=self)
            self.refresh()
        except DatabaseException as e:
            messagebox.showerror("Error", str(e), parent=self)


    def _change_password(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Atención", "Seleccione un usuario", parent=self)
            return
        item = self.tree.item(sel[0])['values']
        uid = item[0]
        pwd = simpledialog.askstring("Nueva contraseña", f"Nueva contraseña para {item[1]}:", parent=self, show='*')
        if pwd is None or pwd == "":
            return
        try:
            self.db.update_user_password(uid, pwd)
            messagebox.showinfo("Éxito", "Contraseña actualizada", parent=self)
        except DatabaseException as e:
            messagebox.showerror("Error", str(e), parent=self)

    def _deactivate_user(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Atención", "Seleccione un usuario", parent=self)
            return
        item = self.tree.item(sel[0])['values']
        uid = item[0]
        if not messagebox.askyesno("Confirmar", f"Desactivar usuario {item[1]}?", parent=self):
            return
        try:
            self.db.delete_user(uid)
            messagebox.showinfo("Éxito", "Usuario desactivado", parent=self)
            self.refresh()
        except DatabaseException as e:
            messagebox.showerror("Error", str(e), parent=self)



class DairyManagementApp(tk.Tk):
    def __init__(self, user):
        super().__init__()
        self.current_user = user   # guardamos el usuario logueado

        self.title(f"Sistema de Gestión Ganadera v{AppConfig.VERSION}")
        self.geometry("1200x700")
        self.minsize(1000, 600)

        # conectar a la base
        try:
            self.db = Database()
        except DatabaseException as e:
            messagebox.showerror("Error crítico", str(e))
            self.quit()
            return

        # estilos
        ModernStyle.configure(self)

        # menú con permisos según rol
        self._setup_menu()

        # resto de la interfaz como ya la tenías
        self._create_widgets()
        self._seed_demo_data()
        self.refresh_all()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _prev_page(self):
        if self._rec_page > 0:
            self._rec_page -= 1
            self.refresh_records()

    def _next_page(self):
        self._rec_page += 1
        self.refresh_records()

    def _setup_menu(self):
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Archivo", menu=file_menu)

        # backup: solo admin y técnico
        if self.current_user["role"] in ("admin", "tecnico"):
            file_menu.add_command(label="Backup Base de Datos", command=self._create_backup)
            # 👇 ESTA ES LA NUEVA OPCIÓN
            file_menu.add_command(label="Restaurar Base de Datos", command=self._restore_backup)

        # gestión de usuarios: solo admin
        if self.current_user["role"] == "admin":
            file_menu.add_command(label="Usuarios", command=self._open_user_manager)

        file_menu.add_separator()
        file_menu.add_command(label="Salir", command=self._on_closing)

        reports_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Reportes", menu=reports_menu)
        reports_menu.add_command(label="Estadísticas Generales", command=self._show_general_stats)

        if self.current_user["role"] in ("admin", "tecnico"):
            reports_menu.add_command(label="Exportar CSV", command=self._export_csv)

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ayuda", menu=help_menu)
        help_menu.add_command(label="Acerca de", command=self._show_about)

    def _create_widgets(self):
        main_paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=1)

        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=2)

        self._create_cows_panel(left_frame)
        self._create_records_panel(right_frame)

    # ---------------------------------------------------------------------
    # PANEL DE VACAS
    # ---------------------------------------------------------------------
    def _create_cows_panel(self, parent):
        ttk.Label(parent, text="Gestión de Hato", style='Title.TLabel').pack(pady=8)

        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        cols = ("id", "tag", "name", "breed", "dob")
        self.cow_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=25)
        for col in cols:
            text = col.upper() if col != "dob" else "F. NAC."
            self.cow_tree.heading(col, text=text)
        self.cow_tree.column("id", width=40, anchor=tk.CENTER)
        self.cow_tree.column("tag", width=90, anchor=tk.CENTER)
        self.cow_tree.column("name", width=130)
        self.cow_tree.column("breed", width=100)
        self.cow_tree.column("dob", width=90, anchor=tk.CENTER)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.cow_tree.yview)
        self.cow_tree.configure(yscrollcommand=vsb.set)

        self.cow_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.cow_tree.bind("<<TreeviewSelect>>", self._on_cow_selected)

        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X, pady=6, padx=5)
        ttk.Button(btn_frame, text="➕ Agregar", command=self._add_cow, style='Success.TButton').pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Button(btn_frame, text="✏️ Editar", command=self._edit_cow, style='Primary.TButton').pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Button(btn_frame, text="🗑️ Eliminar", command=self._delete_cow, style='Danger.TButton').pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)

    # ---------------------------------------------------------------------
    # PANEL DE REGISTROS
    # ---------------------------------------------------------------------
    def _create_records_panel(self, parent):
        notebook = ttk.Notebook(parent)
        notebook.pack(fill=tk.BOTH, expand=True)

        tab_registro = ttk.Frame(notebook)
        notebook.add(tab_registro, text="📝 Registro de Producción")
        self._create_record_form(tab_registro)

        tab_consulta = ttk.Frame(notebook)
        notebook.add(tab_consulta, text="📊 Consulta y Análisis")
        self._create_query_panel(tab_consulta)

        tab_graficos = ttk.Frame(notebook)
        notebook.add(tab_graficos, text="📈 Gráficos")
        self._create_charts_panel(tab_graficos)

    def _create_record_form(self, parent):
        form_frame = ttk.LabelFrame(parent, text="Nueva Producción", padding=12)
        form_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(form_frame, text="Vaca:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.cmb_cow = ttk.Combobox(form_frame, state="readonly", width=40)
        self.cmb_cow.grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)

        ttk.Label(form_frame, text="Fecha:").grid(row=0, column=2, sticky=tk.W, pady=5, padx=(20, 0))
        self.entry_fecha = ttk.Entry(form_frame, width=12)
        self.entry_fecha.grid(row=0, column=3, sticky=tk.W, pady=5, padx=5)
        self.entry_fecha.insert(0, date.today().isoformat())

        ttk.Button(
            form_frame,
            text="Hoy",
            command=lambda: (self.entry_fecha.delete(0, tk.END), self.entry_fecha.insert(0, date.today().isoformat()))
        ).grid(row=0, column=4, padx=5)

        ttk.Label(form_frame, text="Litros:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.entry_litros = ttk.Entry(form_frame, width=15)
        self.entry_litros.grid(row=1, column=1, sticky=tk.W, pady=5, padx=5)

        ttk.Label(form_frame, text="Calidad:").grid(row=1, column=2, sticky=tk.W, pady=5, padx=(20, 0))
        self.cmb_calidad = ttk.Combobox(form_frame, state="readonly", width=15, values=[q.value for q in QualityLevel])
        self.cmb_calidad.grid(row=1, column=3, sticky=tk.W, pady=5, padx=5)
        self.cmb_calidad.set(QualityLevel.BUENA.value)

        ttk.Label(form_frame, text="Observaciones:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.entry_obs = ttk.Entry(form_frame, width=70)
        self.entry_obs.grid(row=2, column=1, columnspan=4, sticky=tk.W, pady=5, padx=5)

        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=3, column=0, columnspan=5, pady=12)
        ttk.Button(btn_frame, text="💾 Guardar Registro", command=self._save_milk_record, style='Success.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="🔄 Limpiar", command=self._clear_form, style='Primary.TButton').pack(side=tk.LEFT, padx=5)

        preview_frame = ttk.LabelFrame(parent, text="Últimos Registros", padding=8)
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)

        cols = ("id", "fecha", "tag", "name", "litros", "calidad")
        self.preview_tree = ttk.Treeview(preview_frame, columns=cols, show="headings", height=10)
        for col in cols:
            self.preview_tree.heading(col, text=col.capitalize())
            if col == "id":
                self.preview_tree.column(col, width=40, anchor=tk.CENTER)
            elif col in ["litros"]:
                self.preview_tree.column(col, width=80, anchor=tk.CENTER)
            else:
                self.preview_tree.column(col, width=120)

        vsb = ttk.Scrollbar(preview_frame, orient="vertical", command=self.preview_tree.yview)
        self.preview_tree.configure(yscrollcommand=vsb.set)
        self.preview_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

    def _create_query_panel(self, parent):
        filter_frame = ttk.LabelFrame(parent, text="Filtros de Búsqueda", padding=10)
        filter_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(filter_frame, text="Vaca:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.cmb_filter_cow = ttk.Combobox(filter_frame, state="readonly", width=30)
        self.cmb_filter_cow.grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)

        ttk.Label(filter_frame, text="Desde:").grid(row=0, column=2, sticky=tk.W, pady=5, padx=(20, 0))
        self.from_entry = ttk.Entry(filter_frame, width=12)
        self.from_entry.grid(row=0, column=3, sticky=tk.W, pady=5, padx=5)

        ttk.Label(filter_frame, text="Hasta:").grid(row=0, column=4, sticky=tk.W, pady=5, padx=(10, 0))
        self.to_entry = ttk.Entry(filter_frame, width=12)
        self.to_entry.grid(row=0, column=5, sticky=tk.W, pady=5, padx=5)

        btn_frame = ttk.Frame(filter_frame)
        btn_frame.grid(row=1, column=0, columnspan=6, pady=10)
        ttk.Button(btn_frame, text="🔍 Buscar", command=self._apply_filters, style='Primary.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="🔄 Limpiar Filtros", command=self._clear_filters).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="📥 Exportar CSV", command=self._export_csv).pack(side=tk.LEFT, padx=5)

        results_frame = ttk.LabelFrame(parent, text="Resultados", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        cols = ("id", "fecha", "tag", "name", "litros", "calidad", "observaciones")
        self.rec_tree = ttk.Treeview(results_frame, columns=cols, show="headings")
        for col in cols:
            self.rec_tree.heading(col, text=col.capitalize())
            if col == "id":
                self.rec_tree.column(col, width=40, anchor=tk.CENTER)
            elif col == "litros":
                self.rec_tree.column(col, width=80, anchor=tk.CENTER)
            elif col == "observaciones":
                self.rec_tree.column(col, width=250)
            else:
                self.rec_tree.column(col, width=100)
        
        # Tamaño de página y página actual
        self.PAGE_SIZE = 300  # ajusta según tu PC (200–1000)
        self._rec_page = 0

        nav_frame = ttk.Frame(results_frame)
        nav_frame.grid(row=4, column=0, columnspan=2, pady=6)

        self.lbl_page = ttk.Label(nav_frame, text="Página 1")
        self.lbl_page.pack(side=tk.LEFT, padx=6)

        ttk.Button(nav_frame, text="⟵ Anterior", command=self._prev_page).pack(side=tk.LEFT, padx=4)
        ttk.Button(nav_frame, text="Siguiente ⟶", command=self._next_page).pack(side=tk.LEFT, padx=4)

        vsb = ttk.Scrollbar(results_frame, orient="vertical", command=self.rec_tree.yview)
        hsb = ttk.Scrollbar(results_frame, orient="horizontal", command=self.rec_tree.xview)
        self.rec_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.rec_tree.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.E, tk.W))
        vsb.grid(row=0, column=1, sticky=(tk.N, tk.S))
        hsb.grid(row=1, column=0, sticky=(tk.E, tk.W))
        results_frame.rowconfigure(0, weight=1)
        results_frame.columnconfigure(0, weight=1)

        edit_frame = ttk.Frame(results_frame)
        edit_frame.grid(row=2, column=0, columnspan=2, pady=10)
        ttk.Button(edit_frame, text="✏️ Editar", command=self._edit_milk_record, style='Primary.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(edit_frame, text="🗑️ Eliminar", command=self._delete_milk_record, style='Danger.TButton').pack(side=tk.LEFT, padx=5)

        self.stats_label = ttk.Label(results_frame, text="", style='Subtitle.TLabel')
        self.stats_label.grid(row=3, column=0, columnspan=2, pady=5)
    
    def _restore_backup(self):
        from tkinter import filedialog, messagebox
        path = filedialog.askopenfilename(
            title="Seleccionar backup",
            filetypes=[("DB", "*.db"), ("Todos", "*.*")]
        )
        if not path:
            return
        if not messagebox.askyesno("Confirmar", "Esto reemplazará la base de datos actual. ¿Continuar?"):
            return
        try:
            self.db.restore(path)
            messagebox.showinfo("Restaurado", "Base de datos restaurada. Reinicia la aplicación.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo restaurar: {e}")


    def _create_charts_panel(self, parent):
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(control_frame, text="Seleccionar Vaca:", style='Subtitle.TLabel').pack(side=tk.LEFT, padx=5)
        self.cmb_chart_cow = ttk.Combobox(control_frame, state="readonly", width=30)
        self.cmb_chart_cow.pack(side=tk.LEFT, padx=5)

        ttk.Label(control_frame, text="Período (días):").pack(side=tk.LEFT, padx=(20, 5))
        self.period_var = tk.IntVar(value=30)
        period_spin = ttk.Spinbox(control_frame, from_=7, to=365, textvariable=self.period_var, width=10)
        period_spin.pack(side=tk.LEFT, padx=5)

        ttk.Button(control_frame, text="📊 Generar Gráfico", command=self._generate_chart, style='Primary.TButton').pack(side=tk.LEFT, padx=10)

        self.chart_frame = ttk.Frame(parent)
        self.chart_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        stats_frame = ttk.LabelFrame(parent, text="Estadísticas del Período", padding=8)
        stats_frame.pack(fill=tk.X, padx=10, pady=6)
        self.chart_stats_label = ttk.Label(stats_frame, text="Seleccione una vaca y genere el gráfico", style='Subtitle.TLabel')
        self.chart_stats_label.pack()

    # ------------------------------------------------------------------
    # MANEJO DE VACAS
    # ------------------------------------------------------------------
    def _on_cow_selected(self, event):
        sel = self.cow_tree.selection()
        if not sel:
            return
        item = self.cow_tree.item(sel[0])
        display = f"{item['values'][1]} - {item['values'][2]}"
        if display in self.cmb_cow['values']:
            self.cmb_cow.set(display)

    def _add_cow(self):
        self._show_cow_dialog(None)

    def _edit_cow(self):
        sel = self.cow_tree.selection()
        if not sel:
            messagebox.showwarning("Atención", "Seleccione una vaca para editar")
            return
        item = self.cow_tree.item(sel[0])
        cow_id = item['values'][0]
        cow = self.db.get_cow(cow_id)
        if cow:
            self._show_cow_dialog(cow)

    def _delete_cow(self):
        sel = self.cow_tree.selection()
        if not sel:
            messagebox.showwarning("Atención", "Seleccione una vaca para eliminar")
            return
        item = self.cow_tree.item(sel[0])
        cow_id, tag = item['values'][0], item['values'][1]
        if not messagebox.askyesno("Confirmar", f"Eliminar la vaca {tag}? (se marcará inactiva)"):
            return
        try:
            self.db.delete_cow(cow_id)
            messagebox.showinfo("Éxito", "Vaca marcada como inactiva")
            self.refresh_all()
        except DatabaseException as e:
            messagebox.showerror("Error", str(e))

    def _show_cow_dialog(self, cow: Optional[sqlite3.Row]):
        dlg = tk.Toplevel(self)
        dlg.title("Nueva Vaca" if cow is None else "Editar Vaca")
        dlg.geometry("480x380")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.transient(self)

        form = ttk.Frame(dlg, padding=14)
        form.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form, text="TAG (Identificador):").grid(row=0, column=0, sticky=tk.W, pady=8)
        e_tag = ttk.Entry(form, width=35)
        e_tag.grid(row=0, column=1, pady=8, padx=6)

        ttk.Label(form, text="Nombre:").grid(row=1, column=0, sticky=tk.W, pady=8)
        e_name = ttk.Entry(form, width=35)
        e_name.grid(row=1, column=1, pady=8, padx=6)

        ttk.Label(form, text="Raza:").grid(row=2, column=0, sticky=tk.W, pady=8)
        e_breed = ttk.Entry(form, width=35)
        e_breed.grid(row=2, column=1, pady=8, padx=6)

        ttk.Label(form, text="Fecha Nacimiento (YYYY-MM-DD):").grid(row=3, column=0, sticky=tk.W, pady=8)
        e_dob = ttk.Entry(form, width=35)
        e_dob.grid(row=3, column=1, pady=8, padx=6)

        ttk.Label(form, text="Notas:").grid(row=4, column=0, sticky=tk.W, pady=8)
        e_notes = tk.Text(form, width=30, height=4)
        e_notes.grid(row=4, column=1, pady=8, padx=6)

        if cow:
            e_tag.insert(0, cow["tag"])
            e_name.insert(0, cow["name"] or "")
            e_breed.insert(0, cow["breed"] or "")
            e_dob.insert(0, cow["dob"] or "")
            e_notes.insert(1.0, cow["notes"] or "")

        def on_save():
            cow_obj = Cow(
                id=cow["id"] if cow else None,
                tag=e_tag.get().strip(),
                name=e_name.get().strip(),
                breed=e_breed.get().strip() or None,
                dob=e_dob.get().strip() or None,
                notes=e_notes.get(1.0, tk.END).strip() or None
            )
            try:
                if cow:
                    self.db.update_cow(cow_obj)
                    messagebox.showinfo("Éxito", "Vaca actualizada correctamente")
                else:
                    self.db.add_cow(cow_obj)
                    messagebox.showinfo("Éxito", "Vaca agregada correctamente")
                dlg.destroy()
                self.refresh_all()
            except DatabaseException as e:
                messagebox.showerror("Error", str(e))

        btn_frame = ttk.Frame(form)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=12)
        ttk.Button(btn_frame, text="💾 Guardar", command=on_save, style='Success.TButton').pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="❌ Cancelar", command=dlg.destroy).pack(side=tk.LEFT, padx=6)

    # ------------------------------------------------------------------
    # REGISTROS DE LECHE
    # ------------------------------------------------------------------
    def _save_milk_record(self):
        cow_text = self.cmb_cow.get().strip()
        if not cow_text:
            messagebox.showwarning("Atención", "Seleccione una vaca")
            return

        cows = self.db.get_all_cows()
        cow_obj = None
        for c in cows:
            if f'{c["tag"]} - {c["name"]}' == cow_text:
                cow_obj = c
                break
        if not cow_obj:
            messagebox.showerror("Error", "Vaca no encontrada")
            return

        try:
            litros = float(self.entry_litros.get().strip())
        except Exception:
            messagebox.showerror("Error", "Litros debe ser un número válido")
            return

        record = MilkRecord(
            id=None,
            cow_id=cow_obj["id"],
            fecha=self.entry_fecha.get().strip(),
            litros=litros,
            calidad=self.cmb_calidad.get() or None,
            observaciones=self.entry_obs.get().strip() or None
        )
        try:
            self.db.add_milk_record(record)
            messagebox.showinfo("Éxito", f"Registro guardado: {litros}L - {cow_obj['tag']}")
            self._clear_form()
            self.refresh_records()
        except DatabaseException as e:
            messagebox.showerror("Error", str(e))

    def _clear_form(self):
        self.entry_litros.delete(0, tk.END)
        self.entry_obs.delete(0, tk.END)
        self.entry_fecha.delete(0, tk.END)
        self.entry_fecha.insert(0, date.today().isoformat())
        self.cmb_calidad.set(QualityLevel.BUENA.value)

    def _edit_milk_record(self):
        sel = self.rec_tree.selection()
        if not sel:
            messagebox.showwarning("Atención", "Seleccione un registro para editar")
            return
        item = self.rec_tree.item(sel[0])
        rec_id = item['values'][0]

        cur = self.db.conn.cursor()
        cur.execute("SELECT * FROM milk_records WHERE id=?", (rec_id,))
        rec = cur.fetchone()
        if not rec:
            messagebox.showerror("Error", "Registro no encontrado")
            return

        dlg = tk.Toplevel(self)
        dlg.title("Editar Registro de Producción")
        dlg.geometry("500x320")
        dlg.resizable(False, False)
        dlg.grab_set()

        form = ttk.Frame(dlg, padding=14)
        form.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form, text="Fecha (YYYY-MM-DD):").grid(row=0, column=0, sticky=tk.W, pady=8)
        e_fecha = ttk.Entry(form, width=20)
        e_fecha.grid(row=0, column=1, pady=8, padx=10)
        e_fecha.insert(0, rec["fecha"])

        ttk.Label(form, text="Litros:").grid(row=1, column=0, sticky=tk.W, pady=8)
        e_litros = ttk.Entry(form, width=20)
        e_litros.grid(row=1, column=1, pady=8, padx=10)
        e_litros.insert(0, str(rec["litros"]))

        ttk.Label(form, text="Calidad:").grid(row=2, column=0, sticky=tk.W, pady=8)
        e_calidad = ttk.Combobox(form, state="readonly", width=18, values=[q.value for q in QualityLevel])
        e_calidad.grid(row=2, column=1, pady=8, padx=10)
        e_calidad.set(rec["calidad"] or QualityLevel.BUENA.value)

        ttk.Label(form, text="Observaciones:").grid(row=3, column=0, sticky=tk.W, pady=8)
        e_obs = tk.Text(form, width=30, height=4)
        e_obs.grid(row=3, column=1, pady=8, padx=10)
        e_obs.insert(1.0, rec["observaciones"] or "")

        def on_update():
            try:
                litros = float(e_litros.get().strip())
            except Exception:
                messagebox.showerror("Error", "Litros inválidos")
                return
            record = MilkRecord(
                id=rec_id,
                cow_id=rec["cow_id"],
                fecha=e_fecha.get().strip(),
                litros=litros,
                calidad=e_calidad.get() or None,
                observaciones=e_obs.get(1.0, tk.END).strip() or None
            )
            try:
                self.db.update_milk_record(record)
                messagebox.showinfo("Éxito", "Registro actualizado")
                dlg.destroy()
                self.refresh_records()
            except DatabaseException as e:
                messagebox.showerror("Error", str(e))

        btn_frame = ttk.Frame(form)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=12)
        ttk.Button(btn_frame, text="💾 Actualizar", command=on_update, style='Success.TButton').pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="❌ Cancelar", command=dlg.destroy).pack(side=tk.LEFT, padx=6)

    def _delete_milk_record(self):
        sel = self.rec_tree.selection()
        if not sel:
            messagebox.showwarning("Atención", "Seleccione un registro para eliminar")
            return
        item = self.rec_tree.item(sel[0])
        rec_id = item['values'][0]
        if not messagebox.askyesno("Confirmar", "¿Eliminar este registro de producción?"):
            return
        try:
            self.db.delete_milk_record(rec_id)
            messagebox.showinfo("Éxito", "Registro eliminado")
            self.refresh_records()
        except DatabaseException as e:
            messagebox.showerror("Error", str(e))

    def _apply_filters(self):
        self.refresh_records()

    def _clear_filters(self):
        self.cmb_filter_cow.set("")
        self.from_entry.delete(0, tk.END)
        self.to_entry.delete(0, tk.END)
        self.refresh_records()

    # ------------------------------------------------------------------
    # GRÁFICOS
    # ------------------------------------------------------------------
    def _generate_chart(self):
        cow_text = self.cmb_chart_cow.get().strip()
        if not cow_text:
            messagebox.showwarning("Atención", "Seleccione una vaca")
            return

        cows = self.db.get_all_cows()
        cow_obj = None
        for c in cows:
            if f'{c["id"]}: {c["tag"]} - {c["name"]}' == cow_text:
                cow_obj = c
                break
        if not cow_obj:
            messagebox.showerror("Error", "Vaca no encontrada")
            return

        days = int(self.period_var.get())
        fecha_from = (date.today() - timedelta(days=days)).isoformat()
        records = self.db.get_milk_records(cow_id=cow_obj["id"], fecha_from=fecha_from)
        if not records:
            messagebox.showinfo("Sin Datos", f"No hay registros para {cow_obj['tag']} en los últimos {days} días")
            return

        # ordenar por fecha
        fechas = [datetime.strptime(r["fecha"], AppConfig.DATE_FORMAT).date() for r in records]
        litros = [r["litros"] for r in records]
        pairs = sorted(zip(fechas, litros), key=lambda x: x[0])
        fechas_ord = [p[0] for p in pairs]
        litros_ord = [p[1] for p in pairs]

        # limpiar frame
        for widget in self.chart_frame.winfo_children():
            widget.destroy()

        fig, ax = plt.subplots(figsize=(10, 4.5))
        ax.plot(fechas_ord, litros_ord, marker='o', linestyle='-', linewidth=2, markersize=6, label='Producción')
        if len(litros_ord) > 0:
            avg = np.mean(litros_ord)
            ax.axhline(y=avg, linestyle='--', linewidth=1.5, label=f'Promedio: {avg:.2f}L')

        ax.set_title(f'Producción Láctea - {cow_obj["tag"]} ({cow_obj["name"]})', fontsize=12, fontweight='bold')
        ax.set_xlabel('Fecha')
        ax.set_ylabel('Litros')
        ax.grid(True, alpha=0.3)
        ax.legend()
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        fig.autofmt_xdate()
        plt.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        stats = self.db.get_production_stats(cow_obj["id"], days)
        stats_text = (
            f"Período: {days} días | Registros: {stats.get('total_records', 0)} | "
            f"Total: {stats.get('total_liters', 0)}L | Promedio: {stats.get('avg_liters', 0)}L | "
            f"Máximo: {stats.get('max_liters', 0)}L | Mínimo: {stats.get('min_liters', 0)}L"
        )
        self.chart_stats_label.config(text=stats_text)

    # ------------------------------------------------------------------
    # EXPORTAR / REPORTES
    # ------------------------------------------------------------------
    def _export_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Todos", "*.*")],
            initialfile=f"produccion_{date.today().isoformat()}.csv"
        )
        if not path:
            return

        cow_id = self._get_filtered_cow_id()
        fecha_from = self.from_entry.get().strip() or None
        fecha_to = self.to_entry.get().strip() or None
        records = self.db.get_milk_records(cow_id=cow_id, fecha_from=fecha_from, fecha_to=fecha_to)

        try:
            with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(["ID", "Fecha", "TAG", "Nombre", "Litros", "Calidad", "Observaciones"])
                for r in records:
                    writer.writerow([
                        r["id"],
                        r["fecha"],
                        r["tag"],
                        r["name"],
                        f'{r["litros"]:.2f}',
                        r["calidad"] or "",
                        r["observaciones"] or ""
                    ])
            # registrar report
            cur = self.db.conn.cursor()
            cur.execute("INSERT INTO reports(name, path) VALUES(?,?)", (os.path.basename(path), path))
            self.db.conn.commit()
            messagebox.showinfo("Éxito", f"Exportados {len(records)} registros a:\n{path}")
            logger.info("CSV exportado: %s", path)
        except Exception:
            logger.exception("Error exportando CSV")
            messagebox.showerror("Error", "Error al exportar CSV")

    def _get_filtered_cow_id(self) -> Optional[int]:
        cow_sel = self.cmb_filter_cow.get()
        if not cow_sel or cow_sel == "--Todos--":
            return None
        try:
            return int(cow_sel.split(":")[0])
        except Exception:
            return None

    # ------------------------------------------------------------------
    # REFRESCOS
    # ------------------------------------------------------------------
    def refresh_all(self):
        self.refresh_cows()
        self.refresh_records()

    def refresh_cows(self):
        for i in self.cow_tree.get_children():
            self.cow_tree.delete(i)
        cows = self.db.get_all_cows()
        for c in cows:
            self.cow_tree.insert("", tk.END, values=(c["id"], c["tag"], c["name"], c["breed"] or "", c["dob"] or ""))

        cow_displays = [f'{c["tag"]} - {c["name"]}' for c in cows]
        self.cmb_cow['values'] = cow_displays
        if cow_displays:
            self.cmb_cow.current(0)

        filter_displays = ["--Todos--"] + [f'{c["id"]}: {c["tag"]} - {c["name"]}' for c in cows]
        self.cmb_filter_cow['values'] = filter_displays
        self.cmb_filter_cow.set("--Todos--")

        chart_displays = [f'{c["id"]}: {c["tag"]} - {c["name"]}' for c in cows]
        self.cmb_chart_cow['values'] = chart_displays

        logger.debug("Vacas refrescadas")

    def refresh_records(self):
        # limpiar vistas
        for i in self.rec_tree.get_children(): self.rec_tree.delete(i)
        for i in self.preview_tree.get_children(): self.preview_tree.delete(i)

        cow_id = self._get_filtered_cow_id()
        fecha_from = self.from_entry.get().strip() or None
        fecha_to = self.to_entry.get().strip() or None

        # paginación: contar total y calcular offset
        total = self.db.count_milk_records(cow_id, fecha_from, fecha_to)
        offset = self._rec_page * self.PAGE_SIZE
        if offset >= total and total > 0:
            # si me fui fuera de rango por filtros nuevos, regresar a la última página válida
            self._rec_page = max((total - 1) // self.PAGE_SIZE, 0)
            offset = self._rec_page * self.PAGE_SIZE

        records = self.db.get_milk_records(
            cow_id=cow_id,
            fecha_from=fecha_from,
            fecha_to=fecha_to,
            limit=self.PAGE_SIZE,
            offset=offset
        )

        total_litros = 0.0
        for r in records:
            self.rec_tree.insert("", tk.END, values=(
                r["id"], r["fecha"], r["tag"], r["name"],
                f'{r["litros"]:.2f}', r["calidad"] or "", r["observaciones"] or ""
            ))
            total_litros += r["litros"]

        # preview: solo los primeros de esta página
        for r in records[:10]:
            self.preview_tree.insert("", tk.END, values=(
                r["id"], r["fecha"], r["tag"], r["name"],
                f'{r["litros"]:.2f}', r["calidad"] or ""
            ))

        if total > 0:
            avg_litros = total_litros / len(records) if records else 0
            stats_text = (f"Total registros: {total} | "
                        f"Mostrando {len(records)} | "
                        f"Promedio (página): {avg_litros:.2f} L/día")
        else:
            stats_text = "No hay registros con los filtros seleccionados"

        self.stats_label.config(text=stats_text)
        # actualizar etiqueta de página
        if total == 0:
            self.lbl_page.config(text="Página 0 de 0")
        else:
            total_pages = (total - 1) // self.PAGE_SIZE + 1
            self.lbl_page.config(text=f"Página {self._rec_page + 1} de {total_pages}")

        logger.debug("Registros refrescados")


    # ------------------------------------------------------------------
    # MENÚS / UTILIDADES
    # ------------------------------------------------------------------
    def _create_backup(self):
        try:
            backup_file = self.db.backup()
            messagebox.showinfo("Backup Exitoso", f"Backup creado:\n{backup_file}")
        except DatabaseException as e:
            messagebox.showerror("Error", str(e))

    def _restore_backup(self):
        path = filedialog.askopenfilename(
            title="Seleccionar backup",
            filetypes=[("Base de datos", "*.db"), ("Todos los archivos", "*.*")]
        )
        if not path:
            return
        if not messagebox.askyesno(
            "Confirmar restauración",
            "Esto reemplazará la base de datos actual. ¿Quieres continuar?"
        ):
            return
        try:
            self.db.restore(path)
            messagebox.showinfo(
                "Restaurado",
                "La base de datos fue restaurada correctamente.\nCierra y vuelve a abrir la aplicación."
            )
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo restaurar: {e}")


    def _show_general_stats(self):
        cows = self.db.get_all_cows()
        all_records = self.db.get_milk_records()
        total_cows = len(cows)
        total_records = len(all_records)

        if total_records > 0:
            total_production = sum(r["litros"] for r in all_records)
            avg_production = total_production / total_records

            cow_production: Dict[int, Dict[str, Any]] = {}
            for r in all_records:
                cid = r["cow_id"]
                cow_production.setdefault(cid, {"litros": 0, "count": 0, "tag": r["tag"], "name": r["name"]})
                cow_production[cid]["litros"] += r["litros"]
                cow_production[cid]["count"] += 1
            top_cows = sorted(cow_production.items(), key=lambda x: x[1]["litros"], reverse=True)[:3]
            top_text = "\n".join([
                f"  {i+1}. {c[1]['tag']} - {c[1]['name']}: {c[1]['litros']:.2f}L ({c[1]['count']} registros)"
                for i, c in enumerate(top_cows)
            ])
        else:
            total_production = 0
            avg_production = 0
            top_text = "  No hay datos suficientes"

        dlg = tk.Toplevel(self)
        dlg.title("Estadísticas Generales")
        dlg.geometry("640x520")
        dlg.resizable(False, False)
        dlg.grab_set()

        frame = ttk.Frame(dlg, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="📊 Estadísticas del Sistema", font=('Arial', 14, 'bold')).pack(pady=8)
        stats_text = f"""
🐄 INVENTARIO BOVINO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total de vacas activas: {total_cows}

📝 PRODUCCIÓN LÁCTEA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total de registros: {total_records}
Producción total acumulada: {total_production:.2f} litros
Promedio por registro: {avg_production:.2f} litros

🏆 TOP 3 VACAS PRODUCTORAS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{top_text}

💾 SISTEMA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Versión: {AppConfig.VERSION}
Base de datos: {AppConfig.DB_FILE}
Log de auditoría: Activo
"""
        text_widget = tk.Text(
            frame,
            width=80,
            height=22,
            wrap=tk.WORD,
            font=('Courier', 10),
            bg='#F8F9FA',
            relief=tk.FLAT
        )
        text_widget.insert(1.0, stats_text)
        text_widget.config(state=tk.DISABLED)
        text_widget.pack(pady=6, padx=6, fill=tk.BOTH, expand=True)

        ttk.Button(frame, text="Cerrar", command=dlg.destroy).pack(pady=6)

    def _show_about(self):
        messagebox.showinfo(
            "Acerca de",
            f"Sistema de Gestión Ganadera\nVersión {AppConfig.VERSION}\n© 2025 - Sistema Ganadero"
        )

    def _seed_demo_data(self):
        cows = self.db.get_all_cows()
        if cows:
            # si no hay usuarios, crear admin por defecto
            users = self.db.list_users()
            if not users:
                try:
                    self.db.add_user("admin", "admin123", role="admin")
                    logger.info("Usuario admin creado (admin/admin123) — cambiar la contraseña por seguridad")
                except Exception:
                    pass
            return
        try:
            logger.info("Creando datos demo...")
            c1 = Cow(None, "TAG001", "Luna", "Holstein", "2019-04-20", "Alta producción")
            c2 = Cow(None, "TAG002", "Estrella", "Jersey", "2018-11-05", "Leche de alta calidad")
            c3 = Cow(None, "TAG003", "Sol", "Brown Swiss", "2020-01-10", "Producción constante")
            c4 = Cow(None, "TAG004", "Mariposa", "Holstein", "2019-08-15", None)

            id1 = self.db.add_cow(c1)
            id2 = self.db.add_cow(c2)
            id3 = self.db.add_cow(c3)
            id4 = self.db.add_cow(c4)

            base_date = date.today() - timedelta(days=30)
            for i in range(30):
                d = (base_date + timedelta(days=i)).isoformat()
                self.db.add_milk_record(MilkRecord(
                    None, id1, d, 14.0 + (i % 5) * 0.5,
                    QualityLevel.BUENA.value if i % 3 != 0 else QualityLevel.EXCELENTE.value,
                    None
                ))
                if i % 2 == 0:
                    self.db.add_milk_record(MilkRecord(
                        None, id2, d, 9.5 + (i % 4) * 0.3,
                        QualityLevel.EXCELENTE.value,
                        None
                    ))
                self.db.add_milk_record(MilkRecord(
                    None, id3, d, 11.0 + (i % 3) * 0.2,
                    QualityLevel.BUENA.value,
                    None
                ))
                if i % 3 == 0:
                    self.db.add_milk_record(MilkRecord(
                        None, id4, d, 13.0 + (i % 6) * 0.4,
                        QualityLevel.MEDIA.value if i % 4 == 0 else QualityLevel.BUENA.value,
                        "Revisión veterinaria" if i % 10 == 0 else None
                    ))
            # crear admin por defecto si no existe
            try:
                self.db.add_user("admin", "admin123", role="admin")
                logger.info("Usuario admin creado (admin/admin123)")
            except Exception:
                pass
            logger.info("Datos demo creados")
        except Exception:
            logger.exception("Error creando datos demo")

    def _on_closing(self):
        # intentar backup automático al salir
        try:
            self.db.backup()
        except Exception:
            # no rompemos el cierre si falla el backup
            pass

        self.db.close()
        self.quit()

    def _open_user_manager(self):
        UserManagerDialog(self, self.db)
