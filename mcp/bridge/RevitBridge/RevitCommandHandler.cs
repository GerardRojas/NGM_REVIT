using System;
using System.Collections.Generic;
using System.Threading;
using Autodesk.Revit.DB;
using Autodesk.Revit.UI;

namespace NGM.RevitBridge
{
    /// <summary>
    /// Handles executing Revit API commands on the main Revit thread.
    ///
    /// The Revit API is single-threaded - all calls MUST happen on the main thread.
    /// HTTP requests arrive on background threads. The ExternalEvent pattern bridges
    /// this gap: we queue a command, raise the event, Revit calls Execute() on the
    /// main thread, and we signal the waiting HTTP thread when done.
    /// </summary>
    public class RevitCommandHandler : IExternalEventHandler
    {
        private Document _doc;
        private string _pendingCommand;
        private Dictionary<string, object> _pendingParams;
        private Dictionary<string, object> _result;
        private readonly ManualResetEventSlim _commandComplete = new ManualResetEventSlim(false);

        public void SetDocument(Document doc)
        {
            _doc = doc;
        }

        /// <summary>
        /// Queue a command and wait for it to execute on the Revit main thread.
        /// Called from the HTTP server's background thread.
        /// </summary>
        public Dictionary<string, object> ExecuteCommand(
            string command,
            Dictionary<string, object> parameters,
            ExternalEvent externalEvent)
        {
            _pendingCommand = command;
            _pendingParams = parameters ?? new Dictionary<string, object>();
            _result = null;
            _commandComplete.Reset();

            // Raise the event - Revit will call Execute() on the main thread
            externalEvent.Raise();

            // Wait for completion (timeout 30s)
            if (!_commandComplete.Wait(TimeSpan.FromSeconds(30)))
            {
                return new Dictionary<string, object>
                {
                    { "error", "Command timed out after 30 seconds" }
                };
            }

            return _result;
        }

        /// <summary>
        /// Called by Revit on the MAIN THREAD when the ExternalEvent fires.
        /// This is where we safely access the Revit API.
        /// </summary>
        public void Execute(UIApplication app)
        {
            try
            {
                // Ensure we have the active document
                if (_doc == null || !_doc.IsValidObject)
                    _doc = app.ActiveUIDocument?.Document;

                if (_doc == null)
                {
                    _result = new Dictionary<string, object>
                    {
                        { "error", "No document open in Revit" }
                    };
                    return;
                }

                // Route to the appropriate command handler
                _result = CommandRouter.Route(_doc, app, _pendingCommand, _pendingParams);
            }
            catch (Exception ex)
            {
                _result = new Dictionary<string, object>
                {
                    { "error", ex.Message },
                    { "stack", ex.StackTrace }
                };
            }
            finally
            {
                _commandComplete.Set();
            }
        }

        public string GetName() => "NGM Revit Bridge Command Handler";
    }
}
