import os
import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


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
        
        # Iniciar interfaz
        self.root = tk.Tk()
        self.root.title("Optimizador de Takes para Guiones")
        self.root.geometry("800x600")
        self.create_ui()
    
    # ------------------------------
    # Interfaz Gráfica
    # ------------------------------
    def create_ui(self):
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Botón para cargar archivo
        load_btn = ttk.Button(main_frame, text="Cargar Guion (Excel)", command=self.load_script)
        load_btn.pack(pady=10)
        
        # Frame para configuración
        config_frame = ttk.LabelFrame(main_frame, text="Configuración", padding=10)
        config_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(config_frame, text="Duración máxima por take (segundos):").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.duration_var = tk.StringVar(value=str(self.max_duration))
        ttk.Entry(config_frame, textvariable=self.duration_var, width=10).grid(row=0, column=1, pady=5)
        
        ttk.Label(config_frame, text="Máximo de líneas por take:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.max_lines_var = tk.StringVar(value=str(self.max_lines_per_take))
        ttk.Entry(config_frame, textvariable=self.max_lines_var, width=10).grid(row=1, column=1, pady=5)
        
        ttk.Label(config_frame, text="Máximo de líneas del mismo personaje dentro de un take:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.max_consecutive_var = tk.StringVar(value=str(self.max_consecutive_lines_per_character))
        ttk.Entry(config_frame, textvariable=self.max_consecutive_var, width=10).grid(row=2, column=1, pady=5)
        
        ttk.Label(config_frame, text="Máximo de caracteres por línea:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.max_chars_var = tk.StringVar(value=str(self.max_chars_per_line))
        ttk.Entry(config_frame, textvariable=self.max_chars_var, width=10).grid(row=3, column=1, pady=5)
        
        # Frame para selección de personajes
        self.characters_frame = ttk.LabelFrame(main_frame, text="Selección de Personajes", padding=10)
        self.characters_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Botones de acción
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(action_frame, text="Seleccionar Todos", command=self.select_all_characters).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Deseleccionar Todos", command=self.deselect_all_characters).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Procesar Guion", command=self.process_script).pack(side=tk.RIGHT, padx=5)
    
    def load_script(self):
        """Cargar el archivo Excel del guion"""
        file_path = filedialog.askopenfilename(
            title="Seleccionar archivo Excel del guion",
            filetypes=[("Excel files", "*.xlsx *.xls")]
        )
        
        if not file_path:
            return
            
        try:
            # Cargar datos
            self.script_data = pd.read_excel(file_path)
            
            # Verificar columnas requeridas
            required_columns = ['IN', 'OUT', 'PERSONAJE', 'EUSKERA', 'SCENE']
            for col in required_columns:
                if col not in self.script_data.columns:
                    messagebox.showerror("Error", f"Columna requerida '{col}' no encontrada en el archivo.")
                    self.script_data = None
                    return
            
            # Mostrar muestra de formato de tiempos
            in_sample = str(self.script_data['IN'].iloc[0])
            out_sample = str(self.script_data['OUT'].iloc[0])
            
            messagebox.showinfo(
                "Formato de Tiempo", 
                f"Formato de tiempos detectado:\nIN: {in_sample}\nOUT: {out_sample}\n\n"
                "Si estos no son tiempos válidos, asegúrese de que su Excel contiene "
                "columnas IN y OUT con formatos de tiempo correctos (HH:MM:SS o HH:MM:SS:FF)."
            )
            
            # Mostrar selección de personajes
            self.populate_character_selection()
            
            messagebox.showinfo("Éxito", f"Guion cargado correctamente.\nNúmero de líneas: {len(self.script_data)}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar el archivo: {str(e)}")
            self.script_data = None

    def populate_character_selection(self):
        """Mostrar casillas de verificación para seleccionar personajes"""
        for widget in self.characters_frame.winfo_children():
            widget.destroy()
            
        if self.script_data is None:
            return
            
        characters = sorted(self.script_data['PERSONAJE'].unique())
        self.character_vars = {}
        
        # Se muestran en hasta 3 columnas
        num_chars = len(characters)
        num_cols = min(3, num_chars)
        
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
        for var in self.character_vars.values():
            var.set(True)
    
    def deselect_all_characters(self):
        for var in self.character_vars.values():
            var.set(False)
    
    # ------------------------------
    # Procesamiento y lógica de optimización
    # ------------------------------
    def process_script(self):
        """Procesar el guion y crear los takes optimizados"""
        if self.script_data is None:
            messagebox.showerror("Error", "No hay guion cargado.")
            return
            
        try:
            # Actualizar configuración desde la interfaz
            self.max_duration = int(self.duration_var.get())
            self.max_lines_per_take = int(self.max_lines_var.get())
            self.max_consecutive_lines_per_character = int(self.max_consecutive_var.get())
            self.max_chars_per_line = int(self.max_chars_var.get())
            
            # Obtener personajes seleccionados
            self.selected_characters = [
                char for char, var in self.character_vars.items() if var.get()
            ]
            
            if not self.selected_characters:
                messagebox.showerror("Error", "Debe seleccionar al menos un personaje.")
                return
                
            # Filtrar el DataFrame para los personajes seleccionados
            filtered_data = self.script_data[self.script_data['PERSONAJE'].isin(self.selected_characters)].copy()
            
            if filtered_data.empty:
                messagebox.showerror("Error", "No hay líneas para los personajes seleccionados.")
                return
                
            # Aplicar la optimización: agrupar diálogos simultáneos y particionar en takes usando programación dinámica
            detail_df, summary_df = self.create_optimized_takes_dp(filtered_data)
            
            # Guardar resultados en archivos Excel
            self.save_results(detail_df, summary_df)
            
        except Exception as e:
            messagebox.showerror("Error", f"Error al procesar el guion: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def parse_time(self, time_str):
        """
        Convierte una cadena con formato HH:MM:SS o HH:MM:SS:FF a segundos (float).
        """
        parts = str(time_str).split(':')
        if len(parts) == 3:
            hh, mm, ss = parts
            return int(hh) * 3600 + int(mm) * 60 + int(ss)
        elif len(parts) == 4:
            hh, mm, ss, ff = parts
            return int(hh) * 3600 + int(mm) * 60 + int(ss) + int(ff) / self.frame_rate
        else:
            raise ValueError("Formato de tiempo inválido: " + str(time_str))
    
    def expand_dialogue(self, text):
        """
        Divide el texto en líneas de hasta self.max_chars_per_line caracteres efectivos.
        La longitud efectiva se calcula ignorando el contenido de cualquier grupo entre paréntesis,
        de modo que:
          - Un grupo entre paréntesis (junto con los espacios inmediatamente adyacentes) cuenta como 1.
          - Si hay varios grupos consecutivos, se cuentan como 1 en total.
        
        Ejemplo:
          "Hola, soy un usuario" → 20 caracteres efectivos.
          "Hola, (por cierto) soy un usuario" → 20 caracteres efectivos.
          "Hola, (por cierto) (de verdad) (enserio) soy un usuario" → 20 caracteres efectivos.
        """
        import re
        # Separa el texto en tokens, manteniendo intactos los grupos entre paréntesis.
        tokens = []
        # La expresión regular separa los grupos que empiecen con '(' y terminen con ')'
        parts = re.split(r'(\([^)]*\))', text)
        for part in parts:
            if not part.strip():
                continue
            # Si el fragmento es un grupo de paréntesis (sin espacios adicionales)
            if re.fullmatch(r'\([^)]*\)', part.strip()):
                tokens.append((part.strip(), True))
            else:
                # Para el resto, separamos en palabras (asumiendo que los paréntesis ya quedaron aislados)
                for word in part.split():
                    tokens.append((word, False))
        
        lines = []
        current_line_tokens = []
        current_effective_length = 0
        
        # Recorremos los tokens acumulando palabras en cada línea según la longitud efectiva.
        for token, is_paren in tokens:
            # Calcula la contribución del token:
            # - Si el token es normal: se suma su longitud; si no es el primero, se agrega 1 (espacio) extra.
            # - Si es un grupo de paréntesis:
            #     · Si es el primer token de la línea → suma 1.
            #     · Si no es el primero y el token anterior también es de paréntesis, no suma nada.
            #     · Si el token anterior no es de paréntesis, suma 1 (sin contar espacio extra).
            if not current_line_tokens:
                addition = 1 if is_paren else len(token)
            else:
                prev_is_paren = current_line_tokens[-1][1]
                if is_paren:
                    addition = 0 if prev_is_paren else 1
                else:
                    addition = len(token) if prev_is_paren else (1 + len(token))
            
            # Si al agregar este token se excede la longitud máxima, se cierra la línea actual.
            if current_effective_length + addition > self.max_chars_per_line:
                if current_line_tokens:
                    lines.append(" ".join(t for t, _ in current_line_tokens))
                current_line_tokens = [(token, is_paren)]
                current_effective_length = 1 if is_paren else len(token)
            else:
                current_line_tokens.append((token, is_paren))
                current_effective_length += addition
        
        if current_line_tokens:
            lines.append(" ".join(t for t, _ in current_line_tokens))
        
        return lines

    # =====================================================
    # Funciones para la fusión óptima de intervenciones
    # =====================================================
    def optimal_merge_run(self, texts):
        """
        Dada una lista de textos (intervenciones consecutivas del mismo personaje),
        calcula la mínima cantidad de líneas que se pueden obtener al fusionarlas
        de forma óptima, respetando el límite de self.max_chars_per_line mediante expand_dialogue.
        
        Retorna una tupla:
          (min_line_count, segmentation)
        donde 'min_line_count' es la cantidad mínima de líneas resultante,
        y 'segmentation' es una lista (de listas de strings) que muestra cómo se han dividido.
        """
        n = len(texts)
        dp = [float("inf")] * (n + 1)
        segmentation = [None] * (n + 1)
        dp[0] = 0
        segmentation[0] = []
        for i in range(1, n + 1):
            for j in range(i):
                # Se unen las intervenciones de j a i-1
                merged_text = " ".join(texts[j:i])
                merged_lines = self.expand_dialogue(merged_text)
                cost = len(merged_lines)
                if dp[j] + cost < dp[i]:
                    dp[i] = dp[j] + cost
                    segmentation[i] = segmentation[j] + [merged_lines]
        return dp[n], segmentation[n]

    def unify_and_check(self, blocks_segment):
        """
        Fusiona las intervenciones de cada personaje dentro de blocks_segment y calcula:
        - total_lines: cantidad total de líneas resultantes tras la fusión óptima.
        - character_exceeded: True si para algún personaje la suma de líneas dentro del take
            supera el límite definido en max_consecutive_lines_per_character.
        """
        from collections import defaultdict
        interventions = []
        for block in blocks_segment:
            for d in block["dialogues"]:
                interventions.append((d["personaje"], " ".join(d["lines"])))
        if not interventions:
            return 0, False

        # Se acumulan las líneas totales por personaje, aun cuando sus intervenciones no sean consecutivas.
        lines_per_character = defaultdict(int)
        current_char = interventions[0][0]
        current_texts = []
        for person, text in interventions:
            if person == current_char:
                current_texts.append(text)
            else:
                # Se fusiona la corrida actual y se suma al total del personaje.
                run_lines, _ = self.optimal_merge_run(current_texts)
                lines_per_character[current_char] += run_lines
                current_char = person
                current_texts = [text]
        # Procesar la última corrida.
        if current_texts:
            run_lines, _ = self.optimal_merge_run(current_texts)
            lines_per_character[current_char] += run_lines

        total_lines = sum(lines_per_character.values())
        character_exceeded = any(lines > self.max_consecutive_lines_per_character 
                                for lines in lines_per_character.values())
        return total_lines, character_exceeded

    def check_duration(self, blocks_segment):
        """Verifica que la duración total del segmento no exceda max_duration."""
        start = blocks_segment[0]["in_time"]
        end = blocks_segment[-1]["out_time"]
        return (end - start) <= self.max_duration

    def is_segment_feasible(self, blocks_segment):
        """
        Determina si un segmento (lista de bloques) cumple todas las restricciones:
          - La duración total (desde el primer IN hasta el último OUT) no excede max_duration.
          - Tras fusionar las intervenciones consecutivas (usando el wrap de 60 caracteres),
            el número total de líneas no excede max_lines_per_take.
          - Ningún personaje tiene más líneas consecutivas que max_consecutive_lines_per_character.
        """
        if not self.check_duration(blocks_segment):
            return False

        total_lines, max_consecutive_exceeded = self.unify_and_check(blocks_segment)
        if total_lines > self.max_lines_per_take:
            return False
        if max_consecutive_exceeded:
            return False
        return True

    def group_dialogues_simultaneous_dp(self, data):
        """
        Agrupa los diálogos que comparten SCENE, IN y OUT en un único bloque.
        Cada bloque es un diccionario con:
          - scene: escena
          - in_time_str, out_time_str: tiempos en formato original
          - in_time, out_time: tiempos en segundos
          - dialogues: lista de dict con 'personaje' y 'lines' (lista de líneas expandidas)
          - total_lines: suma de líneas del bloque
          - characters: conjunto de personajes presentes
        """
        blocks = []
        grupos = data.groupby(["SCENE", "IN", "OUT"])
        for (scene, in_time_str, out_time_str), grupo in grupos:
            block = {}
            block["scene"] = scene
            block["in_time_str"] = in_time_str
            block["out_time_str"] = out_time_str
            block["in_time"] = self.parse_time(in_time_str)
            block["out_time"] = self.parse_time(out_time_str)
            dialogues = []
            total_lines = 0
            for _, row in grupo.iterrows():
                personaje = row["PERSONAJE"]
                texto = str(row["EUSKERA"])
                lines = self.expand_dialogue(texto)
                dialogues.append({"personaje": personaje, "lines": lines})
                total_lines += len(lines)
            block["dialogues"] = dialogues
            block["total_lines"] = total_lines
            block["characters"] = set(d["personaje"] for d in dialogues)
            blocks.append(block)
        blocks.sort(key=lambda b: (b["scene"], b["in_time"]))
        return blocks

    def partition_scene_blocks(self, blocks):
        """
        Particiona una lista de bloques (de la misma escena) en segmentos (takes)
        usando programación dinámica para minimizar el coste total.
        El coste de un segmento es el número de personajes únicos presentes.
        Retorna la lista de segmentos (como pares de índices) y el coste total.
        """
        n = len(blocks)
        dp = [float("inf")] * (n + 1)
        partition_index = [-1] * (n + 1)
        dp[0] = 0
        
        for i in range(n):
            for j in range(i, n):
                segment = blocks[i:j+1]
                if not self.is_segment_feasible(segment):
                    break
                seg_characters = set()
                for b in segment:
                    seg_characters.update(b["characters"])
                cost = len(seg_characters)
                if dp[i] + cost < dp[j+1]:
                    dp[j+1] = dp[i] + cost
                    partition_index[j+1] = i
        
        segments = []
        idx = n
        while idx > 0:
            start = partition_index[idx]
            segments.append((start, idx))
            idx = start
        segments.reverse()
        return segments, dp[n]

    def generate_detail(self, blocks):
        """
        Genera un DataFrame detalle con las líneas FUSIONADAS, 
        asignando a cada corrida consecutiva de un mismo personaje su propio IN y OUT.
        """
        from collections import defaultdict

        # Agrupamos los bloques por (scene, take)
        scene_take_map = defaultdict(list)
        for block in blocks:
            scene_take_map[(block["scene"], block.get("take"))].append(block)
        
        detail_rows = []
        
        for (scene, take), blocks_in_take in scene_take_map.items():
            # Ordenamos los bloques por tiempo
            blocks_in_take.sort(key=lambda b: b["in_time"])
            
            # Creamos una lista de intervenciones: (personaje, texto, IN, OUT)
            interventions = []
            for block in blocks_in_take:
                in_time_str = block["in_time_str"]
                out_time_str = block["out_time_str"]
                for d in block["dialogues"]:
                    personaje = d["personaje"]
                    full_text = " ".join(d["lines"])
                    interventions.append((personaje, full_text, in_time_str, out_time_str))
            
            if not interventions:
                continue
            
            # Agrupamos intervenciones consecutivas del mismo personaje
            final_lines = []
            current_run = [interventions[0]]
            for inter in interventions[1:]:
                if inter[0] == current_run[-1][0]:
                    current_run.append(inter)
                else:
                    # Para la corrida actual se fusionan los textos
                    merged_lines = self._fuse_run_texts([t[1] for t in current_run])
                    run_in = current_run[0][2]         # IN de la primera intervención
                    run_out = current_run[-1][3]         # OUT de la última intervención
                    for ml in merged_lines:
                        final_lines.append({
                            "personaje": current_run[0][0],
                            "texto": ml,
                            "IN": run_in,
                            "OUT": run_out
                        })
                    current_run = [inter]
            # Procesar la última corrida
            if current_run:
                merged_lines = self._fuse_run_texts([t[1] for t in current_run])
                run_in = current_run[0][2]
                run_out = current_run[-1][3]
                for ml in merged_lines:
                    final_lines.append({
                        "personaje": current_run[0][0],
                        "texto": ml,
                        "IN": run_in,
                        "OUT": run_out
                    })
            
            # Volcamos las líneas fusionadas al detalle
            for fl in final_lines:
                detail_rows.append({
                    "SCENE": scene,
                    "TAKE": take,
                    "IN": fl["IN"],
                    "OUT": fl["OUT"],
                    "PERSONAJE": fl["personaje"],
                    "EUSKERA": fl["texto"]
                })
        
        # Ordenamos por escena y por tiempo de IN
        detail_rows.sort(key=lambda x: (x["SCENE"], self.parse_time(x["IN"])))
        return pd.DataFrame(detail_rows)

    def _fuse_run_texts(self, texts):
        """
        Fusiona un conjunto de textos consecutivos (mismo personaje)
        en la menor cantidad de líneas usando expand_dialogue,
        tal como en 'optimal_merge_run', pero aquí devolvemos las líneas resultantes
        (en vez de un conteo).
        """
        merged_text = " ".join(texts)
        return self.expand_dialogue(merged_text)

    def generate_summary(self, blocks):
        """
        Genera un DataFrame resumen con el total de takes por personaje.
        Cada take suma +1 para cada personaje presente.
        """
        resumen = {}
        for block in blocks:
            take = block.get("take", None)
            for p in block["characters"]:
                if p not in resumen:
                    resumen[p] = set()
                resumen[p].add(take)
        resumen_rows = []
        total_cost = 0
        for p, takes in resumen.items():
            num = len(takes)
            resumen_rows.append({"PERSONAJE": p, "TAKES": num})
            total_cost += num
        resumen_rows.append({"PERSONAJE": "TOTAL", "TAKES": total_cost})
        return pd.DataFrame(resumen_rows)

    def create_optimized_takes_dp(self, data):
        """
        A partir de los datos filtrados (DataFrame), agrupa los diálogos en bloques
        y, por escena, utiliza programación dinámica para particionar en takes que cumplan
        las restricciones y minimicen el coste total.
        Retorna un DataFrame de detalle y uno resumen.
        """
        blocks = self.group_dialogues_simultaneous_dp(data)
        blocks_by_scene = {}
        for block in blocks:
            scene = block["scene"]
            blocks_by_scene.setdefault(scene, []).append(block)
        
        global_take_counter = 1
        final_blocks = []
        for scene, scene_blocks in blocks_by_scene.items():
            scene_blocks.sort(key=lambda b: b["in_time"])
            segments, scene_cost = self.partition_scene_blocks(scene_blocks)
            for seg in segments:
                start, end = seg
                for idx in range(start, end):
                    scene_blocks[idx]["take"] = global_take_counter
                global_take_counter += 1
            final_blocks.extend(scene_blocks)
        
        detail_df = self.generate_detail(final_blocks)
        summary_df = self.generate_summary(final_blocks)
        return detail_df, summary_df

    def save_results(self, result_data, take_summary):
        """Guardar los resultados en archivos Excel"""
        save_dir = filedialog.askdirectory(title="Seleccionar directorio para guardar resultados")
        if not save_dir:
            return
            
        try:
            detail_path = os.path.join(save_dir, "detalle_takes.xlsx")
            summary_path = os.path.join(save_dir, "resumen_takes.xlsx")
            
            result_data.to_excel(detail_path, index=False)
            take_summary.to_excel(summary_path, index=False)
            
            messagebox.showinfo(
                "Proceso completado", 
                f"Proceso completado con éxito.\n\n"
                f"Total de takes generados: {result_data['TAKE'].max()}\n"
                f"Suma total de takes por personaje: {take_summary.iloc[-1]['TAKES']}\n\n"
                f"Archivos guardados en:\n{save_dir}"
            )
        except Exception as e:
            messagebox.showerror("Error", f"Error al guardar los resultados: {str(e)}")
    
    # ------------------------------
    # Ejecución de la aplicación
    # ------------------------------
    def run(self):
        self.root.mainloop()


# Punto de entrada
if __name__ == "__main__":
    app = ScriptTakeOptimizer()
    app.run()
