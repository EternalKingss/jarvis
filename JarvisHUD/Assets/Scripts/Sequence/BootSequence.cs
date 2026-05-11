using System.Collections;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

/// <summary>
/// Cinematic boot sequence played on application start.
///
/// Sequence:
///   1. Black screen — diagnostic text scrolls in line by line
///   2. Ring power-up flare (triggers MessageBus animation event)
///   3. Main HUD fades in
///   4. Boot overlay fades out and is disabled
///
/// Wire up in Inspector:
///   hudCanvas    — the main HUD CanvasGroup (starts alpha 0)
///   diagText     — TMP_Text for diagnostic scroll (on boot overlay)
///   bootOverlay  — CanvasGroup for the black boot screen
///   audioSource  — AudioSource for sound effects
/// </summary>
public class BootSequence : MonoBehaviour
{
    [Header("References")]
    [SerializeField] private CanvasGroup hudCanvas;
    [SerializeField] private TMP_Text    diagText;
    [SerializeField] private CanvasGroup bootOverlay;
    [SerializeField] private AudioSource audioSource;

    [Header("Audio")]
    [SerializeField] private AudioClip powerUpClip;
    [SerializeField] private AudioClip bootCompleteClip;

    [Header("Timing")]
    [SerializeField] private float lineDelay    = 0.18f;   // seconds between each diag line
    [SerializeField] private float preFadePause = 0.5f;
    [SerializeField] private float hudFadeDuration   = 1.2f;
    [SerializeField] private float overlayFadeDuration = 0.5f;

    private static readonly string[] DiagLines =
    {
        "JARVIS MARK-VII HUD SYSTEM",
        "Copyright Eternal Industries",
        "",
        "Initializing neural interface............... OK",
        "Loading Windows control subsystem.......... OK",
        "Connecting to MCP bridge................... OK",
        "Voice recognition module................... ONLINE",
        "ElevenLabs TTS engine...................... READY",
        "Named pipe IPC............................. LISTENING",
        "",
        "All systems nominal.",
        "",
        "GOOD MORNING.",
    };

    void Start()
    {
        if (hudCanvas != null)    hudCanvas.alpha = 0f;
        if (bootOverlay != null)  bootOverlay.alpha = 1f;
        StartCoroutine(PlaySequence());
    }

    private IEnumerator PlaySequence()
    {
        yield return new WaitForSeconds(0.3f);

        // Phase 1: Diagnostic text scroll
        if (diagText != null)
        {
            diagText.text = string.Empty;
            foreach (var line in DiagLines)
            {
                diagText.text += line + "\n";
                yield return new WaitForSeconds(lineDelay);
            }
        }

        yield return new WaitForSeconds(preFadePause);

        // Phase 2: Ring power-up
        if (powerUpClip != null && audioSource != null)
            audioSource.PlayOneShot(powerUpClip);

        MessageBus.FireAnimation(new AnimTriggerData { Animation = "pulse", Intensity = 3.0f });
        yield return new WaitForSeconds(0.6f);

        // Phase 3: Fade in HUD
        if (hudCanvas != null)
        {
            float t = 0f;
            while (t < hudFadeDuration)
            {
                hudCanvas.alpha = t / hudFadeDuration;
                t += Time.deltaTime;
                yield return null;
            }
            hudCanvas.alpha = 1f;
        }

        // Phase 4: Fade out boot overlay
        if (bootOverlay != null)
        {
            float t = 0f;
            while (t < overlayFadeDuration)
            {
                bootOverlay.alpha = 1f - t / overlayFadeDuration;
                t += Time.deltaTime;
                yield return null;
            }
            bootOverlay.gameObject.SetActive(false);
        }

        if (bootCompleteClip != null && audioSource != null)
            audioSource.PlayOneShot(bootCompleteClip);

        Debug.Log("[BootSequence] Complete — HUD active.");
    }
}
