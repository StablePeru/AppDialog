# guion_editor/utils/takeo_optimizer_logic.py
import pandas as pd
import re
from collections import defaultdict

class TakeoOptimizerLogic:
    def __init__(self, config: dict):
        self.max_duration = config.get('max_duration', 30)
        self.max_lines_per_take = config.get('max_lines_per_take', 10)
        self.max_consecutive_lines_per_character = config.get('max_consecutive_lines_per_character', 5)
        self.max_chars_per_line = config.get('max_chars_per_line', 60)
        self.max_silence_between_interventions = config.get('max_silence_between_interventions', 10)
        self.frame_rate = config.get('frame_rate', 25)

        self.problematic_interventions_report = []
        self.segmentation_failures_report = []
        self.actual_takes_generated = 0

    def run_optimization(self, script_data: pd.DataFrame, selected_characters: list, dialogue_source_column: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        if script_data is None or script_data.empty or dialogue_source_column not in script_data.columns:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        self._check_individual_interventions(script_data, dialogue_source_column)
        
        filtered_data = script_data[script_data['PERSONAJE'].isin(selected_characters)].copy()
        if filtered_data.empty:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
            
        detail_df, summary_df = self._create_optimized_takes_dp(filtered_data, dialogue_source_column)
        
        failures_df = pd.DataFrame()
        if self.segmentation_failures_report:
            failures_df = pd.DataFrame(self.segmentation_failures_report).drop_duplicates()

        return detail_df, summary_df, failures_df

    def parse_time(self, time_str):
        parts = str(time_str).split(':')
        if len(parts) == 3: hh, mm, ss = map(int, parts); return hh * 3600 + mm * 60 + ss
        elif len(parts) == 4: hh, mm, ss, ff = map(int, parts); return hh * 3600 + mm * 60 + ss + ff / self.frame_rate
        else: raise ValueError(f"Formato de tiempo inválido: '{time_str}'. Se esperaba HH:MM:SS o HH:MM:SS:FF.")
    
    def _get_effective_len(self, text):
        parentheticals = re.findall(r'\([^)]*\)', text)
        return len(text) - sum(len(p) for p in parentheticals) + len(parentheticals)

    def expand_dialogue(self, text):
        lines, current_line = [], ""
        for word in str(text).split():
            if not current_line: current_line = word
            elif self._get_effective_len(f"{current_line} {word}") > self.max_chars_per_line: lines.append(current_line); current_line = word
            else: current_line += " " + word
        if current_line: lines.append(current_line)
        return lines

    def _check_individual_interventions(self, script_data, dialogue_source_column: str):
        self.problematic_interventions_report = []
        if script_data is None: return
        for index, row in script_data.iterrows():
            # -> MODIFICADO
            dialogue_text = str(row[dialogue_source_column])
            details = {"SCENE": row.get('SCENE', 'N/A'), "PERSONAJE": row['PERSONAJE'], "IN": str(row['IN']), "OUT": str(row['OUT']), f"{dialogue_source_column}_Snippet": dialogue_text[:70] + "..."}
            try:
                duration = self.parse_time(row['OUT']) - self.parse_time(row['IN'])
                if duration > self.max_duration:
                    self.problematic_interventions_report.append({**details, "PROBLEMA_TIPO": "Duración Excesiva", "DETALLE": f"Duración ({duration:.2f}s) > max ({self.max_duration}s)."})
                # -> MODIFICADO
                num_lines = len(self.expand_dialogue(dialogue_text))
                if num_lines > self.max_lines_per_take:
                    self.problematic_interventions_report.append({**details, "PROBLEMA_TIPO": "Líneas Excesivas", "DETALLE": f"Líneas ({num_lines}) > max ({self.max_lines_per_take})."})
            except Exception as e:
                self.problematic_interventions_report.append({**details, "PROBLEMA_TIPO": "Error de Procesamiento", "DETALLE": str(e)})

    def unify_and_check(self, blocks_segment):
        interventions = [(d["personaje"], " ".join(d["lines"])) for b in blocks_segment for d in b["dialogues"]]
        if not interventions: return 0, False
        lines_per_char, total_lines = defaultdict(int), 0
        current_char, char_run_texts = None, []
        for person, text in interventions:
            if person == current_char: char_run_texts.append(text)
            else:
                if char_run_texts:
                    run_lines = len(self.expand_dialogue(" _ ".join(char_run_texts))); lines_per_char[current_char] += run_lines; total_lines += run_lines
                current_char, char_run_texts = person, [text]
        if char_run_texts:
            run_lines = len(self.expand_dialogue(" _ ".join(char_run_texts))); lines_per_char[current_char] += run_lines; total_lines += run_lines
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

    def group_dialogues_simultaneous_dp(self, data, dialogue_source_column: str):
        blocks = []
        data_copy = data.copy()
        data_copy['IN_str'] = data_copy['IN'].astype(str)
        data_copy['OUT_str'] = data_copy['OUT'].astype(str)
        for (scene, in_str, out_str), group in data_copy.groupby(["SCENE", "IN_str", "OUT_str"]):
            try:
                block = {"scene": scene, "in_time_str": in_str, "out_time_str": out_str, "in_time": self.parse_time(in_str), "out_time": self.parse_time(out_str)}
                # -> LÍNEA CLAVE MODIFICADA
                dialogues = [{"personaje": row["PERSONAJE"], "lines": self.expand_dialogue(str(row[dialogue_source_column]))} for _, row in group.iterrows()]
                block["dialogues"], block["characters"] = dialogues, {d["personaje"] for d in dialogues}
                blocks.append(block)
            except ValueError as e:
                print(f"Advertencia: Saltando bloque con tiempo inválido '{in_str}' o '{out_str}': {e}")
        blocks.sort(key=lambda b: (b["scene"], b["in_time"]))
        return blocks

    def partition_scene_blocks(self, blocks):
        n = len(blocks); dp, p_idx = [float("inf")] * (n + 1), [-1] * (n + 1); dp[0] = 0
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
        if dp[n] == float("inf"): return [], float("inf")
        while idx > 0: start = p_idx[idx]; segments.append((start, idx)); idx = start
        segments.reverse(); return segments, dp[n]

    def _fuse_run_texts(self, texts_list_of_lists):
        return self.expand_dialogue(" _ ".join(" ".join(lines) for lines in texts_list_of_lists))

    def generate_detail(self, blocks_with_takes, dialogue_source_column: str):
        rows = []
        df_blocks = pd.DataFrame(blocks_with_takes)
        
        for take, group_df in df_blocks.groupby("take"):
            group_records = sorted(group_df.to_dict('records'), key=lambda x: x['in_time'])
            interventions = [{"char": d["personaje"], "lines": d["lines"], "in": b["in_time_str"], "out": b["out_time_str"]} for b in group_records for d in b["dialogues"]]
            if not interventions: continue
            
            run = []
            for interv in interventions:
                if not run or interv["char"] == run[-1]["char"]:
                    run.append(interv)
                else:
                    fused_lines = self._fuse_run_texts([r["lines"] for r in run])
                    for line in fused_lines:
                        row_data = {"TAKE": take, "PERSONAJE": run[0]["char"], dialogue_source_column: line, "IN": run[0]["in"], "OUT": run[-1]["out"]}
                        rows.append(row_data)
                    run = [interv]
            
            if run:
                fused_lines = self._fuse_run_texts([r["lines"] for r in run])
                for line in fused_lines:
                    row_data = {"TAKE": take, "PERSONAJE": run[0]["char"], dialogue_source_column: line, "IN": run[0]["in"], "OUT": run[-1]["out"]}
                    rows.append(row_data)

        if not rows: return pd.DataFrame()
        
        df = pd.DataFrame(rows)
        if dialogue_source_column not in df.columns:
            df[dialogue_source_column] = ""

        # --- INICIO DE LA LÓGICA DE ORDENACIÓN Y RENUMERACIÓN FINAL ---
        
        # 1. Crear columnas auxiliares para la ordenación cronológica.
        df['sort_key'] = df['IN'].apply(self.parse_time)
        df['take_start_time'] = df.groupby('TAKE')['sort_key'].transform('min')

        # 2. Ordenar el DataFrame cronológicamente.
        df_sorted = df.sort_values(by=["take_start_time", "sort_key"])

        # 3. Renumerar los takes para que sean secuenciales.
        #    Obtenemos los números de take únicos en su nuevo orden cronológico.
        chronological_take_order = df_sorted['TAKE'].unique()
        #    Creamos un mapa de traducción: {take_antiguo: take_nuevo, ...}
        #    Ej: {1: 1, 15: 2, 2: 3, 14: 4, ...}
        take_renumber_map = {old_take_num: new_take_num for new_take_num, old_take_num in enumerate(chronological_take_order, 1)}
        #    Aplicamos el mapa para reemplazar los números antiguos por los nuevos.
        df_sorted['TAKE'] = df_sorted['TAKE'].map(take_renumber_map)

        # 4. Eliminar las columnas auxiliares y devolver el resultado final.
        return df_sorted.drop(columns=['take_start_time', 'sort_key'])

    def generate_summary(self, blocks_with_takes):
        summary = defaultdict(set)
        for block in blocks_with_takes:
            if "take" in block:
                for p in block["characters"]: summary[p].add(block["take"])
        rows = [{"PERSONAJE": p, "TAKES (apariciones)": len(t)} for p, t in sorted(summary.items())]
        total = sum(row["TAKES (apariciones)"] for row in rows)
        rows.append({"PERSONAJE": "TOTAL SUMA APARICIONES", "TAKES (apariciones)": total})
        return pd.DataFrame(rows)

    def _create_optimized_takes_dp(self, data, dialogue_source_column: str):
        blocks_by_scene = defaultdict(list)
        # 1. Agrupar diálogos por escena
        for block in self.group_dialogues_simultaneous_dp(data, dialogue_source_column):
            blocks_by_scene[block["scene"]].append(block)

        # --- INICIO DE LA LÓGICA CORREGIDA ---
        counter, final_blocks = 1, []
        for scene in sorted(blocks_by_scene.keys()):
            scene_blocks = blocks_by_scene[scene]
            # 2. Particionar los bloques de cada escena en takes óptimos
            segments, _ = self.partition_scene_blocks(scene_blocks)
            
            # Si la partición falla, segments estará vacío
            if not segments and scene_blocks:
                 print(f"Advertencia: No se pudo encontrar una partición válida para la escena {scene}.")
                 # Opcionalmente, podrías querer manejar esto de forma más explícita
                 continue

            # 3. Asignar el número de take (counter) a cada segmento
            for start, end in segments:
                for i in range(start, end):
                    scene_blocks[i]["take"] = counter
                counter += 1 # Incrementar el contador para el siguiente take
            
            final_blocks.extend(scene_blocks)
        # --- FIN DE LA LÓGICA CORREGIDA ---

        assigned = [b for b in final_blocks if "take" in b]
        detail_df = self.generate_detail(assigned, dialogue_source_column)
        summary_df = self.generate_summary(assigned)
        
        # Guardar el número total de takes generados
        self.actual_takes_generated = detail_df['TAKE'].max() if not detail_df.empty and 'TAKE' in detail_df.columns else 0
        
        return detail_df, summary_df