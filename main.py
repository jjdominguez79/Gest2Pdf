import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import fitz  # PyMuPDF
from PIL import Image, ImageTk
from pypdf import PdfReader, PdfWriter


THUMB_WIDTH = 160
RENDER_ZOOM = 1.2
ITEM_PAD = 8
SPLIT_THUMB_WIDTH = 140
SPLIT_RENDER_ZOOM = 0.8
BG_COLOR = "#f4f6f8"
CARD_COLOR = "#ffffff"
ACCENT_COLOR = "#1e5b7a"
ACCENT_DARK = "#17465e"
TEXT_MUTED = "#5c6773"
CARD_BORDER = "#e2e7ee"


class PdfPageComposer(tk.Tk):
    """
    Composer de páginas PDF:
    - Añade varios PDFs
    - Muestra miniaturas
    - Reordena con drag & drop
    - Exporta PDF final
    """

    def __init__(self):
        super().__init__()
        self.title("Gest2PDF — Componer, unir y dividir")
        self.geometry("1150x780")
        self.configure(bg=BG_COLOR)
        self._setup_theme()
        self._build_menu()

        # docs: lista de dicts {path, reader, doc_fitz, page_count, name}
        self.docs = []

        # pages: lista de tuplas (doc_idx, page_idx) en el ORDEN ACTUAL
        self.pages = []

        # caches
        self.thumb_cache = {}   # (doc_idx, page_idx) -> PhotoImage
        self.item_widgets = []  # widgets por item (frame, img_label, text_label)

        # selección y drag-drop
        self.selected = set()   # set de índices en self.pages (posición en la lista)
        self.drag_from = None   # índice origen
        self.drag_hover = None  # índice destino (hover)
        self._build_ui()

    def _setup_theme(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("TFrame", background=BG_COLOR)
        style.configure("Card.TFrame", background=CARD_COLOR)
        style.configure("Header.TFrame", background=BG_COLOR)
        style.configure("Title.TLabel", background=BG_COLOR, foreground=ACCENT_COLOR, font=("Segoe UI Semibold", 17))
        style.configure("Subtitle.TLabel", background=BG_COLOR, foreground=TEXT_MUTED, font=("Segoe UI", 10))
        style.configure("TLabel", background=BG_COLOR, foreground="#1b1f24", font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=BG_COLOR, foreground=TEXT_MUTED, font=("Segoe UI", 9))
        style.configure("Card.TLabel", background=CARD_COLOR, foreground="#1b1f24", font=("Segoe UI", 10))
        style.configure("Item.TFrame", background=CARD_COLOR, relief="solid", borderwidth=1)
        style.configure("Item.TLabel", background=CARD_COLOR, foreground="#1b1f24", font=("Segoe UI", 10))
        style.configure("Selected.TFrame", background="#e7f0f5", relief="solid", borderwidth=2)
        style.configure("Hover.TFrame", background="#f1f4f7", relief="solid", borderwidth=2)
        style.configure("SplitItem.TFrame", background=CARD_COLOR, relief="solid", borderwidth=1)
        style.configure("SplitItem.TLabel", background=CARD_COLOR, foreground="#1b1f24", font=("Segoe UI", 9))
        style.configure("SplitCut.TFrame", background="#e7f0f5", relief="solid", borderwidth=2)
        style.configure("SplitCut.TLabel", background="#e7f0f5", foreground=ACCENT_DARK, font=("Segoe UI", 9, "bold"))
        style.configure(
            "Accent.TButton",
            background=ACCENT_COLOR,
            foreground="white",
            borderwidth=0,
            focusthickness=1,
            focuscolor=ACCENT_DARK,
            padding=(12, 6),
            font=("Segoe UI Semibold", 10),
        )
        style.map(
            "Accent.TButton",
            background=[("active", ACCENT_DARK)],
            foreground=[("active", "white")],
        )

    def _build_menu(self):
        menubar = tk.Menu(self)

        archivo = tk.Menu(menubar, tearoff=0)
        archivo.add_command(label="Añadir PDFs...", command=self.add_pdfs)
        archivo.add_command(label="Exportar PDF...", command=self.export_pdf)
        archivo.add_command(label="Limpiar proyecto", command=self.clear_project)
        archivo.add_separator()
        archivo.add_command(label="Salir", command=self.destroy)
        menubar.add_cascade(label="Archivo", menu=archivo)

        util = tk.Menu(menubar, tearoff=0)
        util.add_command(label="Unir PDFs (rápido)...", command=self.merge_pdfs_quick)
        util.add_command(label="Dividir PDF...", command=self.split_pdf)
        util.add_command(label="Comprimir PDF...", command=self.compress_pdf)
        menubar.add_cascade(label="Utilidades", menu=util)

        self.config(menu=menubar)

    # ---------------- UI ----------------
    def _build_ui(self):
        top = ttk.Frame(self, padding=12, style="Header.TFrame")
        top.pack(side=tk.TOP, fill=tk.X)

        title_block = ttk.Frame(top, style="Header.TFrame")
        title_block.pack(side=tk.LEFT, padx=(2, 14))
        ttk.Label(title_block, text="Gest2PDF", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            title_block,
            text="Unir, reordenar y dividir PDFs con vista previa",
            style="Subtitle.TLabel"
        ).pack(anchor="w", pady=(2, 0))

        ttk.Separator(self, orient=tk.HORIZONTAL).pack(side=tk.TOP, fill=tk.X, padx=12)

        toolbar = ttk.Frame(self, padding=(12, 8), style="Header.TFrame")
        toolbar.pack(side=tk.TOP, fill=tk.X)

        main_section = ttk.Frame(toolbar, style="Header.TFrame")
        main_section.pack(side=tk.LEFT, padx=(0, 24))
        ttk.Label(main_section, text="Documento", style="Muted.TLabel").pack(anchor="w")
        main_buttons = ttk.Frame(main_section, style="Header.TFrame")
        main_buttons.pack(anchor="w", pady=(4, 0))
        ttk.Button(main_buttons, text="Añadir PDFs...", command=self.add_pdfs).pack(side=tk.LEFT, padx=4)
        ttk.Button(main_buttons, text="Exportar PDF...", command=self.export_pdf, style="Accent.TButton").pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(main_buttons, text="Limpiar proyecto", command=self.clear_project).pack(side=tk.LEFT, padx=4)

        util_section = ttk.Frame(toolbar, style="Header.TFrame")
        util_section.pack(side=tk.LEFT)
        ttk.Label(util_section, text="Utilidades", style="Muted.TLabel").pack(anchor="w")
        util_buttons = ttk.Frame(util_section, style="Header.TFrame")
        util_buttons.pack(anchor="w", pady=(4, 0))
        ttk.Button(util_buttons, text="Unir PDFs (rápido)...", command=self.merge_pdfs_quick).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(util_buttons, text="Dividir PDF...", command=self.split_pdf).pack(side=tk.LEFT, padx=4)
        ttk.Button(util_buttons, text="Comprimir PDF...", command=self.compress_pdf).pack(side=tk.LEFT, padx=4)

        action_bar = ttk.Frame(self, padding=(12, 8), style="Header.TFrame")
        action_bar.pack(side=tk.TOP, fill=tk.X)
        ttk.Button(action_bar, text="Seleccionar todo", command=self.select_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_bar, text="Limpiar selección", command=self.clear_selection).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_bar, text="Eliminar seleccionadas", command=self.delete_selected).pack(side=tk.LEFT, padx=5)

        self.info_var = tk.StringVar(value="Añade uno o varios PDFs para empezar.")
        ttk.Label(self, textvariable=self.info_var, padding=(12, 4), style="Muted.TLabel").pack(
            side=tk.TOP, fill=tk.X
        )

        # Paned: lista miniaturas + ayuda
        main = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        left = ttk.Frame(main, style="Card.TFrame")
        main.add(left, weight=4)

        right = ttk.Frame(main, padding=12, style="Card.TFrame")
        main.add(right, weight=1)

        ttk.Label(right, text="Guía rápida", style="Card.TLabel", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(
            right,
            text=(
                "• Clic para seleccionar páginas\n"
                "• Shift + clic: rango\n"
                "• Ctrl + clic: multi-selección\n\n"
                "Reordenar:\n"
                "• Arrastra una página y suéltala\n"
                "  donde quieres colocarla.\n\n"
                "Exportar:\n"
                "• 'Exportar PDF...' genera el\n"
                "  PDF unido con el orden actual.\n\n"
                "Dividir:\n"
                "• 'Dividir PDF...' crea PDFs\n"
                "  por página o por rangos."
            ),
            justify=tk.LEFT,
            style="Card.TLabel"
        ).pack(anchor="w", pady=(6, 10))

        ttk.Label(right, text="Tip", style="Card.TLabel", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", pady=(10, 0)
        )
        ttk.Label(
            right,
            text="Si el PDF tiene cientos de páginas,\nsube THUMB_WIDTH o baja RENDER_ZOOM\npara ir más fluido.",
            justify=tk.LEFT,
            style="Card.TLabel"
        ).pack(anchor="w", pady=(6, 0))

        # Canvas scroll vertical
        self.canvas = tk.Canvas(left, highlightthickness=0, bg=CARD_COLOR)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        vsb = ttk.Scrollbar(left, orient="vertical", command=self.canvas.yview)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.configure(yscrollcommand=vsb.set)

        self.list_container = ttk.Frame(self.canvas, style="Card.TFrame")
        self.canvas_window = self.canvas.create_window((0, 0), window=self.list_container, anchor="nw")

        self.list_container.bind("<Configure>", self._on_container_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Rueda
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel_linux)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel_linux)

        self.status_var = tk.StringVar(value="Listo.")
        ttk.Label(self, textvariable=self.status_var, padding=10, style="Muted.TLabel").pack(
            side=tk.BOTTOM, fill=tk.X
        )

    def _on_container_configure(self, _evt=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        delta = int(-1 * (event.delta / 120))
        self.canvas.yview_scroll(delta, "units")

    def _on_mousewheel_linux(self, event):
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")

    # ---------------- Data ----------------
    def add_pdfs(self):
        paths = filedialog.askopenfilenames(
            title="Selecciona uno o varios PDFs",
            filetypes=[("PDF", "*.pdf")],
        )
        if not paths:
            return

        added_pages = 0
        for path in paths:
            try:
                reader = PdfReader(path)
                doc_fitz = fitz.open(path)
                page_count = doc_fitz.page_count
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo abrir:\n{path}\n\n{e}")
                continue

            doc_idx = len(self.docs)
            self.docs.append({
                "path": path,
                "name": os.path.basename(path),
                "reader": reader,
                "doc_fitz": doc_fitz,
                "page_count": page_count
            })

            for p in range(page_count):
                self.pages.append((doc_idx, p))
                added_pages += 1

        self.info_var.set(
            f"Documentos: {len(self.docs)} | Páginas totales: {len(self.pages)}"
        )
        self.status_var.set(f"Añadidas {added_pages} páginas. Renderizando miniaturas...")
        self.selected.clear()
        self._rebuild_list()
        self.status_var.set("Listo. Arrastra para reordenar.")

    def clear_project(self):
        # Cerrar docs fitz
        for d in self.docs:
            try:
                d["doc_fitz"].close()
            except Exception:
                pass
        self.docs.clear()
        self.pages.clear()
        self.thumb_cache.clear()
        self.selected.clear()
        self._clear_list_widgets()

        self.info_var.set("Añade uno o varios PDFs para empezar.")
        self.status_var.set("Proyecto limpio.")

    # ---------------- Rendering ----------------
    def _clear_list_widgets(self):
        for w in self.list_container.winfo_children():
            w.destroy()
        self.item_widgets = []

    def _rebuild_list(self):
        self._clear_list_widgets()
        self.item_widgets = [None] * len(self.pages)

        # Render item por item
        for idx in range(len(self.pages)):
            self._create_item(idx)

        self._refresh_styles()

    def _create_item(self, list_index: int):
        (doc_idx, page_idx) = self.pages[list_index]
        doc_name = self.docs[doc_idx]["name"]
        page_label = f"{doc_name} — pág. {page_idx + 1}"

        frame = ttk.Frame(self.list_container, padding=ITEM_PAD, style="Item.TFrame")
        frame.pack(side=tk.TOP, fill=tk.X, padx=8, pady=4)

        inner = ttk.Frame(frame, style="Item.TFrame")
        inner.pack(side=tk.TOP, fill=tk.X)

        img_label = ttk.Label(inner)
        img_label.pack(side=tk.LEFT)

        text = ttk.Label(inner, text=page_label, style="Item.TLabel")
        text.pack(side=tk.LEFT, padx=12)

        # Render miniatura
        photo = self._get_thumbnail(doc_idx, page_idx)
        img_label.configure(image=photo)

        # Eventos de selección y drag-drop
        for w in (frame, inner, img_label, text):
            w.bind("<Button-1>", lambda e, i=list_index: self.on_click_item(e, i))
            w.bind("<B1-Motion>", lambda e, i=list_index: self.on_drag_motion(e, i))
            w.bind("<ButtonRelease-1>", lambda e, i=list_index: self.on_drop(e, i))

        self.item_widgets[list_index] = (frame, img_label, text)

    def _get_thumbnail(self, doc_idx: int, page_idx: int) -> ImageTk.PhotoImage:
        key = (doc_idx, page_idx)
        if key in self.thumb_cache:
            return self.thumb_cache[key]

        doc_fitz = self.docs[doc_idx]["doc_fitz"]
        page = doc_fitz.load_page(page_idx)
        mat = fitz.Matrix(RENDER_ZOOM, RENDER_ZOOM)
        pix = page.get_pixmap(matrix=mat, alpha=False)

        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

        ratio = THUMB_WIDTH / img.width
        new_size = (THUMB_WIDTH, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

        photo = ImageTk.PhotoImage(img)
        self.thumb_cache[key] = photo
        return photo

    def _render_preview_thumbnail(self, doc_fitz, page_idx: int) -> ImageTk.PhotoImage:
        page = doc_fitz.load_page(page_idx)
        mat = fitz.Matrix(SPLIT_RENDER_ZOOM, SPLIT_RENDER_ZOOM)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

        ratio = SPLIT_THUMB_WIDTH / img.width
        new_size = (SPLIT_THUMB_WIDTH, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

        return ImageTk.PhotoImage(img)

    # ---------------- Selection ----------------
    def on_click_item(self, event, index: int):
        if not self.pages:
            return

        # Shift: rango desde el último seleccionado (si existe)
        if (event.state & 0x0001) and self.selected:  # Shift
            last = max(self.selected)
            a, b = sorted((last, index))
            for i in range(a, b + 1):
                self.selected.add(i)

        # Ctrl: toggle
        elif event.state & 0x0004:  # Ctrl
            if index in self.selected:
                self.selected.remove(index)
            else:
                self.selected.add(index)

        # Normal: seleccionar solo ese
        else:
            self.selected = {index}

        # Preparar drag
        self.drag_from = index
        self.drag_hover = None

        self._refresh_styles()
        self._update_status_selection()

    def select_all(self):
        self.selected = set(range(len(self.pages)))
        self._refresh_styles()
        self._update_status_selection()

    def clear_selection(self):
        self.selected.clear()
        self._refresh_styles()
        self._update_status_selection()

    def delete_selected(self):
        if not self.selected:
            messagebox.showwarning("Aviso", "No hay páginas seleccionadas.")
            return
        # borrar de atrás hacia delante para no romper índices
        for i in sorted(self.selected, reverse=True):
            self.pages.pop(i)
        self.selected.clear()
        self._rebuild_list()
        self.info_var.set(f"Documentos: {len(self.docs)} | Páginas totales: {len(self.pages)}")
        self.status_var.set("Páginas eliminadas.")

    def _update_status_selection(self):
        if not self.selected:
            self.status_var.set("Sin selección.")
            return
        s = sorted(self.selected)
        preview = ", ".join(str(i + 1) for i in s[:15])
        if len(s) > 15:
            preview += "..."
        self.status_var.set(f"Seleccionadas {len(s)} (posiciones en lista): {preview}")

    def _refresh_styles(self):
        for i, wtuple in enumerate(self.item_widgets):
            if not wtuple:
                continue
            frame, _, _ = wtuple
            if i == self.drag_hover and self.drag_from is not None and i != self.drag_from:
                frame.configure(style="Hover.TFrame")
            elif i in self.selected:
                frame.configure(style="Selected.TFrame")
            else:
                frame.configure(style="Item.TFrame")

    # ---------------- Drag & Drop reorder ----------------
    def on_drag_motion(self, event, index: int):
        if self.drag_from is None:
            return

        # Detectar “hover” en función de dónde está el ratón
        # Obtener y relativa al contenedor
        y_root = event.y_root
        hover = self._hit_test_index(y_root)
        if hover is not None and hover != self.drag_hover:
            self.drag_hover = hover
            self._refresh_styles()

    def on_drop(self, event, _index: int):
        if self.drag_from is None:
            return

        target = self.drag_hover
        src = self.drag_from
        self.drag_from = None
        self.drag_hover = None

        if target is None or target == src:
            self._refresh_styles()
            return

        # Mover elemento (drag single item)
        item = self.pages.pop(src)

        # Ajuste si al quitar src cambia el índice destino
        if target > src:
            target -= 1

        self.pages.insert(target, item)

        # Ajustar selección: la simplificamos (selección pasa a esa página movida)
        self.selected = {target}

        self._rebuild_list()
        self.status_var.set(f"Reordenado: movida a posición {target + 1}.")

    def _hit_test_index(self, y_root: int):
        # Determina sobre qué item está el ratón (por coordenada Y global)
        for i, wtuple in enumerate(self.item_widgets):
            if not wtuple:
                continue
            frame = wtuple[0]
            y1 = frame.winfo_rooty()
            y2 = y1 + frame.winfo_height()
            if y1 <= y_root <= y2:
                return i
        return None

    # ---------------- Export ----------------
    def export_pdf(self):
        if not self.pages:
            messagebox.showwarning("Aviso", "No hay páginas en el proyecto.")
            return

        out_path = filedialog.asksaveasfilename(
            title="Guardar PDF final",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile="resultado.pdf",
        )
        if not out_path:
            return

        try:
            writer = PdfWriter()

            # Añadir en el orden actual
            for (doc_idx, page_idx) in self.pages:
                reader = self.docs[doc_idx]["reader"]
                writer.add_page(reader.pages[page_idx])

            os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
            with open(out_path, "wb") as f:
                writer.write(f)

        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar:\n{e}")
            return

        messagebox.showinfo("OK", f"PDF exportado:\n{out_path}")

    # ---------------- Quick merge ----------------
    def merge_pdfs_quick(self):
        paths = filedialog.askopenfilenames(
            title="Selecciona PDFs para unir",
            filetypes=[("PDF", "*.pdf")],
        )
        if not paths:
            return

        out_path = filedialog.asksaveasfilename(
            title="Guardar PDF unido",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile="unido.pdf",
        )
        if not out_path:
            return

        try:
            writer = PdfWriter()
            total_pages = 0
            for path in paths:
                reader = PdfReader(path)
                for page in reader.pages:
                    writer.add_page(page)
                    total_pages += 1

            os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
            with open(out_path, "wb") as f:
                writer.write(f)

        except Exception as e:
            messagebox.showerror("Error", f"No se pudo unir:\n{e}")
            return

        messagebox.showinfo("OK", f"PDF unido:\n{out_path}\nPáginas: {total_pages}")

    # ---------------- Compress ----------------
    def compress_pdf(self):
        path = filedialog.askopenfilename(
            title="Selecciona el PDF a comprimir",
            filetypes=[("PDF", "*.pdf")],
        )
        if not path:
            return

        base = os.path.splitext(os.path.basename(path))[0]
        out_path = filedialog.asksaveasfilename(
            title="Guardar PDF comprimido",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=f"{base}_comprimido.pdf",
        )
        if not out_path:
            return

        try:
            before = os.path.getsize(path)
        except Exception:
            before = None

        try:
            doc = fitz.open(path)
            try:
                doc.save(
                    out_path,
                    garbage=4,
                    deflate=True,
                    clean=True,
                    deflate_images=True,
                    deflate_fonts=True,
                )
            except TypeError:
                doc.save(out_path, garbage=4, deflate=True, clean=True)
            doc.close()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo comprimir:\n{e}")
            return

        try:
            after = os.path.getsize(out_path)
        except Exception:
            after = None

        if before and after:
            ratio = 100 - int((after / before) * 100)
            messagebox.showinfo(
                "OK",
                f"PDF comprimido:\n{out_path}\nAntes: {before/1024/1024:.2f} MB\nDespués: {after/1024/1024:.2f} MB\nAhorro: {max(ratio, 0)}%",
            )
        else:
            messagebox.showinfo("OK", f"PDF comprimido:\n{out_path}")

    # ---------------- Split ----------------
    def split_pdf(self):
        path = filedialog.askopenfilename(
            title="Selecciona el PDF a dividir",
            filetypes=[("PDF", "*.pdf")],
        )
        if not path:
            return

        try:
            reader = PdfReader(path)
            total_pages = len(reader.pages)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el PDF:\n{e}")
            return

        self._open_split_dialog(path, total_pages)

    def _open_split_dialog(self, path: str, total_pages: int):
        dialog = tk.Toplevel(self)
        dialog.title("Dividir PDF")
        dialog.geometry("920x520")
        dialog.configure(bg=BG_COLOR)
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        container = ttk.Frame(dialog, padding=16, style="Card.TFrame")
        container.pack(fill=tk.BOTH, expand=True)

        preview_panel = ttk.Frame(container, style="Card.TFrame")
        preview_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 16))

        controls_panel = ttk.Frame(container, style="Card.TFrame")
        controls_panel.pack(side=tk.RIGHT, fill=tk.Y)

        base_name = os.path.splitext(os.path.basename(path))[0]
        default_out = os.path.dirname(path)
        default_prefix = f"{base_name}_split"

        mode_var = tk.StringVar(value="per_page")
        range_var = tk.StringVar(value="1-3, 5, 7-9")
        out_dir_var = tk.StringVar(value=default_out)
        prefix_var = tk.StringVar(value=default_prefix)
        cut_count_var = tk.StringVar(value="Cortes: 0")

        ttk.Label(controls_panel, text="Dividir PDF", style="Card.TLabel", font=("Segoe UI Semibold", 12)).pack(
            anchor="w"
        )
        ttk.Label(controls_panel, text=f"Archivo: {os.path.basename(path)}", style="Card.TLabel").pack(anchor="w")
        ttk.Label(
            controls_panel,
            text=f"Páginas totales: {total_pages}",
            style="Card.TLabel"
        ).pack(anchor="w", pady=(4, 12))

        options = ttk.Frame(controls_panel, style="Card.TFrame")
        options.pack(fill=tk.X)

        ttk.Radiobutton(
            options,
            text="Dividir por cada página (un PDF por página)",
            variable=mode_var,
            value="per_page",
        ).pack(anchor="w")
        ttk.Radiobutton(
            options,
            text="Dividir por rangos personalizados",
            variable=mode_var,
            value="custom",
        ).pack(anchor="w", pady=(6, 4))

        range_row = ttk.Frame(controls_panel, style="Card.TFrame")
        range_row.pack(fill=tk.X, pady=(4, 10))
        ttk.Label(range_row, text="Rangos:", style="Card.TLabel").pack(side=tk.LEFT)
        range_entry = ttk.Entry(range_row, textvariable=range_var)
        range_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))

        ttk.Label(
            controls_panel,
            text="Formato: 1-3,5,7-9 (usa números de página)",
            style="Card.TLabel"
        ).pack(anchor="w", pady=(0, 12))

        ttk.Label(
            controls_panel,
            text="Si marcas cortes en la vista previa, se usarán esos cortes.",
            style="Card.TLabel"
        ).pack(anchor="w", pady=(0, 8))

        cuts_row = ttk.Frame(controls_panel, style="Card.TFrame")
        cuts_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(cuts_row, textvariable=cut_count_var, style="Card.TLabel").pack(side=tk.LEFT)
        ttk.Button(cuts_row, text="Limpiar cortes", command=lambda: clear_cuts()).pack(side=tk.RIGHT)

        out_row = ttk.Frame(controls_panel, style="Card.TFrame")
        out_row.pack(fill=tk.X)
        ttk.Label(out_row, text="Carpeta salida:", style="Card.TLabel").pack(side=tk.LEFT)
        out_entry = ttk.Entry(out_row, textvariable=out_dir_var)
        out_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 6))
        ttk.Button(
            out_row,
            text="Elegir...",
            command=lambda: self._choose_output_dir(out_dir_var),
        ).pack(side=tk.LEFT)

        prefix_row = ttk.Frame(controls_panel, style="Card.TFrame")
        prefix_row.pack(fill=tk.X, pady=(10, 16))
        ttk.Label(prefix_row, text="Prefijo archivo:", style="Card.TLabel").pack(side=tk.LEFT)
        ttk.Entry(prefix_row, textvariable=prefix_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))

        action_row = ttk.Frame(controls_panel, style="Card.TFrame")
        action_row.pack(side=tk.BOTTOM, fill=tk.X)

        # -------- Preview panel --------
        preview_header = ttk.Frame(preview_panel, style="Card.TFrame")
        preview_header.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(preview_header, text="Vista previa (marca donde cortar)", style="Card.TLabel").pack(anchor="w")
        ttk.Label(
            preview_header,
            text="Clic en una página para cortar después de ella.",
            style="Card.TLabel"
        ).pack(anchor="w", pady=(2, 0))

        preview_canvas = tk.Canvas(preview_panel, highlightthickness=0, bg=CARD_COLOR)
        preview_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        preview_scroll = ttk.Scrollbar(preview_panel, orient="vertical", command=preview_canvas.yview)
        preview_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        preview_canvas.configure(yscrollcommand=preview_scroll.set)

        preview_container = ttk.Frame(preview_canvas, style="Card.TFrame")
        preview_window = preview_canvas.create_window((0, 0), window=preview_container, anchor="nw")

        def on_preview_configure(_evt=None):
            preview_canvas.configure(scrollregion=preview_canvas.bbox("all"))

        def on_preview_canvas_configure(event):
            preview_canvas.itemconfigure(preview_window, width=event.width)

        preview_container.bind("<Configure>", on_preview_configure)
        preview_canvas.bind("<Configure>", on_preview_canvas_configure)

        preview_photos = []
        preview_items = []
        cut_after = [False] * total_pages
        doc_fitz = fitz.open(path)

        def update_cut_count():
            cut_count_var.set(f"Cortes: {sum(1 for c in cut_after if c)}")

        def apply_cut_style(index: int):
            item = preview_items[index]
            if cut_after[index]:
                item["frame"].configure(style="SplitCut.TFrame")
                item["badge"].configure(text="Corte", style="SplitCut.TLabel")
                item["badge"].pack(side=tk.RIGHT, padx=6)
            else:
                item["frame"].configure(style="SplitItem.TFrame")
                item["badge"].pack_forget()

        def sync_ranges_from_cuts():
            ranges = self._ranges_from_cuts(cut_after, total_pages)
            range_var.set(self._ranges_to_text(ranges))
            update_cut_count()

        def toggle_cut(index: int):
            if mode_var.get() != "custom":
                return
            cut_after[index] = not cut_after[index]
            apply_cut_style(index)
            sync_ranges_from_cuts()

        def clear_cuts():
            for i in range(total_pages):
                if cut_after[i]:
                    cut_after[i] = False
                    apply_cut_style(i)
            sync_ranges_from_cuts()

        for i in range(total_pages):
            frame = ttk.Frame(preview_container, style="SplitItem.TFrame", padding=6)
            frame.pack(fill=tk.X, padx=6, pady=4)

            inner = ttk.Frame(frame, style="SplitItem.TFrame")
            inner.pack(fill=tk.X)

            thumb = self._render_preview_thumbnail(doc_fitz, i)
            preview_photos.append(thumb)
            img_label = ttk.Label(inner, image=thumb, style="SplitItem.TLabel")
            img_label.pack(side=tk.LEFT)

            text_label = ttk.Label(inner, text=f"Página {i + 1}", style="SplitItem.TLabel")
            text_label.pack(side=tk.LEFT, padx=10)

            badge = ttk.Label(inner, style="SplitCut.TLabel")

            preview_items.append({"frame": frame, "badge": badge})

            for w in (frame, inner, img_label, text_label):
                w.bind("<Button-1>", lambda _e, idx=i: toggle_cut(idx))

        def toggle_range_state(*_):
            if mode_var.get() == "custom":
                range_entry.configure(state="normal")
            else:
                range_entry.configure(state="disabled")

        mode_var.trace_add("write", toggle_range_state)
        toggle_range_state()
        sync_ranges_from_cuts()

        def on_confirm():
            out_dir = out_dir_var.get().strip()
            prefix = prefix_var.get().strip()
            mode = mode_var.get()
            if not out_dir:
                messagebox.showwarning("Aviso", "Selecciona una carpeta de salida.")
                return
            if not prefix:
                messagebox.showwarning("Aviso", "Indica un prefijo de archivo.")
                return

            try:
                os.makedirs(out_dir, exist_ok=True)
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo crear la carpeta:\n{e}")
                return

            try:
                if mode == "per_page":
                    created = self._split_per_page(reader_path=path, out_dir=out_dir, prefix=prefix)
                else:
                    if any(cut_after):
                        ranges = self._ranges_from_cuts(cut_after, total_pages)
                    else:
                        ranges = self._parse_ranges(range_var.get(), total_pages)
                    created = self._split_by_ranges(
                        reader_path=path,
                        out_dir=out_dir,
                        prefix=prefix,
                        ranges=ranges,
                    )
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo dividir:\n{e}")
                return

            on_close()
            messagebox.showinfo("OK", f"PDFs generados: {created}\nCarpeta: {out_dir}")

        def on_close():
            try:
                doc_fitz.close()
            except Exception:
                pass
            dialog.destroy()

        ttk.Button(action_row, text="Cancelar", command=on_close).pack(side=tk.RIGHT, padx=6)
        ttk.Button(action_row, text="Dividir", style="Accent.TButton", command=on_confirm).pack(side=tk.RIGHT)

        dialog.protocol("WM_DELETE_WINDOW", on_close)

    def _choose_output_dir(self, var: tk.StringVar):
        selected = filedialog.askdirectory(title="Selecciona la carpeta de salida")
        if selected:
            var.set(selected)

    def _parse_ranges(self, text: str, max_page: int):
        ranges = []
        if not text.strip():
            raise ValueError("Introduce al menos un rango de páginas.")
        for part in text.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                left, right = part.split("-", 1)
                if not left.strip() or not right.strip():
                    raise ValueError(f"Rango inválido: '{part}'")
                start = int(left)
                end = int(right)
            else:
                start = end = int(part)

            if start < 1 or end < 1 or start > max_page or end > max_page or start > end:
                raise ValueError(f"Rango fuera de límites: '{part}'")

            ranges.append((start, end))

        if not ranges:
            raise ValueError("Introduce al menos un rango válido.")
        return ranges

    def _ranges_from_cuts(self, cut_after, total_pages: int):
        ranges = []
        start = 1
        for idx, cut in enumerate(cut_after, start=1):
            if cut:
                ranges.append((start, idx))
                start = idx + 1
        if start <= total_pages:
            ranges.append((start, total_pages))
        return ranges

    def _ranges_to_text(self, ranges):
        parts = []
        for start, end in ranges:
            if start == end:
                parts.append(str(start))
            else:
                parts.append(f"{start}-{end}")
        return ", ".join(parts)

    def _split_per_page(self, reader_path: str, out_dir: str, prefix: str) -> int:
        reader = PdfReader(reader_path)
        total = len(reader.pages)
        created = 0
        for i in range(total):
            writer = PdfWriter()
            writer.add_page(reader.pages[i])
            out_name = f"{prefix}_p{(i + 1):03}.pdf"
            out_path = os.path.join(out_dir, out_name)
            with open(out_path, "wb") as f:
                writer.write(f)
            created += 1
        return created

    def _split_by_ranges(self, reader_path: str, out_dir: str, prefix: str, ranges) -> int:
        reader = PdfReader(reader_path)
        created = 0
        for start, end in ranges:
            writer = PdfWriter()
            for idx in range(start - 1, end):
                writer.add_page(reader.pages[idx])
            out_name = f"{prefix}_{start:03}-{end:03}.pdf"
            out_path = os.path.join(out_dir, out_name)
            with open(out_path, "wb") as f:
                writer.write(f)
            created += 1
        return created


if __name__ == "__main__":
    app = PdfPageComposer()
    app.mainloop()
