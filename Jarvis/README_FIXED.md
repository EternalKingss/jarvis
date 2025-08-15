# Jarvis AI Assistant - Fixed Version

This is the fixed version of your Jarvis AI Assistant. All major bugs have been resolved.

## Quick Start

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

   If you have issues with PyAudio on Windows:
   ```bash
   pip install pipwin
   pipwin install pyaudio
   ```

2. **Set Up API Keys**
   Run the setup script:
   ```bash
   python setup_api_keys.py
   ```

   Or manually set environment variables:
   ```bash
   set OPENAI_API_KEY=your_api_key_here
   ```

3. **Run Jarvis**
   ```bash
   python main.py
   ```

## Fixed Issues

- ✅ Updated to new OpenAI API (v1.0+)
- ✅ Fixed import errors in main.py
- ✅ Fixed authentication module compatibility
- ✅ Added missing sleep monitor
- ✅ Fixed API key decryption issues
- ✅ Updated deprecated package versions
- ✅ Added proper error handling for missing modules
- ✅ Fixed voice controller initialization

## Voice Commands

- "Hey Jarvis, open Chrome"
- "Hey Jarvis, what's the weather?"
- "Hey Jarvis, search for [topic]"
- "Hey Jarvis, play music"
- "Hey Jarvis, close [application]"
- "Hey Jarvis, create a folder named [name]"
- "Hey Jarvis, show clipboard history"

## Configuration

Edit `jarvis_config.ini` to customize:
- Voice settings
- Wake word
- API keys
- Advanced settings

## Troubleshooting

1. **"No module named 'openai'"**
   - Run: `pip install openai>=1.0.0`

2. **"API key not configured"**
   - Run: `python setup_api_keys.py`
   - Or set: `set OPENAI_API_KEY=your_key`

3. **Audio issues**
   - Install PyAudio using pipwin on Windows
   - Check microphone permissions

4. **Import errors**
   - Make sure you're in the Jarvis-main directory
   - Run: `pip install -r requirements.txt`

## Development

To add new commands, edit:
- `command_jarvis/gpt_command_handler.py` - Register new functions
- Add implementation in appropriate command module

## Support

If you encounter issues:
1. Check `jarvis_log.txt` for errors
2. Ensure all API keys are correctly set
