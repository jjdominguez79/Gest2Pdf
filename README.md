# Gest2Pdf — PDF Composer de escritorio

Aplicación sencilla en Tkinter para unir y reordenar páginas de varios PDFs usando miniaturas con arrastrar y soltar. Todo sucede en local: no se suben archivos a ningún servidor.

## Características
- Añade múltiples PDFs y muestra todas sus páginas como miniaturas.
- Selección flexible: clic simple, `Shift` para rangos, `Ctrl/Cmd` para multiselección.
- Reordenamiento por drag & drop directamente sobre la lista.
- Eliminación rápida de páginas seleccionadas.
- Exporta un único PDF con el orden actual.
- Utilidades: unir PDFs (rápido), dividir por rangos y comprimir PDF.
- Compresión configurable al comprimir PDF: nivel **Baja**, **Media** o **Alta**.
- Ajustes rápidos en el código: `THUMB_WIDTH`, `RENDER_ZOOM` y `ITEM_PAD` al inicio de `main.py` controlan tamaño de miniaturas y espaciado.

## Requisitos
- Python 3.9+ (probado con 3.11).
- Tkinter (incluido en Python en Windows y macOS; en muchas distros Linux se instala con el paquete `python3-tk`).
- Dependencias Python: `pymupdf` (se importa como `fitz`), `Pillow`, `pypdf`.

Instalación de dependencias en un entorno virtual recomendado:

```bash
python -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install pymupdf Pillow pypdf
```

## Uso
1) Activa el entorno virtual (opcional pero recomendado).  
2) Ejecuta la aplicación:

```bash
python main.py
```

3) En la ventana:
   - Pulsa **"Añadir PDFs..."** para cargar uno o varios archivos.
   - Selecciona páginas con clic, `Shift` (rango) o `Ctrl/Cmd` (multiselección).
   - Arrastra una página para moverla a otra posición.
   - Usa **"Eliminar seleccionadas"** si necesitas quitar páginas.
   - Pulsa **"Exportar PDF..."** para guardar el resultado.
   - En **Utilidades** encontrarás: **Unir PDFs (rápido)**, **Dividir PDF** y **Comprimir PDF**.

## Crear ejecutable (.exe en Windows)
1) Activa el entorno virtual (recomendado) e instala PyInstaller:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install pyinstaller
```

2) Ejecuta PyInstaller desde la raíz del proyecto (recomendado con `python -m`):

```bash
python -m PyInstaller --onefile --noconsole --name Gest2Pdf main.py
```

3) El ejecutable quedará en `dist/Gest2Pdf.exe`.

Notas:
- Si quieres una carpeta con recursos en lugar de un solo archivo, usa `--onedir`.
- Si ves que faltan dependencias, ejecuta el comando dentro del mismo `venv` donde instalaste `pymupdf`, `Pillow` y `pypdf`.
- En Windows, usar `python -m PyInstaller` evita errores del launcher cuando `pyinstaller.exe` apunta a un Python que ya no existe.

## Consejos de rendimiento
- Para PDFs con cientos de páginas, aumenta `THUMB_WIDTH` o reduce `RENDER_ZOOM` en `main.py` para generar miniaturas más pequeñas y rápidas.
- Cerrar y volver a abrir el proyecto con **"Limpiar proyecto"** ayuda a liberar memoria después de manejar documentos grandes.

## Estructura del repositorio
- `main.py`: todo el código de la interfaz y la lógica de composición.

## Licencia
No se ha declarado una licencia. Añade una si planeas distribuir el proyecto.
