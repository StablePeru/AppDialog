# guion_editor/utils/srt_processor.py
import pandas as pd
import re
from math import floor
import unicodedata

class SRTProcessor:
    DEFAULT_CONFIG = {
        "FPS": 25,
        "SMALL_GAP_S": 0.04,
        "SENTENCE_GAP_S": 0.4,
        "MAX_CHARS_PER_LINE": 37,
        "MAX_LINES_PER_SUB": 2,
        "MAX_OVERLAP_S": 2.0,
        "FIXED_GAP_S": 0.05
    }
    
    REST_CODE = "<BN1>" 

    def __init__(self, config: dict = None):
        if config is None:
            config = self.DEFAULT_CONFIG
        
        self.FPS = int(config.get("FPS", self.DEFAULT_CONFIG["FPS"]))
        self.SMALL_GAP_S = float(config.get("SMALL_GAP_S", self.DEFAULT_CONFIG["SMALL_GAP_S"]))
        self.SENTENCE_GAP_S = float(config.get("SENTENCE_GAP_S", self.DEFAULT_CONFIG.get("SENTENCE_GAP_S", 0.4)))
        self.MAX_CHARS_PER_LINE = int(config.get("MAX_CHARS_PER_LINE", self.DEFAULT_CONFIG["MAX_CHARS_PER_LINE"]))
        self.MAX_LINES_PER_SUB = int(config.get("MAX_LINES_PER_SUB", self.DEFAULT_CONFIG["MAX_LINES_PER_SUB"]))
        self.MAX_OVERLAP_S = float(config.get("MAX_OVERLAP_S", self.DEFAULT_CONFIG["MAX_OVERLAP_S"]))
        self.FIXED_GAP_S = float(config.get("FIXED_GAP_S", self.DEFAULT_CONFIG["FIXED_GAP_S"]))

    def _parse_timecode(self, x) -> float | None:
        if x is None: return None
        if isinstance(x, (int, float)): return float(x)
        s = str(x).strip()
        if not s: return None
        if ":" in s:
            parts = s.split(":")
            try:
                if len(parts) == 4:
                    hh, mm, ss, ff = parts
                    sec = float(ss) if "." in ss else int(ss)
                    frames = int(re.sub(r"[^\d].*$", "", ff)) if ff else 0
                    return int(hh) * 3600 + int(mm) * 60 + sec + frames / self.FPS
                if len(parts) == 3:
                    hh, mm, ss = parts
                    return int(hh) * 3600 + int(mm) * 60 + float(ss)
            except (ValueError, TypeError):
                return None
        return None

    def _fmt_srt_timestamp(self, seconds: float) -> str:
        if seconds is None or seconds < 0: seconds = 0.0
        total_seconds_int = int(floor(seconds))
        fraction = seconds - total_seconds_int
        ms = int(round(fraction * 1000))
        if ms >= 1000:
            total_seconds_int += 1
            ms = 0
        hh = total_seconds_int // 3600
        mm = (total_seconds_int % 3600) // 60
        ss = total_seconds_int % 60
        return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"

    def _clean_text(self, text: str) -> str:
        if text is None: return ""
        t = str(text)
        t = re.sub(r"\([^()]*\)", "", t)
        t = re.sub(r"\s+_\s+", " ", t)
        t = re.sub(r"^_\s+", "", t)
        t = re.sub(r"\s+_$", "", t)
        t = t.replace('"', "''").replace("…", "...")
        t = re.sub(r"^\s+", "", t)
        t = re.sub(r"\s{2,}", " ", t).strip()
        return t

    def _tokenize_dialogue(self, text: str) -> list[str]:
        if "|" in text:
            parts = [p.strip() for p in text.split("|") if p.strip()]
            return parts
        temp_text = re.sub(r'([.?!]+)(\s+)', r'\1|', text)
        temp_text = re.sub(r'(\s)([-—–])', r'|\2', temp_text)
        parts = [p.strip() for p in temp_text.split("|") if p.strip()]
        return parts

    def _word_wrap(self, text: str, width: int):
        words = text.split()
        lines = []
        cur = ""
        for w in words:
            if not cur: cur = w
            elif len(cur) + 1 + len(w) <= width: cur += " " + w
            else:
                lines.append(cur)
                cur = w
        if cur: lines.append(cur)
        return lines

    def _solve_global_overlaps(self, records: list[dict]) -> list[dict]:
        if not records: return []
        sorted_records = sorted(records, key=lambda x: x['start'])
        for i in range(len(sorted_records) - 1):
            current = sorted_records[i]
            next_sub = sorted_records[i+1]
            limit = next_sub['start'] - self.FIXED_GAP_S
            if current['end'] > limit:
                current['end'] = max(current['start'], limit)
        return sorted_records

    def _process_single_row_srt(self, text, start_time, end_time, personaje, char_color_map: dict) -> list[dict]:
        if not text or start_time is None or end_time is None or end_time <= start_time:
            return []

        blocks = self._tokenize_dialogue(text)
        if not blocks: return []

        total_duration = end_time - start_time
        block_lengths = [max(1, len(b)) for b in blocks]
        total_chars = sum(block_lengths)
        
        num_internal_gaps = len(blocks) - 1
        required_gap_time = num_internal_gaps * self.SENTENCE_GAP_S
        available_for_text = total_duration - required_gap_time
        
        if available_for_text <= 0 or (total_chars / available_for_text) > 25:
            current_gap = self.SMALL_GAP_S
            available_for_text = total_duration - (num_internal_gaps * current_gap)
        else:
            current_gap = self.SENTENCE_GAP_S

        if available_for_text <= 0:
            available_for_text = total_duration
            current_gap = 0 

        srt_entries = []
        cur_time = start_time
        
        color_code = char_color_map.get(personaje, self.REST_CODE)

        for i, block_text in enumerate(blocks):
            weight = block_lengths[i] / total_chars
            block_dur = available_for_text * weight
            block_end = cur_time + block_dur
            
            lines = self._word_wrap(block_text, self.MAX_CHARS_PER_LINE)
            if lines:
                packs = [lines[j:j+self.MAX_LINES_PER_SUB] for j in range(0, len(lines), self.MAX_LINES_PER_SUB)]
                n_packs = len(packs)
                
                pack_total_gaps = self.SMALL_GAP_S * (n_packs - 1)
                pack_effective_dur = max(0.0, block_dur - pack_total_gaps)
                pack_base_dur = pack_effective_dur / n_packs if n_packs > 0 else 0
                
                pack_start = cur_time
                for pack in packs:
                    final_text_lines = []
                    for line_idx, line_str in enumerate(pack):
                        if line_idx == 0 and color_code:
                            # --- CAMBIO AQUÍ: Eliminado el espacio entre {color_code} y {line_str} ---
                            final_text_lines.append(f"{color_code}{line_str}")
                        else:
                            final_text_lines.append(line_str)
                    
                    pack_text = "\n".join(final_text_lines)
                    
                    pack_end = pack_start + pack_base_dur
                    srt_entries.append({"start": pack_start, "end": pack_end, "text": pack_text})
                    pack_start = pack_end + self.SMALL_GAP_S
            
            cur_time = block_end + current_gap

        return srt_entries

    def generate_srt_string(self, df, col_mapping, char_color_mapping):
        starts = df[col_mapping["IN"]].apply(self._parse_timecode)
        ends   = df[col_mapping["OUT"]].apply(self._parse_timecode)
        texts_clean = df[col_mapping["DIALOGO"]].astype(str).apply(self._clean_text)
        
        all_temp_records = []
        
        for i, row in df.iterrows():
            personaje_raw = row[col_mapping["PERSONAJE"]]
            personaje = str(personaje_raw).strip() if pd.notna(personaje_raw) else ""
            
            text = texts_clean.iloc[i]
            st = starts.iloc[i]
            et = ends.iloc[i]
            
            records = self._process_single_row_srt(text, st, et, personaje, char_color_mapping)
            all_temp_records.extend(records)

        final_records = self._solve_global_overlaps(all_temp_records)

        srt_blocks = []
        for idx, rec in enumerate(final_records, 1):
            if rec['end'] - rec['start'] < 0.04: continue
            block = f"{idx}\n{self._fmt_srt_timestamp(rec['start'])} --> {self._fmt_srt_timestamp(rec['end'])}\n{rec['text'].strip()}"
            srt_blocks.append(block)
            
        return "\n\n".join(srt_blocks)