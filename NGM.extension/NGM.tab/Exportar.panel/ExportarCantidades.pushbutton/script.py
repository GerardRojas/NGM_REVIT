# -*- coding: utf-8 -*-
"""Exportar Cantidades - Agrupa elementos por Family+Type con totales.

Genera un resumen tipo "schedule" agrupado por categoria y tipo,
con conteo, area total y volumen total. Ideal para cuantificacion
rapida compatible con el estimador de NGM.
"""
__title__ = "Exportar\nCantidades"
__author__ = "NGM"

import clr
import os
import json
import codecs
from datetime import datetime
from collections import OrderedDict

clr.AddReference('RevitAPI')
from Autodesk.Revit.DB import (
    FilteredElementCollector,
    BuiltInCategory,
    BuiltInParameter,
)

from pyrevit import revit, DB, script

output = script.get_output()
doc = revit.doc

EXPORT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ))),
    "exports"
)

CATEGORIES = OrderedDict([
    (BuiltInCategory.OST_Walls, {
        "name": "Walls",
        "unit": "m2",
        "primary_qty": "area",
    }),
    (BuiltInCategory.OST_Floors, {
        "name": "Floors",
        "unit": "m2",
        "primary_qty": "area",
    }),
    (BuiltInCategory.OST_Roofs, {
        "name": "Roofs",
        "unit": "m2",
        "primary_qty": "area",
    }),
    (BuiltInCategory.OST_StructuralColumns, {
        "name": "Structural Columns",
        "unit": "m3",
        "primary_qty": "volume",
    }),
    (BuiltInCategory.OST_StructuralFraming, {
        "name": "Structural Framing",
        "unit": "ml",
        "primary_qty": "length",
    }),
    (BuiltInCategory.OST_StructuralFoundation, {
        "name": "Foundations",
        "unit": "m3",
        "primary_qty": "volume",
    }),
    (BuiltInCategory.OST_Doors, {
        "name": "Doors",
        "unit": "pza",
        "primary_qty": "count",
    }),
    (BuiltInCategory.OST_Windows, {
        "name": "Windows",
        "unit": "pza",
        "primary_qty": "count",
    }),
    (BuiltInCategory.OST_Stairs, {
        "name": "Stairs",
        "unit": "pza",
        "primary_qty": "count",
    }),
    (BuiltInCategory.OST_Rebar, {
        "name": "Rebar",
        "unit": "kg",
        "primary_qty": "length",
    }),
])

# Conversion de unidades internas de Revit (imperial) a metrico
FT2_TO_M2 = 0.092903
FT3_TO_M3 = 0.0283168
FT_TO_M = 0.3048


def get_quantity(element, qty_type):
    """Extrae la cantidad principal de un elemento segun su tipo."""
    try:
        if qty_type == "area":
            param = element.get_Parameter(BuiltInParameter.HOST_AREA_COMPUTED)
            if param and param.HasValue:
                return round(param.AsDouble() * FT2_TO_M2, 4)
        elif qty_type == "volume":
            param = element.get_Parameter(BuiltInParameter.HOST_VOLUME_COMPUTED)
            if param and param.HasValue:
                return round(param.AsDouble() * FT3_TO_M3, 4)
        elif qty_type == "length":
            # Intentar largo de curva o parametro de longitud
            param = element.get_Parameter(
                BuiltInParameter.CURVE_ELEM_LENGTH
            )
            if param and param.HasValue:
                return round(param.AsDouble() * FT_TO_M, 4)
            # Fallback: instance length
            param = element.get_Parameter(
                BuiltInParameter.INSTANCE_LENGTH_PARAM
            )
            if param and param.HasValue:
                return round(param.AsDouble() * FT_TO_M, 4)
        elif qty_type == "count":
            return 1
    except Exception:
        pass
    return 0


def main():
    output.print_md("# NGM - Exportar Cantidades")
    output.print_md("Modelo: **{}**".format(doc.Title))

    items = []

    for bic, cat_info in CATEGORIES.items():
        cat_name = cat_info["name"]
        primary_unit = cat_info["unit"]
        primary_qty_type = cat_info["primary_qty"]

        collector = (
            FilteredElementCollector(doc)
            .OfCategory(bic)
            .WhereElementIsNotElementType()
        )
        elements = list(collector)

        if not elements:
            continue

        # Agrupar por Family + Type
        groups = {}
        for elem in elements:
            try:
                elem_type = doc.GetElement(elem.GetTypeId())
                if not elem_type:
                    continue

                t_param = elem_type.get_Parameter(
                    BuiltInParameter.ALL_MODEL_TYPE_NAME
                )
                f_param = elem_type.get_Parameter(
                    BuiltInParameter.ALL_MODEL_FAMILY_NAME
                )
                type_name = t_param.AsString() if t_param else "Unknown"
                family_name = f_param.AsString() if f_param else "Unknown"
                key = "{} : {}".format(family_name, type_name)

                qty = get_quantity(elem, primary_qty_type)

                if key not in groups:
                    groups[key] = {
                        "category": cat_name,
                        "family": family_name,
                        "type": type_name,
                        "unit": primary_unit,
                        "quantity": 0,
                        "count": 0,
                        "element_ids": [],
                    }
                groups[key]["quantity"] += qty
                groups[key]["count"] += 1
                groups[key]["element_ids"].append(elem.Id.IntegerValue)
            except Exception:
                continue

        output.print_md("### {}".format(cat_name))
        table_data = []
        for key in sorted(groups.keys()):
            g = groups[key]
            g["quantity"] = round(g["quantity"], 2)
            items.append(g)
            table_data.append([
                g["family"],
                g["type"],
                str(g["count"]),
                "{} {}".format(g["quantity"], g["unit"]),
            ])

        output.print_table(
            table_data,
            columns=["Family", "Type", "Count", "Quantity"],
        )

    # JSON de salida
    export_data = {
        "export_info": {
            "revit_file": doc.Title,
            "export_date": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "export_type": "quantities",
            "units": "metric",
            "total_line_items": len(items),
        },
        "items": items,
    }

    if not os.path.exists(EXPORT_DIR):
        os.makedirs(EXPORT_DIR)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = "quantities_{project}_{ts}.json".format(
        project=doc.Title.replace(" ", "_"),
        ts=timestamp,
    )
    filepath = os.path.join(EXPORT_DIR, filename)

    with codecs.open(filepath, "w", "utf-8") as f:
        json.dump(export_data, f, indent=2)

    output.print_md("---")
    output.print_md(
        "Exportado: **{}** items agrupados".format(len(items))
    )
    output.print_md("Archivo: `{}`".format(filepath))


main()
