import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import fitz  # PyMuPDF
from PIL import Image, ImageTk
from pypdf import PdfReader, PdfWriter


THUMB_WIDTH = 160
RENDER_ZOOM = 1.2
ITEM_PAD = 8


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
        self.title("PDF Composer (Unir + Reordenar)")
        self.geometry("1150x780")

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

    # ---------------- UI ----------------
    def _build_ui(self):
        style = ttk.Style()
        style.configure("Selected.TFrame", relief="solid", borderwidth=2)
        style.configure("Hover.TFrame", relief="solid", borderwidth=2)

        top = ttk.Frame(self, padding=8)
        top.pack(side=tk.TOP, fill=tk.X)

        ttk.Button(top, text="Añadir PDFs...", command=self.add_pdfs).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text="Limpiar proyecto", command=self.clear_project).pack(side=tk.LEFT, padx=5)

        ttk.Separator(top, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        ttk.Button(top, text="Seleccionar todo", command=self.select_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text="Limpiar selección", command=self.clear_selection).pack(side=tk.LEFT, padx=5)
        ttk.Button(top, text="Eliminar seleccionadas", command=self.delete_selected).pack(side=tk.LEFT, padx=5)

        ttk.Separator(top, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        ttk.Button(top, text="Exportar PDF...", command=self.export_pdf).pack(side=tk.LEFT, padx=5)

        self.info_var = tk.StringVar(value="Añade uno o varios PDFs para empezar.")
        ttk.Label(self, textvariable=self.info_var, padding=(10, 4)).pack(side=tk.TOP, fill=tk.X)

        # Paned: lista miniaturas + ayuda
        main = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        left = ttk.Frame(main)
        main.add(left, weight=4)

        right = ttk.Frame(main, padding=10)
        main.add(right, weight=1)

        ttk.Label(right, text="Cómo se usa", font=("Segoe UI", 10, "bold")).pack(anchor="w")
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
                "  PDF unido con el orden actual."
            ),
            justify=tk.LEFT
        ).pack(anchor="w", pady=(6, 10))

        ttk.Label(right, text="Tip", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 0))
        ttk.Label(
            right,
            text="Si el PDF tiene cientos de páginas,\nsube THUMB_WIDTH o baja RENDER_ZOOM\npara ir más fluido.",
            justify=tk.LEFT
        ).pack(anchor="w", pady=(6, 0))

        # Canvas scroll vertical
        self.canvas = tk.Canvas(left, highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        vsb = ttk.Scrollbar(left, orient="vertical", command=self.canvas.yview)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.configure(yscrollcommand=vsb.set)

        self.list_container = ttk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.list_container, anchor="nw")

        self.list_container.bind("<Configure>", self._on_container_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Rueda
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel_linux)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel_linux)

        self.status_var = tk.StringVar(value="Listo.")
        ttk.Label(self, textvariable=self.status_var, padding=8).pack(side=tk.BOTTOM, fill=tk.X)

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

        frame = ttk.Frame(self.list_container, padding=ITEM_PAD)
        frame.pack(side=tk.TOP, fill=tk.X, padx=8, pady=4)

        inner = ttk.Frame(frame)
        inner.pack(side=tk.TOP, fill=tk.X)

        img_label = ttk.Label(inner)
        img_label.pack(side=tk.LEFT)

        text = ttk.Label(inner, text=page_label)
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
                frame.configure(style="TFrame")

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


if __name__ == "__main__":
    app = PdfPageComposer()
    app.mainloop()