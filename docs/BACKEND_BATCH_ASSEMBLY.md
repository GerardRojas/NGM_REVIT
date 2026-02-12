# NGM Backend — Batch Assembly Instructions

> **Purpose**: This document tells the NGM_API backend agent how to assemble a `.batch.json` file
> from OCR/Vision output + user selections. The batch is downloaded by the user and executed in
> pyRevit Build Engine to construct a complete Revit model.
>
> **Source of truth**: The NGM_REVIT repo (https://github.com/GerardRojas/NGM_REVIT)
> contains all schemas, definitions, families, and templates referenced here.

---

## 1. High-Level Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│  USER ON WEBSITE                                            │
│  1. Uploads screenshot(s) of floor plan                     │
│  2. Selects project type: residential / commercial / indust │
│  3. Selects specifics: "ADU, 2 story, slab foundation"      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  OCR / VISION ENGINE                                        │
│  - Scans screenshot at known scale (px/ft)                  │
│  - Detects lines → segments with start/end px coords        │
│  - Detects text labels → tags with position + content       │
│  - Outputs: raw point cloud + tag list per level            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  BACKEND NORMALIZER (this is what you build)                │
│  Step A: Scale px → decimal feet                            │
│  Step B: Snap lines to grid / orthogonal / clean angles     │
│  Step C: Classify tags → map to NGM definitions             │
│  Step D: Detect closed polygons → floor boundaries          │
│  Step E: Detect room labels → room placements               │
│  Step F: Detect fixture tags → family + type + point        │
│  Step G: Detect grid lines and column positions             │
│  Step H: Assemble batch JSON per schema                     │
│  Step I: Validate referential integrity                     │
│  Step J: Return batch for download                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  USER IN REVIT + pyRevit                                    │
│  - Opens base.rvt (blank document)                          │
│  - Runs "Build From Batch" button                           │
│  - Selects downloaded .batch.json via file dialog            │
│  - Build Engine executes 19 steps → complete model          │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Batch JSON Structure

Schema: `manifests/_batch_schema.json` in NGM_REVIT repo.

Top-level required sections:

```json
{
  "batch_meta":   { ... },   // envelope metadata
  "project":      { ... },   // project identity
  "definitions":  { ... },   // wall types, floor types, view templates, etc.
  "families":     [ ... ],   // family download list
  "manifest":     { ... },   // geometry: levels, grids, walls, floors, etc.
  "materials":    [ ... ]    // optional: filtered material map
}
```

### 2.1 `batch_meta`

```json
{
  "batch_version": "1.0.0",
  "batch_id": "<uuid-v4>",
  "created_at": "<ISO 8601>",
  "created_by": "api_assembler",
  "ngm_project_id": "<project uuid from NGM HUB>",
  "ngm_user_id": "<user uuid>",
  "source_template": "residential | commercial | industrial"
}
```

### 2.2 `project`

```json
{
  "project_name": "ADU Maple Street",
  "project_type": "residential",
  "project_number": "NGM-2026-0087",
  "client_name": "Johnson Residence",
  "address": "1234 Maple Street, Austin, TX 78701",
  "description": "2-story ADU with slab foundation, 3 bed / 1.5 bath",
  "units": "imperial"
}
```

`units` is always `"imperial"`. All numeric values in the batch are in **decimal feet**.

### 2.3 `definitions` — what gets CREATED in Revit

This is the heart of the batch. The Build Engine uses these to create wall types, floor types, etc.
**Only include definitions this specific project needs** — don't dump the whole library.

#### 2.3.1 `definitions.wall_types[]`

Each object becomes a `WallType` in Revit via `CompoundStructure`.

```json
{
  "name": "Ext - CMU 6\" + Plaster",
  "function": "exterior | interior | structural",
  "structural": false,
  "total_width_ft": 0.6667,
  "layers": [
    {"function": "finish", "material": "Plaster - Cement", "width_ft": 0.0833},
    {"function": "substrate", "material": "Concrete Masonry Units", "width_ft": 0.5},
    {"function": "finish", "material": "Plaster - Cement", "width_ft": 0.0833}
  ]
}
```

**Layer function values**: `finish`, `substrate`, `structure`, `thermal`, `membrane`

**CRITICAL**: `name` must match EXACTLY what `manifest.walls[].type` references.

#### 2.3.2 `definitions.floor_types[]`

```json
{
  "name": "SOG - Concrete 6\"",
  "structural": true,
  "total_thickness_ft": 0.5,
  "layers": [
    {"function": "structure", "material": "Concrete - Cast In Place", "width_ft": 0.5}
  ]
}
```

**CRITICAL**: `name` must match EXACTLY what `manifest.floors[].type` references.

#### 2.3.3 Other definitions (optional)

- `definitions.view_templates[]` — view config
- `definitions.sheet_layout` — titleblock, paper size, viewport positions
- `definitions.graphic_styles` — line weights, colors, fill patterns
- `definitions.naming_conventions` — naming patterns
- `definitions.shared_parameters[]` — NGM custom parameters

These are for Steps 13-18 of the Build Engine (currently stubbed but will be implemented).
Include them now so the batch is future-proof.

### 2.4 `families[]` — what gets LOADED into Revit

```json
{
  "name": "NGM_Door_Single",
  "category": "structural | architectural | mep | annotations",
  "types_to_activate": ["3'-0\" x 7'-0\"", "2'-8\" x 7'-0\""],
  "vault_url": "https://vault.ngm.com/families/architectural/NGM_Door_Single.rfa",
  "vault_path": "families/architectural/NGM_Door_Single.rfa",
  "status": "available | planned | deprecated"
}
```

**CRITICAL**: `name` must match EXACTLY what `manifest.fixtures[].family`, `manifest.columns[].family`, and `manifest.beams[].family` reference.

- `status: "planned"` → Build Engine skips gracefully (no error)
- `status: "available"` → Build Engine downloads and loads
- `types_to_activate` → only the types this project uses (not all types in the family)

### 2.5 `manifest` — the GEOMETRY

This is where OCR output maps directly. All coordinates in **decimal feet**.

#### 2.5.1 `manifest.levels[]`

```json
{"name": "Ground Floor", "elevation_ft": 0.0}
```

Every element references a level by name. Levels MUST be created first.

#### 2.5.2 `manifest.grids[]`

```json
{"name": "A", "start": [0, 0], "end": [0, 50.0]}
```

Grid lines are infinite in Revit, but need start/end for extent. Use `[x, y]` in feet.

#### 2.5.3 `manifest.walls[]`

```json
{
  "type": "Ext - CMU 6\" + Plaster",
  "level": "Ground Floor",
  "start": [0, 0],
  "end": [20.0, 0],
  "height_ft": 9.1875,
  "structural": false
}
```

- `type` → must exist in `definitions.wall_types[].name`
- `level` → must exist in `manifest.levels[].name`
- `start`, `end` → `[x, y]` in decimal feet
- `height_ft` → optional, defaults to level-to-level height
- Walls are indexed by array position (0, 1, 2...) — fixtures use `host_wall_index`

#### 2.5.4 `manifest.fixtures[]`

```json
{
  "family": "NGM_Door_Single",
  "type": "3'-0\" x 7'-0\"",
  "point": [5.0, 0],
  "level": "Ground Floor",
  "host_wall_index": 0,
  "rotation_deg": 0
}
```

- `family` → must exist in `families[].name`
- `type` → must exist in that family's `types_to_activate[]`
- `point` → `[x, y]` or `[x, y, z]` in feet (z = sill height for windows)
- `host_wall_index` → index into `manifest.walls[]` array for wall-hosted elements (doors, windows)
- Omit `host_wall_index` for freestanding fixtures (toilets, sinks, lights)

#### 2.5.5 `manifest.floors[]`

```json
{
  "type": "SOG - Concrete 6\"",
  "level": "Foundation",
  "boundary": [[0, 0], [20.0, 0], [20.0, 24.0], [0, 24.0]]
}
```

- `boundary` → closed polygon of `[x, y]` points (last point connects to first)
- `type` → must exist in `definitions.floor_types[].name`

#### 2.5.6 `manifest.columns[]`

```json
{
  "family": "NGM_Column_Rectangular",
  "type": "12x12 in",
  "point": [0, 0],
  "base_level": "Foundation",
  "top_level": "Roof"
}
```

- Columns span from `base_level` to `top_level`
- Place at grid intersections

#### 2.5.7 `manifest.beams[]`

```json
{
  "family": "NGM_Beam_Rectangular",
  "type": "8x16 in",
  "start": [0, 0, 9.1875],
  "end": [10.0, 0, 9.1875],
  "level": "Second Floor"
}
```

- `start`, `end` → `[x, y, z]` (3 coordinates, z = elevation in feet)
- Beams are line-based — placed along a vector between two points

#### 2.5.8 `manifest.rooms[]`

```json
{
  "name": "Living Room",
  "number": "101",
  "point": [5.0, 6.0],
  "level": "Ground Floor",
  "floor_finish": "Ceramic Tile",
  "wall_finish": "Plaster + Paint",
  "ceiling_finish": "Plaster + Paint"
}
```

- `point` → must be INSIDE a closed wall boundary on the given level
- Revit auto-detects the room boundary from surrounding walls

#### 2.5.9 `manifest.views` and `manifest.sheets`

Can be `"use_template_defaults"` (Build Engine reads from template) or explicit arrays.
For OCR-generated batches, use `"use_template_defaults"`.

### 2.6 `materials[]` — filtered material map

```json
{
  "revit_name": "Concrete - Cast In Place",
  "ngm_code": "CONC-001",
  "ngm_name": "Cast-in-Place Concrete 4000 psi",
  "unit": "cu yd",
  "category": "Structural"
}
```

Only include materials referenced by this project's definitions layers.

---

## 3. OCR Output → Batch Mapping

This is the core transformation the backend must perform.

### 3.1 Coordinate Transformation

```
OCR gives:  pixel coordinates (px)
Batch needs: decimal feet (ft)

scale_factor = known_dimension_ft / known_dimension_px

x_ft = (x_px - origin_x_px) * scale_factor
y_ft = (y_px - origin_y_px) * scale_factor
```

- Origin (0,0) is typically bottom-left of the plan
- OCR image origin is usually top-left → **flip Y axis**: `y_ft = (image_height_px - y_px) * scale`
- Round to 4 decimal places (Revit tolerance)

### 3.2 Line Segments → Walls

OCR detects line segments. Each segment that represents a wall becomes a `manifest.walls[]` entry.

```
OCR line:   start_px, end_px, tag "ext wall" or thickness tag "6in"
            ↓
Normalize:  snap to orthogonal if angle < 5° off axis
            snap endpoints to grid if within tolerance
            ↓
Classify:   tag → wall type name from definition catalog
            ↓
Output:     {"type": "Ext - CMU 6\" + Plaster", "level": "Ground Floor",
             "start": [x1_ft, y1_ft], "end": [x2_ft, y2_ft]}
```

**Wall type classification** (see Section 5 for full catalog):

| OCR tag / context | → Definition name |
|---|---|
| Perimeter line, thick, "ext", "exterior" | `Ext - CMU 6" + Plaster` or `Ext - CMU 8" + Plaster` |
| Interior line, medium, "int", "interior" | `Int - CMU 4" + Plaster` or `Int - Drywall 5"` |
| Thick line, "structural", "concrete" | `Struct - Concrete 8"` / `10"` / `12"` |
| "metal panel", "insulated" | `Ext - Metal Panel + Insulation 6"` |
| Partition, thin, "drywall", "gypsum" | `Int - Drywall 5"` |

### 3.3 Text Labels → Room Names

OCR text labels inside closed wall boundaries → `manifest.rooms[]`

```
OCR text:   "LIVING ROOM" at position (px)
            ↓
Normalize:  convert position to ft, verify it's inside a wall polygon
            ↓
Output:     {"name": "Living Room", "number": "101", "point": [x_ft, y_ft],
             "level": "Ground Floor"}
```

Room numbering convention:
- Ground Floor: 100s (101, 102, ...)
- Second Floor: 200s (201, 202, ...)
- Third Floor: 300s (301, 302, ...)

### 3.4 Symbol Tags → Fixtures

OCR detects standard architectural symbols or text tags for doors, windows, fixtures.

```
OCR symbol: door arc at position (px) on wall segment
            ↓
Classify:   arc span → door size → family + type
            nearest wall → host_wall_index
            ↓
Output:     {"family": "NGM_Door_Single", "type": "3'-0\" x 7'-0\"",
             "point": [x_ft, y_ft], "level": "Ground Floor",
             "host_wall_index": 3}
```

**host_wall_index**: The index (0-based) of the wall in `manifest.walls[]` that the fixture is hosted on. To determine this:
1. Find the wall segment closest to the fixture point
2. Verify the fixture point lies ON or very near (< 0.5 ft) the wall line
3. Use that wall's index in the `manifest.walls[]` array

**Fixture classification** (see Section 6 for full family catalog):

| OCR symbol / tag | → Family | → Type |
|---|---|---|
| Door arc ~3ft span | `NGM_Door_Single` | `3'-0" x 7'-0"` |
| Door arc ~2.67ft span | `NGM_Door_Single` | `2'-8" x 7'-0"` |
| Double door arc | `NGM_Door_Double` | `6'-0" x 7'-0"` |
| Sliding door symbol | `NGM_Door_Sliding` | `6'-0" x 7'-0"` |
| Window lines on wall | `NGM_Window_Sliding` | `4'-0" x 4'-0"` |
| Fixed window (no slide mark) | `NGM_Window_Fixed` | `3'-0" x 4'-0"` |
| "WC", toilet symbol | `NGM_Plumbing_Toilet` | `Floor Mount` |
| Sink symbol | `NGM_Plumbing_Sink` | `Single Bowl` |
| Shower square | `NGM_Plumbing_Shower` | `36x36 in` |

### 3.5 Grid Lines → Grids + Columns

OCR detects grid lines (labeled with letters/numbers) and their intersections.

```
OCR lines:  horizontal lines labeled "A", "B", "C"
            vertical lines labeled "1", "2", "3"
            ↓
Output grids:  {"name": "A", "start": [x1, y1], "end": [x2, y2]}
            ↓
Output columns: one column at each grid intersection
            {"family": "NGM_Column_Rectangular", "type": "12x12 in",
             "point": [x, y], "base_level": "Foundation", "top_level": "Roof"}
```

Convention: horizontal grids = letters, vertical grids = numbers.

### 3.6 Closed Polygons → Floor Boundaries

The outer wall perimeter per level forms the floor boundary.

```
Trace:      follow exterior walls to form closed polygon
            ↓
Output:     {"type": "SOG - Concrete 6\"", "level": "Foundation",
             "boundary": [[0,0], [20,0], [20,24], [0,24]]}
```

### 3.7 Multi-Level Handling

If the user provides multiple floor plan screenshots (one per level):
- Process each level independently
- All share the same origin point (0,0)
- Assign correct `level` name to all elements
- Walls on upper levels get separate indices (wall index is global across ALL levels)
- Columns typically span from Foundation to Roof (full height)
- Beams sit at the elevation of the UPPER level they support

If the user provides only one floor plan for a multi-story building:
- Duplicate the wall layout for each level
- Adjust `host_wall_index` for fixtures on upper levels (indices offset by walls_per_level)
- Level elevations come from user input (number of floors + typical height)

---

## 4. Level Conventions

### By project type (from templates)

**Residential** (typical_height = 9.1875 ft / 2.80m):
```json
[
  {"name": "Foundation", "elevation_ft": -0.5},
  {"name": "Ground Floor", "elevation_ft": 0.0},
  {"name": "Second Floor", "elevation_ft": 9.1875},
  {"name": "Third Floor", "elevation_ft": 18.375},
  {"name": "Roof", "elevation_ft": 27.5625}
]
```

**Commercial** (typical_height = 11.4829 ft / 3.50m):
```json
[
  {"name": "Foundation", "elevation_ft": -1.0},
  {"name": "Basement", "elevation_ft": -11.4829},
  {"name": "Ground Floor", "elevation_ft": 0.0},
  {"name": "Level 2", "elevation_ft": 11.4829},
  {"name": "Level 3", "elevation_ft": 22.9659},
  {"name": "Roof", "elevation_ft": 34.4488}
]
```

**Industrial** (typical_height = 19.685 ft / 6.00m):
```json
[
  {"name": "Foundation", "elevation_ft": -0.5},
  {"name": "Ground Floor", "elevation_ft": 0.0},
  {"name": "Mezzanine", "elevation_ft": 9.8425},
  {"name": "Roof", "elevation_ft": 19.685}
]
```

Adjust number of levels based on user input. Foundation is always first, Roof always last.

---

## 5. Definition Catalog — Wall Types

These are the available wall types in the NGM_REVIT library. Include ONLY the ones the project needs.

### Exterior walls
| Name | Width (ft) | Primary material |
|---|---|---|
| `Ext - CMU 6" + Plaster` | 0.6667 | Concrete Masonry Units 6" + plaster both sides |
| `Ext - CMU 8" + Plaster` | 0.8333 | Concrete Masonry Units 8" + plaster both sides |
| `Ext - Metal Panel + Insulation 6"` | 0.5 | Insulated metal panel (industrial) |

### Interior walls
| Name | Width (ft) | Primary material |
|---|---|---|
| `Int - CMU 4" + Plaster` | 0.5 | CMU 4" + plaster both sides |
| `Int - CMU 6" + Plaster` | 0.6667 | CMU 6" + plaster both sides |
| `Int - Drywall 5"` | 0.4167 | Gypsum board + metal stud 3-5/8" |

### Structural walls
| Name | Width (ft) | Material |
|---|---|---|
| `Struct - Concrete 8"` | 0.6667 | Cast-in-place concrete |
| `Struct - Concrete 10"` | 0.8333 | Cast-in-place concrete |
| `Struct - Concrete 12"` | 1.0 | Cast-in-place concrete |

### Full layer data

Copy the layer arrays directly from `definitions/wall_types.json` in the NGM_REVIT repo.
The batch must include the complete layer definition — not just the name.

Example for `Ext - CMU 6" + Plaster`:
```json
{
  "name": "Ext - CMU 6\" + Plaster",
  "function": "exterior",
  "structural": false,
  "total_width_ft": 0.6667,
  "layers": [
    {"function": "finish", "material": "Plaster - Cement", "width_ft": 0.0833},
    {"function": "substrate", "material": "Concrete Masonry Units", "width_ft": 0.5},
    {"function": "finish", "material": "Plaster - Cement", "width_ft": 0.0833}
  ]
}
```

---

## 6. Definition Catalog — Floor Types

| Name | Thickness (ft) | Use case |
|---|---|---|
| `Slab - Concrete 5"` | 0.4167 | Standard elevated slab |
| `Slab - Concrete 6"` | 0.5 | Thicker elevated slab |
| `Slab - Concrete 8"` | 0.6667 | Heavy load slab |
| `Foundation Slab 8"` | 0.6667 | Foundation slab |
| `Foundation Mat 16"` | 1.3333 | Mat foundation (commercial) |
| `SOG - Concrete 6"` | 0.5 | Slab-on-grade (residential) |
| `Slab + Ceramic Tile` | 0.4583 | Slab with ceramic finish |
| `Metal Deck Composite` | 0.4375 | Steel structure composite deck |

### Floor type selection by project type

| Project type | Foundation level | Typical floor | Roof slab |
|---|---|---|---|
| Residential (slab) | `SOG - Concrete 6"` | `Slab + Ceramic Tile` | `Slab - Concrete 5"` |
| Residential (foundation) | `Foundation Slab 8"` | `Slab + Ceramic Tile` | `Slab - Concrete 5"` |
| Commercial | `Foundation Mat 16"` | `Slab - Concrete 8"` | `Slab - Concrete 6"` |
| Industrial | `SOG - Concrete 6"` | `Metal Deck Composite` | `Metal Deck Composite` |

---

## 7. Family Catalog

Families are .rfa files that get loaded into Revit. The batch references them by `name`.

### Structural families
| Name | Types | Used for |
|---|---|---|
| `NGM_Column_Rectangular` | `12x12 in`, `16x16 in`, `20x20 in` | Concrete columns |
| `NGM_Column_Circular` | `12 in dia`, `18 in dia` | Round concrete columns |
| `NGM_Column_Steel_W` | `W8x31`, `W10x49`, `W12x65` | Steel W columns |
| `NGM_Column_Steel_HSS` | `HSS6x6x3/8`, `HSS8x8x1/2` | Steel HSS columns |
| `NGM_Beam_Rectangular` | `8x16 in`, `10x20 in`, `12x24 in` | Concrete beams |
| `NGM_Beam_Steel_W` | `W10x22`, `W12x26`, `W16x36` | Steel W beams |
| `NGM_Beam_Steel_Joist` | `18K3`, `22K6`, `28K7` | Open-web steel joists |
| `NGM_Truss_Standard` | `Span 20ft`, `Span 30ft`, `Span 40ft` | Steel trusses |
| `NGM_Foundation_Strip` | `12x24 in`, `16x30 in` | Strip footings |
| `NGM_Foundation_Pad` | `4x4 ft`, `6x6 ft`, `8x8 ft` | Pad footings |
| `NGM_Foundation_Pile` | `12 in dia`, `18 in dia` | Piles |
| `NGM_Brace_Steel` | `L4x4x3/8`, `HSS4x4x1/4` | Steel bracing |

### Architectural families
| Name | Types | Used for |
|---|---|---|
| `NGM_Door_Single` | `2'-8" x 7'-0"`, `3'-0" x 7'-0"` | Standard doors |
| `NGM_Door_Double` | `6'-0" x 7'-0"` | Double doors |
| `NGM_Door_Sliding` | `6'-0" x 7'-0"`, `8'-0" x 7'-0"` | Sliding doors |
| `NGM_Door_Rollup` | `10'-0" x 10'-0"`, `12'-0" x 12'-0"` | Rollup doors (industrial) |
| `NGM_Door_Overhead` | `10'-0" x 10'-0"`, `14'-0" x 14'-0"` | Overhead doors |
| `NGM_Door_Glass` | `3'-0" x 7'-0"`, `6'-0" x 7'-0"` | Glass doors |
| `NGM_Door_Revolving` | `7'-0" dia` | Revolving doors |
| `NGM_Window_Fixed` | `3'-0" x 4'-0"`, `4'-0" x 4'-0"` | Fixed windows |
| `NGM_Window_Sliding` | `4'-0" x 4'-0"`, `5'-0" x 4'-0"`, `6'-0" x 4'-0"` | Sliding windows |
| `NGM_Window_Casement` | `2'-6" x 4'-0"`, `3'-0" x 4'-0"` | Casement windows |
| `NGM_Window_Fixed_Commercial` | `5'-0" x 6'-0"`, `8'-0" x 6'-0"` | Large commercial windows |
| `NGM_Window_Industrial` | `4'-0" x 3'-0"` | Industrial windows |
| `NGM_CurtainWall_Panel` | `Standard` | Curtain wall panels |
| `NGM_Stair_Standard` | `3'-6" wide`, `4'-0" wide` | Residential stairs |
| `NGM_Stair_Commercial` | `4'-0" wide`, `5'-0" wide` | Commercial stairs |
| `NGM_Elevator_Standard` | `Passenger`, `Freight` | Elevators |
| `NGM_Louver_Standard` | `2'-0" x 2'-0"`, `3'-0" x 2'-0"` | HVAC louvers |
| `NGM_Dock_Leveler` | `6'-0" x 8'-0"` | Loading dock levelers |

### MEP families
| Name | Types | Used for |
|---|---|---|
| `NGM_Outlet_Standard` | `Duplex 120V` | Standard outlets |
| `NGM_Outlet_Floor` | `Floor Box` | Floor outlets |
| `NGM_Outlet_Industrial` | `240V 30A` | Industrial power |
| `NGM_Switch_Single` | `Single Pole` | Light switches |
| `NGM_Light_Ceiling` | `Flush Mount` | Residential ceiling lights |
| `NGM_Light_Ceiling_Commercial` | `2x4 Troffer` | Commercial ceiling lights |
| `NGM_Light_Recessed` | `6 in Can` | Recessed lights |
| `NGM_Light_Highbay` | `LED 200W` | Industrial high-bay lights |
| `NGM_HVAC_Diffuser` | `Square 24x24` | Supply air diffusers |
| `NGM_HVAC_Unit_Rooftop` | `5 Ton`, `10 Ton` | Rooftop AC units |
| `NGM_HVAC_Exhaust_Fan` | `12 in`, `24 in` | Exhaust fans |
| `NGM_Fire_Sprinkler` | `Pendant`, `Upright` | Fire sprinkler heads |
| `NGM_Plumbing_Sink` | `Single Bowl` | Residential sinks |
| `NGM_Plumbing_Sink_Commercial` | `Stainless Double` | Commercial sinks |
| `NGM_Plumbing_Toilet` | `Floor Mount` | Residential toilets |
| `NGM_Plumbing_Toilet_Commercial` | `Wall Mount` | Commercial toilets |
| `NGM_Plumbing_Shower` | `36x36 in` | Shower bases |

### Annotation families
| Name | Types |
|---|---|
| `NGM_Titleblock_ARCH-D` | `Standard` |
| `NGM_Titleblock_ARCH-E` | `Standard` |
| `NGM_Tag_Room` | `Standard` |
| `NGM_Tag_Door` | `Standard` |
| `NGM_Tag_Window` | `Standard` |
| `NGM_Tag_Level` | `Standard` |
| `NGM_Tag_Parking` | `Standard` |
| `NGM_Tag_Steel_Member` | `Standard` |

### Family selection by project type

Use the templates as a guide:

**Residential**: Concrete columns/beams, single/sliding doors, sliding/fixed/casement windows, standard stairs, basic MEP
**Commercial**: Add steel columns, glass/revolving doors, commercial windows, curtain walls, elevators, commercial MEP, fire sprinklers
**Industrial**: Steel columns/beams/joists/trusses/braces, rollup/overhead doors, industrial windows, louvers, dock levelers, high-bay lights, industrial outlets

---

## 8. Material Map

Materials referenced in `definitions.wall_types[].layers[].material` and `definitions.floor_types[].layers[].material` must exist in the `materials[]` section.

| `revit_name` (used in layers) | `ngm_code` | `unit` | `category` |
|---|---|---|---|
| `Concrete - Cast In Place` | `CONC-001` | cu yd | Structural |
| `Concrete - Precast` | `CONC-002` | cu yd | Structural |
| `Concrete Masonry Units` | `CMU-001` | pcs | Masonry |
| `Concrete Masonry Units - 8in` | `CMU-002` | pcs | Masonry |
| `Steel - ASTM A36` | `STL-001` | lbs | Steel |
| `Rebar - Grade 60` | `STL-002` | lbs | Steel |
| `Gypsum Wall Board` | `GWB-001` | sq ft | Finishes |
| `Plaster - Cement` | `FIN-001` | sq ft | Finishes |
| `Ceramic Tile` | `FIN-002` | sq ft | Finishes |
| `Paint - Interior` | `PNT-001` | sq ft | Finishes |
| `Paint - Exterior` | `PNT-002` | sq ft | Finishes |
| `Metal - Aluminum` | `ALM-001` | sq ft | Openings |
| `Glass - Clear` | `GLS-001` | sq ft | Openings |
| `Waterproofing Membrane` | `WPF-001` | sq ft | Waterproofing |
| `Insulation - Rigid` | `INS-001` | sq ft | Insulation |
| `Metal Deck` | `DCK-001` | sq ft | Structural |
| `Wood - Structural` | `WD-001` | bf | Wood |
| `Metal Panel - Insulated` | `PNL-001` | sq ft | Cladding |

Materials not in this list: use `revit_name` as-is and `ngm_code: "UNMAPPED"`.

---

## 9. Validation Rules

Before returning the batch, the backend MUST validate these rules. **Fail the batch if any rule is violated.**

### 9.1 Referential integrity

1. Every `manifest.walls[].type` must exist in `definitions.wall_types[].name`
2. Every `manifest.floors[].type` must exist in `definitions.floor_types[].name`
3. Every `manifest.walls[].level` must exist in `manifest.levels[].name`
4. Every `manifest.floors[].level` must exist in `manifest.levels[].name`
5. Every `manifest.fixtures[].level` must exist in `manifest.levels[].name`
6. Every `manifest.columns[].base_level` and `top_level` must exist in `manifest.levels[].name`
7. Every `manifest.beams[].level` must exist in `manifest.levels[].name`
8. Every `manifest.rooms[].level` must exist in `manifest.levels[].name`
9. Every `manifest.fixtures[].family` must exist in `families[].name`
10. Every `manifest.columns[].family` must exist in `families[].name`
11. Every `manifest.beams[].family` must exist in `families[].name`
12. Every `manifest.fixtures[].host_wall_index` (when present) must be a valid index into `manifest.walls[]`
13. Every material in `definitions.wall_types[].layers[].material` should exist in `materials[].revit_name`
14. Every material in `definitions.floor_types[].layers[].material` should exist in `materials[].revit_name`

### 9.2 Geometry validation

15. Wall `start` must not equal `end` (zero-length wall)
16. Floor `boundary` must have at least 3 points
17. Room `point` should be inside its level's floor boundary (approximate check is OK)
18. Column `base_level` elevation must be lower than `top_level` elevation
19. Beam `start` and `end` must have different positions

### 9.3 Consistency

20. `batch_meta.batch_id` must be valid UUID v4
21. `batch_meta.created_at` must be valid ISO 8601
22. `project.units` must be `"imperial"`
23. All coordinates must be numeric (no strings, no nulls)
24. All `elevation_ft`, `height_ft`, `width_ft`, `total_width_ft`, `total_thickness_ft` must be > 0

---

## 10. Assembly Algorithm (Pseudocode)

```python
def assemble_batch(ocr_output, user_selections, project_info):
    """
    ocr_output: {
        levels: [{name, screenshot, lines, labels, symbols}],
        scale_factor: float  # ft per pixel
    }
    user_selections: {
        project_type: "residential" | "commercial" | "industrial",
        num_floors: int,
        floor_height_ft: float,
        foundation_type: "slab" | "mat" | "strip",
        wall_system: "cmu" | "concrete" | "drywall" | "metal_panel",
        ...
    }
    """

    template = load_template(user_selections.project_type)

    # ── Step 1: Build levels ──
    levels = build_levels(
        num_floors=user_selections.num_floors,
        height=user_selections.floor_height_ft,
        template=template
    )

    # ── Step 2: Process OCR per level ──
    all_walls = []
    all_fixtures = []
    all_floors = []
    all_rooms = []
    all_grids = []
    all_columns = []
    all_beams = []

    wall_types_needed = set()
    floor_types_needed = set()
    families_needed = set()

    for level_data in ocr_output.levels:
        level_name = level_data.name
        scale = ocr_output.scale_factor

        # ── Walls ──
        for line in level_data.lines:
            if is_wall_line(line):
                wall_type = classify_wall(line, user_selections)
                wall_types_needed.add(wall_type)
                wall = {
                    "type": wall_type,
                    "level": level_name,
                    "start": scale_point(line.start, scale),
                    "end": scale_point(line.end, scale),
                    "height_ft": user_selections.floor_height_ft
                }
                all_walls.append(wall)

        # ── Fixtures ──
        for symbol in level_data.symbols:
            family, type_name = classify_fixture(symbol)
            families_needed.add(family)
            host_idx = find_nearest_wall(symbol.position, all_walls)
            fixture = {
                "family": family,
                "type": type_name,
                "point": scale_point(symbol.position, scale),
                "level": level_name
            }
            if host_idx is not None:
                fixture["host_wall_index"] = host_idx
            all_fixtures.append(fixture)

        # ── Rooms ──
        for label in level_data.labels:
            if is_room_label(label):
                all_rooms.append({
                    "name": label.text,
                    "number": assign_room_number(label, level_name),
                    "point": scale_point(label.position, scale),
                    "level": level_name,
                    "floor_finish": default_finish(label.text),
                    "wall_finish": default_finish(label.text),
                    "ceiling_finish": "Plaster + Paint"
                })

        # ── Floor boundary ──
        boundary = trace_exterior_boundary(all_walls, level_name)
        floor_type = select_floor_type(level_name, user_selections)
        floor_types_needed.add(floor_type)
        all_floors.append({
            "type": floor_type,
            "level": level_name,
            "boundary": boundary
        })

    # ── Grids (from first level, applies to all) ──
    all_grids = detect_grids(ocr_output.levels[0], scale)

    # ── Columns (at grid intersections, full height) ──
    col_family = select_column_family(user_selections)
    families_needed.add(col_family)
    for intersection in grid_intersections(all_grids):
        all_columns.append({
            "family": col_family,
            "type": select_column_type(user_selections),
            "point": intersection,
            "base_level": levels[0]["name"],    # Foundation
            "top_level": levels[-1]["name"]     # Roof
        })

    # ── Beams (between columns at each upper level) ──
    beam_family = select_beam_family(user_selections)
    families_needed.add(beam_family)
    for level in levels[1:]:  # skip foundation
        z = level["elevation_ft"]
        for col_a, col_b in adjacent_column_pairs(all_columns):
            all_beams.append({
                "family": beam_family,
                "type": select_beam_type(user_selections),
                "start": [col_a[0], col_a[1], z],
                "end": [col_b[0], col_b[1], z],
                "level": level["name"]
            })

    # ── Step 3: Filter definitions ──
    wall_type_defs = filter_definitions("wall_types", wall_types_needed)
    floor_type_defs = filter_definitions("floor_types", floor_types_needed)

    # ── Step 4: Build families list ──
    families_list = build_families_list(families_needed, template)

    # ── Step 5: Filter materials ──
    materials_needed = extract_materials(wall_type_defs, floor_type_defs)
    materials_list = filter_material_map(materials_needed)

    # ── Step 6: Assemble batch ──
    batch = {
        "batch_meta": build_meta(project_info),
        "project": build_project(project_info),
        "definitions": {
            "wall_types": wall_type_defs,
            "floor_types": floor_type_defs,
            "view_templates": template_view_templates(template),
            "sheet_layout": template_sheet_layout(template),
            "graphic_styles": load_graphic_styles(),
            "naming_conventions": load_naming_conventions(),
            "shared_parameters": filter_shared_params(template)
        },
        "families": families_list,
        "manifest": {
            "levels": levels,
            "grids": all_grids,
            "walls": all_walls,
            "fixtures": all_fixtures,
            "floors": all_floors,
            "columns": all_columns,
            "beams": all_beams,
            "rooms": all_rooms,
            "views": "use_template_defaults",
            "sheets": "use_template_defaults"
        },
        "materials": materials_list
    }

    # ── Step 7: Validate ──
    validate_batch(batch)  # raises if invalid

    return batch
```

---

## 11. Common Defaults by Room Type

When OCR detects a room label, apply these default finishes:

| Room label contains | `floor_finish` | `wall_finish` | `ceiling_finish` |
|---|---|---|---|
| bathroom, bath, WC, restroom | Ceramic Tile | Ceramic Tile | Plaster + Paint |
| kitchen, cocina | Ceramic Tile | Ceramic Tile | Plaster + Paint |
| laundry, lavanderia | Ceramic Tile | Plaster + Paint | Plaster + Paint |
| bedroom, recamara | Ceramic Tile | Plaster + Paint | Plaster + Paint |
| living, sala | Ceramic Tile | Plaster + Paint | Plaster + Paint |
| office, oficina | Ceramic Tile | Plaster + Paint | Plaster + Paint |
| garage | Concrete (no finish) | Plaster + Paint | None |
| warehouse, bodega | Concrete (no finish) | None | None |

---

## 12. Beam Placement at Elevation

Beams sit at the elevation of the level they support. For a 2-story building:

```
Roof level:         18.375 ft  ← beams here support roof slab
Second Floor level:  9.1875 ft ← beams here support 2nd floor slab
Ground Floor level:  0.0 ft    ← no beams at ground (sits on foundation)
Foundation level:   -0.5 ft    ← no beams at foundation
```

The z-coordinate in `beams[].start` and `beams[].end` equals the level's `elevation_ft`.

---

## 13. Quick Start Example

For a minimal residential ADU (1 story, slab on grade, 20ft x 24ft):

```json
{
  "batch_meta": {
    "batch_version": "1.0.0",
    "batch_id": "...",
    "created_at": "...",
    "created_by": "api_assembler",
    "source_template": "residential"
  },
  "project": {
    "project_name": "Simple ADU",
    "project_type": "residential",
    "units": "imperial"
  },
  "definitions": {
    "wall_types": [
      {
        "name": "Ext - CMU 6\" + Plaster",
        "function": "exterior",
        "structural": false,
        "total_width_ft": 0.6667,
        "layers": [
          {"function": "finish", "material": "Plaster - Cement", "width_ft": 0.0833},
          {"function": "substrate", "material": "Concrete Masonry Units", "width_ft": 0.5},
          {"function": "finish", "material": "Plaster - Cement", "width_ft": 0.0833}
        ]
      }
    ],
    "floor_types": [
      {
        "name": "SOG - Concrete 6\"",
        "structural": true,
        "total_thickness_ft": 0.5,
        "layers": [
          {"function": "structure", "material": "Concrete - Cast In Place", "width_ft": 0.5}
        ]
      }
    ]
  },
  "families": [],
  "manifest": {
    "levels": [
      {"name": "Foundation", "elevation_ft": -0.5},
      {"name": "Ground Floor", "elevation_ft": 0.0},
      {"name": "Roof", "elevation_ft": 9.1875}
    ],
    "grids": [],
    "walls": [
      {"type": "Ext - CMU 6\" + Plaster", "level": "Ground Floor", "start": [0,0], "end": [20,0], "height_ft": 9.1875},
      {"type": "Ext - CMU 6\" + Plaster", "level": "Ground Floor", "start": [20,0], "end": [20,24], "height_ft": 9.1875},
      {"type": "Ext - CMU 6\" + Plaster", "level": "Ground Floor", "start": [20,24], "end": [0,24], "height_ft": 9.1875},
      {"type": "Ext - CMU 6\" + Plaster", "level": "Ground Floor", "start": [0,24], "end": [0,0], "height_ft": 9.1875}
    ],
    "fixtures": [],
    "floors": [
      {"type": "SOG - Concrete 6\"", "level": "Foundation", "boundary": [[0,0],[20,0],[20,24],[0,24]]}
    ],
    "columns": [],
    "beams": [],
    "rooms": [
      {"name": "Main Room", "number": "101", "point": [10, 12], "level": "Ground Floor"}
    ],
    "views": "use_template_defaults",
    "sheets": "use_template_defaults"
  },
  "materials": [
    {"revit_name": "Concrete - Cast In Place", "ngm_code": "CONC-001", "ngm_name": "Cast-in-Place Concrete 4000 psi", "unit": "cu yd", "category": "Structural"},
    {"revit_name": "Concrete Masonry Units", "ngm_code": "CMU-001", "ngm_name": "CMU Block 6x8x16", "unit": "pcs", "category": "Masonry"},
    {"revit_name": "Plaster - Cement", "ngm_code": "FIN-001", "ngm_name": "Cement Plaster", "unit": "sq ft", "category": "Finishes"}
  ]
}
```

---

## 14. Files in NGM_REVIT Repo to Sync

When the NGM_REVIT repo updates, the backend should re-sync these files:

| File | What it contains | When to re-read |
|---|---|---|
| `manifests/_batch_schema.json` | JSON Schema for validation | On schema version change |
| `definitions/wall_types.json` | Full wall type library | On definition updates |
| `definitions/floor_types.json` | Full floor type library | On definition updates |
| `definitions/view_templates.json` | View template configs | On definition updates |
| `definitions/sheet_layouts.json` | Sheet layout config | On definition updates |
| `definitions/graphic_styles.json` | Style overrides | On definition updates |
| `definitions/naming_conventions.json` | Naming patterns | On definition updates |
| `definitions/shared_parameters.json` | NGM custom parameters | On definition updates |
| `materials/material_map.json` | Material bidirectional map | On material updates |
| `templates/residential.json` | Residential defaults | On template updates |
| `templates/commercial.json` | Commercial defaults | On template updates |
| `templates/industrial.json` | Industrial defaults | On template updates |
| `registry.json` | Family catalog with all types | On family vault updates |

The backend can either: (a) clone the repo and read files directly, or (b) use the GitHub raw content API to fetch individual files.
