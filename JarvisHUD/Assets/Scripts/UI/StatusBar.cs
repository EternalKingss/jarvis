using TMPro;
using UnityEngine;
using UnityEngine.UI;

/// <summary>
/// Displays real-time CPU and RAM usage driven by system_stats heartbeat.
/// Wire up thin Slider UI elements styled with custom materials for the HUD aesthetic.
/// </summary>
public class StatusBar : MonoBehaviour
{
    [Header("CPU")]
    [SerializeField] private Slider  cpuSlider;
    [SerializeField] private TMP_Text cpuLabel;

    [Header("RAM")]
    [SerializeField] private Slider  ramSlider;
    [SerializeField] private TMP_Text ramLabel;

    [Header("Connection")]
    [SerializeField] private TMP_Text connectionLabel;
    [SerializeField] private Image    connectionIndicator;
    [SerializeField] private Color    connectedColor    = new Color(0f, 1f, 0.5f);
    [SerializeField] private Color    disconnectedColor = new Color(1f, 0.2f, 0.2f);

    [Header("Smoothing")]
    [SerializeField] private float lerpSpeed = 2f;

    private float _targetCpu;
    private float _targetRam;

    void Awake()
    {
        MessageBus.OnSystemStats += OnSystemStats;
    }

    void OnDestroy()
    {
        MessageBus.OnSystemStats -= OnSystemStats;
    }

    void Start()
    {
        if (cpuSlider != null) { cpuSlider.minValue = 0; cpuSlider.maxValue = 100; }
        if (ramSlider != null) { ramSlider.minValue = 0; ramSlider.maxValue = 100; }
        UpdateConnectionStatus(false);
    }

    void Update()
    {
        // Smooth the gauge values
        if (cpuSlider != null)
            cpuSlider.value = Mathf.Lerp(cpuSlider.value, _targetCpu, lerpSpeed * Time.deltaTime);

        if (ramSlider != null)
            ramSlider.value = Mathf.Lerp(ramSlider.value, _targetRam, lerpSpeed * Time.deltaTime);

        // Reflect pipe connection state
        if (HUDManager.Instance != null)
        {
            bool connected = HUDManager.Instance.GetComponent<PipeClient>()?.IsConnected ?? false;
            UpdateConnectionStatus(connected);
        }
    }

    private void OnSystemStats(SystemStatsData data)
    {
        _targetCpu = data.CpuPct;
        _targetRam = data.RamPct;

        if (cpuLabel != null) cpuLabel.text = $"CPU {data.CpuPct:0}%";
        if (ramLabel != null) ramLabel.text = $"RAM {data.RamPct:0}%";
    }

    private void UpdateConnectionStatus(bool connected)
    {
        if (connectionLabel != null)
            connectionLabel.text = connected ? "HUD ONLINE" : "CONNECTING...";

        if (connectionIndicator != null)
            connectionIndicator.color = connected ? connectedColor : disconnectedColor;
    }
}
