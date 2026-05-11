using System;
using UnityEngine;

/// <summary>
/// Central static event hub. HUDManager parses raw JSON and fires these.
/// Other scripts subscribe to only what they need — fully decoupled.
/// All events are fired on the Unity main thread (inside Update).
/// </summary>
public static class MessageBus
{
    // ── Voice lifecycle ─────────────────────────────────────────────────────
    public static event Action<string> OnVoiceStateChanged;  // "IDLE"|"LISTENING"|"PROCESSING"|"SPEAKING"
    public static event Action         OnWakeWordDetected;
    public static event Action<string> OnTranscriptReady;    // final user transcript
    public static event Action<string> OnResponseChunk;      // streaming token (future use)
    public static event Action<string> OnResponseEnd;        // full final response text
    public static event Action<string> OnToolCall;           // tool name being executed
    public static event Action         OnSpeakingStart;
    public static event Action         OnSpeakingEnd;
    public static event Action         OnConversationCleared;

    // ── HUD commands from Claude ────────────────────────────────────────────
    public static event Action<HudMessageData>   OnHudMessage;
    public static event Action<AnimTriggerData>  OnAnimationTrigger;
    public static event Action<SystemStatsData>  OnSystemStats;

    // ── Error events ────────────────────────────────────────────────────────
    public static event Action<string, bool> OnError;  // (message, recoverable)

    // ── Internal fire methods — only HUDManager calls these ────────────────
    public static void FireVoiceState(string s)            => OnVoiceStateChanged?.Invoke(s);
    public static void FireWakeWord()                      => OnWakeWordDetected?.Invoke();
    public static void FireTranscript(string t)            => OnTranscriptReady?.Invoke(t);
    public static void FireChunk(string c)                 => OnResponseChunk?.Invoke(c);
    public static void FireResponseEnd(string t)           => OnResponseEnd?.Invoke(t);
    public static void FireToolCall(string name)           => OnToolCall?.Invoke(name);
    public static void FireSpeakingStart()                 => OnSpeakingStart?.Invoke();
    public static void FireSpeakingEnd()                   => OnSpeakingEnd?.Invoke();
    public static void FireConversationCleared()           => OnConversationCleared?.Invoke();
    public static void FireHudMessage(HudMessageData m)    => OnHudMessage?.Invoke(m);
    public static void FireAnimation(AnimTriggerData a)    => OnAnimationTrigger?.Invoke(a);
    public static void FireStats(SystemStatsData s)        => OnSystemStats?.Invoke(s);
    public static void FireError(string msg, bool recov)   => OnError?.Invoke(msg, recov);
}

// ── Data records ─────────────────────────────────────────────────────────────

public class HudMessageData
{
    public string Message     { get; set; }
    public string MessageType { get; set; } = "info";
    public int    DurationMs  { get; set; } = 5000;
}

public class AnimTriggerData
{
    public string Animation { get; set; }
    public float  Intensity { get; set; } = 1.0f;
}

public class SystemStatsData
{
    public float CpuPct { get; set; }
    public float RamPct { get; set; }
}
