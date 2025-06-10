# Takeo/script_optimizer_logic.py
import os
import pandas as pd
import re
from collections import defaultdict

class ScriptOptimizerLogic:
    def __init__(self):
        # Configuración por defecto - estos serán seteados por la UI
        self.max_duration = 30
        self.max_lines_per_take = 10
        self.max_consecutive_lines_per_character = 5
        self.max_chars_per_line = 60
        self.frame_rate = 25  # fps para tiempos con frames
        
        self.script_data = None
        # self.selected_characters ya no es un atributo de clase, se pasa como parámetro

    def set_configuration(self, config_dict):
        """La UI llamará a esto para pasar la configuración."""
        try:
            self.max_duration = int(config_dict.get('max_duration', self.max_duration))
            self.max_lines_per_take = int(config_dict.get('max_lines_per_take', self.max_lines_per_take))
            self.max_consecutive_lines_per_character = int(config_dict.get('max_consecutive_lines_per_character', self.max_consecutive_lines_per_character))
            self.max_chars_per_line = int(config_dict.get('max_chars_per_line', self.max_chars_per_line))
            
            if not (self.max_duration > 0 and \
                    self.max_lines_per_take > 0 and \
                    self.max_consecutive_lines_per_character > 0 and \
                    self.max_chars_per_line > 0):
                raise ValueError("Todos los valores de configuración deben ser números positivos.")

        except ValueError as e:
            # Re-lanzar para que la UI lo maneje
            raise ValueError(f"Error en valor de configuración: {e}")


    def load_script_data(self, file_path):
        """
        Carga y valida el guion. 
        Retorna (lista_personajes, mensaje_formato_tiempo, problematic_interventions_report, line_count) 
        o lanza excepción.
        """
        try:
            self.script_data = pd.read_excel(file_path)
            required_columns = ['IN', 'OUT', 'PERSONAJE', 'EUSKERA', 'SCENE']
            missing_cols = [col for col in required_columns if col not in self.script_data.columns]
            if missing_cols:
                raise ValueError(f"Columnas requeridas faltantes: {', '.join(missing_cols)}.")

            problematic_interventions = self._check_individual_interventions_logic()

            in_sample = str(self.script_data['IN'].iloc[0]) if not self.script_data.empty else "N/A"
            out_sample = str(self.script_data['OUT'].iloc[0]) if not self.script_data.empty else "N/A"
            time_format_msg = (
                f"Formato de tiempos detectado (primera línea):\nIN: {in_sample}\nOUT: {out_sample}\n\n"
                "Asegúrese de que su Excel contiene columnas IN y OUT con formatos correctos (HH:MM:SS o HH:MM:SS:FF)."
            )
            
            characters = sorted(list(self.script_data['PERSONAJE'].unique())) if not self.script_data.empty else []
            return characters, time_format_msg, problematic_interventions, len(self.script_data)

        except Exception as e:
            self.script_data = None # Resetear en caso de error
            # Envolver la excepción original en una más genérica para la UI si es necesario,
            # o dejar que la excepción original se propague.
            raise RuntimeError(f"Error al cargar el archivo '{os.path.basename(file_path)}': {str(e)}")


    def _check_individual_interventions_logic(self):
        """
        Chequea cada intervención individual contra las normas.
        Retorna una lista de diccionarios, cada uno representando un problema.
        """
        if self.script_data is None:
            return [] # No hay datos para chequear
        
        problem_report = []
        for index, row in self.script_data.iterrows():
            intervention_details_base = {
                "SCENE": row.get('SCENE', 'N/A'),
                "PERSONAJE": row['PERSONAJE'],
                "IN": str(row['IN']),
                "OUT": str(row['OUT']),
                "EUSKERA_Snippet": str(row["EUSKERA"])[:70] + ("..." if len(str(row["EUSKERA"])) > 70 else ""),
                "ROW_INDEX_EXCEL": index + 2 # +1 por header, +1 por index 0-based
            }
            try:
                in_time_s = self.parse_time(row['IN'])
                out_time_s = self.parse_time(row['OUT'])
                duration = out_time_s - in_time_s
                
                if duration > self.max_duration:
                    entry = intervention_details_base.copy()
                    entry.update({
                        "PROBLEMA_TIPO": "Duración Excesiva Individual",
                        "DETALLE": f"Duración ({duration:.2f}s) excede el máximo para un take ({self.max_duration}s)."
                    })
                    problem_report.append(entry)

                expanded_lines = self.expand_dialogue(str(row["EUSKERA"]))
                num_expanded_lines = len(expanded_lines)

                if num_expanded_lines > self.max_lines_per_take: # Usamos max_lines_per_take como límite
                    entry = intervention_details_base.copy()
                    entry.update({
                        "PROBLEMA_TIPO": "Demasiadas Líneas Individuales",
                        "DETALLE": f"Intervención genera {num_expanded_lines} líneas (límite basado en máx. líneas por take: {self.max_lines_per_take}, con {self.max_chars_per_line} caract./línea)."
                    })
                    problem_report.append(entry)
            
            except ValueError as ve: # Errores de parse_time
                entry = intervention_details_base.copy()
                entry.update({
                    "PROBLEMA_TIPO": "Error de Formato de Tiempo",
                    "DETALLE": str(ve)
                })
                problem_report.append(entry)
            except Exception as e: # Otros errores inesperados
                entry = intervention_details_base.copy()
                entry.update({
                    "PROBLEMA_TIPO": "Error Inesperado en Chequeo Individual",
                    "DETALLE": str(e)
                })
                problem_report.append(entry)
        return problem_report


    def process_script_logic(self, selected_characters_list):
        """
        Procesa el guion con los personajes seleccionados.
        Retorna (detail_df, summary_df, stats_dict) o lanza excepción.
        """
        if self.script_data is None:
            raise ValueError("No hay guion cargado para procesar.")
        
        if not selected_characters_list: # selected_characters_list es la lista de la UI
            raise ValueError("Debe seleccionar al menos un personaje para procesar.")
            
        filtered_data = self.script_data[self.script_data['PERSONAJE'].isin(selected_characters_list)].copy()
        
        if filtered_data.empty:
            raise ValueError("No hay líneas para los personajes seleccionados en el guion cargado.")
        
        try:
            detail_df, summary_df, actual_takes_generated = self.create_optimized_takes_dp(filtered_data)

            sum_takes_personaje_val = "N/A"
            if not summary_df.empty and "TAKES (apariciones)" in summary_df.columns and \
               summary_df.iloc[-1]["PERSONAJE"] == "TOTAL SUMA APARICIONES":
                sum_takes_personaje_val = summary_df.iloc[-1]["TAKES (apariciones)"]
            
            stats = {
                "total_takes": actual_takes_generated,
                "sum_takes_char_appearances": sum_takes_personaje_val
            }
            return detail_df, summary_df, stats
        except Exception as e:
            # import traceback # Descomentar para debugging detallado en consola
            # traceback.print_exc()
            raise RuntimeError(f"Error crítico durante el procesamiento del guion: {str(e)}")

    def parse_time(self, time_str):
        parts = str(time_str).split(':')
        try:
            if len(parts) == 3:
                hh, mm, ss = map(int, parts)
                return hh * 3600 + mm * 60 + ss
            elif len(parts) == 4:
                hh, mm, ss, ff = map(int, parts)
                if not (0 <= ff < self.frame_rate): # Validación de frames
                     raise ValueError(f"Valor de frames '{ff}' fuera de rango (0-{self.frame_rate-1}).")
                return hh * 3600 + mm * 60 + ss + ff / self.frame_rate
            else:
                raise ValueError("Formato incorrecto. Se esperaba HH:MM:SS o HH:MM:SS:FF.")
        except ValueError as e: # Captura errores de map(int, parts) también
            raise ValueError(f"Tiempo inválido '{time_str}': {e}")


    def expand_dialogue(self, text):
        tokens = []
        # La expresión regular separa los grupos que empiecen con '(' y terminen con ')'
        parts = re.split(r'(\([^)]*\))', text)
        for part in parts:
            if not part.strip():
                continue
            # Si el fragmento es un grupo de paréntesis (sin espacios adicionales)
            if re.fullmatch(r'\([^)]*\)', part.strip()):
                tokens.append((part.strip(), True)) # True indica que es parentético
            else:
                # Para el resto, separamos en palabras
                for word in part.split():
                    if word: # Evitar palabras vacías si hay múltiples espacios
                        tokens.append((word, False))
        
        lines = []
        current_line_tokens = []
        current_effective_length = 0
        
        for token_text, is_paren_group in tokens:
            addition = 0
            if not current_line_tokens: # Primer token en la línea
                addition = 1 if is_paren_group else len(token_text)
            else: # No es el primer token
                prev_is_paren = current_line_tokens[-1][1]
                if is_paren_group:
                    addition = 0 if prev_is_paren else 1 # Solo +1 si el anterior NO era paréntesis
                else: # Token actual no es parentético
                    # Espacio + longitud_palabra, a menos que el anterior fuera parentético (ya contó "1")
                    addition = len(token_text) if prev_is_paren else (1 + len(token_text)) 
            
            if current_line_tokens and (current_effective_length + addition > self.max_chars_per_line):
                lines.append(" ".join(t for t, _ in current_line_tokens))
                current_line_tokens = [(token_text, is_paren_group)]
                current_effective_length = 1 if is_paren_group else len(token_text) # Longitud del primer token de la nueva línea
            else:
                current_line_tokens.append((token_text, is_paren_group))
                current_effective_length += addition
        
        if current_line_tokens:
            lines.append(" ".join(t for t, _ in current_line_tokens))
        
        return lines if lines else [""] # Asegurar que siempre devuelve una lista, incluso para texto vacío


    def optimal_merge_run(self, texts):
        n = len(texts)
        if n == 0:
            return 0, []
        dp = [float("inf")] * (n + 1)
        segmentation_result = [None] * (n + 1) # Guarda las líneas segmentadas
        dp[0] = 0
        segmentation_result[0] = []

        for i in range(1, n + 1):
            for j in range(i):
                # Se unen las intervenciones de texts[j] a texts[i-1]
                merged_text_for_segment = " ".join(texts[j:i])
                expanded_lines_for_segment = self.expand_dialogue(merged_text_for_segment)
                cost = len(expanded_lines_for_segment)
                
                if dp[j] + cost < dp[i]:
                    dp[i] = dp[j] + cost
                    # segmentation_result[i] = segmentation_result[j] + [expanded_lines_for_segment]
                    # Corrección: No anidar listas de listas de líneas si solo queremos el resultado final
                    # Si queremos la segmentación exacta de cómo se formó, la línea anterior es correcta.
                    # Si solo queremos las líneas resultantes de esta fusión óptima, es diferente.
                    # La función está pensada para retornar (costo, lista_de_segmentos_fusionados_y_expandidos)
                    temp_segmentation = list(segmentation_result[j]) # Copia para no modificar la anterior
                    temp_segmentation.append(expanded_lines_for_segment) # Añade el nuevo segmento de líneas
                    segmentation_result[i] = temp_segmentation

        return dp[n], segmentation_result[n]


    def unify_and_check(self, blocks_segment):
        """
        Fusiona óptimamente intervenciones del mismo personaje DENTRO del segmento de bloques.
        Calcula:
        - total_lines_after_char_merge: líneas totales tras esta fusión óptima de corridas de personaje.
        - character_exceeded_consecutive: True si algún personaje excede max_consecutive_lines_per_character.
        """
        interventions = [] # (personaje, texto_completo_original_de_la_intervencion)
        for block in blocks_segment:
            for d_dialogue in block["dialogues"]: # d_dialogue es {'personaje': P, 'lines': [l1,l2]}
                # Unimos las líneas originales de esta intervención para optimal_merge_run
                original_text_of_intervention = " ".join(d_dialogue["lines"])
                interventions.append((d_dialogue["personaje"], original_text_of_intervention))
        
        if not interventions:
            return 0, False

        lines_per_character_after_optimal_merge = defaultdict(int)
        current_char_for_run = interventions[0][0]
        texts_for_current_char_run = []
        
        total_lines_after_char_merge = 0

        for person, text_intervention in interventions:
            if person == current_char_for_run:
                texts_for_current_char_run.append(text_intervention)
            else:
                # Procesar la corrida del personaje anterior
                if texts_for_current_char_run:
                    run_line_count, _ = self.optimal_merge_run(texts_for_current_char_run)
                    lines_per_character_after_optimal_merge[current_char_for_run] += run_line_count
                    total_lines_after_char_merge += run_line_count
                
                # Iniciar nueva corrida
                current_char_for_run = person
                texts_for_current_char_run = [text_intervention]
        
        # Procesar la última corrida
        if texts_for_current_char_run:
            run_line_count, _ = self.optimal_merge_run(texts_for_current_char_run)
            lines_per_character_after_optimal_merge[current_char_for_run] += run_line_count
            total_lines_after_char_merge += run_line_count

        character_exceeded_consecutive = any(
            lines > self.max_consecutive_lines_per_character 
            for lines in lines_per_character_after_optimal_merge.values()
        )
        
        return total_lines_after_char_merge, character_exceeded_consecutive


    def check_duration(self, blocks_segment):
        if not blocks_segment: return True 
        start_time = blocks_segment[0]["in_time"]
        end_time = blocks_segment[-1]["out_time"] # Asume bloques ordenados por tiempo
        return (end_time - start_time) <= self.max_duration

    def is_segment_feasible(self, blocks_segment):
        if not blocks_segment: return False 
        
        if not self.check_duration(blocks_segment):
            return False

        # Chequeo 1: Total de líneas del segmento (suma de líneas expandidas de cada intervención individualmente)
        # no debe exceder max_lines_per_take.
        # 'total_lines' en cada bloque ya es len(self.expand_dialogue(texto_original_intervencion))
        current_segment_total_lines = sum(b['total_lines'] for b in blocks_segment)
        if current_segment_total_lines > self.max_lines_per_take:
            return False

        # Chequeo 2: Líneas consecutivas por personaje DENTRO del segmento,
        # después de fusionar óptimamente las corridas de un mismo personaje en ESE segmento.
        # La función unify_and_check hace esto.
        # El primer valor de retorno de unify_and_check (total_lines_after_char_merge) no se usa aquí
        # para la restricción de max_lines_per_take, ya que esa se evaluó arriba.
        _, character_exceeded_consecutive = self.unify_and_check(blocks_segment)
        if character_exceeded_consecutive:
            return False
            
        return True

    def group_dialogues_simultaneous_dp(self, data_df):
        """
        Agrupa diálogos por SCENE, IN, OUT. 'data_df' es el DataFrame filtrado.
        """
        blocks = []
        # Copiar para evitar SettingWithCopyWarning si se modifica data_df
        df_copy = data_df.copy()
        df_copy['IN_str'] = df_copy['IN'].astype(str)
        df_copy['OUT_str'] = df_copy['OUT'].astype(str)

        # Agrupar por escena y tiempos como strings para evitar problemas de precisión con floats
        grouped_by_time = df_copy.groupby(["SCENE", "IN_str", "OUT_str"])
        
        for (scene, in_time_str, out_time_str), group_df in grouped_by_time:
            block_data = {}
            block_data["scene"] = scene
            block_data["in_time_str"] = in_time_str
            block_data["out_time_str"] = out_time_str
            try:
                block_data["in_time"] = self.parse_time(in_time_str)
                block_data["out_time"] = self.parse_time(out_time_str)
            except ValueError as e:
                # Si un tiempo es inválido, este bloque no se puede procesar.
                # Podríamos registrar esto o lanzar una advertencia específica.
                print(f"Advertencia (lógica): Saltando bloque en {scene} ({in_time_str}-{out_time_str}) debido a error de parse_time: {e}")
                continue 

            dialogues_in_block = []
            total_lines_for_this_block = 0
            for _, row in group_df.iterrows():
                personaje = row["PERSONAJE"]
                texto_euskera = str(row["EUSKERA"])
                expanded_lines_for_intervention = self.expand_dialogue(texto_euskera)
                
                dialogues_in_block.append({
                    "personaje": personaje, 
                    "lines": expanded_lines_for_intervention # Lista de líneas
                })
                total_lines_for_this_block += len(expanded_lines_for_intervention)
            
            block_data["dialogues"] = dialogues_in_block
            block_data["total_lines"] = total_lines_for_this_block # Suma de líneas de todas las intervenciones en este bloque
            block_data["characters"] = set(d["personaje"] for d in dialogues_in_block)
            blocks.append(block_data)
        
        # Ordenar bloques globalmente por escena y luego por tiempo de inicio
        blocks.sort(key=lambda b: (b.get("scene", ""), b.get("in_time", float('inf'))))
        return blocks

    def partition_scene_blocks(self, scene_blocks_list):
        """
        Particiona una lista de bloques (de la misma escena) en segmentos (takes).
        Retorna (lista_de_segmentos_indices, coste_total_escena).
        """
        n = len(scene_blocks_list)
        if n == 0:
            return [], 0
            
        dp_cost = [float("inf")] * (n + 1) # Costo mínimo para particionar los primeros k bloques
        partition_point_idx = [-1] * (n + 1) # Índice del inicio del último segmento en la partición óptima
        dp_cost[0] = 0
        
        for j in range(1, n + 1): # Consideramos particionar blocks[0...j-1]
            for i in range(1, j + 1): # El último segmento es blocks[i-1...j-1]
                current_segment_to_test = scene_blocks_list[i-1:j]
                
                if self.is_segment_feasible(current_segment_to_test):
                    # Calcular costo del segmento actual (número de personajes únicos)
                    segment_chars = set()
                    for block_in_segment in current_segment_to_test:
                        segment_chars.update(block_in_segment["characters"])
                    cost_current_segment = len(segment_chars)
                    
                    if dp_cost[i-1] != float("inf") and (dp_cost[i-1] + cost_current_segment < dp_cost[j]):
                        dp_cost[j] = dp_cost[i-1] + cost_current_segment
                        partition_point_idx[j] = i-1 # El segmento empieza en i-1
        
        if dp_cost[n] == float("inf"):
            # No se pudo encontrar una partición válida para esta escena
            return [], float("inf") 

        # Reconstruir la partición
        segments_indices = []
        current_idx = n
        while current_idx > 0:
            start_of_segment_idx = partition_point_idx[current_idx]
            if start_of_segment_idx == -1 and current_idx > 0: # Error si no se inicializó bien
                 raise Exception(f"Error reconstruyendo partición para escena. Idx: {current_idx}, Punto: {start_of_segment_idx}")

            segments_indices.append((start_of_segment_idx, current_idx)) # Segmento es [start, current_idx-1]
            current_idx = start_of_segment_idx
        
        segments_indices.reverse() # Para tenerlos en orden cronológico
        return segments_indices, dp_cost[n]


    def _fuse_run_texts_for_final_output(self, list_of_dialogue_interventions_for_char):
        """
        Entrada: [{'personaje': P, 'lines_original_expansion': [l1,l2], 'in_str':T1, 'out_str':T2}, ...]
        Retorna la lista de líneas de texto finales tras fusionar las 'lines_original_expansion'.
        """
        # Extraer las listas de líneas de cada intervención
        texts_to_fuse_as_lists_of_lines = [interv["lines_original_expansion"] for interv in list_of_dialogue_interventions_for_char]
        
        # Unir las líneas de cada intervención para obtener el texto completo por intervención
        full_texts_strings_for_run = [" ".join(lines_list) for lines_list in texts_to_fuse_as_lists_of_lines]
        
        # Unir todos esos textos completos en un solo gran texto para la corrida
        merged_text_for_entire_run = " ".join(full_texts_strings_for_run)
        
        # Expandir este texto único
        return self.expand_dialogue(merged_text_for_entire_run)


    def generate_detail(self, final_blocks_with_take_numbers):
        """
        Genera el DataFrame de detalle con líneas fusionadas por personaje dentro de cada take.
        """
        detail_rows_list = []
        
        # Agrupar bloques por (escena, número de take)
        # Asegurarse que solo se procesan bloques que tienen un 'take' asignado
        takes_map = defaultdict(list)
        for block in final_blocks_with_take_numbers:
            if "take" in block: # Solo si el bloque fue asignado a un take
                takes_map[(block["scene"], block["take"])].append(block)
        
        for (scene_id, take_number), blocks_in_current_take in sorted(takes_map.items()):
            # Ordenar bloques dentro del take por su tiempo de inicio original
            blocks_in_current_take.sort(key=lambda b: b.get("in_time", float('inf')))
            
            # Recopilar todas las intervenciones del take en orden cronológico
            all_interventions_in_take = [] 
            for block_item in blocks_in_current_take:
                for dialogue_item in block_item["dialogues"]:
                    all_interventions_in_take.append({
                        "personaje": dialogue_item["personaje"],
                        "lines_original_expansion": dialogue_item["lines"], # Lista de líneas ya expandidas
                        "in_str": block_item["in_time_str"],
                        "out_str": block_item["out_time_str"]
                    })
            
            if not all_interventions_in_take:
                continue

            # Agrupar intervenciones consecutivas del MISMO personaje DENTRO de este take
            final_lines_for_take_output = []
            current_character_run = [] # Lista de diccionarios de intervención para la corrida actual

            for i, intervention_data in enumerate(all_interventions_in_take):
                if not current_character_run or \
                   intervention_data["personaje"] == current_character_run[-1]["personaje"]:
                    current_character_run.append(intervention_data)
                else:
                    # Personaje cambió, procesar la corrida anterior
                    character_of_the_run = current_character_run[0]["personaje"]
                    fused_text_lines_for_run = self._fuse_run_texts_for_final_output(current_character_run)
                    
                    run_start_time_str = current_character_run[0]["in_str"]
                    run_end_time_str = current_character_run[-1]["out_str"]
                    for single_line_text in fused_text_lines_for_run:
                        final_lines_for_take_output.append({
                            "SCENE": scene_id, "TAKE": take_number, "PERSONAJE": character_of_the_run,
                            "EUSKERA": single_line_text, "IN": run_start_time_str, "OUT": run_end_time_str
                        })
                    current_character_run = [intervention_data] # Iniciar nueva corrida

            # Procesar la última corrida acumulada del take
            if current_character_run:
                character_of_the_run = current_character_run[0]["personaje"]
                fused_text_lines_for_run = self._fuse_run_texts_for_final_output(current_character_run)
                run_start_time_str = current_character_run[0]["in_str"]
                run_end_time_str = current_character_run[-1]["out_str"]
                for single_line_text in fused_text_lines_for_run:
                    final_lines_for_take_output.append({
                        "SCENE": scene_id, "TAKE": take_number, "PERSONAJE": character_of_the_run,
                        "EUSKERA": single_line_text, "IN": run_start_time_str, "OUT": run_end_time_str
                    })
            
            detail_rows_list.extend(final_lines_for_take_output)

        if not detail_rows_list: 
            return pd.DataFrame(columns=["SCENE", "TAKE", "PERSONAJE", "EUSKERA", "IN", "OUT"])

        detail_df = pd.DataFrame(detail_rows_list)
        
        # Ordenar el DataFrame final por SCENE, TAKE, y luego por el IN original (como string es suficiente si el formato es consistente)
        # Para un ordenamiento temporal más robusto, convertir IN a segundos para la clave de ordenación
        # Pero esto puede ser lento para DFs grandes solo para ordenar.
        # Si los IN_str son consistentes (ej. HH:MM:SS:FF), el orden lexicográfico funciona.
        # Por ahora, asumimos que el orden de generación y `sorted(takes_map.items())` es suficiente.
        # Para ser más rigurosos:
        def get_sort_key(row_series):
            try:
                return self.parse_time(row_series['IN'])
            except ValueError:
                return float('inf') # Poner al final si hay error
        
        if not detail_df.empty:
             detail_df['temp_sort_in_seconds'] = detail_df.apply(get_sort_key, axis=1)
             detail_df = detail_df.sort_values(by=["SCENE", "TAKE", "temp_sort_in_seconds"])
             detail_df = detail_df.drop(columns=['temp_sort_in_seconds'])
        
        return detail_df


    def generate_summary(self, final_blocks_with_take_numbers):
        """
        Genera el DataFrame resumen.
        Retorna (summary_df, max_take_number_generated)
        """
        character_take_appearances = defaultdict(set)
        max_take_num = 0
        
        for block in final_blocks_with_take_numbers:
            take_num = block.get("take") # Solo procesar si tiene un take
            if take_num is None:
                continue

            max_take_num = max(max_take_num, take_num if isinstance(take_num, int) else 0)
            for char_name in block["characters"]:
                character_take_appearances[char_name].add(take_num)
        
        summary_rows = []
        total_sum_of_character_take_appearances = 0
        
        for char_name in sorted(character_take_appearances.keys()): # Ordenar alfabéticamente
            num_takes_for_char = len(character_take_appearances[char_name])
            summary_rows.append({"PERSONAJE": char_name, "TAKES (apariciones)": num_takes_for_char})
            total_sum_of_character_take_appearances += num_takes_for_char
        
        if summary_rows: # Solo añadir total si hay datos
            summary_rows.append({
                "PERSONAJE": "TOTAL SUMA APARICIONES", 
                "TAKES (apariciones)": total_sum_of_character_take_appearances
            })
        
        summary_df = pd.DataFrame(summary_rows)
        if summary_df.empty: # Asegurar columnas si está vacío
            summary_df = pd.DataFrame(columns=["PERSONAJE", "TAKES (apariciones)"])

        return summary_df, max_take_num


    def create_optimized_takes_dp(self, filtered_script_data):
        """
        Orquesta la creación de takes optimizados.
        Retorna (detail_df, summary_df, actual_takes_generated_count)
        """
        # 1. Agrupar diálogos simultáneos en bloques
        # Estos bloques ya tienen 'in_time' como segundos y 'lines' expandidas.
        initial_script_blocks = self.group_dialogues_simultaneous_dp(filtered_script_data)
        
        # 2. Agrupar bloques por escena
        blocks_grouped_by_scene = defaultdict(list)
        for block_item in initial_script_blocks:
            blocks_grouped_by_scene[block_item["scene"]].append(block_item)
        
        global_take_id_counter = 1
        all_final_blocks_with_takes = [] # Lista de todos los bloques, con un campo 'take' añadido
        
        # Procesar cada escena independientemente
        for scene_name in sorted(blocks_grouped_by_scene.keys()): # Ordenar escenas
            current_scene_blocks = blocks_grouped_by_scene[scene_name]
            # Los bloques dentro de la escena ya deberían estar ordenados por 'in_time'
            # desde group_dialogues_simultaneous_dp
            
            # 3. Particionar los bloques de la escena en takes (segmentos)
            # segments_indices es lista de tuplas (start_block_idx, end_block_idx_exclusive)
            segments_indices, scene_cost = self.partition_scene_blocks(current_scene_blocks)
            
            if scene_cost == float("inf"):
                # No se pudo particionar esta escena, se podría registrar
                print(f"Advertencia (lógica): Escena '{scene_name}' no pudo ser particionada completamente. "
                      f"Algunos bloques podrían no ser asignados a takes.")
                # Podríamos añadir los bloques sin 'take' para que el usuario sepa que existen
                # o simplemente omitirlos de los takes finales. Por ahora, los omitimos de la asignación de 'take'.
                all_final_blocks_with_takes.extend(current_scene_blocks) # Añadir sin 'take'
                continue

            for start_idx, end_idx_exclusive in segments_indices:
                for block_idx_in_scene_list in range(start_idx, end_idx_exclusive):
                    current_scene_blocks[block_idx_in_scene_list]["take"] = global_take_id_counter
                global_take_id_counter += 1
            all_final_blocks_with_takes.extend(current_scene_blocks) # Añadir bloques procesados de la escena
        
        # Filtrar solo bloques que realmente obtuvieron un número de take
        blocks_assigned_to_takes = [b for b in all_final_blocks_with_takes if "take" in b]

        # 4. Generar DataFrames de detalle y resumen
        detail_output_df = self.generate_detail(blocks_assigned_to_takes)
        summary_output_df, actual_number_of_takes_generated = self.generate_summary(blocks_assigned_to_takes)
        
        return detail_output_df, summary_output_df, actual_number_of_takes_generated