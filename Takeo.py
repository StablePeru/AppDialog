import os
import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import re
from collections import defaultdict

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
        
        # Iniciar interfaz
        self.root = tk.Tk()
        self.root.title("Optimizador de Takes para Guiones")
        self.root.geometry("800x680")
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

        ttk.Label(config_frame, text="Máx. silencio entre intervenciones (segundos):").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.silence_var = tk.StringVar(value=str(self.max_silence_between_interventions))
        ttk.Entry(config_frame, textvariable=self.silence_var, width=10).grid(row=4, column=1, pady=5)
        
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
            self.max_silence_between_interventions = int(self.silence_var.get())
            
            if self.max_duration <= 0 or self.max_lines_per_take <= 0 or \
               self.max_consecutive_lines_per_character <= 0 or self.max_chars_per_line <= 0 or \
               self.max_silence_between_interventions < 0:
                messagebox.showerror("Error de Configuración", "Todos los valores de configuración deben ser positivos (el silencio puede ser 0).")
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

        for index, row in self.script_data.iterrows():
            intervention_details = {
                "SCENE": row.get('SCENE', 'N/A'),
                "PERSONAJE": row['PERSONAJE'],
                "IN": str(row['IN']),
                "OUT": str(row['OUT']),
                "EUSKERA_Snippet": str(row["EUSKERA"])[:70] + ("..." if len(str(row["EUSKERA"])) > 70 else ""),
            }
            try:
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

                expanded_lines = self.expand_dialogue(str(row["EUSKERA"]))
                num_expanded_lines = len(expanded_lines)

                if num_expanded_lines > self.max_lines_per_take:
                    report_entry = intervention_details.copy()
                    report_entry.update({
                        "PROBLEMA_TIPO": "Demasiadas Líneas Individuales",
                        "DETALLE": f"Intervención genera {num_expanded_lines} líneas (límite basado en máx. líneas por take: {self.max_lines_per_take}, con {self.max_chars_per_line} caract./línea)."
                    })
                    self.problematic_interventions_report.append(report_entry)
            
            except ValueError as ve:
                report_entry = intervention_details.copy()
                report_entry.update({
                    "PROBLEMA_TIPO": "Error de Formato de Tiempo",
                    "DETALLE": str(ve)
                })
                self.problematic_interventions_report.append(report_entry)
            except Exception as e:
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
            if not self._update_config_from_ui():
                 self.script_data = None
                 return

            self.script_data = pd.read_excel(file_path)
            
            required_columns = ['IN', 'OUT', 'PERSONAJE', 'EUSKERA', 'SCENE']
            for col in required_columns:
                if col not in self.script_data.columns:
                    messagebox.showerror("Error", f"Columna requerida '{col}' no encontrada en el archivo.")
                    self.script_data = None
                    return
            
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
            
        if self.script_data is None or self.script_data.empty:
            return
            
        characters = sorted(self.script_data['PERSONAJE'].unique())
        self.character_vars = {}
        
        num_chars = len(characters)
        num_cols = min(3, max(1, num_chars))
        
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
        if hasattr(self, 'character_vars'):
            for var in self.character_vars.values():
                var.set(True)
    
    def deselect_all_characters(self):
        if hasattr(self, 'character_vars'):
            for var in self.character_vars.values():
                var.set(False)
    
    def process_script(self):
        if self.script_data is None:
            messagebox.showerror("Error", "No hay guion cargado.")
            return
            
        if not self._update_config_from_ui():
            return
            
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
        import re
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
            
            if current_line_tokens and current_effective_length + addition > self.max_chars_per_line :
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
                # MODIFICADO: Usar " _ " para juntar textos de la misma intervención
                merged_text = " _ ".join(texts[j:i])
                merged_lines = self.expand_dialogue(merged_text)
                cost = len(merged_lines)
                if dp[j] + cost < dp[i]:
                    dp[i] = dp[j] + cost
                    segmentation[i] = segmentation[j] + [merged_lines]
        return dp[n], segmentation[n]

    def unify_and_check(self, blocks_segment):
        from collections import defaultdict
        interventions = []
        for block in blocks_segment:
            for d in block["dialogues"]:
                interventions.append((d["personaje"], " ".join(d["lines"])))
        if not interventions:
            return 0, False

        lines_per_character = defaultdict(int)
        current_char = interventions[0][0]
        current_texts_for_char_run = []
        
        total_lines_in_take = 0

        for person, text_block_as_single_string in interventions:
            if person == current_char:
                current_texts_for_char_run.append(text_block_as_single_string)
            else:
                if current_texts_for_char_run:
                    run_lines, _ = self.optimal_merge_run(current_texts_for_char_run)
                    lines_per_character[current_char] += run_lines
                    total_lines_in_take += run_lines
                current_char = person
                current_texts_for_char_run = [text_block_as_single_string]
        
        if current_texts_for_char_run:
            run_lines, _ = self.optimal_merge_run(current_texts_for_char_run)
            lines_per_character[current_char] += run_lines
            total_lines_in_take += run_lines

        character_exceeded_max_consecutive = any(lines > self.max_consecutive_lines_per_character 
                                                 for lines in lines_per_character.values())
        
        return total_lines_in_take, character_exceeded_max_consecutive

    def check_duration(self, blocks_segment):
        if not blocks_segment: return True
        start = blocks_segment[0]["in_time"]
        end = blocks_segment[-1]["out_time"]
        return (end - start) <= self.max_duration

    def check_inter_intervention_silence(self, blocks_segment):
        """
        Comprueba que el silencio entre bloques de diálogo consecutivos en un segmento
        no exceda el máximo permitido.
        """
        for i in range(len(blocks_segment) - 1):
            current_block_out_time = blocks_segment[i]["out_time"]
            next_block_in_time = blocks_segment[i+1]["in_time"]
            
            silence_duration = next_block_in_time - current_block_out_time
            
            if silence_duration > self.max_silence_between_interventions:
                return False
        
        return True

    def is_segment_feasible(self, blocks_segment):
        if not blocks_segment: return False
        
        if not self.check_duration(blocks_segment):
            return False

        if not self.check_inter_intervention_silence(blocks_segment):
            return False

        # El chequeo de líneas ahora usa la lógica de fusión optimizada
        segment_total_lines, character_exceeded_consecutive = self.unify_and_check(blocks_segment)
        
        if segment_total_lines > self.max_lines_per_take:
            return False

        if character_exceeded_consecutive:
            return False
            
        return True

    def group_dialogues_simultaneous_dp(self, data):
        blocks = []
        data_copy = data.copy()
        data_copy['IN_str'] = data_copy['IN'].astype(str)
        data_copy['OUT_str'] = data_copy['OUT'].astype(str)

        grupos = data_copy.groupby(["SCENE", "IN_str", "OUT_str"])
        for (scene, in_time_str, out_time_str), grupo in grupos:
            block = {}
            block["scene"] = scene
            block["in_time_str"] = in_time_str
            block["out_time_str"] = out_time_str
            try:
                block["in_time"] = self.parse_time(in_time_str)
                block["out_time"] = self.parse_time(out_time_str)
            except ValueError as e:
                print(f"Advertencia: Saltando bloque debido a error de parse_time en group_dialogues: {e} para {scene}, {in_time_str}, {out_time_str}")
                continue

            dialogues = []
            total_lines_in_block = 0
            for _, row in grupo.iterrows():
                personaje = row["PERSONAJE"]
                texto = str(row["EUSKERA"])
                lines = self.expand_dialogue(texto)
                dialogues.append({"personaje": personaje, "lines": lines})
                total_lines_in_block += len(lines)
            block["dialogues"] = dialogues
            block["total_lines"] = total_lines_in_block
            block["characters"] = set(d["personaje"] for d in dialogues)
            blocks.append(block)
        
        blocks.sort(key=lambda b: (b["scene"], b["in_time"]))
        return blocks

    def partition_scene_blocks(self, blocks):
        n = len(blocks)
        dp = [float("inf")] * (n + 1)
        partition_index = [-1] * (n + 1)
        dp[0] = 0
        
        for i in range(n):
            if dp[i] == float("inf"): continue
            for j in range(i, n):
                segment = blocks[i:j+1]
                if not self.is_segment_feasible(segment):
                    # Como is_segment_feasible ahora es más preciso, este break
                    # se activará solo cuando sea realmente imposible continuar.
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
        if dp[n] == float("inf"):
            messagebox.showwarning("Partición Imposible", 
                                   f"No se pudo encontrar una partición válida para todos los bloques de la escena {blocks[0]['scene'] if blocks else 'desconocida'} "
                                   f"bajo las restricciones actuales. Esta escena podría no aparecer en los resultados o estar incompleta.")
            return [], float("inf")

        while idx > 0:
            start = partition_index[idx]
            if start == -1:
                messagebox.showerror("Error de Partición", "Error al reconstruir la partición.")
                return [], float("inf")
            segments.append((start, idx))
            idx = start
        segments.reverse()
        return segments, dp[n]


    def _fuse_run_texts(self, texts_list_of_lists_of_lines):
        """
        Fusiona una lista de intervenciones (donde cada intervención es una lista de líneas)
        en una única lista de líneas finales, usando el separador " _ ".
        """
        # Une las líneas de cada intervención individual en un solo string
        full_texts_for_run = [" ".join(lines_list) for lines_list in texts_list_of_lists_of_lines]
        # MODIFICADO: Une las diferentes intervenciones con el separador " _ "
        merged_text_complete = " _ ".join(full_texts_for_run)
        # Vuelve a expandir el texto completamente fusionado en líneas según el max_chars_per_line
        return self.expand_dialogue(merged_text_complete)

    def generate_detail(self, blocks_with_takes):
        from collections import defaultdict
        detail_rows = []
        
        scene_take_map = defaultdict(list)
        for block in blocks_with_takes:
            if "take" not in block: continue
            scene_take_map[(block["scene"], block["take"])].append(block)
        
        for (scene, take_num), blocks_in_this_take in scene_take_map.items():
            blocks_in_this_take.sort(key=lambda b: b["in_time"])
            
            interventions_in_take = []
            for block in blocks_in_this_take:
                for dialogue in block["dialogues"]:
                    interventions_in_take.append({
                        "personaje": dialogue["personaje"],
                        "lines_original_expansion": dialogue["lines"],
                        "in_str": block["in_time_str"],
                        "out_str": block["out_time_str"]
                    })
            
            if not interventions_in_take:
                continue

            final_output_lines_for_take = []
            current_run_for_char = []

            for i, interv in enumerate(interventions_in_take):
                if not current_run_for_char or interv["personaje"] == current_run_for_char[-1]["personaje"]:
                    current_run_for_char.append(interv)
                else:
                    char_of_run = current_run_for_char[0]["personaje"]
                    texts_to_fuse = [r["lines_original_expansion"] for r in current_run_for_char]
                    # La fusión para la salida final ahora usa la nueva lógica
                    fused_lines = self._fuse_run_texts(texts_to_fuse)
                    
                    run_in_time = current_run_for_char[0]["in_str"]
                    run_out_time = current_run_for_char[-1]["out_str"]
                    for line_text in fused_lines:
                        final_output_lines_for_take.append({
                            "SCENE": scene, "TAKE": take_num, "PERSONAJE": char_of_run,
                            "EUSKERA": line_text, "IN": run_in_time, "OUT": run_out_time
                        })
                    current_run_for_char = [interv]

            if current_run_for_char:
                char_of_run = current_run_for_char[0]["personaje"]
                texts_to_fuse = [r["lines_original_expansion"] for r in current_run_for_char]
                 # La fusión para la salida final ahora usa la nueva lógica
                fused_lines = self._fuse_run_texts(texts_to_fuse)
                run_in_time = current_run_for_char[0]["in_str"]
                run_out_time = current_run_for_char[-1]["out_str"]
                for line_text in fused_lines:
                    final_output_lines_for_take.append({
                        "SCENE": scene, "TAKE": take_num, "PERSONAJE": char_of_run,
                        "EUSKERA": line_text, "IN": run_in_time, "OUT": run_out_time
                    })
            
            detail_rows.extend(final_output_lines_for_take)

        if not detail_rows: return pd.DataFrame()

        df_detail = pd.DataFrame(detail_rows)
        def safe_parse_time_for_sort(time_str):
            try:
                return self.parse_time(time_str)
            except ValueError:
                return float('inf')

        if not df_detail.empty:
            df_detail['sort_key_in_time'] = df_detail['IN'].apply(safe_parse_time_for_sort)
            df_detail = df_detail.sort_values(by=["SCENE", "TAKE", "sort_key_in_time"]).drop(columns=['sort_key_in_time'])
        
        return df_detail


    def generate_summary(self, blocks_with_takes):
        resumen = {}
        processed_takes_count = 0
        
        for block in blocks_with_takes:
            take = block.get("take", None)
            if take is None: continue

            processed_takes_count = max(processed_takes_count, take if isinstance(take, int) else 0)

            for p in block["characters"]:
                if p not in resumen:
                    resumen[p] = set()
                resumen[p].add(take)
        
        resumen_rows = []
        total_sum_of_takes_per_character = 0
        
        sorted_characters = sorted(resumen.keys())

        for p in sorted_characters:
            num_takes_for_char = len(resumen[p])
            resumen_rows.append({"PERSONAJE": p, "TAKES (apariciones)": num_takes_for_char})
            total_sum_of_takes_per_character += num_takes_for_char
        
        resumen_rows.append({"PERSONAJE": "TOTAL SUMA APARICIONES", "TAKES (apariciones)": total_sum_of_takes_per_character})

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
            
            segments_indices, scene_total_cost = self.partition_scene_blocks(scene_blocks)
            
            if scene_total_cost == float("inf"):
                print(f"Advertencia: La escena {scene} no pudo ser particionada y no se incluirá en los takes.")
                final_blocks_with_takes_assigned.extend(scene_blocks)
                continue

            for start_idx, end_idx_plus_one in segments_indices:
                for block_idx_in_scene in range(start_idx, end_idx_plus_one):
                    scene_blocks[block_idx_in_scene]["take"] = global_take_counter
                global_take_counter += 1
            final_blocks_with_takes_assigned.extend(scene_blocks)
        
        blocks_successfully_assigned_to_takes = [b for b in final_blocks_with_takes_assigned if "take" in b]

        detail_df = self.generate_detail(blocks_successfully_assigned_to_takes)
        summary_df, max_take_num_generated = self.generate_summary(blocks_successfully_assigned_to_takes)
        
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