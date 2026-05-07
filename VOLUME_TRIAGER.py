import os
import re
from glob import glob

import qt
import slicer
from slicer.ScriptedLoadableModule import (
    ScriptedLoadableModule,
    ScriptedLoadableModuleWidget,
)


PATIENT_ID_REGEX = re.compile(r'^([SN]\d+)')
STUDY_ID_REGEX = re.compile(r'(CSRA\d+)')
VOLUME_GLOB = "*.nii.gz"
TRIAGED_SUBDIR = "triaged"
BRAIN_WINDOW = 80
BRAIN_LEVEL = 40


class VOLUME_TRIAGER(ScriptedLoadableModule):
    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        parent.title = "Volume Triager"
        parent.categories = ["Triage"]
        parent.dependencies = []
        parent.contributors = ["Laurent Letourneau-Guillon"]
        parent.helpText = (
            "Browse a folder of NIfTI volumes, review each, and save kept volumes "
            "to a 'triaged/' subfolder. If the listed file is unusable, manually "
            "load a replacement volume into the scene and click Save or Next — "
            "the most recently loaded volume node is what gets saved, under the "
            "original case filename."
        )
        parent.acknowledgementText = ""


class VOLUME_TRIAGERWidget(ScriptedLoadableModuleWidget):
    def __init__(self, parent=None):
        ScriptedLoadableModuleWidget.__init__(self, parent)
        self.input_folder = None
        self.case_paths = []
        self.current_index = -1
        self.loaded_case_node = None
        self.current_patient_id = None

    def setup(self):
        ScriptedLoadableModuleWidget.setup(self)

        folder_box = qt.QGroupBox("Input folder")
        folder_layout = qt.QVBoxLayout(folder_box)
        self.browse_button = qt.QPushButton("Browse folder…")
        self.browse_button.clicked.connect(self.on_browse)
        folder_layout.addWidget(self.browse_button)
        self.folder_label = qt.QLabel("No folder selected")
        self.folder_label.setWordWrap(True)
        folder_layout.addWidget(self.folder_label)
        self.layout.addWidget(folder_box)

        info_box = qt.QGroupBox("Current case")
        info_form = qt.QFormLayout(info_box)
        self.index_label = qt.QLabel("—")
        self.patient_label = qt.QLabel("—")
        self.study_label = qt.QLabel("—")
        self.file_label = qt.QLabel("—")
        self.file_label.setWordWrap(True)
        for label in (self.patient_label, self.study_label):
            label.setStyleSheet("font-weight: bold;")
        info_form.addRow("Index:", self.index_label)
        info_form.addRow("Patient ID:", self.patient_label)
        info_form.addRow("Study ID:", self.study_label)
        info_form.addRow("File:", self.file_label)
        self.layout.addWidget(info_box)

        self.list_widget = qt.QListWidget()
        self.list_widget.itemSelectionChanged.connect(self.on_list_selection)
        self.layout.addWidget(self.list_widget)

        self.load_replacement_button = qt.QPushButton("Load replacement file…")
        self.load_replacement_button.clicked.connect(self.on_load_replacement)
        self.layout.addWidget(self.load_replacement_button)

        nav = qt.QHBoxLayout()
        self.previous_button = qt.QPushButton("Previous")
        self.save_button = qt.QPushButton("Save")
        self.next_button = qt.QPushButton("Save + Next")
        self.previous_button.clicked.connect(self.on_previous)
        self.save_button.clicked.connect(lambda: self.save_current_volume())
        self.next_button.clicked.connect(self.on_next)
        for btn in (self.previous_button, self.save_button, self.next_button):
            nav.addWidget(btn)
        self.layout.addLayout(nav)

        self.status_label = qt.QLabel("")
        self.status_label.setWordWrap(True)
        self.layout.addWidget(self.status_label)

        self.layout.addStretch()
        self._set_nav_enabled(False)

    def _set_nav_enabled(self, enabled):
        for btn in (
            self.previous_button,
            self.save_button,
            self.next_button,
            self.load_replacement_button,
        ):
            btn.setEnabled(enabled)

    def on_browse(self):
        folder = qt.QFileDialog.getExistingDirectory(None, "Select folder of NIfTI volumes")
        if not folder:
            return
        self.input_folder = folder
        self.folder_label.setText(folder)
        self.case_paths = sorted(glob(os.path.join(folder, VOLUME_GLOB)))
        self.list_widget.clear()
        for path in self.case_paths:
            self.list_widget.addItem(os.path.basename(path))
        if not self.case_paths:
            self._set_nav_enabled(False)
            self.current_index = -1
            self._set_status(f"No {VOLUME_GLOB} files found in folder.", error=True)
            return
        self._set_nav_enabled(True)
        self.current_index = -1
        self._refresh_list_colors()
        self.goto_index(0)

    def goto_index(self, index):
        if index < 0 or index >= len(self.case_paths):
            return
        self.list_widget.blockSignals(True)
        self.list_widget.setCurrentRow(index)
        self.list_widget.blockSignals(False)
        self.current_index = index
        self.load_case(index)

    def on_list_selection(self):
        row = self.list_widget.currentRow
        if row < 0 or row == self.current_index:
            return
        self.current_index = row
        self.load_case(row)

    def load_case(self, index):
        path = self.case_paths[index]
        slicer.mrmlScene.Clear(0)
        try:
            node = slicer.util.loadVolume(path)
        except Exception as exc:
            self._set_status(f"Failed to load {os.path.basename(path)}: {exc}", error=True)
            return
        self.loaded_case_node = node
        self._apply_brain_window(node)
        basename = os.path.basename(path)
        patient = PATIENT_ID_REGEX.match(basename)
        study = STUDY_ID_REGEX.search(basename)
        patient_id = patient.group(1) if patient else "—"
        study_id = study.group(1) if study else "—"
        self.current_patient_id = patient.group(1) if patient else None
        self.index_label.setText(f"{index + 1} / {len(self.case_paths)}")
        self.patient_label.setText(patient_id)
        self.study_label.setText(study_id)
        self.file_label.setText(basename)
        print(f"[VOLUME_TRIAGER] case {index + 1}/{len(self.case_paths)} | "
              f"Patient ID: {patient_id} | Study ID: {study_id} | File: {basename}")
        if study_id != "—":
            qt.QApplication.clipboard().setText(study_id)
        self._set_status(f"Loaded {basename}  (study ID copied to clipboard)")

    def on_load_replacement(self):
        if self.current_index < 0:
            return
        start_dir = self.input_folder or ""
        path = qt.QFileDialog.getOpenFileName(
            None,
            "Select replacement volume",
            start_dir,
            "NIfTI volumes (*.nii.gz *.nii);;All files (*)",
        )
        if not path:
            return
        try:
            node = slicer.util.loadVolume(path)
        except Exception as exc:
            self._set_status(f"Failed to load {os.path.basename(path)}: {exc}", error=True)
            return
        self._apply_brain_window(node)
        self._set_status(f"Loaded replacement: {os.path.basename(path)}")

    def _apply_brain_window(self, node):
        if node is None:
            return
        display = node.GetDisplayNode()
        if display is None:
            return
        display.AutoWindowLevelOff()
        display.SetWindow(BRAIN_WINDOW)
        display.SetLevel(BRAIN_LEVEL)

    def _most_recent_volume_node(self):
        nodes = slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")
        return nodes[-1] if nodes else None

    def save_current_volume(self):
        if self.current_index < 0 or not self.input_folder:
            print("[VOLUME_TRIAGER] save aborted: no current case or input folder")
            return False
        node = self._most_recent_volume_node()
        if node is None:
            self._set_status("No volume in scene — nothing to save.", error=True)
            return False
        case_basename = os.path.basename(self.case_paths[self.current_index])
        if node is self.loaded_case_node:
            # No replacement was loaded — preserve the original case basename.
            out_basename = case_basename
        else:
            # User loaded a replacement; use that file's basename, prefixed with
            # the current patient ID if it's not already there.
            storage = node.GetStorageNode()
            source_path = storage.GetFileName() if storage else None
            replacement_basename = os.path.basename(source_path) if source_path else case_basename
            existing = PATIENT_ID_REGEX.match(replacement_basename)
            if (
                self.current_patient_id
                and (existing is None or existing.group(1) != self.current_patient_id)
            ):
                out_basename = f"{self.current_patient_id}_{replacement_basename}"
            else:
                out_basename = replacement_basename
            print(f"[VOLUME_TRIAGER] using replacement basename: {out_basename}")
        out_dir = os.path.join(self.input_folder, TRIAGED_SUBDIR)
        try:
            os.makedirs(out_dir, exist_ok=True)
        except Exception as exc:
            msg = f"Cannot create {out_dir}: {exc}"
            print(f"[VOLUME_TRIAGER] {msg}")
            self._set_status(msg, error=True)
            return False
        out_path = os.path.join(out_dir, out_basename)
        print(
            f"[VOLUME_TRIAGER] saving node {node.GetName()!r} "
            f"(class={node.GetClassName()}) to {out_path}"
        )
        try:
            ok = slicer.util.saveNode(node, out_path)
        except Exception as exc:
            msg = f"saveNode raised: {exc}"
            print(f"[VOLUME_TRIAGER] {msg}")
            self._set_status(msg, error=True)
            return False
        on_disk = os.path.exists(out_path)
        print(f"[VOLUME_TRIAGER] saveNode returned {ok!r}; file on disk: {on_disk}")
        if on_disk:
            self._set_status(f"Saved → {out_path}")
            self._refresh_list_colors()
            return True
        self._set_status(f"Failed to save → {out_path} (saveNode={ok!r})", error=True)
        return False

    def _refresh_list_colors(self):
        if not self.input_folder:
            return
        triaged_dir = os.path.join(self.input_folder, TRIAGED_SUBDIR)
        triaged_study_ids = set()
        if os.path.isdir(triaged_dir):
            for fname in os.listdir(triaged_dir):
                m = STUDY_ID_REGEX.search(fname)
                if m:
                    triaged_study_ids.add(m.group(1))
        green = qt.QColor("#1b5e20")
        red = qt.QColor("#b00020")
        for i, path in enumerate(self.case_paths):
            item = self.list_widget.item(i)
            if item is None:
                continue
            m = STUDY_ID_REGEX.search(os.path.basename(path))
            study_id = m.group(1) if m else None
            item.setForeground(green if study_id and study_id in triaged_study_ids else red)

    def on_previous(self):
        if self.current_index > 0:
            self.goto_index(self.current_index - 1)

    def on_next(self):
        if not self.save_current_volume():
            return
        if self.current_index >= len(self.case_paths) - 1:
            self._set_status("Reached last case.")
            return
        self.goto_index(self.current_index + 1)

    def _set_status(self, text, error=False):
        color = "#b00020" if error else "#1b5e20"
        self.status_label.setText(f"<span style='color:{color}'>{text}</span>")
