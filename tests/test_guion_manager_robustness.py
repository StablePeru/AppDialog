import pytest
import pandas as pd
import os
from guion_editor.utils.guion_manager import GuionManager
from guion_editor import constants_logic as C

class TestGuionManagerRobustness:
    @pytest.fixture
    def manager(self):
        return GuionManager()

    def test_process_dataframe_missing_critical_columns(self, manager):
        """Test processing a dataframe that lacks standard columns."""
        # Create a "dirty" DF with only some random data
        data = {
            "SomeRandomColumn": ["A", "B", "C"],
            C.COL_DIALOGO: ["Hello", "World", "Test"]
        }
        df = pd.DataFrame(data)
        
        # Process it
        processed_df, has_scenes = manager.process_dataframe(df)
        
        # Assertions
        assert C.COL_ID in processed_df.columns
        assert C.COL_SCENE in processed_df.columns
        assert C.COL_IN in processed_df.columns  # Should be added if missing
        assert C.COL_OUT in processed_df.columns # Should be added if missing
        assert C.COL_EUSKERA in processed_df.columns
        assert len(processed_df) == 3
        # Check defaults
        assert processed_df.iloc[0][C.COL_SCENE] == "1"

    def test_process_dataframe_corrupted_scene_numbers(self, manager):
        """Test processing corrupted scene numbers (NaN, floats, text mixed)."""
        data = {
            C.COL_DIALOGO: ["Line 1", "Line 2", "Line 3", "Line 4"],
            C.COL_SCENE: ["1", "1.0", None, "nan"] # Mixed bad data
        }
        df = pd.DataFrame(data)
        
        processed_df, _ = manager.process_dataframe(df)
        
        # Verify scene normalization
        scenes = processed_df[C.COL_SCENE].tolist()
        # "1" stays "1"
        # "1.0" should become "1"
        # None should be ffilled or filled with default "1"
        # "nan" string should be handled
        
        # First row "1" -> "1"
        assert scenes[0] == "1"
        # "1.0" -> "1"
        assert scenes[1] == "1"
        # None -> ffill from "1" -> "1"
        assert scenes[2] == "1"
        # "nan" -> ffill from "1" -> "1"
        assert scenes[3] == "1"

    def test_process_dataframe_timecode_integrity(self, manager):
        """Test that timecode columns are preserved or added, but not strictly validated here (validation is in Model)."""
        # Manager mainly ensures columns exist
        data = {C.COL_DIALOGO: ["Hi"]}
        df = pd.DataFrame(data)
        
        processed_df, _ = manager.process_dataframe(df)
        assert C.COL_IN in processed_df.columns
        # Should initiate as empty/NaN if missing
        assert pd.isna(processed_df.iloc[0][C.COL_IN]) or processed_df.iloc[0][C.COL_IN] == ""

    def test_save_empty_dataframe(self, manager, tmp_path):
        """Test saving an empty dataframe to JSON properly."""
        df = pd.DataFrame() # Completely empty
        # Process should add columns even to empty DF
        processed_df, _ = manager.process_dataframe(df)
        
        save_path = tmp_path / "empty_test.json"
        header = {"Project": "Test"}
        
        # Should not crash
        manager.save_to_json(str(save_path), processed_df, header)
        
        assert os.path.exists(save_path)
        
        # Reload to verify
        loaded_df, loaded_header, _ = manager.load_from_json(str(save_path))
        assert loaded_header["Project"] == "Test"
        assert loaded_df.empty # Should still be empty rows, but have columns?
        # Actually process_dataframe on empty adds columns but rows remain 0
        assert len(loaded_df) == 0
        assert C.COL_DIALOGO in loaded_df.columns

    def test_check_excel_columns_header_parsing(self, manager, tmp_path):
        """Test logic for reading Excel headers (mocking file creation)."""
        # Create a real small Excel file
        path = tmp_path / "test_header.xlsx"
        
        with pd.ExcelWriter(path) as writer:
            # Data sheet
            pd.DataFrame({C.COL_DIALOGO: ["Test"]}).to_excel(writer, sheet_name='Guion', index=False)
            # Header sheet
            pd.DataFrame([("reference_number", "12345"), ("Project", "Alpha")]).to_excel(writer, sheet_name='Header', header=False, index=False)
            
        df, header_data, needs_mapping = manager.check_excel_columns(str(path))
        
        assert not df.empty
        assert header_data.get("reference_number") == "12345"
        assert header_data.get("Project") == "Alpha"

if __name__ == "__main__":
    pytest.main()
