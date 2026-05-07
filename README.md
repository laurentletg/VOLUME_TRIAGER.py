# Volume Triager

A minimal 3D Slicer scripted module for triaging NIfTI volumes — go through a folder of cases, review each one, and save the kept volumes to a `triaged/` subfolder. Built for pre-inference review workflows where a human decides which volumes are usable.

No segmentation, no annotations, no config file. Single Python file, GUI built in code.

## Install

1. In Slicer: **Edit → Application Settings → Modules**
2. Under **Additional module paths**, add the folder containing `VOLUME_TRIAGER.py` (i.e. this directory).
3. Restart Slicer. The module appears under category **Triage** as **Volume Triager**.

## Workflow

1. Click **Browse folder…** and select a folder containing `*.nii.gz` volumes. The list populates and the first case auto-loads.
2. The **Current case** panel shows:
   - **Index** — `n / total`
   - **Patient ID** — first match of `^[SN]\d+` in the filename (e.g. `S12345`, `N6789`)
   - **Study ID** — first match of `CSRA\d+` in the filename
   - **File** — the original filename
3. Review the loaded volume.
   - If it is fine, click **Save** (stays on case) or **Save + Next** (advances).
   - If it is bad, load a replacement using either:
     - the in-module **Load replacement file…** button, or
     - native Slicer drag-and-drop / **File → Add Data**
   - Then click **Save** or **Save + Next**.
4. Use **Previous** / clicking on a list row to navigate without saving.

## What gets saved

When you click **Save** or **Save + Next**, the **most recently loaded volume node** in the scene is written to:

```
<input_folder>/triaged/<basename_of_loaded_file>
```

The output basename is the actual filename of the loaded volume — so if you replaced the original case with `S12345_corrected.nii.gz`, that exact name lands in `triaged/`. The `triaged/` folder is auto-created.

If the most recent node has no backing file (e.g. created in code), the original case basename is used as a fallback.

## Filename conventions

The module assumes inputs like:

```
S12345_CSRA0001_anything.nii.gz
N67890_CSRA0042_other.nii.gz
```

- **Patient ID regex**: `^([SN]\d+)` — anchored to start of filename, S or N + digits.
- **Study ID regex**: `(CSRA\d+)` — `CSRA` + digits, anywhere in the filename.

To change the patterns, edit `PATIENT_ID_REGEX` and `STUDY_ID_REGEX` near the top of `VOLUME_TRIAGER.py`.

## Notes

- Only `*.nii.gz` files are listed. Edit `VOLUME_GLOB` in the source to widen this.
- Switching cases via the list clears the scene before loading. Manually loaded volumes (drag-drop, **Load replacement…**, **File → Add Data**) are added on top — the most recent one is the one saved.
- Existing files in `triaged/` will be overwritten without confirmation.
