# guion_editor/widgets/export_selection_dialog.py
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QCheckBox, QDialogButtonBox, QGroupBox
from PyQt6.QtCore import Qt

class ExportSelectionDialog(QDialog):
    def __init__(self, reports_available: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Seleccionar Archivos a Exportar")
        self.setMinimumWidth(350)
        
        layout = QVBoxLayout(self)
        group = QGroupBox("Marque los informes que desea guardar:")
        group_layout = QVBoxLayout(group)
        
        self.detail_check = QCheckBox("Informe Detallado de Takes")
        self.detail_check.setChecked(reports_available.get("detail", False))
        self.detail_check.setEnabled(reports_available.get("detail", False))
        group_layout.addWidget(self.detail_check)
        
        self.summary_check = QCheckBox("Informe Resumido de Takes")
        self.summary_check.setChecked(reports_available.get("summary", False))
        self.summary_check.setEnabled(reports_available.get("summary", False))
        group_layout.addWidget(self.summary_check)
        
        self.failures_check = QCheckBox("Reporte de Fallos de Agrupación")
        self.failures_check.setChecked(reports_available.get("failures", False))
        self.failures_check.setEnabled(reports_available.get("failures", False))
        group_layout.addWidget(self.failures_check)
        
        self.problems_check = QCheckBox("Reporte de Intervenciones Problemáticas")
        self.problems_check.setChecked(reports_available.get("problems", False))
        self.problems_check.setEnabled(reports_available.get("problems", False))
        group_layout.addWidget(self.problems_check)
        
        layout.addWidget(group)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_choices(self) -> dict | None:
        if self.result() == QDialog.DialogCode.Accepted:
            return {
                "detail": self.detail_check.isChecked(),
                "summary": self.summary_check.isChecked(),
                "failures": self.failures_check.isChecked(),
                "problems": self.problems_check.isChecked()
            }
        return None