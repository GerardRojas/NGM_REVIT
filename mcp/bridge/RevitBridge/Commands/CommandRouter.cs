using System;
using System.Collections.Generic;
using System.Linq;
using Autodesk.Revit.DB;
using Autodesk.Revit.DB.Architecture;
using Autodesk.Revit.UI;

namespace NGM.RevitBridge
{
    /// <summary>
    /// Routes incoming commands to the appropriate Revit API operations.
    /// All methods here run on the Revit MAIN THREAD via ExternalEvent.
    /// </summary>
    public static class CommandRouter
    {
        public static Dictionary<string, object> Route(
            Document doc,
            UIApplication uiApp,
            string command,
            Dictionary<string, object> parameters)
        {
            switch (command)
            {
                case "get_document_info":
                    return GetDocumentInfo(doc);

                case "get_elements_by_category":
                    return GetElementsByCategory(doc, parameters);

                case "get_element_parameters":
                    return GetElementParameters(doc, parameters);

                case "get_quantities_summary":
                    return GetQuantitiesSummary(doc);

                case "get_rooms":
                    return GetRooms(doc);

                case "get_levels":
                    return GetLevels(doc);

                case "get_materials_summary":
                    return GetMaterialsSummary(doc);

                case "get_selected_elements":
                    return GetSelectedElements(uiApp);

                case "search_elements":
                    return SearchElements(doc, parameters);

                case "create_wall":
                    return CreateWall(doc, parameters);

                case "set_parameter":
                    return SetParameter(doc, parameters);

                // TODO: export_quantities, export_materials, push_to_estimator

                default:
                    return new Dictionary<string, object>
                    {
                        { "error", $"Unknown command: {command}" }
                    };
            }
        }

        // -------------------------------------------------------------------
        // Query commands
        // -------------------------------------------------------------------

        private static Dictionary<string, object> GetDocumentInfo(Document doc)
        {
            var collector = new FilteredElementCollector(doc)
                .WhereElementIsNotElementType();

            return new Dictionary<string, object>
            {
                { "title", doc.Title },
                { "path", doc.PathName ?? "Not saved" },
                { "element_count", collector.GetElementCount() }
            };
        }

        private static Dictionary<string, object> GetElementsByCategory(
            Document doc, Dictionary<string, object> parameters)
        {
            var categoryName = parameters["category"]?.ToString();
            var builtInCat = CategoryNameToBuiltIn(categoryName);

            if (builtInCat == null)
                return Error($"Unknown category: {categoryName}");

            var collector = new FilteredElementCollector(doc)
                .OfCategory(builtInCat.Value)
                .WhereElementIsNotElementType();

            var elements = collector.Select(e => new Dictionary<string, object>
            {
                { "id", e.Id.IntegerValue },
                { "name", e.Name },
                { "family", GetFamilyName(e) },
                { "type", GetTypeName(doc, e) },
                { "level", GetLevelName(doc, e) }
            }).ToList();

            return new Dictionary<string, object>
            {
                { "category", categoryName },
                { "count", elements.Count },
                { "elements", elements }
            };
        }

        private static Dictionary<string, object> GetElementParameters(
            Document doc, Dictionary<string, object> parameters)
        {
            var id = Convert.ToInt32(parameters["element_id"]);
            var element = doc.GetElement(new ElementId(id));

            if (element == null)
                return Error($"Element not found: {id}");

            var paramList = new List<Dictionary<string, object>>();
            foreach (Parameter p in element.Parameters)
            {
                if (!p.HasValue) continue;
                paramList.Add(new Dictionary<string, object>
                {
                    { "name", p.Definition.Name },
                    { "value", GetParameterValue(p) },
                    { "type", p.StorageType.ToString() },
                    { "read_only", p.IsReadOnly }
                });
            }

            return new Dictionary<string, object>
            {
                { "element_id", id },
                { "name", element.Name },
                { "category", element.Category?.Name ?? "None" },
                { "parameters", paramList }
            };
        }

        private static Dictionary<string, object> GetQuantitiesSummary(Document doc)
        {
            var categories = new[]
            {
                BuiltInCategory.OST_Walls,
                BuiltInCategory.OST_Floors,
                BuiltInCategory.OST_Roofs,
                BuiltInCategory.OST_StructuralColumns,
                BuiltInCategory.OST_StructuralFraming,
                BuiltInCategory.OST_StructuralFoundation,
                BuiltInCategory.OST_Doors,
                BuiltInCategory.OST_Windows,
                BuiltInCategory.OST_Stairs,
                BuiltInCategory.OST_Rooms
            };

            var summary = new List<Dictionary<string, object>>();

            foreach (var cat in categories)
            {
                var elements = new FilteredElementCollector(doc)
                    .OfCategory(cat)
                    .WhereElementIsNotElementType()
                    .ToList();

                if (elements.Count == 0) continue;

                // Group by type name
                var grouped = elements.GroupBy(e => GetTypeName(doc, e));
                foreach (var group in grouped)
                {
                    double area = 0, volume = 0;
                    foreach (var el in group)
                    {
                        var areaParam = el.get_Parameter(BuiltInParameter.HOST_AREA_COMPUTED);
                        if (areaParam?.HasValue == true)
                            area += areaParam.AsDouble();

                        var volParam = el.get_Parameter(BuiltInParameter.HOST_VOLUME_COMPUTED);
                        if (volParam?.HasValue == true)
                            volume += volParam.AsDouble();
                    }

                    summary.Add(new Dictionary<string, object>
                    {
                        { "category", cat.ToString().Replace("OST_", "") },
                        { "type", group.Key },
                        { "count", group.Count() },
                        { "area_sqft", Math.Round(area, 2) },
                        { "volume_cuft", Math.Round(volume, 2) }
                    });
                }
            }

            return new Dictionary<string, object> { { "quantities", summary } };
        }

        private static Dictionary<string, object> GetRooms(Document doc)
        {
            var rooms = new FilteredElementCollector(doc)
                .OfCategory(BuiltInCategory.OST_Rooms)
                .WhereElementIsNotElementType()
                .Cast<Room>()
                .Where(r => r.Area > 0)
                .Select(r => new Dictionary<string, object>
                {
                    { "id", r.Id.IntegerValue },
                    { "name", r.get_Parameter(BuiltInParameter.ROOM_NAME)?.AsString() ?? "" },
                    { "number", r.Number },
                    { "level", r.Level?.Name ?? "" },
                    { "area_sqft", Math.Round(r.Area, 2) },
                    { "perimeter_ft", Math.Round(r.Perimeter, 2) },
                    { "floor_finish", r.get_Parameter(BuiltInParameter.ROOM_FINISH_FLOOR)?.AsString() ?? "" },
                    { "wall_finish", r.get_Parameter(BuiltInParameter.ROOM_FINISH_WALL)?.AsString() ?? "" },
                    { "ceiling_finish", r.get_Parameter(BuiltInParameter.ROOM_FINISH_CEILING)?.AsString() ?? "" }
                }).ToList();

            return new Dictionary<string, object>
            {
                { "count", rooms.Count },
                { "rooms", rooms }
            };
        }

        private static Dictionary<string, object> GetLevels(Document doc)
        {
            var levels = new FilteredElementCollector(doc)
                .OfClass(typeof(Level))
                .Cast<Level>()
                .OrderBy(l => l.Elevation)
                .Select(l => new Dictionary<string, object>
                {
                    { "id", l.Id.IntegerValue },
                    { "name", l.Name },
                    { "elevation_ft", Math.Round(l.Elevation, 4) }
                }).ToList();

            return new Dictionary<string, object>
            {
                { "count", levels.Count },
                { "levels", levels }
            };
        }

        private static Dictionary<string, object> GetMaterialsSummary(Document doc)
        {
            // Collect all elements that have materials
            var collector = new FilteredElementCollector(doc)
                .WhereElementIsNotElementType()
                .Where(e => e.Category != null);

            var materialData = new Dictionary<int, Dictionary<string, object>>();

            foreach (var el in collector)
            {
                foreach (var matId in el.GetMaterialIds(false))
                {
                    var mat = doc.GetElement(matId) as Material;
                    if (mat == null) continue;

                    var id = matId.IntegerValue;
                    if (!materialData.ContainsKey(id))
                    {
                        materialData[id] = new Dictionary<string, object>
                        {
                            { "id", id },
                            { "name", mat.Name },
                            { "area_sqft", 0.0 },
                            { "volume_cuft", 0.0 },
                            { "element_count", 0 }
                        };
                    }

                    var area = el.GetMaterialArea(matId, false);
                    var volume = el.GetMaterialVolume(matId);
                    materialData[id]["area_sqft"] =
                        (double)materialData[id]["area_sqft"] + area;
                    materialData[id]["volume_cuft"] =
                        (double)materialData[id]["volume_cuft"] + volume;
                    materialData[id]["element_count"] =
                        (int)materialData[id]["element_count"] + 1;
                }
            }

            var materials = materialData.Values
                .OrderByDescending(m => (double)m["area_sqft"])
                .ToList();

            // Round values
            foreach (var m in materials)
            {
                m["area_sqft"] = Math.Round((double)m["area_sqft"], 2);
                m["volume_cuft"] = Math.Round((double)m["volume_cuft"], 2);
            }

            return new Dictionary<string, object>
            {
                { "count", materials.Count },
                { "materials", materials }
            };
        }

        private static Dictionary<string, object> GetSelectedElements(UIApplication uiApp)
        {
            var uidoc = uiApp.ActiveUIDocument;
            if (uidoc == null)
                return Error("No active document");

            var selection = uidoc.Selection.GetElementIds();
            var elements = selection.Select(id =>
            {
                var el = uidoc.Document.GetElement(id);
                return new Dictionary<string, object>
                {
                    { "id", id.IntegerValue },
                    { "name", el.Name },
                    { "category", el.Category?.Name ?? "None" },
                    { "family", GetFamilyName(el) },
                    { "type", GetTypeName(uidoc.Document, el) }
                };
            }).ToList();

            return new Dictionary<string, object>
            {
                { "count", elements.Count },
                { "elements", elements }
            };
        }

        private static Dictionary<string, object> SearchElements(
            Document doc, Dictionary<string, object> parameters)
        {
            var query = parameters["query"]?.ToString()?.ToLowerInvariant() ?? "";

            var collector = new FilteredElementCollector(doc)
                .WhereElementIsNotElementType()
                .Where(e => e.Category != null);

            var results = collector.Where(e =>
                (e.Name?.ToLowerInvariant().Contains(query) == true) ||
                (GetFamilyName(e)?.ToLowerInvariant().Contains(query) == true) ||
                (GetTypeName(doc, e)?.ToLowerInvariant().Contains(query) == true)
            )
            .Take(100) // Limit results
            .Select(e => new Dictionary<string, object>
            {
                { "id", e.Id.IntegerValue },
                { "name", e.Name },
                { "category", e.Category?.Name ?? "None" },
                { "family", GetFamilyName(e) },
                { "type", GetTypeName(doc, e) }
            }).ToList();

            return new Dictionary<string, object>
            {
                { "query", query },
                { "count", results.Count },
                { "elements", results }
            };
        }

        // -------------------------------------------------------------------
        // Modify commands
        // -------------------------------------------------------------------

        private static Dictionary<string, object> CreateWall(
            Document doc, Dictionary<string, object> parameters)
        {
            // Parse parameters
            var start = parameters["start"] as object[];
            var end = parameters["end"] as object[];
            var wallTypeName = parameters["wall_type"]?.ToString();
            var levelName = parameters["level"]?.ToString();
            var heightFt = Convert.ToDouble(parameters["height_ft"]);

            // Find wall type
            var wallType = new FilteredElementCollector(doc)
                .OfClass(typeof(WallType))
                .FirstOrDefault(t => t.Name == wallTypeName) as WallType;

            if (wallType == null)
                return Error($"Wall type not found: {wallTypeName}");

            // Find level
            var level = new FilteredElementCollector(doc)
                .OfClass(typeof(Level))
                .FirstOrDefault(l => l.Name == levelName) as Level;

            if (level == null)
                return Error($"Level not found: {levelName}");

            // Create the wall
            using (var trans = new Transaction(doc, "NGM Bridge: Create Wall"))
            {
                trans.Start();

                var line = Line.CreateBound(
                    new XYZ(Convert.ToDouble(start[0]), Convert.ToDouble(start[1]), 0),
                    new XYZ(Convert.ToDouble(end[0]), Convert.ToDouble(end[1]), 0)
                );

                var wall = Wall.Create(doc, line, wallType.Id, level.Id, heightFt, 0, false, false);
                trans.Commit();

                return new Dictionary<string, object>
                {
                    { "created", true },
                    { "element_id", wall.Id.IntegerValue },
                    { "wall_type", wallTypeName },
                    { "level", levelName },
                    { "length_ft", Math.Round(line.Length, 4) },
                    { "height_ft", heightFt }
                };
            }
        }

        private static Dictionary<string, object> SetParameter(
            Document doc, Dictionary<string, object> parameters)
        {
            var id = Convert.ToInt32(parameters["element_id"]);
            var paramName = parameters["parameter_name"]?.ToString();
            var value = parameters["value"]?.ToString();

            var element = doc.GetElement(new ElementId(id));
            if (element == null)
                return Error($"Element not found: {id}");

            var param = element.LookupParameter(paramName);
            if (param == null)
                return Error($"Parameter not found: {paramName}");

            if (param.IsReadOnly)
                return Error($"Parameter is read-only: {paramName}");

            using (var trans = new Transaction(doc, "NGM Bridge: Set Parameter"))
            {
                trans.Start();

                bool success;
                switch (param.StorageType)
                {
                    case StorageType.String:
                        success = param.Set(value);
                        break;
                    case StorageType.Integer:
                        success = param.Set(Convert.ToInt32(value));
                        break;
                    case StorageType.Double:
                        success = param.Set(Convert.ToDouble(value));
                        break;
                    default:
                        success = false;
                        break;
                }

                if (success)
                    trans.Commit();
                else
                    trans.RollBack();

                return new Dictionary<string, object>
                {
                    { "success", success },
                    { "element_id", id },
                    { "parameter", paramName },
                    { "value", value }
                };
            }
        }

        // -------------------------------------------------------------------
        // Helpers
        // -------------------------------------------------------------------

        private static string GetFamilyName(Element e)
        {
            if (e is FamilyInstance fi)
                return fi.Symbol?.Family?.Name ?? "";
            return "";
        }

        private static string GetTypeName(Document doc, Element e)
        {
            var typeId = e.GetTypeId();
            if (typeId == ElementId.InvalidElementId) return e.Name;
            var typeElement = doc.GetElement(typeId);
            return typeElement?.Name ?? e.Name;
        }

        private static string GetLevelName(Document doc, Element e)
        {
            var levelId = e.LevelId;
            if (levelId == null || levelId == ElementId.InvalidElementId) return "";
            var level = doc.GetElement(levelId) as Level;
            return level?.Name ?? "";
        }

        private static string GetParameterValue(Parameter p)
        {
            switch (p.StorageType)
            {
                case StorageType.String: return p.AsString() ?? "";
                case StorageType.Integer: return p.AsInteger().ToString();
                case StorageType.Double: return Math.Round(p.AsDouble(), 6).ToString();
                case StorageType.ElementId: return p.AsElementId().IntegerValue.ToString();
                default: return "";
            }
        }

        private static BuiltInCategory? CategoryNameToBuiltIn(string name)
        {
            var map = new Dictionary<string, BuiltInCategory>(StringComparer.OrdinalIgnoreCase)
            {
                { "Walls", BuiltInCategory.OST_Walls },
                { "Floors", BuiltInCategory.OST_Floors },
                { "Roofs", BuiltInCategory.OST_Roofs },
                { "Doors", BuiltInCategory.OST_Doors },
                { "Windows", BuiltInCategory.OST_Windows },
                { "Structural Columns", BuiltInCategory.OST_StructuralColumns },
                { "Structural Framing", BuiltInCategory.OST_StructuralFraming },
                { "Structural Foundation", BuiltInCategory.OST_StructuralFoundation },
                { "Rooms", BuiltInCategory.OST_Rooms },
                { "Stairs", BuiltInCategory.OST_Stairs },
                { "Columns", BuiltInCategory.OST_Columns },
                { "Ceilings", BuiltInCategory.OST_Ceilings },
                { "Furniture", BuiltInCategory.OST_Furniture },
                { "Plumbing Fixtures", BuiltInCategory.OST_PlumbingFixtures },
                { "Mechanical Equipment", BuiltInCategory.OST_MechanicalEquipment },
                { "Electrical Fixtures", BuiltInCategory.OST_ElectricalFixtures }
            };

            return map.ContainsKey(name) ? (BuiltInCategory?)map[name] : null;
        }

        private static Dictionary<string, object> Error(string message)
        {
            return new Dictionary<string, object> { { "error", message } };
        }
    }
}
