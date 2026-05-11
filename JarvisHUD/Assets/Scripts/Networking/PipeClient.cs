using System;
using System.Collections.Concurrent;
using System.IO;
using System.IO.Pipes;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;

/// <summary>
/// Connects to the Python Named Pipe server (\\.\pipe\JarvisMCP).
/// Reads newline-delimited JSON on a background Task; enqueues lines for
/// Update() to dispatch on the main thread. Reconnects automatically on drop.
/// </summary>
public class PipeClient : MonoBehaviour
{
    private const string PipeName         = "JarvisMCP";
    private const int    ReconnectDelayMs = 2000;
    private const int    ConnectTimeoutMs = 5000;
    private const int    MaxQueueSize     = 200;

    // Main-thread queue: background Task writes, Update() reads
    private readonly ConcurrentQueue<string> _incoming = new();

    private NamedPipeClientStream _pipe;
    private CancellationTokenSource _cts;
    private bool _connected;

    public bool IsConnected => _connected;

    /// <summary>Fired on the main thread for each raw JSON line received.</summary>
    public event Action<string> OnRawMessage;

    void Awake()
    {
        _cts = new CancellationTokenSource();
        Task.Run(() => ConnectLoop(_cts.Token));
    }

    void Update()
    {
        // Drain queue — guard against stale buildup
        int drained = 0;
        while (_incoming.TryDequeue(out var msg))
        {
            OnRawMessage?.Invoke(msg);
            if (++drained >= MaxQueueSize) break; // safety cap per frame
        }
    }

    void OnDestroy()
    {
        _cts.Cancel();
        _pipe?.Dispose();
    }

    // ── Background connection loop ──────────────────────────────────────────

    private async Task ConnectLoop(CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            try
            {
                _pipe = new NamedPipeClientStream(
                    ".", PipeName,
                    PipeDirection.InOut,
                    PipeOptions.Asynchronous);

                Debug.Log("[PipeClient] Connecting to Python pipe...");
                await _pipe.ConnectAsync(ConnectTimeoutMs, ct);
                _connected = true;
                Debug.Log("[PipeClient] Connected.");

                // Handshake
                await SendJsonAsync(new { type = "hud_ready", version = "1.0.0" }, ct);

                await ReadLoop(ct);
            }
            catch (OperationCanceledException) { break; }
            catch (Exception ex)
            {
                Debug.LogWarning($"[PipeClient] Disconnected: {ex.Message}");
            }
            finally
            {
                _connected = false;
                _pipe?.Dispose();
                _pipe = null;
            }

            if (!ct.IsCancellationRequested)
                await Task.Delay(ReconnectDelayMs, ct).ConfigureAwait(false);
        }
    }

    private async Task ReadLoop(CancellationToken ct)
    {
        using var reader = new StreamReader(_pipe, Encoding.UTF8, leaveOpen: true);
        while (!ct.IsCancellationRequested && (_pipe?.IsConnected ?? false))
        {
            var line = await reader.ReadLineAsync().ConfigureAwait(false);
            if (line == null) break;
            if (string.IsNullOrWhiteSpace(line)) continue;

            // Guard queue size
            if (_incoming.Count >= MaxQueueSize)
            {
                // Drain oldest items to make room
                for (int i = 0; i < 10 && _incoming.TryDequeue(out _); i++) { }
            }
            _incoming.Enqueue(line);
        }
    }

    /// <summary>Send a JSON-serializable object to Python. Call from any thread.</summary>
    public async Task SendJsonAsync(object obj, CancellationToken ct = default)
    {
        if (_pipe == null || !_pipe.IsConnected) return;
        try
        {
            var json  = Newtonsoft.Json.JsonConvert.SerializeObject(obj);
            var bytes = Encoding.UTF8.GetBytes(json + "\n");
            await _pipe.WriteAsync(bytes, 0, bytes.Length, ct).ConfigureAwait(false);
            await _pipe.FlushAsync(ct).ConfigureAwait(false);
        }
        catch (Exception ex)
        {
            Debug.LogWarning($"[PipeClient] Write error: {ex.Message}");
        }
    }

    /// <summary>Convenience: fire-and-forget send from the main thread.</summary>
    public void Send(object obj) => _ = SendJsonAsync(obj);
}
