# -*- coding: utf-8 -*-
"""Exportar Materiales - Extrae materiales y cantidades del modelo activo.

Recorre todos los elementos del modelo, agrupa por material,
y exporta un JSON con cantidades (area, volumen) por cada material.
"""
__title__ = "Exportar\nMateriales"
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
    UnitUtils,
)

from pyrevit import revit, DB, script

output = script.get_output()
doc = revit.doc

# Carpeta de salida
EXPORT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ))),
    "exports"
)

# Categorias relevantes para construccion
CATEGORIES = [
    BuiltInCategory.OST_Walls,
    BuiltInCategory.OST_Floors,
    BuiltInCategory.OST_Roofs,
    BuiltInCategory.OST_StructuralColumns,
    BuiltInCategory.OST_StructuralFraming,
    BuiltInCategory.OST_StructuralFoundation,
    BuiltInCategory.OST_Doors,
    BuiltInCategory.OST_Windows,
    BuiltInCategory.OST_Stairs,
]

CATEGORY_NAMES = {
    BuiltInCategory.OST_Walls: "Walls",
    BuiltInCategory.OST_Floors: "Floors",
    BuiltInCategory.OST_Roofs: "Roofs",
    BuiltInCategory.OST_StructuralColumns: "Structural Columns",
    BuiltInCategory.OST_StructuralFraming: "Structural Framing",
    BuiltInCategory.OST_StructuralFoundation: "Foundations",
    BuiltInCategory.OST_Doors: "Doors",
    BuiltInCategory.OST_Windows: "Windows",
    BuiltInCategory.OST_Stairs: "Stairs",
}


def get_element_materials(element):
    """Obtiene los materiales de un elemento y sus areas/volumenes."""
    materials = []
    try:
        mat_ids = element.GetMaterialIds(False)
        for mat_id in mat_ids:
            mat = doc.GetElement(mat_id)
            if mat is None:
                continue
            mat_area = element.GetMaterialArea(mat_id, False)
            mat_vol = element.GetMaterialVolume(mat_id)

            # Convertir de pies internos a metros
            area_m2 = mat_area * 0.092903  # sq ft -> m2
            vol_m3 = mat_vol * 0.0283168   # cu ft -> m3

            if area_m2 > 0.001 or vol_m3 > 0.001:
                materials.append({
                    "material_name": mat.Name,
                    "area_m2": round(area_m2, 4),
                    "volume_m3": round(vol_m3, 4),
                })
    except Exception:
        pass
    return materials


def get_element_info(element, category_name):
    """Extrae informacion basica de un elemento."""
    try:
        family_name = ""
        type_name = ""

        elem_type = doc.GetElement(element.GetTypeId())
        if elem_type:
            type_name = elem_type.get_Parameter(
                BuiltInParameter.ALL_MODEL_TYPE_NAME
            )
            type_name = type_name.AsString() if type_name else ""

            family_name = elem_type.get_Parameter(
                BuiltInParameter.ALL_MODEL_FAMILY_NAME
            )
            family_name = family_name.AsString() if family_name else ""

        # Area y volumen del elemento completo
        area_param = element.get_Parameter(BuiltInParameter.HOST_AREA_COMPUTED)
        vol_param = element.get_Parameter(
            BuiltInParameter.HOST_VOLUME_COMPUTED
        )

        area_m2 = 0
        vol_m3 = 0
        if area_param and area_param.HasValue:
            area_m2 = round(area_param.AsDouble() * 0.092903, 4)
        if vol_param and vol_param.HasValue:
            vol_m3 = round(vol_param.AsDouble() * 0.0283168, 4)

        return {
            "element_id": element.Id.IntegerValue,
            "category": category_name,
            "family": family_name,
            "type": type_name,
            "area_m2": area_m2,
            "volume_m3": vol_m3,
            "materials": get_element_materials(element),
        }
    except Exception:
        return None


def main():
    output.print_md("# NGM - Exportar Materiales")
    output.print_md("Extrayendo datos del modelo: **{}**".format(doc.Title))

    all_items = []
    material_summary = {}

    for bic in CATEGORIES:
        cat_name = CATEGORY_NAMES.get(bic, str(bic))
        collector = (
            FilteredElementCollector(doc)
            .OfCategory(bic)
            .WhereElementIsNotElementType()
        )
        elements = list(collector)

        if not elements:
            continue

        output.print_md("- **{}**: {} elementos".format(cat_name, len(elements)))

        for elem in elements:
            info = get_element_info(elem, cat_name)
            if info is None:
                continue
            all_items.append(info)

            # Agregar al resumen por material
            for mat in info["materials"]:
                mat_name = mat["material_name"]
                if mat_name not in material_summary:
                    material_summary[mat_name] = {
                        "material": mat_name,
                        "total_area_m2": 0,
                        "total_volume_m3": 0,
                        "element_count": 0,
                        "categories": set(),
                    }
                material_summary[mat_name]["total_area_m2"] += mat["area_m2"]
                material_summary[mat_name]["total_volume_m3"] += mat["volume_m3"]
                material_summary[mat_name]["element_count"] += 1
                material_summary[mat_name]["categories"].add(cat_name)

    # Convertir sets a listas para JSON
    summary_list = []
    for mat_name, data in sorted(material_summary.items()):
        summary_list.append({
            "material": data["material"],
            "total_area_m2": round(data["total_area_m2"], 2),
            "total_volume_m3": round(data["total_volume_m3"], 4),
            "element_count": data["element_count"],
            "categories": sorted(list(data["categories"])),
        })

    # Construir JSON de salida
    export_data = {
        "export_info": {
            "revit_file": doc.Title,
            "export_date": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "export_type": "materials",
            "units": "metric",
            "total_elements": len(all_items),
            "total_materials": len(summary_list),
        },
        "material_summary": summary_list,
        "elements": all_items,
    }

    # Guardar JSON
    if not os.path.exists(EXPORT_DIR):
        os.makedirs(EXPORT_DIR)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = "materials_{project}_{ts}.json".format(
        project=doc.Title.replace(" ", "_"),
        ts=timestamp,
    )
    filepath = os.path.join(EXPORT_DIR, filename)

    with codecs.open(filepath, "w", "utf-8") as f:
        json.dump(export_data, f, indent=2)

    output.print_md("---")
    output.print_md(
        "## Exportado: **{}** materiales de **{}** elementos".format(
            len(summary_list), len(all_items)
        )
    )
    output.print_md("Archivo: `{}`".format(filepath))

    # Tabla resumen
    output.print_md("### Resumen por Material")
    table_data = []
    for mat in summary_list:
        table_data.append([
            mat["material"],
            "{:.2f}".format(mat["total_area_m2"]),
            "{:.4f}".format(mat["total_volume_m3"]),
            str(mat["element_count"]),
            ", ".join(mat["categories"]),
        ])

    output.print_table(
        table_data,
        columns=["Material", "Area (m2)", "Volumen (m3)", "Elementos", "Categorias"],
    )


main()
