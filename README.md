# AppDialog - Editor de Guion

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/StablePeru/AppDialog)

AppDialog es una aplicación de escritorio diseñada para la edición de guiones audiovisuales. Facilita la creación y modificación de guiones, integrando herramientas de gestión de tiempos, personajes, diálogos y un reproductor de vídeo sincronizado.

## Características Principales

*   **Edición de Guion Tabular**: Interfaz intuitiva basada en tablas con columnas para Nº de intervención, ID (oculto), Escena, IN, OUT, Personaje, Diálogo y Euskera.
*   **Reproductor de Video Integrado**:
    *   Visualización de vídeo sincronizada con el guion.
    *   Controles de reproducción (Play/Pausa, Avance/Retroceso).
    *   Marcación rápida de tiempos IN y OUT.
    *   Visualización y edición directa de timecodes.
    *   Soporte para pista de audio M+E (Música y Efectos) separada.
    *   Opción para desacoplar el reproductor de vídeo en una ventana independiente.
*   **Gestión de Tiempos**:
    *   Entrada y validación de timecodes en formato HH:MM:SS:FF.
    *   Indicador visual de errores en la duración de las intervenciones (ej. OUT < IN).
    *   Opción para enlazar automáticamente el OUT de una intervención con el IN de la siguiente.
*   **Importación y Exportación**:
    *   Importación de guiones desde archivos DOCX y Excel (.xlsx).
    *   Exportación del guion a formato Excel (.xlsx) y JSON.
    *   Guardado y carga del estado del proyecto (guion y metadatos) en formato JSON.
*   **Herramientas de Edición de Diálogo**:
    *   Ajuste automático de la longitud de las líneas de diálogo (máx. 60 caracteres).
    *   División de una intervención en dos en la posición del cursor.
    *   Unión de intervenciones consecutivas del mismo personaje.
*   **Gestión de Personajes**:
    *   Autocompletado de nombres de personaje.
    *   Ventana de "Reparto Completo" para ver y editar nombres de personajes y su número de intervenciones.
*   **Funcionalidades Adicionales**:
    *   Deshacer/Rehacer para la mayoría de las operaciones de edición.
    *   Búsqueda y reemplazo de texto en columnas de Personaje y Diálogo.
    *   Incremento automático de números de escena.
    *   Configuración de la aplicación (ej. valor de trim para marcar tiempos, tamaño de fuente global).
    *   Gestor de atajos de teclado personalizables con perfiles.
    *   Interfaz con tema oscuro.
    *   Menú de archivos recientes.

## Tecnologías Utilizadas

*   **Python 3**
*   **PyQt6**: Para la interfaz gráfica de usuario.
*   **Pandas**: Para la gestión eficiente de los datos tabulares del guion.
*   **python-docx**: Para la importación de guiones desde archivos .docx.
*   **openpyxl**: Para la lectura y escritura de archivos Excel (.xlsx), utilizado por Pandas.

## Instalación y Ejecución

1.  **Clonar el Repositorio**:
    ```bash
    git clone https://github.com/StablePeru/AppDialog.git
    cd AppDialog
    ```

2.  **Crear un Entorno Virtual (Recomendado)**:
    ```bash
    python -m venv venv
    # En Windows
    venv\Scripts\activate
    # En macOS/Linux
    source venv/bin/activate
    ```

3.  **Instalar Dependencias**:
    Asegúrate de tener pip actualizado. Puedes crear un archivo `requirements.txt` con el siguiente contenido y luego instalarlo:
    ```
    PyQt6
    PyQt6-Qt6
    PyQt6-sip
    pandas
    python-docx
    openpyxl
    ```
    Luego ejecuta:
    ```bash
    pip install -r requirements.txt
    ```
    O instala los paquetes individualmente:
    ```bash
    pip install PyQt6 PyQt6-Qt6 PyQt6-sip pandas python-docx openpyxl
    ```

4.  **Ejecutar la Aplicación**:
    ```bash
    python main.py
    ```

## Uso Básico

1.  **Abrir un Video**: Ve a `Archivo > Abrir Video` para cargar un archivo de video en el reproductor.
2.  **Cargar un Guion**:
    *   `Archivo > Abrir Guion (DOCX)` para importar desde un documento Word.
    *   `Archivo > Importar Guion desde Excel` para importar desde una hoja de cálculo.
    *   `Archivo > Cargar Guion desde JSON` para cargar un proyecto previamente guardado.
3.  **Editar el Guion**:
    *   Haz clic en las celdas para editar los valores.
    *   Usa los botones de la barra de herramientas o los atajos de teclado para añadir/eliminar filas, marcar tiempos IN/OUT, etc.
    *   El diálogo se puede editar directamente; el tamaño de la fila se ajustará.
4.  **Guardar el Guion**:
    *   `Archivo > Exportar Guion a Excel` para guardar en formato Excel.
    *   `Archivo > Guardar Guion como JSON` para guardar el proyecto completo (incluyendo metadatos y el estado del guion).

## Contribuir

Las contribuciones son bienvenidas. Si deseas contribuir, por favor:

1.  Haz un fork del repositorio.
2.  Crea una nueva rama para tus cambios (`git checkout -b feature/nueva-funcionalidad`).
3.  Realiza tus cambios y haz commit (`git commit -am 'Añade nueva funcionalidad'`).
4.  Sube tus cambios a tu fork (`git push origin feature/nueva-funcionalidad`).
5.  Crea un Pull Request.

Por favor, abre un issue para discutir cambios importantes o reportar bugs.

## Licencia

Este proyecto está licenciado bajo los términos de la **GNU General Public License v3.0 (GPLv3)**.

Esto significa que el software es de código abierto y puedes usarlo, estudiarlo, modificarlo y distribuirlo libremente. Sin embargo, cualquier trabajo derivado o modificación que distribuyas debe ser también licenciado bajo GPLv3, asegurando que el código permanezca abierto y accesible para todos.

Puedes encontrar el texto completo de la licencia en el archivo `LICENSE` en este repositorio, o en [https://www.gnu.org/licenses/gpl-3.0.html](https://www.gnu.org/licenses/gpl-3.0.html).

AppDialog - Editor de Guion
Copyright (C) 2024 StablePeru
Este programa es software libre: usted puede redistribuirlo y/o modificarlo
bajo los términos de la Licencia Pública General **GNU** publicada por
la Fundación para el Software Libre, ya sea la versión 3 de la Licencia,
o (a su elección) cualquier versión posterior.
Este programa se distribuye con la esperanza de que sea útil, pero
**SIN GARANTÍA ALGUNA**; ni siquiera la garantía implícita **MERCANTIL** o
de A**PTITUD PARA UN PROPÓSITO DETERMINADO**. Consulte los
detalles de la Licencia Pública General **GNU** para obtener una información más detallada.
Usted debería haber recibido una copia de la Licencia Pública General **GNU**
junto con este programa. En caso contrario, consulte [https://www.gnu.org/licenses](https://www.gnu.org/licenses).

## Autor

**StablePeru**