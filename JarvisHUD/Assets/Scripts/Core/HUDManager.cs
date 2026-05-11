using Newtonsoft.Json.Linq;
using UnityEngine;

/// <summary>
/// Singleton orchestrator. Owns PipeClient, parses incoming JSON,
/// and fires MessageBus events on the Unity main thread.
/// Add this MonoBehaviour to a persistent GameObject in the scene.
/// </summary>
public class HUDManager : MonoBehaviour
{
    public static HUDManager Instance { get; private set; }

    [Header("References")]
    [SerializeField] private PipeClient pipeClient;

    void Awake()
    {
        if (Instance != null) { Destroy(gameObject); return; }
        Instance = this;
        DontDestroyOnLoad(gameObject);
    }

    void Start()
    {
        if (pipeClient == null)
            pipeClient = GetComponentInChildren<PipeClient>();

        pipeClient.OnRawMessage += HandleRawMessage;
    }

    void OnDestroy()
    {
        if (pipeClient != null)
            pipeClient.OnRawMessage -= HandleRawMessage;
    }

    // ── Expose pipe send for other scripts ──────────────────────────────────

    public void SendToPython(object obj) => pipeClient?.Send(obj);

    public void SendMuteVoice(bool muted) =>
        SendToPython(new { type = "mute_voice", muted });

    public void SendForceListen() =>
        SendToPython(new { type = "force_listen", source = "button_press" });

    public void SendClearMemory() =>
        SendToPython(new { type = "clear_memory" });

    // ── JSON routing ────────────────────────────────────────────────────────

    private void HandleRawMessage(string json)
    {
        try
        {
            var obj  = JObject.Parse(json);
            var type = obj["type"]?.ToString() ?? string.Empty;

            switch (type)
            {
                case "voice_state":
                    MessageBus.FireVoiceState(obj["state"]?.ToString());
                    break;

                case "wake_word_detected":
                    MessageBus.FireWakeWord();
                    break;

                case "listening_stop":
                    MessageBus.FireTranscript(obj["transcript"]?.ToString());
                    break;

                case "response_start":
                    // Optionally show the command being processed
                    break;

                case "response_chunk":
                    MessageBus.FireChunk(obj["chunk"]?.ToString());
                    break;

                case "response_end":
                    MessageBus.FireResponseEnd(obj["text"]?.ToString());
                    break;

                case "tool_call":
                    MessageBus.FireToolCall(obj["tool"]?.ToString());
                    break;

                case "speaking_start":
                    MessageBus.FireSpeakingStart();
                    break;

                case "speaking_end":
                    MessageBus.FireSpeakingEnd();
                    break;

                case "conversation_cleared":
                    MessageBus.FireConversationCleared();
                    break;

                case "hud_message":
                    MessageBus.FireHudMessage(new HudMessageData
                    {
                        Message     = obj["message"]?.ToString(),
                        MessageType = obj["message_type"]?.ToString() ?? "info",
                        DurationMs  = obj["duration_ms"]?.ToObject<int>() ?? 5000,
                    });
                    break;

                case "hud_animation":
                    MessageBus.FireAnimation(new AnimTriggerData
                    {
                        Animation = obj["animation"]?.ToString(),
                        Intensity = obj["intensity"]?.ToObject<float>() ?? 1.0f,
                    });
                    break;

                case "system_stats":
                    MessageBus.FireStats(new SystemStatsData
                    {
                        CpuPct = obj["cpu_pct"]?.ToObject<float>() ?? 0f,
                        RamPct = obj["ram_pct"]?.ToObject<float>() ?? 0f,
                    });
                    break;

                case "error":
                    var msg   = obj["message"]?.ToString() ?? "Unknown error";
                    var recov = obj["recoverable"]?.ToObject<bool>() ?? true;
                    MessageBus.FireError(msg, recov);
                    break;

                case "pong":
                    // Keepalive reply — no action needed
                    break;

                default:
                    Debug.LogWarning($"[HUDManager] Unknown message type: {type}");
                    break;
            }
        }
        catch (System.Exception ex)
        {
            Debug.LogWarning($"[HUDManager] Parse error: {ex.Message}\nRaw: {json}");
        }
    }
}
