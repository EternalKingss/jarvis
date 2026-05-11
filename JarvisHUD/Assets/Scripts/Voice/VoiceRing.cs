using System.Collections;
using UnityEngine;

/// <summary>
/// Arc reactor / voice ring visual controller.
///
/// State machine:
///   Idle      — slow breathing pulse (2-3s period, low intensity)
///   WakeWord  — one-shot flare then transitions to Listening
///   Listening — faster green pulse
///   Processing — amber ring with slow rotation
///   Speaking  — warm-white gentle pulse while Jarvis talks
///
/// Glow is driven by MaterialPropertyBlock (_EmissionColor, _GlowIntensity)
/// so no per-instance material leaks occur.
/// Requires a URP Bloom post-process volume on the camera for the full glow effect.
/// </summary>
[RequireComponent(typeof(Renderer))]
public class VoiceRing : MonoBehaviour
{
    public enum RingState { Idle, WakeWord, Listening, Processing, Speaking }

    [Header("Renderer")]
    [SerializeField] private Renderer ringRenderer;
    [SerializeField] private Light    ringPointLight;

    [Header("State Colors")]
    [SerializeField] private Color idleColor       = new Color(0.0f, 0.4f, 1.0f);   // cool blue
    [SerializeField] private Color listeningColor  = new Color(0.0f, 1.0f, 0.5f);   // green
    [SerializeField] private Color processingColor = new Color(1.0f, 0.6f, 0.0f);   // amber
    [SerializeField] private Color speakingColor   = new Color(0.9f, 0.9f, 1.0f);   // warm white
    [SerializeField] private Color alertColor      = new Color(1.0f, 0.1f, 0.1f);   // red

    [Header("Idle Breathing")]
    [SerializeField] private float idlePeriod = 3.0f;
    [SerializeField] private float idleMin    = 0.25f;
    [SerializeField] private float idleMax    = 0.65f;

    [Header("Processing")]
    [SerializeField] private float processingRotSpeed = 60f; // degrees/sec

    // Shader property IDs
    private static readonly int EmissionColorId = Shader.PropertyToID("_EmissionColor");
    private static readonly int GlowIntensityId  = Shader.PropertyToID("_GlowIntensity");

    private MaterialPropertyBlock _mpb;
    private RingState _state = RingState.Idle;

    void Awake()
    {
        _mpb = new MaterialPropertyBlock();
        if (ringRenderer == null) ringRenderer = GetComponent<Renderer>();

        MessageBus.OnVoiceStateChanged  += OnVoiceState;
        MessageBus.OnAnimationTrigger   += OnAnimTrigger;
        MessageBus.OnError              += OnError;
    }

    void OnDestroy()
    {
        MessageBus.OnVoiceStateChanged  -= OnVoiceState;
        MessageBus.OnAnimationTrigger   -= OnAnimTrigger;
        MessageBus.OnError              -= OnError;
    }

    void Update()
    {
        switch (_state)
        {
            case RingState.Idle:
                float breathe = Mathf.Lerp(idleMin, idleMax,
                    (Mathf.Sin(Time.time * (2f * Mathf.PI / idlePeriod)) + 1f) * 0.5f);
                SetGlow(idleColor, breathe);
                break;

            case RingState.Listening:
                float listenGlow = Mathf.Lerp(0.7f, 1.5f,
                    (Mathf.Sin(Time.time * 6f) + 1f) * 0.5f);
                SetGlow(listeningColor, listenGlow);
                break;

            case RingState.Processing:
                transform.Rotate(Vector3.forward, processingRotSpeed * Time.deltaTime);
                float procGlow = Mathf.Lerp(0.8f, 1.3f,
                    (Mathf.Sin(Time.time * 10f) + 1f) * 0.5f);
                SetGlow(processingColor, procGlow);
                break;

            case RingState.Speaking:
                float speakGlow = Mathf.Lerp(0.4f, 0.9f,
                    (Mathf.Sin(Time.time * (2f * Mathf.PI / 1.5f)) + 1f) * 0.5f);
                SetGlow(speakingColor, speakGlow);
                break;

            // WakeWord handled by coroutine
        }
    }

    // ── State transitions ────────────────────────────────────────────────────

    private void OnVoiceState(string state)
    {
        StopAllCoroutines();

        _state = state switch
        {
            "LISTENING"  => RingState.Listening,
            "PROCESSING" => RingState.Processing,
            "SPEAKING"   => RingState.Speaking,
            _            => RingState.Idle,
        };

        if (state == "IDLE" || state == "PROCESSING")
            transform.rotation = Quaternion.identity;

        if (state == "LISTENING")
            StartCoroutine(WakeWordFlare());
    }

    private void OnAnimTrigger(AnimTriggerData data)
    {
        StopAllCoroutines();
        switch (data.Animation)
        {
            case "pulse":       StartCoroutine(PulseCoroutine(data.Intensity)); break;
            case "alert_flash": StartCoroutine(AlertFlash()); break;
            case "scan":        StartCoroutine(ScanPulse(data.Intensity)); break;
        }
    }

    private void OnError(string message, bool recoverable)
    {
        StopAllCoroutines();
        StartCoroutine(AlertFlash());
        _state = RingState.Idle;
    }

    // ── Coroutines ───────────────────────────────────────────────────────────

    private IEnumerator WakeWordFlare()
    {
        // Quick flare on wake word before settling into LISTENING pulse
        float elapsed = 0f;
        while (elapsed < 0.3f)
        {
            SetGlow(listeningColor, Mathf.Lerp(3.0f, 1.0f, elapsed / 0.3f));
            elapsed += Time.deltaTime;
            yield return null;
        }
        // Update() takes over LISTENING pulse from here
    }

    private IEnumerator PulseCoroutine(float intensity)
    {
        float elapsed = 0f;
        float duration = 0.5f;
        while (elapsed < duration)
        {
            float t    = elapsed / duration;
            float glow = Mathf.Lerp(intensity * 3.0f, 0f, t * t);
            SetGlow(listeningColor, glow);
            elapsed += Time.deltaTime;
            yield return null;
        }
        // Return to current state
    }

    private IEnumerator AlertFlash()
    {
        for (int i = 0; i < 3; i++)
        {
            SetGlow(alertColor, 2.5f);
            yield return new WaitForSeconds(0.1f);
            SetGlow(alertColor, 0.05f);
            yield return new WaitForSeconds(0.1f);
        }
    }

    private IEnumerator ScanPulse(float intensity)
    {
        float elapsed = 0f;
        while (elapsed < 1.5f)
        {
            float glow = Mathf.Sin(elapsed * Mathf.PI * 4f) * intensity;
            SetGlow(idleColor, Mathf.Abs(glow) + 0.2f);
            elapsed += Time.deltaTime;
            yield return null;
        }
    }

    // ── Glow helper ──────────────────────────────────────────────────────────

    private void SetGlow(Color color, float intensity)
    {
        ringRenderer.GetPropertyBlock(_mpb);
        _mpb.SetColor(EmissionColorId, color * intensity);
        _mpb.SetFloat(GlowIntensityId, intensity);
        ringRenderer.SetPropertyBlock(_mpb);

        if (ringPointLight != null)
        {
            ringPointLight.color     = color;
            ringPointLight.intensity = intensity * 2f;
        }
    }
}
