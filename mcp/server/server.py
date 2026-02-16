"""
NGM Revit MCP Server

MCP server that exposes Revit model operations as tools for Claude.
Communicates with the Revit Bridge add-in via HTTP on localhost:8080.

Usage:
  python server.py          # stdio mode (for Claude Desktop)
  python server.py --sse    # SSE mode (for web clients)
"""

import sys
from mcp.server.fastmcp import FastMCP

from revit_client import send_command, ping

mcp = FastMCP(
    "NGM Revit",
    version="0.1.0",
    description="Bridge between Claude AI and Autodesk Revit via NGM ecosystem"
)


# ---------------------------------------------------------------------------
# Connection tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def check_connection() -> str:
    """Check if Revit is running and the bridge add-in is active."""
    connected = await ping()
    if connected:
        result = await send_command("get_document_info")
        doc = result.get("data", {})
        return (
            f"Connected to Revit.\n"
            f"Document: {doc.get('title', 'Unknown')}\n"
            f"Path: {doc.get('path', 'Not saved')}\n"
            f"Elements: {doc.get('element_count', '?')}"
        )
    return "NOT connected. Make sure Revit is open with the NGM Bridge add-in loaded."


# ---------------------------------------------------------------------------
# Query tools - Read model data
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_elements_by_category(category: str) -> str:
    """Get all elements of a given Revit category.

    Args:
        category: Revit category name. Examples: "Walls", "Floors", "Doors",
                  "Windows", "Structural Columns", "Structural Framing",
                  "Rooms", "Roofs", "Stairs"
    """
    result = await send_command("get_elements_by_category", {"category": category})
    return _format_result(result)


@mcp.tool()
async def get_element_parameters(element_id: int) -> str:
    """Get all parameters of a specific Revit element by its ID.

    Args:
        element_id: The Revit ElementId (integer)
    """
    result = await send_command("get_element_parameters", {"element_id": element_id})
    return _format_result(result)


@mcp.tool()
async def get_quantities_summary() -> str:
    """Get a summary of all model quantities grouped by category and type.
    Returns counts, areas, and volumes for each element type.
    Useful for cost estimation and material takeoffs.
    """
    result = await send_command("get_quantities_summary")
    return _format_result(result)


@mcp.tool()
async def get_rooms() -> str:
    """Get all rooms in the model with area, perimeter, level, and finishes."""
    result = await send_command("get_rooms")
    return _format_result(result)


@mcp.tool()
async def get_levels() -> str:
    """Get all levels in the model with their elevations."""
    result = await send_command("get_levels")
    return _format_result(result)


@mcp.tool()
async def get_materials_summary() -> str:
    """Get a summary of all materials used in the model with areas and volumes."""
    result = await send_command("get_materials_summary")
    return _format_result(result)


@mcp.tool()
async def search_elements(query: str) -> str:
    """Search for elements by name, type, family, or parameter value.

    Args:
        query: Free-text search query. Examples: "CMU", "exterior wall",
               "NGM_Door_Single", "3'-0\" x 7'-0\""
    """
    result = await send_command("search_elements", {"query": query})
    return _format_result(result)


@mcp.tool()
async def get_selected_elements() -> str:
    """Get details of the currently selected elements in Revit.
    Returns parameters, type info, and geometry data for each selected element.
    """
    result = await send_command("get_selected_elements")
    return _format_result(result)


# ---------------------------------------------------------------------------
# Modify tools - Create/edit elements
# ---------------------------------------------------------------------------

@mcp.tool()
async def create_wall(
    start_x: float, start_y: float,
    end_x: float, end_y: float,
    wall_type: str, level: str,
    height_ft: float = 10.0
) -> str:
    """Create a wall in the Revit model.

    Args:
        start_x: Start X coordinate in decimal feet
        start_y: Start Y coordinate in decimal feet
        end_x: End X coordinate in decimal feet
        end_y: End Y coordinate in decimal feet
        wall_type: Wall type name (e.g. "Ext - CMU 6\" + Plaster")
        level: Level name (e.g. "Ground Floor")
        height_ft: Wall height in decimal feet (default 10.0)
    """
    result = await send_command("create_wall", {
        "start": [start_x, start_y],
        "end": [end_x, end_y],
        "wall_type": wall_type,
        "level": level,
        "height_ft": height_ft
    })
    return _format_result(result)


@mcp.tool()
async def set_parameter(element_id: int, parameter_name: str, value: str) -> str:
    """Set a parameter value on a Revit element.

    Args:
        element_id: The Revit ElementId (integer)
        parameter_name: Name of the parameter to set
        value: New value (will be parsed to appropriate type)
    """
    result = await send_command("set_parameter", {
        "element_id": element_id,
        "parameter_name": parameter_name,
        "value": value
    })
    return _format_result(result)


# ---------------------------------------------------------------------------
# Export tools - Extract data for NGM ecosystem
# ---------------------------------------------------------------------------

@mcp.tool()
async def export_quantities_json() -> str:
    """Export model quantities to JSON format compatible with NGM Estimator.
    Groups elements by Family+Type with count, area, and volume totals.
    """
    result = await send_command("export_quantities")
    return _format_result(result)


@mcp.tool()
async def export_materials_json() -> str:
    """Export all model materials with areas and volumes to JSON.
    Compatible with NGM material mapping system.
    """
    result = await send_command("export_materials")
    return _format_result(result)


# ---------------------------------------------------------------------------
# NGM Integration tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def push_to_estimator(project_id: str) -> str:
    """Push current model quantities directly to an NGM project estimator.

    Args:
        project_id: The NGM project UUID to push quantities to
    """
    result = await send_command("push_to_estimator", {"project_id": project_id})
    return _format_result(result)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_result(result: dict) -> str:
    """Format a bridge response for Claude consumption."""
    import json
    if result.get("error"):
        return f"Error: {result['error']}"
    data = result.get("data", result)
    if isinstance(data, (dict, list)):
        return json.dumps(data, indent=2, default=str)
    return str(data)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if "--sse" in sys.argv:
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")
