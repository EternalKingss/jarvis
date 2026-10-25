"""
Helpers for calling Windows Runtime (WinRT) APIs from Windows PowerShell 5.1.

Built-in OCR, toast notifications and the Bluetooth radio are WinRT APIs with
no Python binding in our dependency set. PowerShell 5.1 can reach them, but
their async methods return IAsyncOperation objects that PowerShell cannot
await, so AWAIT_PRELUDE defines an `Await` function that converts them to
.NET Tasks and blocks on the result.
"""

from xml.sax.saxutils import escape

AWAIT_PRELUDE = r"""
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$__asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
$__asTaskAction = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction' })[0]
function Await($op, [Type]$type) {
    $task = $__asTaskGeneric.MakeGenericMethod($type).Invoke($null, @($op))
    $task.Wait(-1) | Out-Null
    $task.Result
}
function AwaitAction($op) {
    $task = $__asTaskAction.Invoke($null, @($op))
    $task.Wait(-1) | Out-Null
}
"""

# Toasts need an AppUserModelID registered with Windows. Windows PowerShell's
# own ID is present on every Windows 10/11 install, so notifications show
# under "Windows PowerShell".
_TOAST_APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"


def ps_quote(text: str) -> str:
    """Quote a string as a PowerShell single-quoted literal."""
    return "'" + text.replace("'", "''") + "'"


def toast_script(title: str, message: str) -> str:
    """PowerShell that shows a Windows toast notification."""
    xml = (
        "<toast><visual><binding template='ToastGeneric'>"
        f"<text>{escape(title)}</text><text>{escape(message)}</text>"
        "</binding></visual></toast>"
    )
    return (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null\n"
        "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null\n"
        "$xml = New-Object Windows.Data.Xml.Dom.XmlDocument\n"
        f"$xml.LoadXml({ps_quote(xml)})\n"
        "$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)\n"
        f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier({ps_quote(_TOAST_APP_ID)}).Show($toast)\n"
        "Write-Output 'shown'\n"
    )


def ocr_script(image_path: str) -> str:
    """PowerShell that prints the text Windows OCR finds in an image, one line per text line."""
    return AWAIT_PRELUDE + (
        "[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null\n"
        "[Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null\n"
        "[Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime] | Out-Null\n"
        "$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()\n"
        "if ($null -eq $engine) { Write-Error 'NO_OCR_LANGUAGE'; exit 3 }\n"
        f"$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync({ps_quote(image_path)})) ([Windows.Storage.StorageFile])\n"
        "$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])\n"
        "$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])\n"
        "$bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])\n"
        "$result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])\n"
        "$stream.Dispose()\n"
        "foreach ($line in $result.Lines) { Write-Output $line.Text }\n"
    )


OCR_MAX_DIMENSION_SCRIPT = (
    "[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null\n"
    "[Windows.Media.Ocr.OcrEngine]::MaxImageDimension\n"
)
