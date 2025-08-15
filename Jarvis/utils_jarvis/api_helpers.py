"""
API Helpers - API interaction utilities for Jarvis
"""

import os
import json
import logging
import time
from .circuit_breaker import CircuitBreaker
import requests
from typing import Any, Dict, List, Optional, Union

# Check OpenAI version
try:
    import openai
    OPENAI_V1 = hasattr(openai, 'OpenAI')
except ImportError:
    openai = None
    OPENAI_V1 = False

openai_cb = CircuitBreaker()
elevenlabs_cb = CircuitBreaker()


def make_api_request(
    url: str,
    method: str = 'GET',
    params: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    json_data: Optional[Dict[str, Any]] = None,
    timeout: int = 10,
    circuit_breaker: CircuitBreaker | None = None,
    auth: Optional[tuple] = None
) -> Dict[str, Any]:
    """
    Make an API request with error handling
    
    Args:
        url: API endpoint URL
        method: HTTP method (GET, POST, PUT, DELETE)
        params: URL parameters
        data: Form data
        headers: HTTP headers
        json_data: JSON data for request body
        timeout: Request timeout in seconds
        auth: Basic authentication tuple (username, password)
        
    Returns:
        Dictionary with response data or error information
    """
    result = {
        'success': False,
        'status_code': None,
        'data': None,
        'error': None
    }
    
    try:
        if headers is None:
            headers = {
                'User-Agent': 'Jarvis AI Assistant',
                'Accept': 'application/json'
            }

        def do_request():
            resp = requests.request(
                method=method.upper(),
                url=url,
                params=params,
                data=data,
                headers=headers,
                json=json_data,
                timeout=timeout,
                auth=auth
            )
            resp.raise_for_status()
            return resp

        last_err = None
        for attempt in range(3):
            try:
                response = circuit_breaker.call(do_request) if circuit_breaker else do_request()
                last_err = None
                break
            except Exception as e:
                last_err = e
                logging.debug(f"API attempt {attempt+1} failed: {e}")
                time.sleep(2 ** attempt)

        if last_err:
            raise last_err
        
        # Set status code
        result['status_code'] = response.status_code
        
        # Check if request was successful
        
        # Try to parse as JSON if content type indicates JSON
        content_type = response.headers.get('Content-Type', '')
        if content_type.startswith('application/json'):
            try:
                result['data'] = response.json()
            except Exception:
                result['data'] = response.text
        else:
            result['data'] = response.content
            
        result['success'] = True
        
    except requests.exceptions.HTTPError as e:
        result['error'] = f"HTTP Error: {str(e)}"
        try:
            ct = response.headers.get('Content-Type', '')
            if ct.startswith('application/json'):
                result['data'] = response.json()
            else:
                result['data'] = response.content
        except Exception:
            if hasattr(response, 'text'):
                result['data'] = response.text
                
    except requests.exceptions.ConnectionError:
        result['error'] = "Connection Error: Failed to connect to the server"
        
    except requests.exceptions.Timeout:
        result['error'] = f"Timeout Error: Request timed out after {timeout} seconds"
        
    except requests.exceptions.RequestException as e:
        result['error'] = f"Request Error: {str(e)}"

    except RuntimeError as e:
        # Circuit breaker open
        result['error'] = str(e)

    except Exception as e:
        result['error'] = f"Unexpected Error: {str(e)}"
    
    # Log the result
    if result['success']:
        logging.info(f"API request to {url} successful (Status: {result['status_code']})")
    else:
        logging.error(f"API request to {url} failed: {result['error']}")
    
    return result


def get_openai_response(
    api_key: str,
    messages: List[Dict[str, str]],
    model: str = "gpt-3.5-turbo",
    max_tokens: int = 150,
    temperature: float = 0.7
) -> Optional[str]:
    """
    Get a response from OpenAI's GPT API (compatible with both v0 and v1)
    
    Args:
        api_key: OpenAI API key
        messages: List of message dictionaries with 'role' and 'content'
        model: Model to use
        max_tokens: Maximum tokens in response
        temperature: Temperature parameter
        
    Returns:
        Response text or None if request failed
    """
    if not openai:
        logging.error("OpenAI package not installed")
        return None
    
    try:
        if OPENAI_V1:
            # New v1.0+ API
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
            return response.choices[0].message.content
        else:
            # Old API
            openai.api_key = api_key
            response = openai.ChatCompletion.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
            return response['choices'][0]['message']['content']
    except Exception as e:
        logging.error(f"OpenAI API error: {str(e)}")
        return None


def get_elevenlabs_audio(
    api_key: str,
    text: str,
    voice_id: str,
    model_id: str = "eleven_multilingual_v2"
) -> Optional[bytes]:
    """
    Get speech audio from ElevenLabs API
    
    Args:
        api_key: ElevenLabs API key
        text: Text to convert to speech
        voice_id: ElevenLabs voice ID
        model_id: Model ID to use
        
    Returns:
        Audio data as bytes or None if request failed
    """
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key
    }
    
    json_data = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.5
        }
    }
    
    result = make_api_request(
        url=url,
        method="POST",
        headers=headers,
        json_data=json_data,
        timeout=30,
        circuit_breaker=elevenlabs_cb
    )

    if result["success"] and result["data"]:
        # data is bytes when success
        if isinstance(result["data"], (bytes, bytearray)):
            return result["data"]
        else:
            # In case make_api_request parsed json
            return result["data"]
    return None


def get_openai_audio(
    api_key: str,
    text: str,
    voice: str = "alloy"
) -> Optional[bytes]:
    """
    Get speech audio from OpenAI TTS API
    
    Args:
        api_key: OpenAI API key
        text: Text to convert to speech
        voice: Voice to use
        
    Returns:
        Audio data as bytes or None if request failed
    """
    try:
        if OPENAI_V1:
            # New v1.0+ API
            client = openai.OpenAI(api_key=api_key)
            response = client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text
            )
            return response.content
        else:
            # Fallback to direct API call for old versions
            url = "https://api.openai.com/v1/audio/speech"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            json_data = {
                "model": "tts-1",
                "voice": voice,
                "input": text
            }
            response = requests.post(url, json=json_data, headers=headers)
            return response.content
    except Exception as e:
        logging.error(f"OpenAI TTS API error: {str(e)}")
        return None


def get_edmonton_weather() -> Optional[Dict[str, Any]]:
    """
    Get weather data for Edmonton, Alberta from Open-Meteo API
    No API key required.
    
    Returns:
        Weather data dictionary or None if request failed
    """
    url = "https://api.open-meteo.com/v1/forecast"
    
    params = {
        "latitude": 53.5501,
        "longitude": -113.4687,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,wind_direction_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,apparent_temperature_max,apparent_temperature_min,precipitation_sum,precipitation_probability_max",
        "timezone": "America/Edmonton",
        "temperature_unit": "celsius",
        "wind_speed_unit": "km/h",
        "precipitation_unit": "mm"
    }
    
    result = make_api_request(url=url, params=params)
    
    if result['success'] and result['data']:
        return result['data']
    else:
        return None


def format_edmonton_weather(weather_data: Dict[str, Any]) -> str:
    """
    Format Open-Meteo weather data for Edmonton into a human-readable response
    
    Args:
        weather_data: Weather data from get_edmonton_weather()
        
    Returns:
        Formatted weather information as a string
    """
    if not weather_data or 'current' not in weather_data:
        return "Sorry, I couldn't retrieve the weather information for Edmonton."
    
    current = weather_data['current']
    daily = weather_data.get('daily', {})
    
    # Weather code to condition mapping
    weather_codes = {
        0: "Clear sky",
        1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Fog", 48: "Depositing rime fog",
        51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
        61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
        71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
        80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
        95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail"
    }
    
    # Get weather condition
    weather_code = current.get('weather_code')
    condition = weather_codes.get(weather_code, "Unknown conditions")
    
    # Current conditions
    response = f"Current weather in Edmonton: {condition}, {current.get('temperature_2m', 'N/A')}°C, "
    response += f"feels like {current.get('apparent_temperature', 'N/A')}°C. "
    response += f"Humidity is {current.get('relative_humidity_2m', 'N/A')}%, "
    response += f"wind speed is {current.get('wind_speed_10m', 'N/A')} km/h. "
    
    # Add forecast if available
    if daily and 'temperature_2m_max' in daily and len(daily['temperature_2m_max']) > 0:
        response += f"Today's forecast: High of {daily['temperature_2m_max'][0]}°C, "
        response += f"low of {daily['temperature_2m_min'][0]}°C. "
        
        if 'precipitation_probability_max' in daily and len(daily['precipitation_probability_max']) > 0:
            precip_prob = daily['precipitation_probability_max'][0]
            if precip_prob > 0:
                response += f"There's a {precip_prob}% chance of precipitation."
    
    return response


def get_news_headlines(
    api_key: str,
    country: str = "us",
    category: str = "general",
    page_size: int = 5
) -> Optional[List[Dict[str, Any]]]:
    """
    Get news headlines from NewsAPI
    
    Args:
        api_key: NewsAPI key
        country: Country code (e.g., us, gb, de)
        category: News category (business, entertainment, general, health, science, sports, technology)
        page_size: Number of headlines to return
        
    Returns:
        List of news articles or None if request failed
    """
    url = "https://newsapi.org/v2/top-headlines"
    
    params = {
        "country": country,
        "category": category,
        "pageSize": page_size,
        "apiKey": api_key
    }
    
    result = make_api_request(url=url, params=params)
    
    if result['success'] and result['data'] and 'articles' in result['data']:
        return result['data']['articles']
    else:
        return None


def search_youtube_videos(
    api_key: str,
    query: str,
    max_results: int = 5
) -> Optional[List[Dict[str, Any]]]:
    """
    Search for videos on YouTube using the YouTube Data API
    
    Args:
        api_key: YouTube Data API key
        query: Search query
        max_results: Maximum number of results to return
        
    Returns:
        List of video items or None if request failed
    """
    url = "https://www.googleapis.com/youtube/v3/search"
    
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": max_results,
        "key": api_key
    }
    
    result = make_api_request(url=url, params=params)
    
    if result['success'] and result['data'] and 'items' in result['data']:
        return result['data']['items']
    else:
        return None


def translate_text(
    api_key: str,
    text: str,
    target_language: str,
    source_language: Optional[str] = None
) -> Optional[str]:
    """
    Translate text using Google Cloud Translation API
    
    Args:
        api_key: Google Cloud API key
        text: Text to translate
        target_language: Target language code (e.g., en, es, fr)
        source_language: Source language code (auto-detect if None)
        
    Returns:
        Translated text or None if request failed
    """
    url = "https://translation.googleapis.com/language/translate/v2"
    
    params = {
        "key": api_key,
        "q": text,
        "target": target_language
    }
    
    if source_language:
        params["source"] = source_language
    
    result = make_api_request(url=url, method="POST", params=params)
    
    if result['success'] and result['data'] and 'data' in result['data']:
        try:
            return result['data']['data']['translations'][0]['translatedText']
        except (KeyError, IndexError):
            logging.error("Unexpected translation API response format")
            return None
    else:
        return None


def cache_api_response(
    cache_file: str,
    key: str,
    data: Any,
    expiry_hours: int = 24
) -> bool:
    """
    Cache API response to a file
    
    Args:
        cache_file: Path to cache file
        key: Cache key
        data: Data to cache
        expiry_hours: Number of hours until cache expires
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create cache directory if it doesn't exist
        cache_dir = os.path.dirname(cache_file)
        if cache_dir and not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        
        # Read existing cache
        cache = {}
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                cache = json.load(f)
        
        # Add new data with expiry timestamp
        import time
        expiry_time = time.time() + (expiry_hours * 3600)
        
        cache[key] = {
            'data': data,
            'expires': expiry_time
        }
        
        # Write cache to file
        with open(cache_file, 'w') as f:
            json.dump(cache, f)
        
        return True
    except Exception as e:
        logging.error(f"Error caching API response: {str(e)}")
        return False


def get_cached_api_response(
    cache_file: str,
    key: str
) -> Optional[Any]:
    """
    Get cached API response
    
    Args:
        cache_file: Path to cache file
        key: Cache key
        
    Returns:
        Cached data or None if not found or expired
    """
    try:
        # Check if cache file exists
        if not os.path.exists(cache_file):
            return None
        
        # Read cache
        with open(cache_file, 'r') as f:
            cache = json.load(f)
        
        # Check if key exists in cache
        if key not in cache:
            return None
        
        # Check if cache has expired
        import time
        if time.time() > cache[key]['expires']:
            return None
        
        return cache[key]['data']
    except Exception as e:
        logging.error(f"Error reading cached API response: {str(e)}")
        return None