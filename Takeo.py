import os
import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import re # Asegurarse de que re está importado globalmente si se usa fuera de un método específico.
from collections import defaultdict # Para generate_detail y unify_and_check

class ScriptTakeOptimizer:
    def __init__(self):
        # Configuración por defecto
        self.max_duration = 30  # segundos
        self.max_lines_per_take = 10
        self.max_consecutive_lines_per_character = 5
        self.max_chars_per_line = 60
        self.frame_rate = 25  # fps para tiempos con frames

        # Variables de estado
        self.script_data = None
        self.selected_characters = []
        self.problematic_interventions_report = [] # Para el reporte de errores
        
        # Iniciar interfaz
        self.root = tk.Tk()
        self.root.title("Optimizador de Takes para Guiones")
        self.root.geometry("800x650") # Aumenté un poco la altura para el posible nuevo campo (aunque no se use directamente para error, es buena práctica)
        self.create_ui()
    
    # ------------------------------
    # Interfaz Gráfica
    # ------------------------------
    def create_ui(self):
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        load_btn = ttk.Button(main_frame, text="Cargar Guion (Excel)", command=self.load_script)
        load_btn.pack(pady=10)
        
        config_frame = ttk.LabelFrame(main_frame, text="Configuración de Takes", padding=10)
        config_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(config_frame, text="Duración máxima por take (segundos):").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.duration_var = tk.StringVar(value=str(self.max_duration))
        ttk.Entry(config_frame, textvariable=self.duration_var, width=10).grid(row=0, column=1, pady=5)
        
        ttk.Label(config_frame, text="Máximo de líneas por take:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.max_lines_var = tk.StringVar(value=str(self.max_lines_per_take))
        ttk.Entry(config_frame, textvariable=self.max_lines_var, width=10).grid(row=1, column=1, pady=5)
        
        ttk.Label(config_frame, text="Máx. líneas consecutivas mismo personaje (en take):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.max_consecutive_var = tk.StringVar(value=str(self.max_consecutive_lines_per_character))
        ttk.Entry(config_frame, textvariable=self.max_consecutive_var, width=10).grid(row=2, column=1, pady=5)
        
        ttk.Label(config_frame, text="Máximo de caracteres por línea (diálogo):").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.max_chars_var = tk.StringVar(value=str(self.max_chars_per_line))
        ttk.Entry(config_frame, textvariable=self.max_chars_var, width=10).grid(row=3, column=1, pady=5)
        
        self.characters_frame = ttk.LabelFrame(main_frame, text="Selección de Personajes", padding=10)
        self.characters_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(action_frame, text="Seleccionar Todos", command=self.select_all_characters).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Deseleccionar Todos", command=self.deselect_all_characters).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Procesar Guion", command=self.process_script).pack(side=tk.RIGHT, padx=5)

    def _update_config_from_ui(self):
        """Actualiza las variables de configuración desde los valores de la UI."""
        try:
            self.max_duration = int(self.duration_var.get())
            self.max_lines_per_take = int(self.max_lines_var.get())
            self.max_consecutive_lines_per_character = int(self.max_consecutive_var.get())
            self.max_chars_per_line = int(self.max_chars_var.get())
            # self.frame_rate es fija por ahora
            if self.max_duration <=0 or self.max_lines_per_take <=0 or \
               self.max_consecutive_lines_per_character <=0 or self.max_chars_per_line <=0:
                messagebox.showerror("Error de Configuración", "Todos los valores de configuración deben ser positivos.")
                return False
            return True
        except ValueError:
            messagebox.showerror("Error de Configuración", "Valores de configuración no válidos (deben ser números enteros). Por favor, corríjalos.")
            return False

    def _check_individual_interventions(self):
        """
        Chequea cada intervención individual contra las normas de takeo
        para duración y número de líneas.
        """
        self.problematic_interventions_report = []
        if self.script_data is None:
            return

        # La configuración ya debería estar actualizada por _update_config_from_ui() 
        # llamada en load_script antes que esta función.

        for index, row in self.script_data.iterrows():
            intervention_details = {
                "SCENE": row.get('SCENE', 'N/A'),
                "PERSONAJE": row['PERSONAJE'],
                "IN": str(row['IN']),
                "OUT": str(row['OUT']),
                "EUSKERA_Snippet": str(row["EUSKERA"])[:70] + ("..." if len(str(row["EUSKERA"])) > 70 else ""),
            }
            try:
                # Chequeo de duración
                in_time_s = self.parse_time(row['IN'])
                out_time_s = self.parse_time(row['OUT'])
                duration = out_time_s - in_time_s
                
                if duration > self.max_duration:
                    report_entry = intervention_details.copy()
                    report_entry.update({
                        "PROBLEMA_TIPO": "Duración Excesiva Individual",
                        "DETALLE": f"Duración ({duration:.2f}s) excede el máximo para un take ({self.max_duration}s)."
                    })
                    self.problematic_interventions_report.append(report_entry)

                # Chequeo de número de líneas tras expansión
                expanded_lines = self.expand_dialogue(str(row["EUSKERA"]))
                num_expanded_lines = len(expanded_lines)

                # Usamos max_lines_per_take como el límite para una intervención individual
                if num_expanded_lines > self.max_lines_per_take:
                    report_entry = intervention_details.copy()
                    report_entry.update({
                        "PROBLEMA_TIPO": "Demasiadas Líneas Individuales",
                        "DETALLE": f"Intervención genera {num_expanded_lines} líneas (límite basado en máx. líneas por take: {self.max_lines_per_take}, con {self.max_chars_per_line} caract./línea)."
                    })
                    self.problematic_interventions_report.append(report_entry)
            
            except ValueError as ve: # Errores de parse_time
                report_entry = intervention_details.copy()
                report_entry.update({
                    "PROBLEMA_TIPO": "Error de Formato de Tiempo",
                    "DETALLE": str(ve)
                })
                self.problematic_interventions_report.append(report_entry)
            except Exception as e: # Otros errores inesperados durante el chequeo
                report_entry = intervention_details.copy()
                report_entry.update({
                    "PROBLEMA_TIPO": "Error Inesperado en Chequeo Individual",
                    "DETALLE": str(e)
                })
                self.problematic_interventions_report.append(report_entry)
        
        if self.problematic_interventions_report:
            self._save_problematic_interventions_report()

    def _save_problematic_interventions_report(self):
        """Guarda el reporte de intervenciones problemáticas en un archivo Excel."""
        if not self.problematic_interventions_report:
            return

        # Intentar obtener el directorio del archivo cargado como sugerencia
        # Esto es un poco más complejo si script_data.name no está disponible o es StringIO
        # Por simplicidad, usaremos un askdirectory estándar
        save_dir = filedialog.askdirectory(title="Seleccionar directorio para GUARDAR REPORTE DE INTERVENCIONES PROBLEMÁTICAS")
        if not save_dir:
            messagebox.showwarning("Cancelado", "Guardado de reporte de intervenciones problemáticas cancelado.")
            return

        try:
            report_df = pd.DataFrame(self.problematic_interventions_report)
            report_file_path = os.path.join(save_dir, "reporte_intervenciones_problematicas.xlsx")
            report_df.to_excel(report_file_path, index=False)
            messagebox.showwarning("Intervenciones Problemáticas Encontradas",
                                f"Se encontraron {len(self.problematic_interventions_report)} intervenciones individuales con problemas "
                                f"según las normas de takeo.\n"
                                f"El reporte ha sido guardado en:\n{report_file_path}\n\n"
                                "Estas intervenciones podrían causar dificultades o ser imposibles de incluir en takes válidos.")
        except Exception as e:
            messagebox.showerror("Error al Guardar Reporte", f"No se pudo guardar el reporte de intervenciones problemáticas: {str(e)}")


    def load_script(self):
        file_path = filedialog.askopenfilename(
            title="Seleccionar archivo Excel del guion",
            filetypes=[("Excel files", "*.xlsx *.xls")]
        )
        
        if not file_path:
            return
            
        try:
            # Primero, actualiza la configuración desde la UI para que los chequeos la usen.
            if not self._update_config_from_ui():
                 self.script_data = None # Resetea si la config es inválida
                 return

            self.script_data = pd.read_excel(file_path)
            
            required_columns = ['IN', 'OUT', 'PERSONAJE', 'EUSKERA', 'SCENE']
            for col in required_columns:
                if col not in self.script_data.columns:
                    messagebox.showerror("Error", f"Columna requerida '{col}' no encontrada en el archivo.")
                    self.script_data = None
                    return
            
            # Chequeo de intervenciones individuales problemáticas ANTES de continuar
            self._check_individual_interventions()
            
            in_sample = str(self.script_data['IN'].iloc[0]) if not self.script_data.empty else "N/A"
            out_sample = str(self.script_data['OUT'].iloc[0]) if not self.script_data.empty else "N/A"
            
            messagebox.showinfo(
                "Formato de Tiempo", 
                f"Formato de tiempos detectado (primera línea):\nIN: {in_sample}\nOUT: {out_sample}\n\n"
                "Si estos no son tiempos válidos, asegúrese de que su Excel contiene "
                "columnas IN y OUT con formatos de tiempo correctos (HH:MM:SS o HH:MM:SS:FF)."
            )
            
            self.populate_character_selection()
            
            messagebox.showinfo("Éxito", f"Guion cargado correctamente.\nNúmero de líneas: {len(self.script_data)}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar el archivo: {str(e)}")
            self.script_data = None


    def populate_character_selection(self):
        for widget in self.characters_frame.winfo_children():
            widget.destroy()
            
        if self.script_data is None or self.script_data.empty: # Añadida comprobación de empty
            return
            
        characters = sorted(self.script_data['PERSONAJE'].unique())
        self.character_vars = {}
        
        num_chars = len(characters)
        num_cols = min(3, max(1, num_chars)) # Evitar num_cols = 0 si no hay personajes
        
        for i, character in enumerate(characters):
            var = tk.BooleanVar(value=True)
            self.character_vars[character] = var
            row = i // num_cols
            col = i % num_cols
            ttk.Checkbutton(
                self.characters_frame, 
                text=character, 
                variable=var
            ).grid(row=row, column=col, sticky=tk.W, padx=10, pady=2)
    
    def select_all_characters(self):
        if hasattr(self, 'character_vars'): # Asegurar que existe
            for var in self.character_vars.values():
                var.set(True)
    
    def deselect_all_characters(self):
        if hasattr(self, 'character_vars'): # Asegurar que existe
            for var in self.character_vars.values():
                var.set(False)
    
    def process_script(self):
        if self.script_data is None:
            messagebox.showerror("Error", "No hay guion cargado.")
            return
            
        # Actualizar configuración desde la interfaz
        if not self._update_config_from_ui():
            return # Detener si la configuración es inválida
            
        try:
            self.selected_characters = [
                char for char, var in self.character_vars.items() if var.get()
            ]
            
            if not self.selected_characters:
                messagebox.showerror("Error", "Debe seleccionar al menos un personaje.")
                return
                
            filtered_data = self.script_data[self.script_data['PERSONAJE'].isin(self.selected_characters)].copy()
            
            if filtered_data.empty:
                messagebox.showerror("Error", "No hay líneas para los personajes seleccionados.")
                return
                
            detail_df, summary_df = self.create_optimized_takes_dp(filtered_data)
            
            self.save_results(detail_df, summary_df)
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al procesar el guion: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def parse_time(self, time_str):
        parts = str(time_str).split(':')
        if len(parts) == 3:
            hh, mm, ss = map(int, parts)
            return hh * 3600 + mm * 60 + ss
        elif len(parts) == 4:
            hh, mm, ss, ff = map(int, parts)
            return hh * 3600 + mm * 60 + ss + ff / self.frame_rate
        else:
            raise ValueError(f"Formato de tiempo inválido: '{time_str}'. Se esperaba HH:MM:SS o HH:MM:SS:FF.")
    
    def expand_dialogue(self, text):
        import re # Ya importado globalmente, pero localmente es buena práctica para claridad
        tokens = []
        parts = re.split(r'(\([^)]*\))', text)
        for part in parts:
            if not part.strip():
                continue
            if re.fullmatch(r'\([^)]*\)', part.strip()):
                tokens.append((part.strip(), True))
            else:
                for word in part.split():
                    tokens.append((word, False))
        
        lines = []
        current_line_tokens = []
        current_effective_length = 0
        
        for token, is_paren in tokens:
            if not current_line_tokens:
                addition = 1 if is_paren else len(token)
            else:
                prev_is_paren = current_line_tokens[-1][1]
                if is_paren:
                    addition = 0 if prev_is_paren else 1
                else:
                    addition = len(token) if prev_is_paren else (1 + len(token))
            
            if current_line_tokens and current_effective_length + addition > self.max_chars_per_line : # Añadido 'current_line_tokens and' para no romper en la primera palabra si es muy larga
                lines.append(" ".join(t for t, _ in current_line_tokens))
                current_line_tokens = [(token, is_paren)]
                current_effective_length = 1 if is_paren else len(token)
            else:
                current_line_tokens.append((token, is_paren))
                current_effective_length += addition
        
        if current_line_tokens:
            lines.append(" ".join(t for t, _ in current_line_tokens))
        
        return lines

    def optimal_merge_run(self, texts):
        n = len(texts)
        dp = [float("inf")] * (n + 1)
        segmentation = [None] * (n + 1)
        dp[0] = 0
        segmentation[0] = []
        for i in range(1, n + 1):
            for j in range(i):
                merged_text = " ".join(texts[j:i])
                merged_lines = self.expand_dialogue(merged_text)
                cost = len(merged_lines)
                if dp[j] + cost < dp[i]:
                    dp[i] = dp[j] + cost
                    segmentation[i] = segmentation[j] + [merged_lines]
        return dp[n], segmentation[n]

    def unify_and_check(self, blocks_segment):
        from collections import defaultdict # Ya importado globalmente
        interventions = []
        for block in blocks_segment:
            for d in block["dialogues"]:
                interventions.append((d["personaje"], " ".join(d["lines"]))) # Usamos el texto ya expandido
        if not interventions:
            return 0, False

        lines_per_character = defaultdict(int)
        current_char = interventions[0][0]
        current_texts_for_char_run = [] # Textos de la corrida actual del personaje
        
        total_lines_in_take = 0

        for person, text_block_as_single_string in interventions: # text_block_as_single_string es un string ya unido de d["lines"]
            if person == current_char:
                current_texts_for_char_run.append(text_block_as_single_string)
            else:
                # Se fusiona la corrida actual del personaje anterior y se suma al total del personaje
                # y al total del take.
                if current_texts_for_char_run:
                    run_lines, _ = self.optimal_merge_run(current_texts_for_char_run)
                    lines_per_character[current_char] += run_lines
                    total_lines_in_take += run_lines
                current_char = person
                current_texts_for_char_run = [text_block_as_single_string]
        
        # Procesar la última corrida.
        if current_texts_for_char_run:
            run_lines, _ = self.optimal_merge_run(current_texts_for_char_run)
            lines_per_character[current_char] += run_lines
            total_lines_in_take += run_lines

        # La restricción es sobre el total de líneas del take, no la suma de óptimos por personaje.
        # El total de líneas ya está en block["total_lines"] (original, sin fusionar corridas)
        # La fusión óptima en unify_and_check es para ver si CADA personaje excede SUS líneas consecutivas.
        
        # Recalculamos el total de líneas del take DESPUÉS de la fusión óptima de corridas de personaje.
        # total_lines = sum(lines_per_character.values()) # Esto es lo que estaba antes, es correcto.

        character_exceeded_max_consecutive = any(lines > self.max_consecutive_lines_per_character 
                                                 for lines in lines_per_character.values())
        
        return total_lines_in_take, character_exceeded_max_consecutive


    def check_duration(self, blocks_segment):
        if not blocks_segment: return True # Un segmento vacío cumple
        start = blocks_segment[0]["in_time"]
        end = blocks_segment[-1]["out_time"]
        return (end - start) <= self.max_duration

    def is_segment_feasible(self, blocks_segment):
        if not blocks_segment: return False # Un segmento debe tener al menos un bloque
        
        if not self.check_duration(blocks_segment):
            return False

        # El total de líneas del take (pre-fusión de corridas de mismo personaje)
        # Este es el número de líneas que se generó al expandir cada intervención individualmente.
        # Esta es la restricción que debe cumplir el take.
        segment_total_lines = sum(b['total_lines'] for b in blocks_segment)
        if segment_total_lines > self.max_lines_per_take:
            return False

        # Ahora, verificamos las líneas consecutivas POR PERSONAJE DENTRO DEL TAKE,
        # lo cual implica fusionar sus intervenciones si aparecen varias veces en el segmento.
        _, character_exceeded_consecutive = self.unify_and_check(blocks_segment)
        if character_exceeded_consecutive:
            return False
            
        return True

    def group_dialogues_simultaneous_dp(self, data):
        blocks = []
        # Asegurarse que IN y OUT sean strings para el groupby, o parsearlos antes si son mixed types
        data_copy = data.copy()
        data_copy['IN_str'] = data_copy['IN'].astype(str)
        data_copy['OUT_str'] = data_copy['OUT'].astype(str)

        grupos = data_copy.groupby(["SCENE", "IN_str", "OUT_str"]) # Usar las columnas de string
        for (scene, in_time_str, out_time_str), grupo in grupos:
            block = {}
            block["scene"] = scene
            block["in_time_str"] = in_time_str # Ya es string
            block["out_time_str"] = out_time_str # Ya es string
            try:
                block["in_time"] = self.parse_time(in_time_str)
                block["out_time"] = self.parse_time(out_time_str)
            except ValueError as e:
                print(f"Advertencia: Saltando bloque debido a error de parse_time en group_dialogues: {e} para {scene}, {in_time_str}, {out_time_str}")
                continue # Saltar este bloque si los tiempos son inválidos

            dialogues = []
            total_lines_in_block = 0
            for _, row in grupo.iterrows():
                personaje = row["PERSONAJE"]
                texto = str(row["EUSKERA"])
                lines = self.expand_dialogue(texto)
                dialogues.append({"personaje": personaje, "lines": lines}) # lines ya es una lista de strings
                total_lines_in_block += len(lines)
            block["dialogues"] = dialogues
            block["total_lines"] = total_lines_in_block # Suma de longitudes de todas las listas 'lines'
            block["characters"] = set(d["personaje"] for d in dialogues)
            blocks.append(block)
        
        blocks.sort(key=lambda b: (b["scene"], b["in_time"]))
        return blocks

    def partition_scene_blocks(self, blocks):
        n = len(blocks)
        dp = [float("inf")] * (n + 1)
        partition_index = [-1] * (n + 1)
        dp[0] = 0
        
        for i in range(n): # Considerar bloques[0...i-1] ya particionados
            if dp[i] == float("inf"): continue # No hay forma de llegar a esta partición
            for j in range(i, n): # Intentar crear un nuevo segmento blocks[i...j]
                segment = blocks[i:j+1]
                if not self.is_segment_feasible(segment):
                    # Si el segmento [i...j] no es factible, entonces [i...j+1] tampoco lo será
                    # si la infactibilidad es por duración o líneas totales.
                    # Sin embargo, podría volverse factible si el problema es de líneas consecutivas
                    # y un personaje problemático no está en el bloque j+1.
                    # Por ahora, la ruptura simple es una heurística común, pero no siempre óptima
                    # si 'is_segment_feasible' tiene chequeos complejos.
                    # La implementación actual de is_segment_feasible verifica duración primero,
                    # luego total de líneas, luego consecutivas. Si falla en las primeras,
                    # alargar el segmento no ayudará. Si falla en consecutivas, podría.
                    # Para simplificar, mantenemos el break.
                    break 
                
                seg_characters = set()
                for b_in_seg in segment:
                    seg_characters.update(b_in_seg["characters"])
                cost = len(seg_characters)
                
                if dp[i] + cost < dp[j+1]:
                    dp[j+1] = dp[i] + cost
                    partition_index[j+1] = i
        
        segments = []
        idx = n
        if dp[n] == float("inf"): # No se encontró una partición válida para toda la escena
            messagebox.showwarning("Partición Imposible", 
                                   f"No se pudo encontrar una partición válida para todos los bloques de la escena {blocks[0]['scene'] if blocks else 'desconocida'} "
                                   f"bajo las restricciones actuales. Esta escena podría no aparecer en los resultados o estar incompleta.")
            return [], float("inf") # Retornar vacío si no es posible

        while idx > 0:
            start = partition_index[idx]
            if start == -1: # Debería ser cubierto por dp[n] == inf, pero por si acaso
                messagebox.showerror("Error de Partición", "Error al reconstruir la partición.")
                return [], float("inf")
            segments.append((start, idx)) # El segmento es blocks[start ... idx-1]
            idx = start
        segments.reverse()
        return segments, dp[n]


    def _fuse_run_texts(self, texts_list_of_lists_of_lines):
        """
        texts_list_of_lists_of_lines: [['line1', 'line2'], ['line3']]
        Fusiona un conjunto de textos (ya divididos en líneas) de un mismo personaje
        en la menor cantidad de líneas usando expand_dialogue sobre el texto completo.
        """
        # Primero, une las líneas de cada intervención original para tener los textos completos.
        full_texts_for_run = [" ".join(lines_list) for lines_list in texts_list_of_lists_of_lines]
        # Luego, une estos textos completos en uno solo.
        merged_text_complete = " ".join(full_texts_for_run)
        # Finalmente, expande este texto único.
        return self.expand_dialogue(merged_text_complete)

    def generate_detail(self, blocks_with_takes):
        from collections import defaultdict # Ya importado globalmente
        detail_rows = []
        
        # Agrupar bloques por (scene, take)
        scene_take_map = defaultdict(list)
        for block in blocks_with_takes:
            if "take" not in block: continue # Si un bloque no pudo ser asignado a un take
            scene_take_map[(block["scene"], block["take"])].append(block)
        
        for (scene, take_num), blocks_in_this_take in scene_take_map.items():
            blocks_in_this_take.sort(key=lambda b: b["in_time"])
            
            # Recopilar todas las intervenciones del take en orden
            interventions_in_take = [] # Lista de tuplas (personaje, [líneas originales], in_str, out_str)
            for block in blocks_in_this_take:
                for dialogue in block["dialogues"]:
                    interventions_in_take.append({
                        "personaje": dialogue["personaje"],
                        "lines_original_expansion": dialogue["lines"], # Lista de líneas ya expandidas
                        "in_str": block["in_time_str"],
                        "out_str": block["out_time_str"]
                    })
            
            if not interventions_in_take:
                continue

            # Agrupar intervenciones consecutivas del MISMO personaje DENTRO de este take
            # para aplicar la fusión de texto final (_fuse_run_texts)
            final_output_lines_for_take = []
            current_run_for_char = [] # Lista de diccionarios de intervención para la corrida actual

            for i, interv in enumerate(interventions_in_take):
                if not current_run_for_char or interv["personaje"] == current_run_for_char[-1]["personaje"]:
                    current_run_for_char.append(interv)
                else:
                    # Personaje cambió, procesar la corrida anterior
                    char_of_run = current_run_for_char[0]["personaje"]
                    texts_to_fuse = [r["lines_original_expansion"] for r in current_run_for_char]
                    fused_lines = self._fuse_run_texts(texts_to_fuse)
                    
                    run_in_time = current_run_for_char[0]["in_str"]
                    run_out_time = current_run_for_char[-1]["out_str"]
                    for line_text in fused_lines:
                        final_output_lines_for_take.append({
                            "SCENE": scene, "TAKE": take_num, "PERSONAJE": char_of_run,
                            "EUSKERA": line_text, "IN": run_in_time, "OUT": run_out_time
                        })
                    current_run_for_char = [interv] # Iniciar nueva corrida

            # Procesar la última corrida acumulada
            if current_run_for_char:
                char_of_run = current_run_for_char[0]["personaje"]
                texts_to_fuse = [r["lines_original_expansion"] for r in current_run_for_char]
                fused_lines = self._fuse_run_texts(texts_to_fuse)
                run_in_time = current_run_for_char[0]["in_str"]
                run_out_time = current_run_for_char[-1]["out_str"]
                for line_text in fused_lines:
                    final_output_lines_for_take.append({
                        "SCENE": scene, "TAKE": take_num, "PERSONAJE": char_of_run,
                        "EUSKERA": line_text, "IN": run_in_time, "OUT": run_out_time
                    })
            
            detail_rows.extend(final_output_lines_for_take)

        if not detail_rows: return pd.DataFrame() # Evitar error si no hay nada que procesar

        # Ordenar por escena, luego por take, luego por tiempo de IN (parseado)
        # Esto requiere parsear el 'IN' para ordenar correctamente
        df_detail = pd.DataFrame(detail_rows)
        # Convert IN times to seconds for sorting, handle potential errors
        def safe_parse_time_for_sort(time_str):
            try:
                return self.parse_time(time_str)
            except ValueError:
                return float('inf') # Put unparseable times at the end

        if not df_detail.empty:
            df_detail['sort_key_in_time'] = df_detail['IN'].apply(safe_parse_time_for_sort)
            df_detail = df_detail.sort_values(by=["SCENE", "TAKE", "sort_key_in_time"]).drop(columns=['sort_key_in_time'])
        
        return df_detail


    def generate_summary(self, blocks_with_takes):
        resumen = {}
        processed_takes_count = 0 # Para el mensaje final
        
        for block in blocks_with_takes:
            take = block.get("take", None)
            if take is None: continue # Bloque no asignado a take

            processed_takes_count = max(processed_takes_count, take if isinstance(take, int) else 0)

            for p in block["characters"]:
                if p not in resumen:
                    resumen[p] = set()
                resumen[p].add(take) # take es el número global del take
        
        resumen_rows = []
        total_sum_of_takes_per_character = 0
        
        sorted_characters = sorted(resumen.keys())

        for p in sorted_characters:
            num_takes_for_char = len(resumen[p])
            resumen_rows.append({"PERSONAJE": p, "TAKES (apariciones)": num_takes_for_char})
            total_sum_of_takes_per_character += num_takes_for_char
        
        resumen_rows.append({"PERSONAJE": "TOTAL SUMA APARICIONES", "TAKES (apariciones)": total_sum_of_takes_per_character})
        # También es útil saber el número total de takes únicos generados.
        # Esto se puede obtener del max take_num o del mensaje en save_results.

        return pd.DataFrame(resumen_rows), processed_takes_count


    def create_optimized_takes_dp(self, data):
        initial_blocks = self.group_dialogues_simultaneous_dp(data)
        
        blocks_by_scene = {}
        for block in initial_blocks:
            scene = block["scene"]
            blocks_by_scene.setdefault(scene, []).append(block)
        
        global_take_counter = 1
        final_blocks_with_takes_assigned = []
        
        sorted_scenes = sorted(blocks_by_scene.keys())

        for scene in sorted_scenes:
            scene_blocks = blocks_by_scene[scene]
            # scene_blocks ya deberían estar ordenados por in_time desde group_dialogues_simultaneous_dp
            
            segments_indices, scene_total_cost = self.partition_scene_blocks(scene_blocks)
            
            if scene_total_cost == float("inf"):
                # No se pudo particionar esta escena, los bloques no se añadirán con 'take'
                print(f"Advertencia: La escena {scene} no pudo ser particionada y no se incluirá en los takes.")
                final_blocks_with_takes_assigned.extend(scene_blocks) # Añadir sin 'take' para posible debugging
                continue

            for start_idx, end_idx_plus_one in segments_indices:
                # El segmento es scene_blocks[start_idx ... end_idx_plus_one - 1]
                for block_idx_in_scene in range(start_idx, end_idx_plus_one):
                    scene_blocks[block_idx_in_scene]["take"] = global_take_counter
                global_take_counter += 1
            final_blocks_with_takes_assigned.extend(scene_blocks) # Todos los bloques de la escena (con o sin take si hubo error parcial)
        
        # Filtramos solo los bloques que realmente tienen un take asignado para el detalle y resumen
        blocks_successfully_assigned_to_takes = [b for b in final_blocks_with_takes_assigned if "take" in b]

        detail_df = self.generate_detail(blocks_successfully_assigned_to_takes)
        summary_df, max_take_num_generated = self.generate_summary(blocks_successfully_assigned_to_takes)
        
        # Actualizamos el global_take_counter usado en el mensaje final para reflejar el número real de takes creados
        # El max_take_num_generated del resumen es más fiable.
        # O si detail_df no está vacío, detail_df['TAKE'].max()
        if not detail_df.empty and 'TAKE' in detail_df.columns:
            self.actual_takes_generated = detail_df['TAKE'].max() if pd.notna(detail_df['TAKE'].max()) else 0
        else:
            self.actual_takes_generated = 0


        return detail_df, summary_df


    def save_results(self, result_data_df, take_summary_df):
        save_dir = filedialog.askdirectory(title="Seleccionar directorio para guardar resultados")
        if not save_dir:
            return
            
        try:
            detail_path = os.path.join(save_dir, "detalle_takes.xlsx")
            summary_path = os.path.join(save_dir, "resumen_takes.xlsx")
            
            if not result_data_df.empty:
                 result_data_df.to_excel(detail_path, index=False)
            else:
                messagebox.showinfo("Resultados Detalle", "No se generaron datos para el detalle de takes.")
            
            if not take_summary_df.empty:
                take_summary_df.to_excel(summary_path, index=False)
            else:
                 messagebox.showinfo("Resultados Resumen", "No se generaron datos para el resumen de takes.")

            total_takes_val = self.actual_takes_generated
            sum_takes_personaje_val = "N/A"
            if not take_summary_df.empty and "TAKES (apariciones)" in take_summary_df.columns:
                 # El último valor de la columna 'TAKES (apariciones)' si la fila es 'TOTAL SUMA APARICIONES'
                if take_summary_df.iloc[-1]["PERSONAJE"] == "TOTAL SUMA APARICIONES":
                    sum_takes_personaje_val = take_summary_df.iloc[-1]["TAKES (apariciones)"]

            messagebox.showinfo(
                "Proceso completado", 
                f"Proceso completado.\n\n"
                f"Número total de takes únicos generados: {total_takes_val}\n"
                f"Suma total de apariciones de personajes en takes: {sum_takes_personaje_val}\n\n"
                f"Archivos guardados en (o intentado guardar en):\n{save_dir}"
            )
        except Exception as e:
            messagebox.showerror("Error", f"Error al guardar los resultados: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = ScriptTakeOptimizer()
    app.run()