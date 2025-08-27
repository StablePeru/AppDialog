import os
import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import re
from collections import defaultdict

# Módulos para lanzar la otra aplicación
import sys
import subprocess

class ScriptTakeOptimizer:
    def __init__(self):
        # Configuración por defecto
        self.max_duration = 30  # segundos
        self.max_lines_per_take = 10
        self.max_consecutive_lines_per_character = 5
        self.max_chars_per_line = 60
        self.max_silence_between_interventions = 10 # Nueva regla
        self.frame_rate = 25  # fps para tiempos con frames

        # Variables de estado
        self.script_data = None
        self.selected_characters = []
        self.problematic_interventions_report = []
        self.segmentation_failures_report = []
        
        # Iniciar interfaz
        self.root = tk.Tk()
        self.root.title("Optimizador de Takes y Herramientas de Guion")
        self.root.geometry("800x720") # Un poco más de alto para el nuevo botón
        self.create_ui()

    def launch_converter_app(self):
        """
        Encuentra y ejecuta la aplicación de conversión de Excel a TXT.
        """
        try:
            # Obtener la ruta del directorio donde se está ejecutando Takeo.py
            # __file__ es la forma más robusta de obtener la ruta del script actual
            current_dir = os.path.dirname(os.path.abspath(__file__))
            
            # Construir la ruta al script 'main.py' del convertidor
            converter_main_script = os.path.join(current_dir, 'xlsx_converter', 'main.py')

            if not os.path.exists(converter_main_script):
                messagebox.showerror(
                    "Error al Abrir",
                    f"No se pudo encontrar el script del convertidor en la ruta esperada:\n{converter_main_script}\n\nAsegúrese de que la carpeta 'xlsx_converter' existe en el mismo directorio que este programa y contiene el archivo 'main.py'."
                )
                return

            # Obtener la ruta al ejecutable de Python que está corriendo este script
            python_executable = sys.executable

            # Usar subprocess.Popen para lanzar el script en un nuevo proceso.
            # Esto es "no bloqueante", lo que permite que ambas ventanas funcionen de forma independiente.
            self.status_var.set("Abriendo el conversor de Excel a TXT...")
            subprocess.Popen([python_executable, converter_main_script])
            
        except Exception as e:
            messagebox.showerror("Error Inesperado", f"Ocurrió un error al intentar abrir la herramienta de conversión: {str(e)}")
            self.status_var.set("Error al abrir el conversor.")


    # ------------------------------
    # Interfaz Gráfica
    # ------------------------------
    def create_ui(self):
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # --- Panel Superior para Carga y Procesamiento ---
        top_panel = ttk.Frame(main_frame)
        top_panel.pack(fill=tk.X, pady=(0, 10))
        load_btn = ttk.Button(top_panel, text="Cargar Guion para Optimizar", command=self.load_script)
        load_btn.pack(side=tk.LEFT, padx=(0, 10))
        self.process_btn = ttk.Button(top_panel, text="Optimizar Takes", command=self.process_script, state=tk.DISABLED)
        self.process_btn.pack(side=tk.RIGHT)

        # --- Notebook para organizar las secciones de optimización ---
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=5)
        config_tab = ttk.Frame(notebook, padding=10)
        characters_tab = ttk.Frame(notebook, padding=10)
        notebook.add(config_tab, text='Configuración de Takes')
        notebook.add(characters_tab, text='Personajes del Guion')

        # --- Pestaña de Configuración ---
        config_frame = ttk.LabelFrame(config_tab, text="Reglas de Takeo", padding=10)
        config_frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(config_frame, text="Duración máxima por take (segundos):").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.duration_var = tk.StringVar(value=str(self.max_duration))
        ttk.Entry(config_frame, textvariable=self.duration_var, width=10).grid(row=0, column=1, pady=5)
        ttk.Label(config_frame, text="Máximo de líneas por take:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.max_lines_var = tk.StringVar(value=str(self.max_lines_per_take))
        ttk.Entry(config_frame, textvariable=self.max_lines_var, width=10).grid(row=1, column=1, pady=5)
        ttk.Label(config_frame, text="Máx. líneas consecutivas mismo personaje:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.max_consecutive_var = tk.StringVar(value=str(self.max_consecutive_lines_per_character))
        ttk.Entry(config_frame, textvariable=self.max_consecutive_var, width=10).grid(row=2, column=1, pady=5)
        ttk.Label(config_frame, text="Máximo de caracteres por línea (diálogo):").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.max_chars_var = tk.StringVar(value=str(self.max_chars_per_line))
        ttk.Entry(config_frame, textvariable=self.max_chars_var, width=10).grid(row=3, column=1, pady=5)
        ttk.Label(config_frame, text="Máx. silencio entre intervenciones (segundos):").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.silence_var = tk.StringVar(value=str(self.max_silence_between_interventions))
        ttk.Entry(config_frame, textvariable=self.silence_var, width=10).grid(row=4, column=1, pady=5)

        # --- Pestaña de Personajes ---
        char_actions_frame = ttk.Frame(characters_tab)
        char_actions_frame.pack(fill=tk.X, pady=5)
        ttk.Button(char_actions_frame, text="Seleccionar Todos", command=self.select_all_characters).pack(side=tk.LEFT, padx=5)
        ttk.Button(char_actions_frame, text="Deseleccionar Todos", command=self.deselect_all_characters).pack(side=tk.LEFT, padx=5)
        canvas = tk.Canvas(characters_tab, borderwidth=0)
        scrollbar = ttk.Scrollbar(characters_tab, orient="vertical", command=canvas.yview)
        self.characters_frame = ttk.Frame(canvas)
        self.characters_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.characters_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # --- Sección para herramientas adicionales ---
        tools_frame = ttk.LabelFrame(main_frame, text="Otras Herramientas", padding=10)
        tools_frame.pack(fill=tk.X, pady=(10, 5))
        
        converter_btn = ttk.Button(tools_frame, text="Abrir Conversor Excel a TXT...", command=self.launch_converter_app)
        converter_btn.pack(pady=5, padx=5, anchor='w')
        
        # --- Barra de Estado ---
        self.status_var = tk.StringVar()
        self.status_var.set("Listo. Cargue un guion para optimizar o use otras herramientas.")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding=5)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X, pady=(5,0))

    def _update_config_from_ui(self):
        try:
            self.max_duration = int(self.duration_var.get())
            self.max_lines_per_take = int(self.max_lines_var.get())
            self.max_consecutive_lines_per_character = int(self.max_consecutive_var.get())
            self.max_chars_per_line = int(self.max_chars_var.get())
            self.max_silence_between_interventions = int(self.silence_var.get())
            if any(v <= 0 for v in [self.max_duration, self.max_lines_per_take, self.max_consecutive_lines_per_character, self.max_chars_per_line]) or self.max_silence_between_interventions < 0:
                messagebox.showerror("Error de Configuración", "Todos los valores deben ser positivos (el silencio puede ser 0).")
                return False
            return True
        except ValueError:
            messagebox.showerror("Error de Configuración", "Valores no válidos (deben ser números enteros).")
            return False

    def _check_individual_interventions(self):
        self.problematic_interventions_report = []
        if self.script_data is None: return
        for index, row in self.script_data.iterrows():
            details = {"SCENE": row.get('SCENE', 'N/A'), "PERSONAJE": row['PERSONAJE'], "IN": str(row['IN']), "OUT": str(row['OUT']), "EUSKERA_Snippet": str(row["EUSKERA"])[:70] + "..."}
            try:
                duration = self.parse_time(row['OUT']) - self.parse_time(row['IN'])
                if duration > self.max_duration:
                    self.problematic_interventions_report.append({**details, "PROBLEMA_TIPO": "Duración Excesiva", "DETALLE": f"Duración ({duration:.2f}s) > max ({self.max_duration}s)."})
                num_lines = len(self.expand_dialogue(str(row["EUSKERA"])))
                if num_lines > self.max_lines_per_take:
                    self.problematic_interventions_report.append({**details, "PROBLEMA_TIPO": "Líneas Excesivas", "DETALLE": f"Líneas ({num_lines}) > max ({self.max_lines_per_take})."})
            except Exception as e:
                self.problematic_interventions_report.append({**details, "PROBLEMA_TIPO": "Error de Procesamiento", "DETALLE": str(e)})
        if self.problematic_interventions_report: self._save_problematic_interventions_report()

    def _save_problematic_interventions_report(self):
        if not self.problematic_interventions_report: return
        save_dir = filedialog.askdirectory(title="Seleccionar directorio para REPORTE DE ERRORES INDIVIDUALES")
        if not save_dir: return
        try:
            report_df = pd.DataFrame(self.problematic_interventions_report)
            path = os.path.join(save_dir, "reporte_intervenciones_problematicas.xlsx")
            report_df.to_excel(path, index=False)
            messagebox.showwarning("Intervenciones Problemáticas", f"Se encontraron problemas en intervenciones individuales. Reporte guardado en:\n{path}")
        except Exception as e:
            messagebox.showerror("Error al Guardar Reporte", f"No se pudo guardar el reporte de intervenciones: {str(e)}")

    def load_script(self):
        file_path = filedialog.askopenfilename(title="Seleccionar archivo Excel del guion", filetypes=[("Excel files", "*.xlsx *.xls")])
        if not file_path: return
        try:
            if not self._update_config_from_ui(): self.script_data = None; return
            self.script_data = pd.read_excel(file_path)
            required = ['IN', 'OUT', 'PERSONAJE', 'EUSKERA', 'SCENE']
            if not all(col in self.script_data.columns for col in required):
                messagebox.showerror("Error", f"Columnas requeridas no encontradas en el Excel: {required}"); self.script_data = None; return
            self._check_individual_interventions()
            self.populate_character_selection()
            messagebox.showinfo("Éxito", f"Guion cargado correctamente con {len(self.script_data)} líneas.")
            self.status_var.set(f"Guion '{os.path.basename(file_path)}' cargado. Listo para optimizar."); self.process_btn.config(state=tk.NORMAL)
        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar el archivo: {str(e)}"); self.script_data = None
            self.status_var.set("Error al cargar el guion. Inténtelo de nuevo."); self.process_btn.config(state=tk.DISABLED)

    def populate_character_selection(self):
        for widget in self.characters_frame.winfo_children(): widget.destroy()
        if self.script_data is None: return
        characters = sorted(self.script_data['PERSONAJE'].dropna().unique())
        self.character_vars = {}
        num_cols = 3
        for i, character in enumerate(characters):
            var = tk.BooleanVar(value=True); self.character_vars[character] = var
            row, col = i // num_cols, i % num_cols
            ttk.Checkbutton(self.characters_frame, text=character, variable=var).grid(row=row, column=col, sticky=tk.W, padx=10, pady=2)
    
    def select_all_characters(self):
        if hasattr(self, 'character_vars'):
            for var in self.character_vars.values(): var.set(True)
    
    def deselect_all_characters(self):
        if hasattr(self, 'character_vars'):
            for var in self.character_vars.values(): var.set(False)
    
    def process_script(self):
        if self.script_data is None: messagebox.showerror("Error", "No hay guion cargado."); return
        if not self._update_config_from_ui(): return
        self.root.config(cursor="watch"); self.status_var.set("Optimizando takes... Esto puede tardar."); self.root.update_idletasks()
        try:
            self.segmentation_failures_report = []
            self.selected_characters = [c for c, v in self.character_vars.items() if v.get()]
            if not self.selected_characters: messagebox.showerror("Error", "Debe seleccionar al menos un personaje."); return
            filtered_data = self.script_data[self.script_data['PERSONAJE'].isin(self.selected_characters)].copy()
            if filtered_data.empty: messagebox.showerror("Error", "No hay líneas para los personajes seleccionados."); return
            detail_df, summary_df = self.create_optimized_takes_dp(filtered_data)
            self.save_results(detail_df, summary_df)
            self.status_var.set("¡Optimización completada! Resultados guardados.")
        except Exception as e:
            self.status_var.set("Error durante la optimización.")
            messagebox.showerror("Error de Proceso", f"Ocurrió un error al procesar el guion: {str(e)}"); import traceback; traceback.print_exc()
        finally:
            self.root.config(cursor="")

    def parse_time(self, time_str):
        parts = str(time_str).split(':')
        if len(parts) == 3: hh, mm, ss = map(int, parts); return hh * 3600 + mm * 60 + ss
        elif len(parts) == 4: hh, mm, ss, ff = map(int, parts); return hh * 3600 + mm * 60 + ss + ff / self.frame_rate
        else: raise ValueError(f"Formato de tiempo inválido: '{time_str}'. Se esperaba HH:MM:SS o HH:MM:SS:FF.")
    
    def expand_dialogue(self, text):
        lines, current_line = [], ""
        for word in str(text).split():
            if not current_line: current_line = word
            elif len(current_line) + 1 + len(word) > self.max_chars_per_line: lines.append(current_line); current_line = word
            else: current_line += " " + word
        if current_line: lines.append(current_line)
        return lines

    def unify_and_check(self, blocks_segment):
        interventions = [(d["personaje"], " ".join(d["lines"])) for b in blocks_segment for d in b["dialogues"]]
        if not interventions: return 0, False
        lines_per_char, total_lines = defaultdict(int), 0
        current_char, char_run_texts = None, []
        for person, text in interventions:
            if person == current_char: char_run_texts.append(text)
            else:
                if char_run_texts:
                    run_lines = len(self.expand_dialogue(" _ ".join(char_run_texts)))
                    lines_per_char[current_char] += run_lines; total_lines += run_lines
                current_char, char_run_texts = person, [text]
        if char_run_texts:
            run_lines = len(self.expand_dialogue(" _ ".join(char_run_texts)))
            lines_per_char[current_char] += run_lines; total_lines += run_lines
        exceeded = any(l > self.max_consecutive_lines_per_character for l in lines_per_char.values())
        return total_lines, exceeded

    def check_duration(self, blocks_segment):
        if not blocks_segment: return True, ""
        duration = blocks_segment[-1]["out_time"] - blocks_segment[0]["in_time"]
        if duration > self.max_duration: return False, f"Duración excedida ({duration:.2f}s > {self.max_duration}s)"
        return True, ""

    def check_inter_intervention_silence(self, blocks_segment):
        for i in range(len(blocks_segment) - 1):
            silence = blocks_segment[i+1]["in_time"] - blocks_segment[i]["out_time"]
            if silence > self.max_silence_between_interventions: return False, f"Silencio excesivo ({silence:.2f}s > {self.max_silence_between_interventions}s)"
        return True, ""

    def is_segment_feasible(self, blocks_segment):
        if not blocks_segment: return False, "Segmento vacío"
        ok, reason = self.check_duration(blocks_segment);
        if not ok: return False, reason
        ok, reason = self.check_inter_intervention_silence(blocks_segment);
        if not ok: return False, reason
        total_lines, exceeded_consecutive = self.unify_and_check(blocks_segment)
        if total_lines > self.max_lines_per_take: return False, f"Límite de líneas excedido ({total_lines} > {self.max_lines_per_take})"
        if exceeded_consecutive: return False, "Límite de líneas consecutivas por personaje excedido"
        return True, ""

    def group_dialogues_simultaneous_dp(self, data):
        blocks = []
        data_copy = data.copy()
        data_copy['IN_str'] = data_copy['IN'].astype(str); data_copy['OUT_str'] = data_copy['OUT'].astype(str)
        for (scene, in_str, out_str), group in data_copy.groupby(["SCENE", "IN_str", "OUT_str"]):
            try:
                block = {"scene": scene, "in_time_str": in_str, "out_time_str": out_str, "in_time": self.parse_time(in_str), "out_time": self.parse_time(out_str)}
                dialogues = [{"personaje": row["PERSONAJE"], "lines": self.expand_dialogue(str(row["EUSKERA"]))} for _, row in group.iterrows()]
                block["dialogues"], block["characters"] = dialogues, {d["personaje"] for d in dialogues}
                blocks.append(block)
            except ValueError as e: print(f"Advertencia: Saltando bloque con tiempo inválido '{in_str}' o '{out_str}': {e}")
        blocks.sort(key=lambda b: (b["scene"], b["in_time"]))
        return blocks

    def partition_scene_blocks(self, blocks):
        n = len(blocks)
        dp, p_idx = [float("inf")] * (n + 1), [-1] * (n + 1); dp[0] = 0
        for i in range(n):
            if dp[i] == float("inf"): continue
            for j in range(i, n):
                segment = blocks[i:j+1]
                is_feasible, reason = self.is_segment_feasible(segment)
                if not is_feasible:
                    chars = {c for b in segment for c in b['characters']}
                    self.segmentation_failures_report.append({"ESCENA": segment[0]['scene'], "REGLA_INCUMPLIDA": reason, "INICIO_SEGMENTO": segment[0]['in_time_str'], "FIN_SEGMENTO": segment[-1]['out_time_str'], "PERSONAJES": ", ".join(sorted(list(chars)))})
                    break
                cost = len({c for b in segment for c in b["characters"]})
                if dp[i] + cost < dp[j+1]: dp[j+1], p_idx[j+1] = dp[i] + cost, i
        segments = []; idx = n
        if dp[n] == float("inf"):
            if blocks: messagebox.showwarning("Partición Imposible", f"No se pudo encontrar una partición válida para la escena {blocks[0]['scene']}. Se generará un reporte de fallos.");
            return [], float("inf")
        while idx > 0: start = p_idx[idx]; segments.append((start, idx)); idx = start
        segments.reverse(); return segments, dp[n]

    def _fuse_run_texts(self, texts_list_of_lists):
        return self.expand_dialogue(" _ ".join(" ".join(lines) for lines in texts_list_of_lists))

    def generate_detail(self, blocks_with_takes):
        rows = []
        df_blocks = pd.DataFrame(blocks_with_takes)
        for (scene, take), group_df in df_blocks.groupby(["scene", "take"]):
            group_records = sorted(group_df.to_dict('records'), key=lambda x: x['in_time'])
            interventions = [{"char": d["personaje"], "lines": d["lines"], "in": b["in_time_str"], "out": b["out_time_str"]} for b in group_records for d in b["dialogues"]]
            if not interventions: continue
            run = []
            for interv in interventions:
                if not run or interv["char"] == run[-1]["char"]: run.append(interv)
                else:
                    fused = self._fuse_run_texts([r["lines"] for r in run])
                    for line in fused: rows.append({"SCENE": scene, "TAKE": take, "PERSONAJE": run[0]["char"], "EUSKERA": line, "IN": run[0]["in"], "OUT": run[-1]["out"]})
                    run = [interv]
            if run:
                fused = self._fuse_run_texts([r["lines"] for r in run])
                for line in fused: rows.append({"SCENE": scene, "TAKE": take, "PERSONAJE": run[0]["char"], "EUSKERA": line, "IN": run[0]["in"], "OUT": run[-1]["out"]})
        if not rows: return pd.DataFrame()
        df = pd.DataFrame(rows); df['sort_key'] = df['IN'].apply(self.parse_time)
        return df.sort_values(by=["SCENE", "TAKE", "sort_key"]).drop(columns=['sort_key'])

    def generate_summary(self, blocks_with_takes):
        summary = defaultdict(set)
        for block in blocks_with_takes:
            if "take" in block:
                for p in block["characters"]: summary[p].add(block["take"])
        rows = [{"PERSONAJE": p, "TAKES (apariciones)": len(t)} for p, t in sorted(summary.items())]
        total = sum(row["TAKES (apariciones)"] for row in rows)
        rows.append({"PERSONAJE": "TOTAL SUMA APARICIONES", "TAKES (apariciones)": total})
        return pd.DataFrame(rows)

    def create_optimized_takes_dp(self, data):
        blocks_by_scene = defaultdict(list)
        for block in self.group_dialogues_simultaneous_dp(data): blocks_by_scene[block["scene"]].append(block)
        counter, final_blocks = 1, []
        for scene in sorted(blocks_by_scene.keys()):
            scene_blocks = blocks_by_scene[scene]
            segments, _ = self.partition_scene_blocks(scene_blocks)
            for start, end in segments:
                for i in range(start, end): scene_blocks[i]["take"] = counter
                counter += 1
            final_blocks.extend(scene_blocks)
        assigned = [b for b in final_blocks if "take" in b]
        detail_df, summary_df = self.generate_detail(assigned), self.generate_summary(assigned)
        self.actual_takes_generated = detail_df['TAKE'].max() if not detail_df.empty and 'TAKE' in detail_df.columns else 0
        return detail_df, summary_df

    def _save_segmentation_failures_report(self, save_dir):
        if not self.segmentation_failures_report: return
        try:
            report_df = pd.DataFrame(self.segmentation_failures_report).drop_duplicates()
            path = os.path.join(save_dir, "reporte_fallos_de_agrupacion.xlsx")
            report_df.to_excel(path, index=False)
            messagebox.showinfo("Reporte de Fallos de Agrupación", f"Se detectaron problemas al agrupar intervenciones. Reporte detallado guardado en:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar el reporte de fallos: {str(e)}")

    def save_results(self, detail_df, summary_df):
        save_dir = filedialog.askdirectory(title="Seleccionar directorio para guardar resultados de optimización")
        if not save_dir: return
        try:
            detail_path = os.path.join(save_dir, "detalle_takes_optimizado.xlsx")
            summary_path = os.path.join(save_dir, "resumen_takes_optimizado.xlsx")
            if not detail_df.empty: detail_df.to_excel(detail_path, index=False)
            if not summary_df.empty: summary_df.to_excel(summary_path, index=False)
            self._save_segmentation_failures_report(save_dir)
            sum_val = summary_df.iloc[-1]["TAKES (apariciones)"] if not summary_df.empty else "N/A"
            messagebox.showinfo("Proceso Completado", f"Optimización finalizada.\n\nTakes únicos generados: {self.actual_takes_generated}\nSuma de apariciones: {sum_val}\n\nArchivos guardados en:\n{save_dir}")
        except Exception as e:
            messagebox.showerror("Error al Guardar", f"Error al guardar los resultados: {str(e)}")

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = ScriptTakeOptimizer()
    app.run()