# -*- coding: utf-8 -*-
"""Exportar Espacios - Extrae Rooms con areas y acabados.

Recorre todos los Rooms del modelo y exporta:
- Nombre, numero, nivel
- Area de piso, perimetro
- Materiales de acabados (piso, muro, techo) si estan asignados
Util para presupuesto de acabados interiores.
"""
__title__ = "Exportar\nEspacios"
__author__ = "NGM"

import clr
import os
import json
import codecs
from datetime import datetime

clr.AddReference('RevitAPI')
from Autodesk.Revit.DB import (
    FilteredElementCollector,
    BuiltInCategory,
    BuiltInParameter,
    SpatialElementBoundaryOptions,
)
from Autodesk.Revit.DB.Architecture import Room

from pyrevit import revit, DB, script

output = script.get_output()
doc = revit.doc

EXPORT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ))),
    "exports"
)

FT2_TO_M2 = 0.092903
FT_TO_M = 0.3048


def get_param_string(element, bip):
    """Obtiene el valor string de un BuiltInParameter."""
    try:
        param = element.get_Parameter(bip)
        if param and param.HasValue:
            return param.AsString() or ""
    except Exception:
        pass
    return ""


def get_param_double(element, bip, factor=1.0):
    """Obtiene el valor numerico de un BuiltInParameter con conversion."""
    try:
        param = element.get_Parameter(bip)
        if param and param.HasValue:
            return round(param.AsDouble() * factor, 4)
    except Exception:
        pass
    return 0


def get_finish_material(element, bip):
    """Obtiene el nombre del material de acabado de un parametro ElementId."""
    try:
        param = element.get_Parameter(bip)
        if param and param.HasValue:
            mat_id = param.AsElementId()
            if mat_id and mat_id.IntegerValue > 0:
                mat = doc.GetElement(mat_id)
                if mat:
                    return mat.Name
    except Exception:
        pass
    return ""


def main():
    output.print_md("# NGM - Exportar Espacios")
    output.print_md("Modelo: **{}**".format(doc.Title))

    collector = (
        FilteredElementCollector(doc)
        .OfCategory(BuiltInCategory.OST_Rooms)
        .WhereElementIsNotElementType()
    )
    rooms = [r for r in collector if isinstance(r, Room) and r.Area > 0]

    if not rooms:
        output.print_md("**No se encontraron Rooms con area en el modelo.**")
        output.print_md(
            "Asegurate de que el modelo tenga Rooms colocados "
            "y con boundaries validos."
        )
        return

    output.print_md("Encontrados: **{}** rooms".format(len(rooms)))

    items = []
    level_summary = {}

    for room in rooms:
        room_name = get_param_string(room, BuiltInParameter.ROOM_NAME)
        room_number = get_param_string(room, BuiltInParameter.ROOM_NUMBER)

        level = room.Level
        level_name = level.Name if level else "Unknown"

        area_m2 = get_param_double(
            room, BuiltInParameter.ROOM_AREA, FT2_TO_M2
        )
        perimeter_m = get_param_double(
            room, BuiltInParameter.ROOM_PERIMETER, FT_TO_M
        )
        height_m = get_param_double(
            room,
            BuiltInParameter.ROOM_UPPER_OFFSET,
            FT_TO_M,
        )

        # Acabados
        floor_finish = get_param_string(
            room, BuiltInParameter.ROOM_FINISH_FLOOR
        )
        wall_finish = get_param_string(
            room, BuiltInParameter.ROOM_FINISH_WALL
        )
        ceiling_finish = get_param_string(
            room, BuiltInParameter.ROOM_FINISH_CEILING
        )

        # Calculos derivados
        wall_area_m2 = round(perimeter_m * height_m, 2) if height_m > 0 else 0

        room_data = {
            "element_id": room.Id.IntegerValue,
            "name": room_name,
            "number": room_number,
            "level": level_name,
            "area_m2": area_m2,
            "perimeter_m": round(perimeter_m, 2),
            "height_m": round(height_m, 2),
            "wall_area_m2": wall_area_m2,
            "finishes": {
                "floor": floor_finish,
                "wall": wall_finish,
                "ceiling": ceiling_finish,
            },
        }
        items.append(room_data)

        # Acumular por nivel
        if level_name not in level_summary:
            level_summary[level_name] = {
                "room_count": 0,
                "total_area_m2": 0,
                "total_wall_area_m2": 0,
            }
        level_summary[level_name]["room_count"] += 1
        level_summary[level_name]["total_area_m2"] += area_m2
        level_summary[level_name]["total_wall_area_m2"] += wall_area_m2

    # Tabla de rooms
    output.print_md("### Rooms")
    table_data = []
    for r in sorted(items, key=lambda x: (x["level"], x["number"])):
        table_data.append([
            r["number"],
            r["name"],
            r["level"],
            "{:.2f} m2".format(r["area_m2"]),
            "{:.2f} m2".format(r["wall_area_m2"]),
            r["finishes"]["floor"] or "-",
        ])

    output.print_table(
        table_data,
        columns=["#", "Name", "Level", "Floor Area", "Wall Area", "Floor Finish"],
    )

    # Resumen por nivel
    output.print_md("### Summary by Level")
    summary_table = []
    for level_name in sorted(level_summary.keys()):
        s = level_summary[level_name]
        summary_table.append([
            level_name,
            str(s["room_count"]),
            "{:.2f} m2".format(s["total_area_m2"]),
            "{:.2f} m2".format(s["total_wall_area_m2"]),
        ])

    output.print_table(
        summary_table,
        columns=["Level", "Rooms", "Total Floor Area", "Total Wall Area"],
    )

    # Resumen de acabados unicos (para mapeo a materiales del estimador)
    all_finishes = set()
    for r in items:
        for v in r["finishes"].values():
            if v:
                all_finishes.add(v)

    # JSON
    export_data = {
        "export_info": {
            "revit_file": doc.Title,
            "export_date": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "export_type": "spaces",
            "units": "metric",
            "total_rooms": len(items),
        },
        "level_summary": [
            {
                "level": k,
                "room_count": v["room_count"],
                "total_area_m2": round(v["total_area_m2"], 2),
                "total_wall_area_m2": round(v["total_wall_area_m2"], 2),
            }
            for k, v in sorted(level_summary.items())
        ],
        "unique_finishes": sorted(list(all_finishes)),
        "rooms": items,
    }

    if not os.path.exists(EXPORT_DIR):
        os.makedirs(EXPORT_DIR)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = "spaces_{project}_{ts}.json".format(
        project=doc.Title.replace(" ", "_"),
        ts=timestamp,
    )
    filepath = os.path.join(EXPORT_DIR, filename)

    with codecs.open(filepath, "w", "utf-8") as f:
        json.dump(export_data, f, indent=2)

    output.print_md("---")
    output.print_md(
        "Exportado: **{}** rooms, **{}** acabados unicos".format(
            len(items), len(all_finishes)
        )
    )
    output.print_md("Archivo: `{}`".format(filepath))


main()
