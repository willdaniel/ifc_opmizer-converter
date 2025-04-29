import sys
import os
import traceback
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QCheckBox,
    QFileDialog, QVBoxLayout, QHBoxLayout, QMessageBox, 
    QProgressDialog, QGroupBox, QGridLayout, QComboBox, QDoubleSpinBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon
from src.optimizer import optimize_ifc

class OptimizerThread(QThread):
    finished = Signal(object, object, dict)
    progress = Signal(str)
    
    def __init__(self, input_file, output_file, options):
        super().__init__()
        self.input_file = input_file
        self.output_file = output_file
        self.options = options

    def run(self):
        try:
            # Redirect print statements to emit progress signals
            original_print = print
            def thread_print(*args, **kwargs):
                message = " ".join(map(str, args))
                self.progress.emit(message)
                original_print(*args, **kwargs)
            
            # Replace print function temporarily
            import builtins
            builtins.print = thread_print
            
            # Run optimization
            stats = optimize_ifc(self.input_file, self.output_file, self.options)
            
            # Restore original print function
            builtins.print = original_print
            
            self.finished.emit(None, self.output_file, stats)
        except Exception as e:
            traceback.print_exc()
            self.finished.emit(str(e), self.output_file, {})

class IFCOptimizerGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IFC Optimizer & OBJ Converter")
        
        # Try to set icon with fallback
        icon_paths = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "axisverde.ico"),
            "axisverde.ico",
            os.path.join(os.path.expanduser("~"), "axisverde.ico")
        ]
        
        icon_set = False
        for icon_path in icon_paths:
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
                icon_set = True
                break
        
        self.setMinimumWidth(650)

        # Optimization options
        self.optimization_options = {
            
            'convert_to_3ds': 'Convert to OBJ Format'
        }

        # Create UI components
        self.create_file_inputs()
        self.create_optimization_settings()
        self.create_schema_conversion()
        self.create_optimize_button()
        self.create_progress_area()

        # Main layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.input_group)
        main_layout.addWidget(self.output_group)
        main_layout.addWidget(self.settings_group)
        main_layout.addWidget(self.schema_group)
        main_layout.addWidget(self.progress_group)
        main_layout.addLayout(self.button_layout)
        self.setLayout(main_layout)
        
        self.progress_dialog = None
        self.thread = None
    
    def create_schema_conversion(self):
        """Create schema conversion UI elements"""
        self.schema_group = QGroupBox("Schema Conversion")
        schema_layout = QHBoxLayout()
        self.convert_checkbox = QCheckBox("Convert to:")
        self.schema_combo = QComboBox()
        self.schema_combo.addItems(["IFC2X3", "IFC4"])
        schema_layout.addWidget(self.convert_checkbox)
        schema_layout.addWidget(self.schema_combo)
        schema_layout.addStretch(1)
        self.schema_group.setLayout(schema_layout)
        
    def create_file_inputs(self):
        """Create file input/output widgets"""
        # Input file section
        self.input_group = QGroupBox("Input File")
        input_layout = QHBoxLayout()
        self.input_line = QLineEdit()
        self.input_browse = QPushButton("Browse")
        self.input_browse.clicked.connect(self.browse_input)
        input_layout.addWidget(self.input_line)
        input_layout.addWidget(self.input_browse)
        self.input_group.setLayout(input_layout)

        # Output file section
        self.output_group = QGroupBox("Output File")
        output_layout = QHBoxLayout()
        self.output_line = QLineEdit()
        self.output_browse = QPushButton("Browse")
        self.output_browse.clicked.connect(self.browse_output)
        output_layout.addWidget(self.output_line)
        output_layout.addWidget(self.output_browse)
        self.output_group.setLayout(output_layout)

    def browse_input(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Select IFC file", "", "IFC Files (*.ifc);;All Files (*)"
        )
        if file_name:
            self.input_line.setText(file_name)
            # Auto-generate output path
            base = os.path.basename(file_name)
            self.output_line.setText(os.path.join(os.path.dirname(file_name), f"optimized_{base}"))

    def browse_output(self):
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Save Optimized IFC As", self.output_line.text() or "", "IFC Files (*.ifc);;All Files (*)"
        )
        if file_name:
            self.output_line.setText(file_name)

    def create_optimization_settings(self):
        """Create optimization checkboxes and parameters"""
        self.settings_group = QGroupBox("Optimization Settings")
        grid = QGridLayout()
    
        self.checkboxes = {}
        self.param_inputs = {}
    
        row, col = 0, 0
        for opt, value in self.optimization_options.items():
            if isinstance(value, tuple):
                label, widget_type = value
                if widget_type == QDoubleSpinBox:
                    # Create checkbox
                    cb = QCheckBox(label)
                    self.checkboxes[opt] = cb
                    grid.addWidget(cb, row, col)
                    
                    # Create spin box for numerical input
                    spin_box = QDoubleSpinBox()
                    spin_box.setRange(0.0001, 10.0)
                    spin_box.setSingleStep(0.001)
                    spin_box.setValue(0.001)
                    spin_box.setDecimals(4)
                    self.param_inputs[opt] = spin_box
                    grid.addWidget(spin_box, row, col + 1)
                    col += 1
                elif isinstance(widget_type, list):
                    # Create checkbox with dropdown
                    cb = QCheckBox(label)
                    self.checkboxes[opt] = cb
                    grid.addWidget(cb, row, col)
                    
                    # Create dropdown
                    combo = QComboBox()
                    combo.addItems(widget_type)
                    combo.setCurrentText('Medium')
                    combo.setMaximumWidth(100)
                    self.param_inputs[opt] = combo
                    grid.addWidget(combo, row, col + 1)
                    col += 1
            else:
                # Simple checkbox
                cb = QCheckBox(value)
                self.checkboxes[opt] = cb
                grid.addWidget(cb, row, col)

            col += 1
            if col >= 3:
                col = 0
                row += 1

        # Set default checked state for common optimizations
        for opt in ['remove_unused_spaces', 'remove_metadata', 'remove_empty_attributes', 
                   'remove_unused_property_sets', 'remove_unused_materials', 
                   'deduplicate_geometry']:
            if opt in self.checkboxes:
                self.checkboxes[opt].setChecked(True)

        self.settings_group.setLayout(grid)

    def create_progress_area(self):
        """Create progress display area"""
        self.progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout()
        
        self.progress_text = QLabel("Ready")
        self.progress_text.setWordWrap(True)
        self.progress_text.setMinimumHeight(60)
        self.progress_text.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.progress_text.setStyleSheet("background-color: #f0f0f0; padding: 5px; border-radius: 3px;")
        
        progress_layout.addWidget(self.progress_text)
        self.progress_group.setLayout(progress_layout)

    def run_optimizer(self):
        input_file = self.input_line.text()
        output_file = self.output_line.text()

        if not input_file or not output_file:
            QMessageBox.warning(self, "Missing Information", "Please select both input and output files.")
            return

        # Gather options (as you already do)
        options = {}
        for opt, cb in self.checkboxes.items():
            if cb.isChecked():
                if opt in self.param_inputs:
                    widget = self.param_inputs[opt]
                    if isinstance(widget, QComboBox):
                        options[opt] = widget.currentText().lower()
                    elif isinstance(widget, QDoubleSpinBox):
                        options[opt] = widget.value()
                    else:
                        options[opt] = widget.text()
                else:
                    options[opt] = True
            else:
                if opt == 'simplify_geometry':
                    options[opt] = 'none'

        options.update({
            'convert_schema': self.convert_checkbox.isChecked(),
            'target_schema': self.schema_combo.currentText()
        })

        self.progress_text.setText("Starting optimization...")
        self.optimize_btn.setEnabled(False)

        # --- Progress Dialog ---
        self.progress_dialog = QProgressDialog("Optimizing...", None, 0, 0, self)
        self.progress_dialog.setWindowTitle("Please Wait")
        self.progress_dialog.setWindowModality(Qt.ApplicationModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setValue(0)
        self.progress_dialog.show()
        # -----------------------

        # Start optimization thread
        self.thread = OptimizerThread(input_file, output_file, options)
        self.thread.finished.connect(self.on_optimization_finished)
        self.thread.progress.connect(self.update_progress)
        self.thread.start()

    def update_progress(self, message):
        """Update progress text with latest message"""
        current_text = self.progress_text.text()
        # Keep only the last 5 lines to avoid too much text
        lines = current_text.split('\n')
        if len(lines) > 5:
            lines = lines[-4:]
        lines.append(message)
        self.progress_text.setText('\n'.join(lines))

    def create_optimize_button(self):
        self.optimize_btn = QPushButton("Optimize")
        self.optimize_btn.setFixedSize(120, 32)
        self.optimize_btn.setStyleSheet("""
            QPushButton {
                background-color: #3da060;
                color: white;
                border: none;
                border-radius: 12px;
                font-weight: bold;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: #15597a; }
            QPushButton:pressed { background-color: #062433; }
            QPushButton:disabled { background-color: #cccccc; color: #666666; }
        """)
        self.optimize_btn.clicked.connect(self.run_optimizer)
    
        self.button_layout = QHBoxLayout()
        self.button_layout.addStretch(1)
        self.button_layout.addWidget(self.optimize_btn)
        self.button_layout.addStretch(1)

    def on_optimization_finished(self, error, output_file, stats):
        self.optimize_btn.setEnabled(True)
        
        if error:
            self.update_progress(f"Error: {error}")
            QMessageBox.critical(self, "Error", f"An error occurred:\n{error}")
        else:
            # Build stats message
            stats_text = "Optimization removed:\n"
            for key, value in stats.items():
                if key != 'converted_to_3ds':  # Skip the 3DS conversion flag
                    stats_text += f"- {value} {key.replace('_', ' ')}\n"
            
            # Get file sizes
            input_size = os.path.getsize(self.input_line.text()) / (1024 * 1024)
            output_size = os.path.getsize(output_file) / (1024 * 1024)
            reduction = input_size - output_size
            percentage = (1 - output_size/input_size) * 100
            
            # Check if 3DS conversion was done
            conversion_text = ""
            if stats.get('converted_to_3ds'):
                output_3ds_path = os.path.splitext(output_file)[0] + '.3ds'
                if os.path.exists(output_3ds_path):
                    conversion_text = f"\nConverted to 3DS format:\n{output_3ds_path}"
                else:
                    output_obj_path = os.path.splitext(output_file)[0] + '.obj'
                    if os.path.exists(output_obj_path):
                        conversion_text = (f"\nConverted to OBJ format (3DS conversion library not available):\n"
                                          f"{output_obj_path}")
            
            message = (
                f"Optimized file saved to:\n{output_file}\n\n"
                f"Original size: {input_size:.2f} MB\n"
                f"Optimized size: {output_size:.2f} MB\n"
                f"Size reduction: {reduction:.2f} MB ({percentage:.2f}%)\n\n"
                f"{stats_text}{conversion_text}"
            )
            
            self.update_progress("Optimization completed successfully!")
            QMessageBox.information(self, "Success", message)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Try to set application icon
    icon_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "axisverde.ico"),
        "axisverde.ico",
        os.path.join(os.path.expanduser("~"), "axisverde.ico")
    ]
    
    for icon_path in icon_paths:
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
            break
    
    window = IFCOptimizerGUI()
    window.show()
    sys.exit(app.exec())



##'remove_unused_spaces': 'Remove Unused Spaces',
##            'remove_metadata': 'Remove Metadata',
##            'remove_empty_attributes': 'Remove Empty Attributes', 
##            'remove_unused_property_sets': 'Remove Unused Property Sets',
##            'remove_unused_materials': 'Remove Unused Materials',
##            'remove_unused_classifications': 'Remove Classifications',
##            'remove_small_elements': ('Remove Small Elements (m³)', QDoubleSpinBox),
##            'remove_orphaned_entities': 'Remove Orphaned Entities',
##            'deduplicate_geometry': 'Deduplicate Geometry',
##            'flatten_spatial_structure': 'Flatten Spatial Structure',
##            'simplify_geometry': ('Simplify Geometry', ['None', 'Low', 'Medium', 'High']),