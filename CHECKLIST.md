# NGM Revit — Checklist de Definiciones y Familias

> Marca con `[x]` lo que ya tienes listo. Agrega notas en la columna de comentarios.
> Este archivo es la referencia viva del estado del vault y las definiciones.

---

## Definiciones de Muro (wall_types.json)

Estas se crean via codigo (CompoundStructure). Solo necesitan que los **materiales** existan en el proyecto Revit base.

| # | Listo | Nombre | Ancho (ft) | Funcion | Comentarios |
|---|---|---|---|---|---|
| 1 | [ ] | `Ext - CMU 6" + Plaster` | 0.6667 | Exterior | Plaster + CMU 6" + Plaster |
| 2 | [ ] | `Ext - CMU 8" + Plaster` | 0.8333 | Exterior | Plaster + CMU 8" + Plaster |
| 3 | [ ] | `Int - CMU 4" + Plaster` | 0.5 | Interior | Plaster + CMU 4" + Plaster |
| 4 | [ ] | `Int - CMU 6" + Plaster` | 0.6667 | Interior | Plaster + CMU 6" + Plaster |
| 5 | [ ] | `Int - Drywall 5"` | 0.4167 | Interior | GWB + Metal Stud 3-5/8" + GWB |
| 6 | [ ] | `Struct - Concrete 8"` | 0.6667 | Structural | Concreto solido |
| 7 | [ ] | `Struct - Concrete 10"` | 0.8333 | Structural | Concreto solido |
| 8 | [ ] | `Struct - Concrete 12"` | 1.0 | Structural | Concreto solido |
| 9 | [ ] | `Ext - Metal Panel + Insulation 6"` | 0.5 | Exterior | Industrial |

**Para agregar un wall type**: editar `definitions/wall_types.json`, actualizar count en `registry.json`.

---

## Definiciones de Piso (floor_types.json)

Misma logica — se crean via codigo. Solo necesitan materiales en el base.rvt.

| # | Listo | Nombre | Espesor (ft) | Comentarios |
|---|---|---|---|---|
| 1 | [ ] | `Slab - Concrete 5"` | 0.4167 | Losa estandar |
| 2 | [ ] | `Slab - Concrete 6"` | 0.5 | Losa gruesa |
| 3 | [ ] | `Slab - Concrete 8"` | 0.6667 | Losa pesada |
| 4 | [ ] | `Foundation Slab 8"` | 0.6667 | Cimentacion |
| 5 | [ ] | `Foundation Mat 16"` | 1.3333 | Losa de cimentacion (comercial) |
| 6 | [ ] | `SOG - Concrete 6"` | 0.5 | Slab-on-grade |
| 7 | [ ] | `Slab + Ceramic Tile` | 0.4583 | Ceramica + mortero + concreto |
| 8 | [ ] | `Metal Deck Composite` | 0.4375 | Losacero (industrial/comercial) |

**Para agregar un floor type**: editar `definitions/floor_types.json`, actualizar count en `registry.json`.

---

## Familias Estructurales (.rfa)

Estas REQUIEREN archivo .rfa creado en Revit Family Editor.

| # | Listo | Familia | Tipos requeridos | Vault path | Comentarios |
|---|---|---|---|---|---|
| 1 | [ ] | `NGM_Column_Rectangular` | 12x12 in, 16x16 in, 20x20 in | `families/structural/` | |
| 2 | [ ] | `NGM_Column_Circular` | 12 in dia, 18 in dia | `families/structural/` | |
| 3 | [ ] | `NGM_Column_Steel_W` | W8x31, W10x49, W12x65 | `families/structural/` | |
| 4 | [ ] | `NGM_Column_Steel_HSS` | HSS6x6x3/8, HSS8x8x1/2 | `families/structural/` | |
| 5 | [ ] | `NGM_Beam_Rectangular` | 8x16 in, 10x20 in, 12x24 in | `families/structural/` | |
| 6 | [ ] | `NGM_Beam_Steel_W` | W10x22, W12x26, W16x36 | `families/structural/` | |
| 7 | [ ] | `NGM_Beam_Steel_Joist` | 18K3, 22K6, 28K7 | `families/structural/` | |
| 8 | [ ] | `NGM_Truss_Standard` | Span 20ft, Span 30ft, Span 40ft | `families/structural/` | |
| 9 | [ ] | `NGM_Foundation_Strip` | 12x24 in, 16x30 in | `families/structural/` | |
| 10 | [ ] | `NGM_Foundation_Pad` | 4x4 ft, 6x6 ft, 8x8 ft | `families/structural/` | |
| 11 | [ ] | `NGM_Foundation_Pile` | 12 in dia, 18 in dia | `families/structural/` | |
| 12 | [ ] | `NGM_Brace_Steel` | L4x4x3/8, HSS4x4x1/4 | `families/structural/` | |

---

## Familias Arquitectonicas (.rfa)

| # | Listo | Familia | Tipos requeridos | Vault path | Comentarios |
|---|---|---|---|---|---|
| 1 | [ ] | `NGM_Door_Single` | 2'-8" x 7'-0", 3'-0" x 7'-0" | `families/architectural/` | Prioridad 1 |
| 2 | [ ] | `NGM_Door_Double` | 6'-0" x 7'-0" | `families/architectural/` | |
| 3 | [ ] | `NGM_Door_Sliding` | 6'-0" x 7'-0", 8'-0" x 7'-0" | `families/architectural/` | |
| 4 | [ ] | `NGM_Door_Rollup` | 10'-0" x 10'-0", 12'-0" x 12'-0" | `families/architectural/` | Industrial |
| 5 | [ ] | `NGM_Door_Overhead` | 10'-0" x 10'-0", 14'-0" x 14'-0" | `families/architectural/` | Industrial |
| 6 | [ ] | `NGM_Door_Glass` | 3'-0" x 7'-0", 6'-0" x 7'-0" | `families/architectural/` | Comercial |
| 7 | [ ] | `NGM_Door_Revolving` | 7'-0" dia | `families/architectural/` | Comercial |
| 8 | [ ] | `NGM_Window_Fixed` | 3'-0" x 4'-0", 4'-0" x 4'-0" | `families/architectural/` | Prioridad 1 |
| 9 | [ ] | `NGM_Window_Sliding` | 4'-0" x 4'-0", 5'-0" x 4'-0", 6'-0" x 4'-0" | `families/architectural/` | Prioridad 1 |
| 10 | [ ] | `NGM_Window_Casement` | 2'-6" x 4'-0", 3'-0" x 4'-0" | `families/architectural/` | |
| 11 | [ ] | `NGM_Window_Fixed_Commercial` | 5'-0" x 6'-0", 8'-0" x 6'-0" | `families/architectural/` | Comercial |
| 12 | [ ] | `NGM_Window_Industrial` | 4'-0" x 3'-0" | `families/architectural/` | Industrial |
| 13 | [ ] | `NGM_CurtainWall_Panel` | Standard | `families/architectural/` | Comercial |
| 14 | [ ] | `NGM_Stair_Standard` | 3'-6" wide, 4'-0" wide | `families/architectural/` | |
| 15 | [ ] | `NGM_Stair_Commercial` | 4'-0" wide, 5'-0" wide | `families/architectural/` | Comercial |
| 16 | [ ] | `NGM_Elevator_Standard` | Passenger, Freight | `families/architectural/` | Comercial |
| 17 | [ ] | `NGM_Louver_Standard` | 2'-0" x 2'-0", 3'-0" x 2'-0" | `families/architectural/` | Industrial |
| 18 | [ ] | `NGM_Dock_Leveler` | 6'-0" x 8'-0" | `families/architectural/` | Industrial |

---

## Familias MEP (.rfa)

| # | Listo | Familia | Tipos requeridos | Vault path | Comentarios |
|---|---|---|---|---|---|
| 1 | [ ] | `NGM_Outlet_Standard` | Duplex 120V | `families/mep/` | |
| 2 | [ ] | `NGM_Outlet_Floor` | Floor Box | `families/mep/` | Comercial |
| 3 | [ ] | `NGM_Outlet_Industrial` | 240V 30A | `families/mep/` | Industrial |
| 4 | [ ] | `NGM_Switch_Single` | Single Pole | `families/mep/` | |
| 5 | [ ] | `NGM_Light_Ceiling` | Flush Mount | `families/mep/` | |
| 6 | [ ] | `NGM_Light_Ceiling_Commercial` | 2x4 Troffer | `families/mep/` | Comercial |
| 7 | [ ] | `NGM_Light_Recessed` | 6 in Can | `families/mep/` | |
| 8 | [ ] | `NGM_Light_Highbay` | LED 200W | `families/mep/` | Industrial |
| 9 | [ ] | `NGM_HVAC_Diffuser` | Square 24x24 | `families/mep/` | Comercial |
| 10 | [ ] | `NGM_HVAC_Unit_Rooftop` | 5 Ton, 10 Ton | `families/mep/` | |
| 11 | [ ] | `NGM_HVAC_Exhaust_Fan` | 12 in, 24 in | `families/mep/` | Industrial |
| 12 | [ ] | `NGM_Fire_Sprinkler` | Pendant, Upright | `families/mep/` | Comercial/Industrial |
| 13 | [ ] | `NGM_Plumbing_Sink` | Single Bowl | `families/mep/` | Prioridad 1 |
| 14 | [ ] | `NGM_Plumbing_Sink_Commercial` | Stainless Double | `families/mep/` | Comercial |
| 15 | [ ] | `NGM_Plumbing_Toilet` | Floor Mount | `families/mep/` | Prioridad 1 |
| 16 | [ ] | `NGM_Plumbing_Toilet_Commercial` | Wall Mount | `families/mep/` | Comercial |
| 17 | [ ] | `NGM_Plumbing_Shower` | 36x36 in | `families/mep/` | |

---

## Familias de Anotacion (.rfa)

| # | Listo | Familia | Tipos | Vault path | Comentarios |
|---|---|---|---|---|---|
| 1 | [ ] | `NGM_Titleblock_ARCH-D` | Standard | `families/annotations/` | 36"x24" — necesario para sheets |
| 2 | [ ] | `NGM_Titleblock_ARCH-E` | Standard | `families/annotations/` | 48"x36" |
| 3 | [ ] | `NGM_Tag_Room` | Standard | `families/annotations/` | Muestra nombre + numero + area |
| 4 | [ ] | `NGM_Tag_Door` | Standard | `families/annotations/` | Muestra marca de puerta |
| 5 | [ ] | `NGM_Tag_Window` | Standard | `families/annotations/` | Muestra marca de ventana |
| 6 | [ ] | `NGM_Tag_Level` | Standard | `families/annotations/` | Head symbol para niveles |
| 7 | [ ] | `NGM_Tag_Parking` | Standard | `families/annotations/` | Comercial |
| 8 | [ ] | `NGM_Tag_Steel_Member` | Standard | `families/annotations/` | Industrial |

---

## Shared Parameters

Definidos en `definitions/shared_parameters.json`. Se vinculan a categorias via codigo (Step 14 del Build Engine).

| # | Listo | Parametro | Tipo | Categorias | Instance/Type |
|---|---|---|---|---|---|
| 1 | [ ] | `NGM_Cost_Per_Unit` | number | Walls, Floors, Roofs, Columns, Framing, Foundations, Doors, Windows | Instance |
| 2 | [ ] | `NGM_Material_Code` | text | Walls, Floors, Roofs, Columns, Framing | Type |
| 3 | [ ] | `NGM_Concept_ID` | text | Walls, Floors, Roofs, Columns, Framing, Foundations, Doors, Windows | Type |
| 4 | [ ] | `NGM_Supplier` | text | Doors, Windows, Plumbing, Lighting | Type |
| 5 | [ ] | `NGM_Unit` | text | Walls, Floors, Roofs, Columns, Framing | Type |

**Para agregar un shared parameter**: editar `definitions/shared_parameters.json`.

---

## Materiales en base.rvt

Estos materiales DEBEN existir en el archivo `base/base.rvt` para que las definiciones de muro/piso funcionen.

| # | Listo | Material Revit | Codigo NGM | Categoria |
|---|---|---|---|---|
| 1 | [ ] | `Concrete - Cast In Place` | CONC-001 | Structural |
| 2 | [ ] | `Concrete - Precast` | CONC-002 | Structural |
| 3 | [ ] | `Concrete Masonry Units` | CMU-001 | Masonry |
| 4 | [ ] | `Concrete Masonry Units - 8in` | CMU-002 | Masonry |
| 5 | [ ] | `Steel - ASTM A36` | STL-001 | Steel |
| 6 | [ ] | `Rebar - Grade 60` | STL-002 | Steel |
| 7 | [ ] | `Gypsum Wall Board` | GWB-001 | Finishes |
| 8 | [ ] | `Plaster - Cement` | FIN-001 | Finishes |
| 9 | [ ] | `Ceramic Tile` | FIN-002 | Finishes |
| 10 | [ ] | `Paint - Interior` | PNT-001 | Finishes |
| 11 | [ ] | `Paint - Exterior` | PNT-002 | Finishes |
| 12 | [ ] | `Metal - Aluminum` | ALM-001 | Openings |
| 13 | [ ] | `Glass - Clear` | GLS-001 | Openings |
| 14 | [ ] | `Waterproofing Membrane` | WPF-001 | Waterproofing |
| 15 | [ ] | `Insulation - Rigid` | INS-001 | Insulation |
| 16 | [ ] | `Metal Deck` | DCK-001 | Structural |
| 17 | [ ] | `Wood - Structural` | WD-001 | Wood |
| 18 | [ ] | `Metal Panel - Insulated` | PNL-001 | Cladding |

**Para agregar un material**: editar `materials/material_map.json`, asegurar que exista en `base/base.rvt`.

---

## Templates de Proyecto

| # | Listo | Template | Archivo | Comentarios |
|---|---|---|---|---|
| 1 | [ ] | Residential | `templates/residential.json` | JSON listo, falta validar vs familias |
| 2 | [ ] | Commercial | `templates/commercial.json` | JSON listo, falta validar vs familias |
| 3 | [ ] | Industrial | `templates/industrial.json` | JSON listo, falta validar vs familias |

---

## Scripts pyRevit

| # | Listo | Script | Panel | Status |
|---|---|---|---|---|
| 1 | [x] | Export Quantities | Export | Funcional |
| 2 | [x] | Export Materials | Export | Funcional |
| 3 | [x] | Export Spaces | Export | Funcional |
| 4 | [x] | Build From Batch | Build | Steps 1-12 funcional, 13-19 stub |
| 5 | [ ] | Load Definitions | Build | Planned |
| 6 | [ ] | Generate Sheets | Drawings | Planned |
| 7 | [ ] | Export PDF | Drawings | Planned |
| 8 | [ ] | Purge Model | Tools | Planned |
| 9 | [ ] | Rename Views | Tools | Planned |
| 10 | [ ] | Model QA | Tools | Planned |
| 11 | [ ] | Sync Materials | Sync | Planned |
| 12 | [ ] | Push to Estimator | Sync | Planned |

---

## Resumen Rapido

| Categoria | Total | Listos | Pendientes |
|---|---|---|---|
| Wall Types | 9 | 0 | 9 |
| Floor Types | 8 | 0 | 8 |
| Familias Structural | 12 | 0 | 12 |
| Familias Architectural | 18 | 0 | 18 |
| Familias MEP | 17 | 0 | 17 |
| Familias Annotation | 8 | 0 | 8 |
| Shared Parameters | 5 | 0 | 5 |
| Materiales en base.rvt | 18 | 0 | 18 |
| Templates | 3 | 0 | 3 |
| Scripts pyRevit | 12 | 4 | 8 |
| **TOTAL** | **110** | **4** | **106** |

---

## Como actualizar esta lista

1. Cuando crees un .rfa, marca `[x]` en la fila correspondiente
2. Cuando agregues un tipo nuevo a una familia, anadelo a "Tipos requeridos"
3. Cuando agregues una familia nueva, anade una fila y actualiza `registry.json`
4. Cuando cambies una definicion, actualiza el JSON fuente y esta lista
5. Actualiza la tabla de resumen al final cuando hagas cambios
