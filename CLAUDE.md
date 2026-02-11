# NGM Revit Suite

## Vision
Suite integral de automatizacion BIM para NGM. El objetivo es crear un ecosistema completo que integre Revit con el sistema NGM HUB para automatizar al extremo los procesos de estimacion, modelado y organizacion de proyectos de construccion.

**Problema actual**: Un archivo template de Revit de 200MB que se copia para cada proyecto. Pesado, lento de compartir, lleno de familias y materiales que no siempre aplican.

**Solucion**: Reemplazar el template monolitico con un sistema inteligente que construya el archivo de proyecto on-demand segun el tipo de proyecto, cargando solo lo necesario. Integrar IA, OCR, Vision y scripts que conviertan semanas de trabajo manual en horas.

## Pilares del Ecosistema

### 1. Template Builder (Generador de Proyectos)
- Script que genera un .rvt limpio basado en el tipo de proyecto
- Input: tipo (residencial, comercial, industrial, etc.), niveles, uso
- Output: archivo Revit con solo las familias, materiales, vistas y sheets relevantes
- Reemplaza el template de 200MB con un generador de ~5MB + librerias modulares

### 2. Family Manager (Gestor de Familias)
- Libreria organizada de familias Revit (.rfa) por categoria y uso
- Catalogo versionado y sincronizado con la base de datos de materiales NGM
- Auto-carga de familias segun tipo de proyecto
- Mapping: familia Revit <-> material/concepto del estimador NGM

### 3. Material Database (Base de Datos de Materiales)
- Materiales Revit vinculados 1:1 con el catalogo de materiales del estimador NGM
- Precios, proveedores y rendimientos embebidos como shared parameters
- Sincronizacion bidireccional: Revit <-> NGM API

### 4. Export Suite (Extraccion de Datos)
- Exportar materiales, cantidades, espacios del modelo a JSON
- Alimentar el estimador de NGM con cantidades reales del BIM
- Eliminar cuantificacion manual

### 5. Drawing Package Automation (Paquete de Planos)
- Generacion automatica de sheets segun tipo de proyecto
- Titleblock estandarizado NGM
- Export a PDF organizado por disciplina
- Nomenclatura estandar de vistas y planos

### 6. AI Agents Integration (Agentes IA)
- Conexion con agentes existentes de NGM (Andrew, Daneel, Arturito)
- Andrew: Validacion de recibos/facturas contra cantidades del modelo
- Daneel: Auto-autorizacion de gastos cruzando con presupuesto BIM
- Nuevo agente BIM: Revision automatica de modelo (clash detection, QA/QC)
- OCR/Vision: Leer planos escaneados, extraer datos, comparar con modelo

### 7. Workflow Helpers (Herramientas de Productividad)
- Scripts para tareas repetitivas del dia a dia del modelador
- Renombrado masivo de vistas, limpieza de modelo, purge automatico
- Estandarizacion de parametros y nomenclatura NGM
- Reportes de avance de modelado

## Contexto del Ecosistema NGM
Este proyecto es parte del ecosistema NGM:
- **NGM HUB WEB** (`C:\Users\germa\Desktop\NGM HUB WEB`) - Frontend web (HTML/CSS/JS vanilla)
- **NGM_API** (`C:\Users\germa\Desktop\NGM_API`) - Backend FastAPI + Supabase
- **NGM_REVIT** (este repo) - Suite de automatizacion BIM

Flujo completo:
```
Template Builder genera .rvt limpio
        |
Modelador trabaja con familias/materiales estandarizados
        |
Export Suite extrae cantidades del modelo
        |
NGM API recibe JSON -> pre-popula estimador
        |
AI Agents validan gastos contra presupuesto BIM
        |
Drawing Package genera entregables automaticamente
```

## Stack y Entorno
- **pyRevit** - Framework que carga scripts Python dentro de Revit
- **IronPython 2.7** - El interprete que usa pyRevit (NO es CPython, NO tiene pip)
- **Revit API** - Accesible via `clr` y namespaces de Autodesk (.NET)
- **.NET interop** - Para HTTP requests usar `System.Net.WebClient`, NO `requests`
- **Revit 2024+** - Version minima target

## Estructura del Proyecto
```
NGM_REVIT/
  CLAUDE.md                          # Este archivo - vision y reglas
  exports/                           # JSONs generados por Export Suite

  # -- Librerias de contenido --
  families/                          # Familias Revit organizadas
    structural/                      # Columnas, vigas, cimentacion
    architectural/                   # Puertas, ventanas, mobiliario
    mep/                             # Instalaciones
    annotations/                     # Etiquetas, titleblocks
  materials/                         # Definiciones de materiales
    material_map.json                # Mapeo material Revit <-> NGM catalogo
  templates/                         # Configs por tipo de proyecto
    residential.json                 # Que familias/vistas/sheets cargar
    commercial.json
    industrial.json

  # -- Extension pyRevit --
  NGM.extension/
    NGM.tab/
      Proyecto.panel/                # Setup y config de proyecto
        TemplateBuilder.pushbutton/
          script.py                  # Genera proyecto desde config
        SyncMaterials.pushbutton/
          script.py                  # Sincroniza materiales con NGM
      Exportar.panel/                # Extraccion de datos
        ExportarMateriales.pushbutton/
          script.py
        ExportarCantidades.pushbutton/
          script.py
        ExportarEspacios.pushbutton/
          script.py
      Planos.panel/                  # Drawing package
        GenerarSheets.pushbutton/
          script.py
        ExportPDF.pushbutton/
          script.py
      Herramientas.panel/            # Helpers del dia a dia
        PurgeModel.pushbutton/
          script.py
        RenameViews.pushbutton/
          script.py
        ModelQA.pushbutton/
          script.py
```

## Como instalar
1. Instalar pyRevit: https://github.com/pyrevitlabs/pyRevit/releases
2. En Revit -> pyRevit tab -> Settings -> Custom Extension Directories
3. Agregar la ruta a `C:\Users\germa\Desktop\NGM_REVIT`
4. Reload pyRevit (o reiniciar Revit)
5. Aparece tab "NGM" en el ribbon con los paneles

## Reglas de Codigo

### Scripts pyRevit (IronPython 2.7)
- Cada script en su carpeta `.pushbutton/` con nombre `script.py`
- Imports de Revit API siempre al inicio:
  ```python
  import clr
  clr.AddReference('RevitAPI')
  clr.AddReference('RevitAPIUI')
  from Autodesk.Revit.DB import *
  from pyrevit import revit, DB, script
  ```
- `doc = revit.doc` para documento activo
- `output = script.get_output()` para consola pyRevit
- Transacciones: `with revit.Transaction('nombre'):` o `DB.Transaction(doc, 'nombre')`
- Archivos de salida van a `exports/` con nombre descriptivo + timestamp
- Formato de salida: JSON (compatible con NGM API)

### Restricciones IronPython 2.7
- NO f-strings -> usar `.format()` o `%`
- NO pathlib -> usar `os.path`
- NO `json.dumps(ensure_ascii=False)` con caracteres especiales
- NO `with open()` sin encoding -> siempre `codecs.open(path, 'w', 'utf-8')`
- NO tiene: dataclasses, type hints, async/await, pip
- SI tiene: os, sys, json, codecs, datetime, collections, math
- HTTP: `System.Net.WebClient` via clr (no requests)

### Formato JSON de Exportacion
```json
{
  "export_info": {
    "revit_file": "nombre_proyecto.rvt",
    "export_date": "2026-02-11T10:30:00",
    "export_type": "materials|quantities|spaces",
    "units": "metric"
  },
  "items": [...]
}
```

### Mapeo Revit -> NGM Estimador
- Revit `Category` -> NGM concepto group
- Revit `Family + Type` -> NGM concepto name
- Revit `Material` -> NGM material (via material_map.json)
- Revit area/volume/count -> NGM cantidad
- Unidades: m2, m3, ml, pza, kg

## Categorias Revit Relevantes
- `OST_Walls` - Muros
- `OST_Floors` - Pisos/Losas
- `OST_Roofs` - Techos
- `OST_StructuralColumns` - Columnas
- `OST_StructuralFraming` - Vigas/Trabes
- `OST_StructuralFoundation` - Cimentacion
- `OST_Doors` - Puertas
- `OST_Windows` - Ventanas
- `OST_Rooms` - Espacios
- `OST_Stairs` - Escaleras
- `OST_Rebar` - Acero de refuerzo

## NGM API Endpoints
- `GET /accounts` - Cuentas/partidas
- `GET /estimator/concepts/{project_id}` - Conceptos del estimador
- `POST /estimator/concepts` - Crear concepto
- Prod: `https://ngm-fastapi.onrender.com`
- Staging: `https://ngm-api-staging.onrender.com`

## Roadmap de Implementacion
1. **Fase 1 - Export Suite** (ACTUAL): Scripts de extraccion de datos
2. **Fase 2 - Template Builder**: Generador de proyectos por tipo
3. **Fase 3 - Family/Material Manager**: Librerias organizadas + sync
4. **Fase 4 - Drawing Package**: Automatizacion de planos
5. **Fase 5 - AI Integration**: Conexion con agentes NGM
6. **Fase 6 - Workflow Helpers**: Herramientas de productividad
