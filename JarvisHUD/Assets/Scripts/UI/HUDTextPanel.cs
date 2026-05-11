using System.Collections;
using TMPro;
using UnityEngine;

/// <summary>
/// Displays Jarvis's responses as streaming text.
/// Appends response_end text; shows tool_call status mid-processing.
/// Hard-capped at 8000 chars — trims oldest 2000 when exceeded.
/// </summary>
public class HUDTextPanel : MonoBehaviour
{
    [Header("References")]
    [SerializeField] private TMP_Text mainText;
    [SerializeField] private TMP_Text statusText;   // small line above main text

    [Header("Settings")]
    [SerializeField] private int   maxChars        = 8000;
    [SerializeField] private int   trimAmount      = 2000;
    [SerializeField] private float messageFadeTime = 0.3f;   // fade in for new text

    private Coroutine _fadeCoroutine;

    void Awake()
    {
        MessageBus.OnResponseEnd         += OnResponseEnd;
        MessageBus.OnToolCall            += OnToolCall;
        MessageBus.OnVoiceStateChanged   += OnVoiceState;
        MessageBus.OnConversationCleared += OnConversationCleared;
        MessageBus.OnHudMessage          += OnHudMessage;
        MessageBus.OnError               += OnError;

        if (mainText   != null) mainText.text   = string.Empty;
        if (statusText != null) statusText.text = string.Empty;
    }

    void OnDestroy()
    {
        MessageBus.OnResponseEnd         -= OnResponseEnd;
        MessageBus.OnToolCall            -= OnToolCall;
        MessageBus.OnVoiceStateChanged   -= OnVoiceState;
        MessageBus.OnConversationCleared -= OnConversationCleared;
        MessageBus.OnHudMessage          -= OnHudMessage;
        MessageBus.OnError               -= OnError;
    }

    // ── Event handlers ───────────────────────────────────────────────────────

    private void OnResponseEnd(string text)
    {
        if (string.IsNullOrWhiteSpace(text)) return;
        SetStatus(string.Empty);
        AppendText($"\n<color=#00CFFF>Jarvis:</color> {text}");
    }

    private void OnToolCall(string toolName)
    {
        SetStatus($"⚡ {toolName.Replace("_", " ")}...");
    }

    private void OnVoiceState(string state)
    {
        switch (state)
        {
            case "LISTENING":
                SetStatus("Listening...");
                break;
            case "PROCESSING":
                SetStatus("Processing...");
                break;
            case "SPEAKING":
                SetStatus(string.Empty);
                break;
            case "IDLE":
                SetStatus(string.Empty);
                break;
        }
    }

    private void OnConversationCleared()
    {
        if (mainText   != null) mainText.text   = string.Empty;
        if (statusText != null) statusText.text = "Memory cleared.";
        Invoke(nameof(ClearStatus), 3f);
    }

    private void OnHudMessage(HudMessageData data)
    {
        var colorHex = data.MessageType switch
        {
            "warning" => "#FFA500",
            "alert"   => "#FF3333",
            "success" => "#00FF88",
            _         => "#00CFFF",
        };
        AppendText($"\n<color={colorHex}>[{data.MessageType.ToUpper()}]</color> {data.Message}");
    }

    private void OnError(string message, bool recoverable)
    {
        SetStatus($"<color=#FF3333>Error: {message}</color>");
        Invoke(nameof(ClearStatus), 5f);
    }

    // ── Helpers ──────────────────────────────────────────────────────────────

    private void AppendText(string text)
    {
        if (mainText == null) return;

        mainText.text += text;

        // Trim if over cap
        if (mainText.text.Length > maxChars)
            mainText.text = "...\n" + mainText.text.Substring(trimAmount);
    }

    private void SetStatus(string text)
    {
        if (statusText != null) statusText.text = text;
    }

    private void ClearStatus() => SetStatus(string.Empty);
}
