import json
import os
import re
import time
import html as _html
import unicodedata
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import requests

# Languages that should prefer Sunbird for local and voice-first responses.
SUNBIRD_LANGUAGE_CODES = {
    'en', 'english',
    'sw', 'swa', 'swahili',
    'lg', 'lug', 'luganda',
    'luo', 'luo',
    'rw', 'kin', 'kinyarwanda',
    'rn', 'run', 'runyankole',
    'to', 'toro', 'rutooro',
    'ach', 'acholi',
    'ny', 'nyankole',
    'lg', 'lugbara',
    'ha', 'hausa',
    'am', 'amh', 'amharic',
    'ig', 'igbo',
    'yo', 'yoruba',
    'zu', 'zulu',
    'sn', 'shona',
    'xh', 'xhosa',
    'st', 'sesotho',
    'ts', 'tswana',
    'om', 'oromo',
    'sw', 'swa',
    'ar', 'arabic',
    'fr', 'french',
    'pt', 'portuguese',
    'es', 'spanish',
    'de', 'german',
    'it', 'italian',
    'nl', 'dutch',
    'ru', 'russian',
    'zh', 'chinese',
    'ja', 'japanese',
    'ko', 'korean',
    'hi', 'hindi',
    'bn', 'bengali',
    'tr', 'turkish',
    'vi', 'vietnamese',
    'ur', 'urdu'
}

# Basic keyword markers for African and widely-used world languages when no language code is provided.
LANGUAGE_MARKERS = {
    'lg': ['webale', 'mukwano', 'omwana', 'tulaba', 'ssente', 'ssebo', 'nsobola', 'obulamu', 'kati', 'kyokka', 'nalaba', 'tuleetawo'],
    'sw': ['habari', 'asante', 'jambo', 'safari', 'kuna', 'sasa', 'kwaheri', 'mambo', 'karibu'],
    'rw': ['amakuru', 'muraho', 'urakoze', 'mwana', 'nyogokuru', 'amakuru yawe'],
    'ach': ['inyongo', 'obedo', 'ker', 'peco', 'awe'],
    'ha': ['sannu', 'lafiya', 'nagode', 'yau'],
    'yo': ['bawo', 'e karo', 'mo dupe', 'oun'],
    'ig': ['kedu', 'daalu', 'ụlọ', 'akwa uwọ'],
    'zu': ['sawubona', 'ngiyabonga', 'yebo', 'unjani'],
    'sn': ['mhoro', 'ndatenda', 'zvaigona', 'shamwari'],
    'am': ['selam', 'amesegenallo', 'tensae', 'dehna neh'],
    'ar': ['مرحبا', 'شكرا', 'كيف حالك', 'صباح الخير'],
    'fr': ['bonjour', 'merci', 'ça va', 'au revoir'],
    'es': ['hola', 'gracias', 'como estas', 'buenos días'],
    'pt': ['olá', 'obrigado', 'como vai', 'bom dia'],
    'zh': ['你好', '谢谢', '再见', '请问'],
    'hi': ['नमस्ते', 'धन्यवाद', 'कैसे हो', 'शुभ प्रभात'],
}

FALLBACK_LANGUAGE_CODE = 'en'


def normalize_language_code(language_code: Optional[str]) -> str:
    if not language_code:
        return ''
    normalized = language_code.strip().lower().replace('_', '-').split('-')[0]
    return normalized


def guess_language_from_text(text: str) -> Optional[str]:
    if not text:
        return None

    normalized_text = text.lower()
    # Prefer simple keyword matching but use whole-word checks to avoid false positives
    for code, markers in LANGUAGE_MARKERS.items():
        for marker in markers:
            try:
                if re.search(r"\b" + re.escape(marker.lower()) + r"\b", normalized_text):
                    return code
            except re.error:
                if marker.lower() in normalized_text:
                    return code

    # Fallback: try langdetect if available (optional dependency)
    try:
        from langdetect import detect
        lang = detect(text)
        if lang:
            return lang.split('-')[0]
    except Exception:
        pass

    return None


def is_sunbird_language(language_code: Optional[str]) -> bool:
    code = normalize_language_code(language_code)
    return code in SUNBIRD_LANGUAGE_CODES


def extract_text_from_response_body(resp_json: Any) -> str:
    def clean_extracted_text(text: str) -> str:
        if not text:
            return ''
        # Unescape HTML entities
        text = _html.unescape(text)
        # Remove control characters
        text = re.sub(r"[\x00-\x1F\x7F-\x9F]", '', text)
        # Normalize unicode (NFKC) to collapse weird symbols
        try:
            text = unicodedata.normalize('NFKC', text)
        except Exception:
            pass
        # Normalize line endings
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        # Collapse multiple blank lines into two
        text = re.sub(r"\n{3,}", '\n\n', text)
        # Trim spaces on each line
        text = '\n'.join([ln.strip() for ln in text.split('\n')])
        # Collapse multiple spaces
        text = re.sub(r"[ \t]{2,}", ' ', text)
        # Final trim
        return text.strip()

    raw_text = ''
    if resp_json is None:
        return ''

    if isinstance(resp_json, str):
        raw_text = resp_json
    elif isinstance(resp_json, dict):
        for key in ('answer', 'response', 'text', 'output', 'result'):
            if key in resp_json and isinstance(resp_json[key], str):
                raw_text = resp_json[key]
                break

        # If there is a deep nested message structure, try to find it.
        if not raw_text and 'candidates' in resp_json and isinstance(resp_json['candidates'], list) and resp_json['candidates']:
            candidate = resp_json['candidates'][0]
            content = candidate.get('content', {})
            if isinstance(content, dict) and 'parts' in content:
                parts_texts = [p.get('text', '') for p in content.get('parts', []) if isinstance(p, dict)]
                raw_text = ' '.join(parts_texts)

        if not raw_text and 'data' in resp_json and isinstance(resp_json['data'], dict):
            raw_text = extract_text_from_response_body(resp_json['data'])

        # Handle OpenAI/Cerebras style completions
        if not raw_text and 'choices' in resp_json and isinstance(resp_json['choices'], list) and resp_json['choices']:
            choice = resp_json['choices'][0]
            if isinstance(choice, dict):
                # Chat-style
                msg = choice.get('message') or choice.get('delta')
                if isinstance(msg, dict):
                    content = msg.get('content') or msg.get('text')
                    if isinstance(content, str):
                        raw_text = content
                # Text-style
                if not raw_text and 'text' in choice and isinstance(choice['text'], str):
                    raw_text = choice['text']

        # If the whole payload is a simple dictionary with a string contained deep in nested keys,
        # return the first string we can find.
        if not raw_text:
            for value in resp_json.values():
                if isinstance(value, str):
                    raw_text = value
                    break

    cleaned = clean_extracted_text(raw_text)
    return cleaned


def get_env_value(*keys: str) -> str:
    for key in keys:
        value = os.environ.get(key, '').strip()
        if value:
            return value
    return ''


def clean_base_url(url: str) -> str:
    """Extracts only the scheme and network location (host:port) to prevent nested path bugs."""
    try:
        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        pass
    return url.rstrip('/')


def get_sunbird_request_payload(prompt: str, system_instruction: str, language_code: str, voice: bool, temperature: float) -> Dict[str, Any]:
    return {
        'prompt': prompt,
        'system_instruction': system_instruction,
        'language_code': language_code or FALLBACK_LANGUAGE_CODE,
        'voice': voice,
        'temperature': temperature,
        'mode': 'multilingual_education',
    }


def call_sunbird_api(prompt: str, system_instruction: str = '', language_code: str = '', voice: bool = False, temperature: float = 0.7) -> str:
    base_url = get_env_value('SUNBIRD_API_URL', 'SUNBIRD_URL')
    api_key = get_env_value('SUNBIRD_API_KEY', 'SUNBIRD_KEY')
    if not base_url or not api_key:
        raise RuntimeError('Sunbird API is not configured.')

    payload = get_sunbird_request_payload(prompt, system_instruction, language_code, voice, temperature)
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }


    # Try a small set of common alternative endpoints
    tried = []
    candidate_paths = [
        '/v1/generate',
        '/tasks/tasks/mix-translate',
        '/v1/completions',
    ]

    # Normalize base (strip any accidental path and keep scheme://host[:port])
    base = clean_base_url(base_url)

    last_exc = None
    for path in candidate_paths:
        target = base + path
        tried.append(target)
        try:
            resp = requests.post(target, json=payload, headers=headers, timeout=30)
            if resp.status_code == 405:
                # Wrong method for this endpoint - try next
                last_exc = requests.exceptions.HTTPError(f'405 Method Not Allowed for {target}')
                continue
            if resp.status_code >= 400 and resp.status_code < 500:
                # Client error - capture and try next
                last_exc = requests.exceptions.HTTPError(f'{resp.status_code} Client Error for {target}')
                continue
            resp.raise_for_status()
            # Attach diagnostics to globals for later inspection (non-invasive)
            globals().setdefault('__last_sunbird_attempts', []).append({'url': target, 'status': resp.status_code})
            return extract_text_from_response_body(resp.json())
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            globals().setdefault('__last_sunbird_attempts', []).append({'url': target, 'error': str(exc)})
            continue

    # If we reach here, all attempts failed
    raise RuntimeError(f'Sunbird API failed. Tried endpoints: {tried}. Last error: {last_exc}')


def call_cerebras_api(prompt: str, language_code: str = '', temperature: float = 0.7) -> str:
    base_url = get_env_value('CEREBRAS_API_URL', 'CEREBRAS_URL')
    api_key = get_env_value('CEREBRAS_API_KEY', 'CEREBRAS_KEY')
    if not base_url or not api_key:
        raise RuntimeError('Cerebras API is not configured.')

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }

    model_name = 'gpt-oss-120b'
    chat_payload = {
        'model': model_name,
        'messages': [
            {'role': 'system', 'content': f'Respond in language: {language_code or FALLBACK_LANGUAGE_CODE}.'},
            {'role': 'user', 'content': prompt}
        ],
        'temperature': temperature,
    }

    completion_payload = {
        'model': model_name,
        'input': prompt,
        'temperature': temperature,
    }

    base = clean_base_url(base_url)
    candidate_paths = [
        ('/v1/chat/completions', chat_payload),
        ('/v1/completions', completion_payload),
    ]

    tried = []
    last_exc = None
    for path, payload in candidate_paths:
        target = base + path
        tried.append(target)
        try:
            resp = requests.post(target, json=payload, headers=headers, timeout=30)
            globals().setdefault('__last_cerebras_attempts', []).append({'url': target, 'status': resp.status_code})
            if resp.status_code >= 400 and resp.status_code < 500:
                last_exc = requests.exceptions.HTTPError(f'{resp.status_code} Client Error for {target}')
                continue
            resp.raise_for_status()
            return extract_text_from_response_body(resp.json())
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            globals().setdefault('__last_cerebras_attempts', []).append({'url': target, 'error': str(exc)})
            continue

    raise RuntimeError(f'Cerebras API failed. Tried endpoints: {tried}. Last error: {last_exc}')


def call_gemini_api(body: Dict[str, Any], model: str = 'gemini-2.5-flash', max_retries: int = 2) -> str:
    api_key = get_env_value('GEMINI_API_KEY') or globals().get('__api_key', '')
    if not api_key:
        raise RuntimeError('Gemini API key is missing.')

    # Build Gemini-compatible request (filter out non-Gemini fields)
    gemini_body = {
        'contents': body.get('contents', []),
    }
    if 'systemInstruction' in body:
        gemini_body['systemInstruction'] = body['systemInstruction']
    if 'config' in body:
        gemini_body['generationConfig'] = body['config']

    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}'
    attempt = 0
    while attempt < max_retries:
        try:
            response = requests.post(url, json=gemini_body, timeout=30)
            if response.status_code == 429:
                # Rate limited - let caller know to switch to fallback immediately
                attempt += 1
                if attempt >= max_retries:
                    raise RuntimeError(f'Gemini API rate limited (429). Switching to fallback providers.')
                sleep_seconds = 1
                print(f'Gemini API rate limited, retrying in {sleep_seconds}s (attempt {attempt}/{max_retries})')
                time.sleep(sleep_seconds)
                continue
            elif response.status_code >= 500:
                # Server error - try a few times
                attempt += 1
                if attempt >= max_retries:
                    response.raise_for_status()
                sleep_seconds = 2 ** (attempt - 1)
                print(f'Gemini API server error {response.status_code}, retrying in {sleep_seconds}s (attempt {attempt}/{max_retries})')
                time.sleep(sleep_seconds)
                continue

            response.raise_for_status()
            return extract_text_from_response_body(response.json())
        except requests.exceptions.RequestException as exc:
            attempt += 1
            if attempt >= max_retries:
                raise
            sleep_seconds = 1
            print(f'Gemini API request failed, retrying in {sleep_seconds}s (attempt {attempt}/{max_retries}): {exc}')
            time.sleep(sleep_seconds)

    raise RuntimeError('Gemini API failed after retrying.')


def create_prompt_from_contents(contents: Any, system_instruction: str = '') -> str:
    prompt_parts = []
    if system_instruction:
        prompt_parts.append(system_instruction)

    if isinstance(contents, list):
        for message in contents:
            if message.get('role') == 'user':
                for part in message.get('parts', []):
                    if isinstance(part, dict):
                        prompt_parts.append(part.get('text', ''))
                    elif isinstance(part, str):
                        prompt_parts.append(part)
    elif isinstance(contents, dict):
        prompt_parts.append(json.dumps(contents))
    return '\n'.join([part for part in prompt_parts if part])


def build_local_fallback_response(prompt: str, language_code: str) -> str:
    user_prompt = prompt.strip() if prompt else ''
    if not user_prompt:
        return 'I’m still here to help. Please try again after 2 seconds.'

    return 'I’m still here to help. I couldn’t reach the AI service right now. Please try again after 2 seconds.'


def route_ai_request(body: Dict[str, Any]) -> Dict[str, Any]:
    contents = body.get('contents', [])
    language_code = normalize_language_code(body.get('language_code', '') or '')
    voice = bool(body.get('voice', False))
    config = body.get('config', {}) or {}
    temperature = float(config.get('temperature', 0.7))
    system_instruction = ''

    system_instruction_source = body.get('systemInstruction')
    if isinstance(system_instruction_source, dict):
        parts = system_instruction_source.get('parts', [])
        if parts and isinstance(parts[0], dict):
            system_instruction = parts[0].get('text', '')
    elif isinstance(system_instruction_source, str):
        system_instruction = system_instruction_source

    prompt = create_prompt_from_contents(contents, system_instruction)
    guessed_code = guess_language_from_text(prompt)
    if not language_code and guessed_code:
        language_code = guessed_code
    if not language_code:
        language_code = FALLBACK_LANGUAGE_CODE

    body['language_code'] = language_code
    body['voice'] = voice

    available_providers = []
    provider_availability = {}
    
    # Check Gemini
    if get_env_value('GEMINI_API_KEY') or globals().get('__api_key', ''):
        available_providers.append('gemini')
        provider_availability['gemini'] = 'configured'
    else:
        provider_availability['gemini'] = 'missing GEMINI_API_KEY'
    
    # Check Sunbird
    sunbird_url = get_env_value('SUNBIRD_API_URL', 'SUNBIRD_URL')
    sunbird_key = get_env_value('SUNBIRD_API_KEY', 'SUNBIRD_KEY')
    if sunbird_url and sunbird_key:
        available_providers.append('sunbird')
        provider_availability['sunbird'] = 'configured'
    else:
        missing_parts = []
        if not sunbird_url:
            missing_parts.append('SUNBIRD_API_URL')
        if not sunbird_key:
            missing_parts.append('SUNBIRD_API_KEY')
        provider_availability['sunbird'] = f"missing {', '.join(missing_parts)}"
    
    # Check Cerebras
    cerebras_url = get_env_value('CEREBRAS_API_URL', 'CEREBRAS_URL')
    cerebras_key = get_env_value('CEREBRAS_API_KEY', 'CEREBRAS_KEY')
    if cerebras_url and cerebras_key:
        available_providers.append('cerebras')
        provider_availability['cerebras'] = 'configured'
    else:
        missing_parts = []
        if not cerebras_url:
            missing_parts.append('CEREBRAS_API_URL')
        if not cerebras_key:
            missing_parts.append('CEREBRAS_API_KEY')
        provider_availability['cerebras'] = f"missing {', '.join(missing_parts)}"

    if not available_providers:
        msg = f'No configured AI providers available. Status: {provider_availability}'
        print(msg)
        return {
            'text': build_local_fallback_response(prompt, language_code),
            'provider': 'unconfigured',
            'language_code': language_code,
            'diagnostics': {
                'available_providers': available_providers,
                'provider_availability': provider_availability,
                'message': msg,
            }
        }

    preferred_order = ['gemini', 'sunbird', 'cerebras']
    if is_sunbird_language(language_code):
        preferred_order = ['sunbird', 'gemini', 'cerebras']

    provider_order = [provider for provider in preferred_order if provider in available_providers]

    provider_errors = []
    response_text = ''
    provider_used = 'fallback'

    for provider in provider_order:
        if provider == 'gemini':
            try:
                response_text = call_gemini_api(body)
                if response_text:
                    provider_used = 'gemini'
                    break
            except Exception as exc:
                provider_errors.append(f'gemini: {exc}')
                continue

        if provider == 'cerebras' and os.environ.get('CEREBRAS_API_URL'):
            try:
                response_text = call_cerebras_api(prompt, language_code, temperature)
                if response_text:
                    provider_used = 'cerebras'
                    break
            except Exception as exc:
                provider_errors.append(f'cerebras: {exc}')
                continue

        if provider == 'sunbird' and os.environ.get('SUNBIRD_API_URL'):
            try:
                response_text = call_sunbird_api(prompt, system_instruction, language_code, voice, temperature)
                if response_text:
                    provider_used = 'sunbird'
                    break
            except Exception as exc:
                provider_errors.append(f'sunbird: {exc}')
                continue

    if not response_text:
        error_msg = f'AI provider failover completed with no successful response. Providers tried: {provider_order}. Errors: {provider_errors}'
        print(error_msg)
        response_text = build_local_fallback_response(prompt, language_code)

    return {
        'text': response_text,
        'provider': provider_used,
        'language_code': language_code,
        'diagnostics': {
            'providers_tried': provider_order,
            'provider_errors': provider_errors,
            'provider_availability': provider_availability,
            'sunbird_attempts': globals().get('__last_sunbird_attempts', []),
            'cerebras_attempts': globals().get('__last_cerebras_attempts', []),
        }
    }


def route_tts_request(text: str, language_code: str) -> Dict[str, Any]:
    language_code = normalize_language_code(language_code) or FALLBACK_LANGUAGE_CODE
    sunbird_tts_url = os.environ.get('SUNBIRD_TTS_URL', '').strip()
    sunbird_api_key = os.environ.get('SUNBIRD_API_KEY', '').strip()
    botlhale_url = os.environ.get('BOTLHALE_TTS_URL', 'https://api.botlhale.xyz/tts').strip()
    botlhale_token = os.environ.get('BOTLHALE_API_TOKEN', '').strip()

    tts_attempts = []

    if sunbird_tts_url and sunbird_api_key:
        try:
            payload = {
                'text': text,
                'language_code': language_code,
                'voice': True,
            }
            headers = {
                'Authorization': f'Bearer {sunbird_api_key}',
                'Content-Type': 'application/json',
            }
            response = requests.post(sunbird_tts_url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            tts_attempts.append(f'sunbird: {exc}')

    if not botlhale_token:
        raise RuntimeError('No TTS provider is configured.')

    try:
        response = requests.post(
            botlhale_url,
            headers={
                'Authorization': f'Bearer {botlhale_token}',
            },
            json={
                'text': text,
                'language_code': language_code,
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        tts_attempts.append(f'botlhale: {exc}')
        raise RuntimeError(
            'TTS service is temporarily unavailable. Please verify your configured provider settings. '
            f'Attempts: {" | ".join(tts_attempts)}'
        )
