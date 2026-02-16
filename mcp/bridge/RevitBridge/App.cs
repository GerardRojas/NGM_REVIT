using System;
using Autodesk.Revit.DB;
using Autodesk.Revit.UI;

namespace NGM.RevitBridge
{
    /// <summary>
    /// Main entry point. Loads when Revit starts, starts the HTTP bridge server,
    /// and registers the ExternalEvent handler for thread-safe API access.
    /// </summary>
    public class App : IExternalApplication
    {
        private HttpServer _httpServer;
        private static ExternalEvent _externalEvent;
        private static RevitCommandHandler _commandHandler;

        public static UIApplication UiApp { get; private set; }

        public Result OnStartup(UIControlledApplication application)
        {
            try
            {
                // Register the ExternalEvent handler - this is how we safely
                // execute Revit API calls from the HTTP server's background thread
                _commandHandler = new RevitCommandHandler();
                _externalEvent = ExternalEvent.Create(_commandHandler);

                // Start the HTTP server on localhost:8080
                _httpServer = new HttpServer(_commandHandler, _externalEvent);
                _httpServer.Start();

                // Store reference for API access
                application.ControlledApplication.DocumentOpened += (sender, args) =>
                {
                    _commandHandler.SetDocument(args.Document);
                };

                TaskDialog.Show("NGM Bridge", "NGM Revit Bridge started on localhost:8080");
                return Result.Succeeded;
            }
            catch (Exception ex)
            {
                TaskDialog.Show("NGM Bridge Error", ex.ToString());
                return Result.Failed;
            }
        }

        public Result OnShutdown(UIControlledApplication application)
        {
            _httpServer?.Stop();
            return Result.Succeeded;
        }
    }
}
