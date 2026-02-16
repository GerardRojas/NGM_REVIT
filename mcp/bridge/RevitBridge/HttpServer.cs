using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using Autodesk.Revit.UI;

namespace NGM.RevitBridge
{
    /// <summary>
    /// Lightweight HTTP server running inside Revit on localhost:8080.
    /// Receives JSON commands from the MCP server and dispatches them
    /// to the RevitCommandHandler via ExternalEvent for thread-safe execution.
    ///
    /// Only listens on localhost - no external network exposure.
    /// </summary>
    public class HttpServer
    {
        private readonly HttpListener _listener;
        private readonly RevitCommandHandler _commandHandler;
        private readonly ExternalEvent _externalEvent;
        private readonly JavaScriptSerializer _json;
        private CancellationTokenSource _cts;
        private const int PORT = 8080;

        public HttpServer(RevitCommandHandler commandHandler, ExternalEvent externalEvent)
        {
            _commandHandler = commandHandler;
            _externalEvent = externalEvent;
            _json = new JavaScriptSerializer { MaxJsonLength = int.MaxValue };
            _listener = new HttpListener();
            _listener.Prefixes.Add($"http://localhost:{PORT}/");
        }

        public void Start()
        {
            _cts = new CancellationTokenSource();
            _listener.Start();

            // Run listener on a background thread
            Task.Run(() => ListenLoop(_cts.Token));
        }

        public void Stop()
        {
            _cts?.Cancel();
            _listener?.Stop();
        }

        private async Task ListenLoop(CancellationToken ct)
        {
            while (!ct.IsCancellationRequested && _listener.IsListening)
            {
                try
                {
                    var context = await _listener.GetContextAsync();
                    // Handle each request on its own thread
                    Task.Run(() => HandleRequest(context));
                }
                catch (HttpListenerException) when (ct.IsCancellationRequested)
                {
                    break; // Normal shutdown
                }
                catch (Exception ex)
                {
                    System.Diagnostics.Debug.WriteLine($"NGM Bridge error: {ex.Message}");
                }
            }
        }

        private void HandleRequest(HttpListenerContext context)
        {
            var request = context.Request;
            var response = context.Response;

            try
            {
                // CORS headers for local development
                response.Headers.Add("Access-Control-Allow-Origin", "*");
                response.Headers.Add("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
                response.Headers.Add("Access-Control-Allow-Headers", "Content-Type");

                if (request.HttpMethod == "OPTIONS")
                {
                    response.StatusCode = 200;
                    response.Close();
                    return;
                }

                string responseBody;

                if (request.Url.AbsolutePath == "/ping")
                {
                    responseBody = _json.Serialize(new Dictionary<string, object>
                    {
                        { "status", "ok" },
                        { "server", "NGM Revit Bridge" },
                        { "port", PORT }
                    });
                }
                else if (request.Url.AbsolutePath == "/command" && request.HttpMethod == "POST")
                {
                    // Read request body
                    string body;
                    using (var reader = new StreamReader(request.InputStream, Encoding.UTF8))
                    {
                        body = reader.ReadToEnd();
                    }

                    var payload = _json.Deserialize<Dictionary<string, object>>(body);
                    var command = payload["command"]?.ToString();
                    var parameters = payload.ContainsKey("params")
                        ? payload["params"] as Dictionary<string, object>
                        : new Dictionary<string, object>();

                    // Execute on Revit's main thread via ExternalEvent
                    var result = _commandHandler.ExecuteCommand(command, parameters, _externalEvent);
                    responseBody = _json.Serialize(new Dictionary<string, object>
                    {
                        { "data", result }
                    });
                }
                else
                {
                    response.StatusCode = 404;
                    responseBody = _json.Serialize(new Dictionary<string, object>
                    {
                        { "error", "Not found. Use POST /command or GET /ping" }
                    });
                }

                var buffer = Encoding.UTF8.GetBytes(responseBody);
                response.ContentType = "application/json";
                response.ContentLength64 = buffer.Length;
                response.OutputStream.Write(buffer, 0, buffer.Length);
            }
            catch (Exception ex)
            {
                try
                {
                    response.StatusCode = 500;
                    var errorBody = Encoding.UTF8.GetBytes(
                        _json.Serialize(new Dictionary<string, object> { { "error", ex.Message } })
                    );
                    response.OutputStream.Write(errorBody, 0, errorBody.Length);
                }
                catch { /* swallow response errors */ }
            }
            finally
            {
                response.Close();
            }
        }
    }
}
