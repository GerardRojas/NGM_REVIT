# -*- coding: utf-8 -*-
"""BuildFromBatch - Reads a .batch.json and builds a complete Revit model.

Opens a file dialog, parses the batch JSON (definitions + families +
manifest), then creates all Revit elements in the correct dependency
order: levels, grids, types, families, geometry, rooms, views, sheets.
"""
__title__ = "Build From\nBatch"
__author__ = "NGM"

import clr
import os
import sys
import json
import codecs
import math
import tempfile
from datetime import datetime
from collections import OrderedDict

clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI')

from Autodesk.Revit.DB import (
    XYZ,
    UV,
    Line,
    Level,
    Grid,
    Wall,
    WallType,
    FloorType,
    CurveArray,
    FilteredElementCollector,
    BuiltInCategory,
    BuiltInParameter,
    CompoundStructure,
    CompoundStructureLayer,
    MaterialFunctionAssignment,
    ElementId,
    Transaction,
    TransactionGroup,
    TransactionStatus,
    ViewPlan,
    ViewFamilyType,
    ViewFamily,
    ViewSheet,
    Viewport,
    SaveAsOptions,
)

from Autodesk.Revit.DB.Structure import StructuralType

from pyrevit import revit, DB, script, forms

output = script.get_output()
doc = revit.doc

TOTAL_STEPS = 19

# ── Layer function mapping: batch JSON string -> Revit enum ──
LAYER_FUNCTION_MAP = {
    "finish": MaterialFunctionAssignment.Finish1,
    "substrate": MaterialFunctionAssignment.Substrate,
    "structure": MaterialFunctionAssignment.Structure,
    "thermal": MaterialFunctionAssignment.ThermalOrAir,
    "membrane": MaterialFunctionAssignment.Membrane,
}

# ── Build context: populated during build, used for cross-referencing ──
ctx = {
    "level_map": {},        # level_name -> Level element
    "wall_type_map": {},    # wall_type_name -> WallType ElementId
    "floor_type_map": {},   # floor_type_name -> FloorType ElementId
    "family_map": {},       # family_name -> Family element
    "symbol_map": {},       # "family_name::type_name" -> FamilySymbol
    "wall_elements": [],    # ordered list matching manifest.walls[] indices
    "grid_map": {},         # grid_name -> Grid element
    "material_map": {},     # material_name -> Material ElementId (cache)
    "view_map": {},         # view_name -> View element
    "sheet_map": {},        # sheet_number -> ViewSheet element
}

# ── Summary counters ──
summary = OrderedDict([
    ("levels", 0),
    ("grids", 0),
    ("wall_types", 0),
    ("floor_types", 0),
    ("families_loaded", 0),
    ("families_skipped", 0),
    ("walls", 0),
    ("floors", 0),
    ("columns", 0),
    ("beams", 0),
    ("fixtures", 0),
    ("rooms", 0),
    ("views", 0),
    ("sheets", 0),
    ("errors", 0),
    ("warnings", 0),
])


# ═══════════════════════════════════════════════════════════════
#  UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def log_step(step_number, title):
    """Print a step header."""
    output.print_md("---")
    output.print_md("## Step {}/{}: {}".format(step_number, TOTAL_STEPS, title))


def log_ok(msg):
    output.print_md("  - {}".format(msg))


def log_warn(msg):
    summary["warnings"] += 1
    output.print_md("  - **WARNING**: {}".format(msg))


def log_error(msg):
    summary["errors"] += 1
    output.print_md("  - **ERROR**: {}".format(msg))


def find_material_id(material_name):
    """Find a material by name in the document. Returns ElementId.
    Caches results. Returns InvalidElementId if not found.
    """
    if material_name in ctx["material_map"]:
        return ctx["material_map"][material_name]

    collector = FilteredElementCollector(doc).OfClass(DB.Material)
    for mat in collector:
        if mat.Name == material_name:
            ctx["material_map"][material_name] = mat.Id
            return mat.Id

    ctx["material_map"][material_name] = ElementId.InvalidElementId
    return ElementId.InvalidElementId


def find_base_wall_type():
    """Find a WallType to use as duplication base."""
    collector = FilteredElementCollector(doc).OfClass(WallType)
    # Try the documented base type first
    for wt in collector:
        if wt.Name == "Generic - 8\"":
            return wt
    # Fallback: any basic wall type
    collector = FilteredElementCollector(doc).OfClass(WallType)
    for wt in collector:
        try:
            if wt.Kind == DB.WallKind.Basic:
                return wt
        except Exception:
            pass
    return None


def find_base_floor_type():
    """Find a FloorType to use as duplication base."""
    collector = FilteredElementCollector(doc).OfClass(FloorType)
    for ft in collector:
        if ft.Name == "Generic Floor - 8\"":
            return ft
    # Fallback: first available
    collector = FilteredElementCollector(doc).OfClass(FloorType)
    for ft in collector:
        return ft
    return None


# ═══════════════════════════════════════════════════════════════
#  STEP 1: READ AND VALIDATE BATCH JSON
# ═══════════════════════════════════════════════════════════════

def step_01_read_batch():
    """Open file dialog, read and validate the batch JSON.
    Returns the parsed dict or None on failure.
    """
    log_step(1, "Read and validate batch JSON")

    batch_path = forms.pick_file(
        file_ext="json",
        title="Select NGM Batch File (.batch.json)"
    )

    if not batch_path:
        output.print_md("**Build cancelled - no file selected.**")
        return None

    output.print_md("File: `{}`".format(batch_path))

    try:
        with codecs.open(batch_path, "r", "utf-8") as f:
            batch = json.load(f)
    except Exception as e:
        log_error("Failed to parse JSON: {}".format(str(e)))
        return None

    # Validate required top-level keys
    required_keys = ["batch_meta", "project", "definitions", "families", "manifest"]
    missing = [k for k in required_keys if k not in batch]
    if missing:
        log_error("Missing required keys: {}".format(", ".join(missing)))
        return None

    if "levels" not in batch["manifest"] or not batch["manifest"]["levels"]:
        log_error("manifest.levels is required and cannot be empty")
        return None

    # Log project info
    project = batch["project"]
    output.print_md("**Project**: {} ({})".format(
        project.get("project_name", "Unknown"),
        project.get("project_type", "Unknown")
    ))
    output.print_md("**Batch ID**: {}".format(
        batch["batch_meta"].get("batch_id", "Unknown")
    ))
    output.print_md("**Created**: {}".format(
        batch["batch_meta"].get("created_at", "Unknown")
    ))

    # Preview element counts
    m = batch["manifest"]
    counts = []
    for key in ["levels", "grids", "walls", "floors", "columns",
                 "beams", "fixtures", "rooms"]:
        items = m.get(key, [])
        if items:
            counts.append("{} {}".format(len(items), key))
    output.print_md("**Elements**: {}".format(", ".join(counts)))

    log_ok("Batch file validated successfully")
    return batch


# ═══════════════════════════════════════════════════════════════
#  STEP 2: CREATE LEVELS
# ═══════════════════════════════════════════════════════════════

def step_02_create_levels(batch):
    """Create levels from manifest.levels."""
    log_step(2, "Create levels")
    levels_data = batch["manifest"]["levels"]

    with revit.Transaction("NGM - Create Levels"):
        for ldata in levels_data:
            try:
                name = ldata["name"]
                elevation = ldata["elevation_ft"]

                # Check if level already exists
                existing = None
                collector = FilteredElementCollector(doc).OfClass(Level)
                for lev in collector:
                    if lev.Name == name:
                        existing = lev
                        break

                if existing:
                    ctx["level_map"][name] = existing
                    log_ok("Level '{}' already exists - reusing".format(name))
                    summary["levels"] += 1
                    continue

                level = Level.Create(doc, elevation)
                level.Name = name

                ctx["level_map"][name] = level
                summary["levels"] += 1
                log_ok("Level '{}' at {:.4f} ft".format(name, elevation))
            except Exception as e:
                log_error("Failed to create level '{}': {}".format(
                    ldata.get("name", "?"), str(e)
                ))

    log_ok("Total: {} levels".format(summary["levels"]))


# ═══════════════════════════════════════════════════════════════
#  STEP 3: CREATE GRIDS
# ═══════════════════════════════════════════════════════════════

def step_03_create_grids(batch):
    """Create grids from manifest.grids."""
    log_step(3, "Create grids")
    grids_data = batch["manifest"].get("grids", [])

    if not grids_data:
        log_ok("No grids defined - skipping")
        return

    with revit.Transaction("NGM - Create Grids"):
        for gdata in grids_data:
            try:
                name = gdata["name"]
                sx, sy = gdata["start"]
                ex, ey = gdata["end"]

                line = Line.CreateBound(
                    XYZ(sx, sy, 0),
                    XYZ(ex, ey, 0)
                )
                grid = Grid.Create(doc, line)
                grid.Name = name

                ctx["grid_map"][name] = grid
                summary["grids"] += 1
            except Exception as e:
                log_error("Failed to create grid '{}': {}".format(
                    gdata.get("name", "?"), str(e)
                ))

    log_ok("Total: {} grids".format(summary["grids"]))


# ═══════════════════════════════════════════════════════════════
#  STEP 4: CREATE WALL TYPES
# ═══════════════════════════════════════════════════════════════

def step_04_create_wall_types(batch):
    """Create wall types from definitions.wall_types."""
    log_step(4, "Create wall types")
    wall_types_data = batch["definitions"].get("wall_types", [])

    if not wall_types_data:
        log_ok("No wall types defined - skipping")
        return

    base_type = find_base_wall_type()
    if base_type is None:
        log_error("Cannot find any base WallType to duplicate")
        return

    with revit.Transaction("NGM - Create Wall Types"):
        for wt_data in wall_types_data:
            try:
                name = wt_data["name"]

                # Check if already exists
                existing = None
                collector = FilteredElementCollector(doc).OfClass(WallType)
                for wt in collector:
                    if wt.Name == name:
                        existing = wt
                        break

                if existing:
                    ctx["wall_type_map"][name] = existing.Id
                    log_ok("Wall type '{}' already exists - reusing".format(name))
                    summary["wall_types"] += 1
                    continue

                # Duplicate base type
                new_type = base_type.Duplicate(name)

                # Build compound structure layers
                layers_data = wt_data.get("layers", [])
                cs_layers = []

                for layer in layers_data:
                    func_str = layer.get("function", "structure")
                    mat_name = layer.get("material", "")
                    width = layer.get("width_ft", 0)

                    func_enum = LAYER_FUNCTION_MAP.get(
                        func_str,
                        MaterialFunctionAssignment.Structure
                    )
                    mat_id = find_material_id(mat_name)

                    if mat_id == ElementId.InvalidElementId:
                        log_warn("Material '{}' not found for wall type '{}'".format(
                            mat_name, name
                        ))

                    cs_layer = CompoundStructureLayer(
                        width, func_enum, mat_id
                    )
                    cs_layers.append(cs_layer)

                # Try Python list first, fallback to .NET List
                try:
                    cs = CompoundStructure.CreateSimpleCompoundStructure(
                        cs_layers
                    )
                except TypeError:
                    from System.Collections.Generic import List as NetList
                    net_layers = NetList[CompoundStructureLayer]()
                    for csl in cs_layers:
                        net_layers.Add(csl)
                    cs = CompoundStructure.CreateSimpleCompoundStructure(
                        net_layers
                    )

                new_type.SetCompoundStructure(cs)

                ctx["wall_type_map"][name] = new_type.Id
                summary["wall_types"] += 1
                log_ok("Wall type '{}' ({} layers, {:.4f} ft)".format(
                    name, len(cs_layers),
                    wt_data.get("total_width_ft", 0)
                ))
            except Exception as e:
                log_error("Failed to create wall type '{}': {}".format(
                    wt_data.get("name", "?"), str(e)
                ))

    log_ok("Total: {} wall types".format(summary["wall_types"]))


# ═══════════════════════════════════════════════════════════════
#  STEP 5: CREATE FLOOR TYPES
# ═══════════════════════════════════════════════════════════════

def step_05_create_floor_types(batch):
    """Create floor types from definitions.floor_types."""
    log_step(5, "Create floor types")
    floor_types_data = batch["definitions"].get("floor_types", [])

    if not floor_types_data:
        log_ok("No floor types defined - skipping")
        return

    base_type = find_base_floor_type()
    if base_type is None:
        log_error("Cannot find any base FloorType to duplicate")
        return

    with revit.Transaction("NGM - Create Floor Types"):
        for ft_data in floor_types_data:
            try:
                name = ft_data["name"]

                # Check if already exists
                existing = None
                collector = FilteredElementCollector(doc).OfClass(FloorType)
                for ft in collector:
                    if ft.Name == name:
                        existing = ft
                        break

                if existing:
                    ctx["floor_type_map"][name] = existing.Id
                    log_ok("Floor type '{}' already exists - reusing".format(name))
                    summary["floor_types"] += 1
                    continue

                new_type = base_type.Duplicate(name)

                layers_data = ft_data.get("layers", [])
                cs_layers = []

                for layer in layers_data:
                    func_str = layer.get("function", "structure")
                    mat_name = layer.get("material", "")
                    width = layer.get("width_ft", 0)

                    func_enum = LAYER_FUNCTION_MAP.get(
                        func_str,
                        MaterialFunctionAssignment.Structure
                    )
                    mat_id = find_material_id(mat_name)

                    if mat_id == ElementId.InvalidElementId:
                        log_warn("Material '{}' not found for floor type '{}'".format(
                            mat_name, name
                        ))

                    cs_layer = CompoundStructureLayer(
                        width, func_enum, mat_id
                    )
                    cs_layers.append(cs_layer)

                try:
                    cs = CompoundStructure.CreateSimpleCompoundStructure(
                        cs_layers
                    )
                except TypeError:
                    from System.Collections.Generic import List as NetList
                    net_layers = NetList[CompoundStructureLayer]()
                    for csl in cs_layers:
                        net_layers.Add(csl)
                    cs = CompoundStructure.CreateSimpleCompoundStructure(
                        net_layers
                    )

                new_type.SetCompoundStructure(cs)

                ctx["floor_type_map"][name] = new_type.Id
                summary["floor_types"] += 1
                log_ok("Floor type '{}' ({} layers, {:.4f} ft)".format(
                    name, len(cs_layers),
                    ft_data.get("total_thickness_ft", 0)
                ))
            except Exception as e:
                log_error("Failed to create floor type '{}': {}".format(
                    ft_data.get("name", "?"), str(e)
                ))

    log_ok("Total: {} floor types".format(summary["floor_types"]))


# ═══════════════════════════════════════════════════════════════
#  STEP 6: LOAD FAMILIES
# ═══════════════════════════════════════════════════════════════

def _load_family_from_path(fam_name, path):
    """Load a .rfa family from disk. Returns True on success."""
    try:
        loaded_family = clr.Reference[DB.Family]()
        success = doc.LoadFamily(path, loaded_family)
        if success:
            ctx["family_map"][fam_name] = loaded_family.Value
            return True
        else:
            # Family may already be loaded (returns False)
            collector = FilteredElementCollector(doc).OfClass(DB.Family)
            for fam in collector:
                if fam.Name == fam_name:
                    ctx["family_map"][fam_name] = fam
                    return True
    except Exception as e:
        log_warn("LoadFamily failed for '{}': {}".format(fam_name, str(e)))
    return False


def _download_and_load_family(fam_name, url):
    """Download .rfa from URL to temp dir, then load. Returns True on success."""
    try:
        clr.AddReference('System')
        from System.Net import WebClient

        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, "{}.rfa".format(fam_name))

        client = WebClient()
        client.DownloadFile(url, temp_path)

        if os.path.isfile(temp_path):
            result = _load_family_from_path(fam_name, temp_path)
            try:
                os.remove(temp_path)
            except Exception:
                pass
            return result
    except Exception as e:
        log_warn("Download failed for '{}': {}".format(fam_name, str(e)))
    return False


def _activate_family_types(family, fam_data):
    """Activate specified types from a loaded family."""
    types_to_activate = fam_data.get("types_to_activate", [])
    fam_name = fam_data.get("name", "")

    symbol_ids = family.GetFamilySymbolIds()

    for sym_id in symbol_ids:
        symbol = doc.GetElement(sym_id)
        if symbol is None:
            continue

        sym_param = symbol.get_Parameter(
            BuiltInParameter.ALL_MODEL_TYPE_NAME
        )
        sym_name = sym_param.AsString() if sym_param else ""

        if not types_to_activate or sym_name in types_to_activate:
            if not symbol.IsActive:
                symbol.Activate()
                doc.Regenerate()

            key = "{}::{}".format(fam_name, sym_name)
            ctx["symbol_map"][key] = symbol


def step_06_load_families(batch):
    """Download and load families from the families[] array."""
    log_step(6, "Load families")
    families_data = batch.get("families", [])

    if not families_data:
        log_ok("No families defined - skipping")
        return

    # Repo root (5 levels up from script.py)
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )))

    with revit.Transaction("NGM - Load Families"):
        for fam_data in families_data:
            fam_name = fam_data.get("name", "Unknown")
            status = fam_data.get("status", "available")

            # Skip planned/deprecated
            if status != "available":
                log_warn("Family '{}' status='{}' - skipped".format(
                    fam_name, status
                ))
                summary["families_skipped"] += 1
                continue

            try:
                # Check if already loaded
                already_loaded = False
                collector = FilteredElementCollector(doc).OfClass(DB.Family)
                for fam in collector:
                    if fam.Name == fam_name:
                        ctx["family_map"][fam_name] = fam
                        already_loaded = True
                        break

                if not already_loaded:
                    loaded = False

                    # Try local vault path
                    vault_path = fam_data.get("vault_path", "")
                    if vault_path:
                        local_path = os.path.join(repo_root, vault_path)
                        if os.path.isfile(local_path):
                            loaded = _load_family_from_path(
                                fam_name, local_path
                            )

                    # Try URL download
                    if not loaded:
                        vault_url = fam_data.get("vault_url", "")
                        if vault_url:
                            loaded = _download_and_load_family(
                                fam_name, vault_url
                            )

                    if not loaded:
                        log_warn("Family '{}' not available - skipped".format(
                            fam_name
                        ))
                        summary["families_skipped"] += 1
                        continue

                # Activate specified types
                family = ctx["family_map"].get(fam_name)
                if family:
                    _activate_family_types(family, fam_data)

                summary["families_loaded"] += 1
                log_ok("Family '{}' loaded".format(fam_name))
            except Exception as e:
                log_error("Failed to load family '{}': {}".format(
                    fam_name, str(e)
                ))
                summary["families_skipped"] += 1

    log_ok("Total: {} loaded, {} skipped".format(
        summary["families_loaded"], summary["families_skipped"]
    ))


# ═══════════════════════════════════════════════════════════════
#  STEP 7: TRACE WALLS
# ═══════════════════════════════════════════════════════════════

def step_07_create_walls(batch):
    """Place walls from manifest.walls."""
    log_step(7, "Trace walls")
    walls_data = batch["manifest"].get("walls", [])

    if not walls_data:
        log_ok("No walls defined - skipping")
        return

    with revit.Transaction("NGM - Create Walls"):
        for i, wdata in enumerate(walls_data):
            try:
                type_name = wdata["type"]
                level_name = wdata["level"]
                sx, sy = wdata["start"]
                ex, ey = wdata["end"]
                height = wdata.get("height_ft", 10.0)
                structural = wdata.get("structural", False)

                wall_type_id = ctx["wall_type_map"].get(type_name)
                level_elem = ctx["level_map"].get(level_name)

                if wall_type_id is None:
                    log_warn("Wall type '{}' not found - skipping wall {}".format(
                        type_name, i
                    ))
                    ctx["wall_elements"].append(None)
                    continue
                if level_elem is None:
                    log_warn("Level '{}' not found - skipping wall {}".format(
                        level_name, i
                    ))
                    ctx["wall_elements"].append(None)
                    continue

                # Validate non-zero length
                if abs(sx - ex) < 0.001 and abs(sy - ey) < 0.001:
                    log_warn("Zero-length wall {} - skipping".format(i))
                    ctx["wall_elements"].append(None)
                    continue

                line = Line.CreateBound(
                    XYZ(sx, sy, 0),
                    XYZ(ex, ey, 0)
                )

                wall = Wall.Create(
                    doc,
                    line,
                    wall_type_id,
                    level_elem.Id,
                    height,
                    0.0,
                    False,
                    structural
                )

                ctx["wall_elements"].append(wall)
                summary["walls"] += 1
            except Exception as e:
                ctx["wall_elements"].append(None)
                log_error("Failed to create wall {}: {}".format(i, str(e)))

    log_ok("Total: {} walls".format(summary["walls"]))


# ═══════════════════════════════════════════════════════════════
#  STEP 8: PLACE FLOORS
# ═══════════════════════════════════════════════════════════════

def step_08_create_floors(batch):
    """Place floors from manifest.floors."""
    log_step(8, "Place floors")
    floors_data = batch["manifest"].get("floors", [])

    if not floors_data:
        log_ok("No floors defined - skipping")
        return

    with revit.Transaction("NGM - Create Floors"):
        for i, fdata in enumerate(floors_data):
            try:
                type_name = fdata["type"]
                level_name = fdata["level"]
                boundary = fdata["boundary"]

                floor_type_id = ctx["floor_type_map"].get(type_name)
                level_elem = ctx["level_map"].get(level_name)

                if floor_type_id is None:
                    log_warn("Floor type '{}' not found - skipping floor {}".format(
                        type_name, i
                    ))
                    continue
                if level_elem is None:
                    log_warn("Level '{}' not found - skipping floor {}".format(
                        level_name, i
                    ))
                    continue

                floor_type = doc.GetElement(floor_type_id)

                # Build CurveArray from boundary polygon
                curve_array = CurveArray()
                for j in range(len(boundary)):
                    p1 = boundary[j]
                    p2 = boundary[(j + 1) % len(boundary)]
                    line = Line.CreateBound(
                        XYZ(p1[0], p1[1], 0),
                        XYZ(p2[0], p2[1], 0)
                    )
                    curve_array.Append(line)

                floor = doc.Create.NewFloor(
                    curve_array,
                    floor_type,
                    level_elem,
                    True  # structural
                )

                summary["floors"] += 1
            except Exception as e:
                log_error("Failed to create floor {}: {}".format(i, str(e)))

    log_ok("Total: {} floors".format(summary["floors"]))


# ═══════════════════════════════════════════════════════════════
#  STEP 9: PLACE COLUMNS
# ═══════════════════════════════════════════════════════════════

def step_09_create_columns(batch):
    """Place columns from manifest.columns."""
    log_step(9, "Place columns")
    columns_data = batch["manifest"].get("columns", [])

    if not columns_data:
        log_ok("No columns defined - skipping")
        return

    with revit.Transaction("NGM - Create Columns"):
        for i, cdata in enumerate(columns_data):
            try:
                fam_name = cdata["family"]
                type_name = cdata.get("type", "")
                x, y = cdata["point"]
                base_level_name = cdata["base_level"]
                top_level_name = cdata["top_level"]

                sym_key = "{}::{}".format(fam_name, type_name)
                symbol = ctx["symbol_map"].get(sym_key)
                base_level = ctx["level_map"].get(base_level_name)
                top_level = ctx["level_map"].get(top_level_name)

                if symbol is None:
                    log_warn("Symbol '{}' not found - skipping column {}".format(
                        sym_key, i
                    ))
                    continue
                if base_level is None:
                    log_warn("Base level '{}' not found - skipping column {}".format(
                        base_level_name, i
                    ))
                    continue

                point = XYZ(x, y, base_level.Elevation)

                col = doc.Create.NewFamilyInstance(
                    point,
                    symbol,
                    base_level,
                    StructuralType.Column
                )

                # Set top level constraint
                if top_level:
                    try:
                        param = col.get_Parameter(
                            BuiltInParameter.FAMILY_TOP_LEVEL_PARAM
                        )
                        if param:
                            param.Set(top_level.Id)
                        offset_param = col.get_Parameter(
                            BuiltInParameter.FAMILY_TOP_LEVEL_OFFSET_PARAM
                        )
                        if offset_param:
                            offset_param.Set(0.0)
                    except Exception:
                        pass

                # Rotation
                rotation = cdata.get("rotation_deg", 0)
                if rotation != 0:
                    try:
                        axis = Line.CreateBound(
                            point,
                            XYZ(x, y, point.Z + 1)
                        )
                        DB.ElementTransformUtils.RotateElement(
                            doc, col.Id, axis, math.radians(rotation)
                        )
                    except Exception:
                        pass

                summary["columns"] += 1
            except Exception as e:
                log_error("Failed to create column {}: {}".format(i, str(e)))

    log_ok("Total: {} columns".format(summary["columns"]))


# ═══════════════════════════════════════════════════════════════
#  STEP 10: PLACE BEAMS
# ═══════════════════════════════════════════════════════════════

def step_10_create_beams(batch):
    """Place beams from manifest.beams."""
    log_step(10, "Place beams")
    beams_data = batch["manifest"].get("beams", [])

    if not beams_data:
        log_ok("No beams defined - skipping")
        return

    with revit.Transaction("NGM - Create Beams"):
        for i, bdata in enumerate(beams_data):
            try:
                fam_name = bdata["family"]
                type_name = bdata.get("type", "")
                sx, sy, sz = bdata["start"]
                ex, ey, ez = bdata["end"]
                level_name = bdata["level"]

                sym_key = "{}::{}".format(fam_name, type_name)
                symbol = ctx["symbol_map"].get(sym_key)
                level = ctx["level_map"].get(level_name)

                if symbol is None:
                    log_warn("Symbol '{}' not found - skipping beam {}".format(
                        sym_key, i
                    ))
                    continue
                if level is None:
                    log_warn("Level '{}' not found - skipping beam {}".format(
                        level_name, i
                    ))
                    continue

                line = Line.CreateBound(
                    XYZ(sx, sy, sz),
                    XYZ(ex, ey, ez)
                )

                beam = doc.Create.NewFamilyInstance(
                    line,
                    symbol,
                    level,
                    StructuralType.Beam
                )

                summary["beams"] += 1
            except Exception as e:
                log_error("Failed to create beam {}: {}".format(i, str(e)))

    log_ok("Total: {} beams".format(summary["beams"]))


# ═══════════════════════════════════════════════════════════════
#  STEP 11: INSERT FIXTURES
# ═══════════════════════════════════════════════════════════════

def step_11_insert_fixtures(batch):
    """Insert fixtures (doors, windows, MEP) from manifest.fixtures."""
    log_step(11, "Insert fixtures")
    fixtures_data = batch["manifest"].get("fixtures", [])

    if not fixtures_data:
        log_ok("No fixtures defined - skipping")
        return

    with revit.Transaction("NGM - Insert Fixtures"):
        for i, fdata in enumerate(fixtures_data):
            try:
                fam_name = fdata["family"]
                type_name = fdata.get("type", "")
                point_data = fdata["point"]
                level_name = fdata["level"]
                host_wall_idx = fdata.get("host_wall_index")
                rotation = fdata.get("rotation_deg", 0)

                sym_key = "{}::{}".format(fam_name, type_name)
                symbol = ctx["symbol_map"].get(sym_key)
                level = ctx["level_map"].get(level_name)

                if symbol is None:
                    log_warn("Symbol '{}' not found - skipping fixture {}".format(
                        sym_key, i
                    ))
                    continue
                if level is None:
                    log_warn("Level '{}' not found - skipping fixture {}".format(
                        level_name, i
                    ))
                    continue

                x = point_data[0]
                y = point_data[1]
                z = point_data[2] if len(point_data) > 2 else 0
                point = XYZ(x, y, z)

                instance = None

                # Wall-hosted fixture (doors, windows)
                if host_wall_idx is not None:
                    if host_wall_idx < len(ctx["wall_elements"]):
                        host_wall = ctx["wall_elements"][host_wall_idx]
                        if host_wall is None:
                            log_warn(
                                "Host wall {} was not created"
                                " - skipping fixture {}".format(
                                    host_wall_idx, i
                                )
                            )
                            continue

                        instance = doc.Create.NewFamilyInstance(
                            point,
                            symbol,
                            host_wall,
                            level,
                            StructuralType.NonStructural
                        )
                    else:
                        log_warn(
                            "host_wall_index {} out of range"
                            " - skipping fixture {}".format(
                                host_wall_idx, i
                            )
                        )
                        continue
                else:
                    # Freestanding fixture
                    instance = doc.Create.NewFamilyInstance(
                        point,
                        symbol,
                        level,
                        StructuralType.NonStructural
                    )

                # Rotation
                if rotation != 0 and instance is not None:
                    try:
                        loc = instance.Location
                        if loc and hasattr(loc, "Point"):
                            rot_point = loc.Point
                        else:
                            rot_point = point
                        axis = Line.CreateBound(
                            rot_point,
                            XYZ(rot_point.X, rot_point.Y, rot_point.Z + 1)
                        )
                        DB.ElementTransformUtils.RotateElement(
                            doc, instance.Id, axis, math.radians(rotation)
                        )
                    except Exception:
                        pass

                summary["fixtures"] += 1
            except Exception as e:
                log_error("Failed to insert fixture {}: {}".format(
                    i, str(e)
                ))

    log_ok("Total: {} fixtures".format(summary["fixtures"]))


# ═══════════════════════════════════════════════════════════════
#  STEP 12: PLACE ROOMS
# ═══════════════════════════════════════════════════════════════

def step_12_create_rooms(batch):
    """Place rooms from manifest.rooms."""
    log_step(12, "Place rooms")
    rooms_data = batch["manifest"].get("rooms", [])

    if not rooms_data:
        log_ok("No rooms defined - skipping")
        return

    with revit.Transaction("NGM - Create Rooms"):
        for i, rdata in enumerate(rooms_data):
            try:
                name = rdata["name"]
                number = rdata.get("number", "")
                x, y = rdata["point"]
                level_name = rdata["level"]

                level = ctx["level_map"].get(level_name)
                if level is None:
                    log_warn("Level '{}' not found - skipping room '{}'".format(
                        level_name, name
                    ))
                    continue

                room = doc.Create.NewRoom(level, UV(x, y))

                # Set name
                name_param = room.get_Parameter(BuiltInParameter.ROOM_NAME)
                if name_param:
                    name_param.Set(name)

                # Set number
                if number:
                    num_param = room.get_Parameter(
                        BuiltInParameter.ROOM_NUMBER
                    )
                    if num_param:
                        num_param.Set(number)

                # Set finishes
                for finish_key, bip in [
                    ("floor_finish", BuiltInParameter.ROOM_FINISH_FLOOR),
                    ("wall_finish", BuiltInParameter.ROOM_FINISH_WALL),
                    ("ceiling_finish", BuiltInParameter.ROOM_FINISH_CEILING),
                ]:
                    finish_val = rdata.get(finish_key, "")
                    if finish_val:
                        param = room.get_Parameter(bip)
                        if param:
                            param.Set(finish_val)

                summary["rooms"] += 1
            except Exception as e:
                log_error("Failed to create room '{}': {}".format(
                    rdata.get("name", "?"), str(e)
                ))

    log_ok("Total: {} rooms".format(summary["rooms"]))


# ═══════════════════════════════════════════════════════════════
#  STEPS 13-18: STUBS (Visual/Documentation Layer)
# ═══════════════════════════════════════════════════════════════

def step_13_apply_graphic_styles(batch):
    """Apply graphic styles. STUB - not yet implemented."""
    log_step(13, "Apply graphic styles")
    styles = batch["definitions"].get("graphic_styles")
    if not styles:
        log_ok("No graphic styles defined - skipping")
        return
    log_warn("Graphic styles application not yet implemented - skipping")
    # TODO: OverrideGraphicSettings per category
    # TODO: Set line weights via doc.Settings.Categories
    # TODO: Apply filter overrides


def step_14_bind_shared_parameters(batch):
    """Bind shared parameters. STUB - not yet implemented."""
    log_step(14, "Bind shared parameters")
    params = batch["definitions"].get("shared_parameters", [])
    if not params:
        log_ok("No shared parameters defined - skipping")
        return
    log_warn(
        "Shared parameter binding not yet implemented"
        " - skipping ({} params)".format(len(params))
    )
    # TODO: Create shared parameter file
    # TODO: Define ExternalDefinition for each param
    # TODO: Create CategorySet, bind via InstanceBinding or TypeBinding


def step_15_create_views(batch):
    """Create views. STUB - not yet implemented."""
    log_step(15, "Create views")
    views_data = batch["manifest"].get("views", "use_template_defaults")
    if views_data == "use_template_defaults":
        log_warn("Views from template defaults not yet implemented")
    else:
        log_warn("Custom view creation not yet implemented ({} views)".format(
            len(views_data)
        ))
    # TODO: Resolve ViewFamilyType IDs
    # TODO: ViewPlan.Create(doc, viewFamilyTypeId, levelId) per level
    # TODO: Handle per_level flag


def step_16_create_sheets(batch):
    """Create sheets. STUB - not yet implemented."""
    log_step(16, "Create sheets")
    sheets_data = batch["manifest"].get("sheets", "use_template_defaults")
    if sheets_data == "use_template_defaults":
        log_warn("Sheets from template defaults not yet implemented")
    else:
        log_warn("Custom sheet creation not yet implemented ({} sheets)".format(
            len(sheets_data)
        ))
    # TODO: Load titleblock family
    # TODO: ViewSheet.Create(doc, titleblockId)
    # TODO: Viewport.Create(doc, sheetId, viewId, center)


def step_17_apply_view_templates(batch):
    """Apply view templates. STUB - not yet implemented."""
    log_step(17, "Apply view templates")
    templates = batch["definitions"].get("view_templates", [])
    if not templates:
        log_ok("No view templates defined - skipping")
        return
    log_warn(
        "View template application not yet implemented"
        " ({} templates)".format(len(templates))
    )
    # TODO: Duplicate view as template
    # TODO: Set scale, detail_level, category visibility
    # TODO: Apply to target views


def step_18_apply_naming_conventions(batch):
    """Apply naming conventions. STUB - not yet implemented."""
    log_step(18, "Apply naming conventions")
    naming = batch["definitions"].get("naming_conventions")
    if not naming:
        log_ok("No naming conventions defined - skipping")
        return
    log_warn("Naming convention application not yet implemented")
    # TODO: Rename levels per pattern
    # TODO: Rename views per discipline/level
    # TODO: Rename sheets per numbering scheme


# ═══════════════════════════════════════════════════════════════
#  STEP 19: SAVE
# ═══════════════════════════════════════════════════════════════

def step_19_save(batch):
    """Save the project. STUB - manual save required."""
    log_step(19, "Save project")
    project_name = batch["project"].get("project_name", "NGM_Project")
    log_warn(
        "Automatic SaveAs not yet implemented. "
        "Please save manually as '{}.rvt'".format(project_name)
    )
    # TODO: forms.save_file(file_ext="rvt", default_name=project_name)
    # TODO: doc.SaveAs(save_path, SaveAsOptions())


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    output.print_md("# NGM Build Engine - Build From Batch")
    output.print_md("**Started**: {}".format(
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    # Step 1: Read batch (before TransactionGroup)
    batch = step_01_read_batch()
    if batch is None:
        return

    # Wrap all model modifications in a TransactionGroup
    tg = TransactionGroup(doc, "NGM - Build From Batch")
    tg.Start()

    try:
        step_02_create_levels(batch)
        step_03_create_grids(batch)
        step_04_create_wall_types(batch)
        step_05_create_floor_types(batch)
        step_06_load_families(batch)
        step_07_create_walls(batch)
        step_08_create_floors(batch)
        step_09_create_columns(batch)
        step_10_create_beams(batch)
        step_11_insert_fixtures(batch)
        step_12_create_rooms(batch)
        step_13_apply_graphic_styles(batch)
        step_14_bind_shared_parameters(batch)
        step_15_create_views(batch)
        step_16_create_sheets(batch)
        step_17_apply_view_templates(batch)
        step_18_apply_naming_conventions(batch)
        step_19_save(batch)

        # Commit all transactions as a single undo group
        tg.Assimilate()

    except Exception as e:
        log_error("CRITICAL: Build failed - {}".format(str(e)))
        output.print_md("**Rolling back all changes...**")
        tg.RollBack()
        return

    # ── Build Summary ──
    output.print_md("---")
    output.print_md("# Build Summary")
    output.print_md("**Completed**: {}".format(
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    table_data = []
    for key, count in summary.items():
        if count > 0:
            table_data.append([
                key.replace("_", " ").title(),
                str(count),
            ])

    output.print_table(
        table_data,
        columns=["Element Type", "Count"],
    )

    if summary["errors"] > 0:
        output.print_md(
            "**{} errors occurred** - review output above.".format(
                summary["errors"]
            )
        )
    if summary["warnings"] > 0:
        output.print_md(
            "{} warnings - review output above.".format(
                summary["warnings"]
            )
        )

    output.print_md("---")
    output.print_md("**Build complete.**")


main()
