# Setup Guide

## Prerequisites

1. **Python 3.11+** with pip
2. **Visual Studio 2022** (Community is fine) with ".NET desktop development" workload
3. **Revit 2024** or newer
4. **Claude Desktop** app

## Step 1: MCP Server (Python)

```bash
cd C:\Users\germa\Desktop\NGM_REVIT\mcp\server
pip install -r requirements.txt
```

Test it runs:
```bash
python server.py
# Should start and wait for stdio input (Ctrl+C to stop)
```

## Step 2: Revit Bridge (C#)

1. Open `mcp\bridge\RevitBridge.sln` in Visual Studio 2022
2. NuGet should auto-restore `Autodesk.Revit.SDK`
3. Build solution (Ctrl+Shift+B)
4. Copy output files to Revit add-ins folder:

```
# Copy these files:
mcp\bridge\RevitBridge\bin\Debug\NGM.RevitBridge.dll
mcp\bridge\RevitBridge\bin\Debug\RevitBridge.addin

# To:
%AppData%\Autodesk\Revit\Addins\2024\
```

Or create a symlink for development:
```cmd
mklink "%AppData%\Autodesk\Revit\Addins\2024\RevitBridge.addin" "C:\Users\germa\Desktop\NGM_REVIT\mcp\bridge\RevitBridge\RevitBridge.addin"
```

## Step 3: Configure Claude Desktop

Edit `%AppData%\Claude\claude_desktop_config.json` and add:

```json
{
  "mcpServers": {
    "ngm-revit": {
      "command": "python",
      "args": ["C:\\Users\\germa\\Desktop\\NGM_REVIT\\mcp\\server\\server.py"]
    }
  }
}
```

Restart Claude Desktop.

## Step 4: Test

1. Open Revit with a project
2. You should see "NGM Revit Bridge started on localhost:8080" dialog
3. Open Claude Desktop
4. You should see the hammer icon (tools) in the chat input
5. Ask Claude: "Check if Revit is connected"
6. Claude will call the `check_connection` tool and report the model info

## Troubleshooting

### "Bridge not connected"
- Make sure Revit is open with a document
- Check if port 8080 is available: `netstat -ano | findstr 8080`
- Try a different port in both HttpServer.cs and revit_client.py

### Revit doesn't load the add-in
- Check the .addin file path is correct
- Make sure the DLL is built for .NET 4.8
- Check Revit's journal file for errors: `%localappdata%\Autodesk\Revit\Autodesk Revit 2024\Journals\`

### "HttpListener access denied"
- Run Revit as Administrator once, or:
- `netsh http add urlacl url=http://localhost:8080/ user=Everyone`
