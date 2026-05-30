import json
import os
import re
from typing import Any, Dict, Optional

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
    for code, markers in LANGUAGE_MARKERS.items():
        for marker in markers:
            if marker in normalized_text:
                return code
    return None


def is_sunbird_language(language_code: Optional[str]) -> bool:
    code = normalize_language_code(language_code)
    return code in SUNBIRD_LANGUAGE_CODES


def extract_text_from_response_body(resp_json: Any) -> str:
    if resp_json is None:
        return ''
    if isinstance(resp_json, str):
        return resp_json

    if isinstance(resp_json, dict):
        for key in ('answer', 'response', 'text', 'output', 'result'):
            if key in resp_json and isinstance(resp_json[key], str):
                return resp_json[key]

        # If there is a deep nested message structure, try to find it.
        if 'candidates' in resp_json and isinstance(resp_json['candidates'], list) and resp_json['candidates']:
            candidate = resp_json['candidates'][0]
            content = candidate.get('content', {})
            if isinstance(content, dict) and 'parts' in content:
                return ' '.join([p.get('text', '') for p in content.get('parts', []) if isinstance(p, dict)])

        if 'data' in resp_json and isinstance(resp_json['data'], dict):
            return extract_text_from_response_body(resp_json['data'])

        # If the whole payload is a simple dictionary with a string contained deep in nested keys,
        # return the first string we can find.
        for value in resp_json.values():
            if isinstance(value, str):
                return value

    return ''


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
    url = os.environ.get('SUNBIRD_API_URL', '').strip()
    api_key = os.environ.get('SUNBIRD_API_KEY', '').strip()
    if not url or not api_key:
        raise RuntimeError('Sunbird API is not configured.')

    payload = get_sunbird_request_payload(prompt, system_instruction, language_code, voice, temperature)
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }

    response = requests.post(url, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    return extract_text_from_response_body(response.json())


def call_cerebras_api(prompt: str, language_code: str = '', temperature: float = 0.7) -> str:
    url = os.environ.get('CEREBRAS_API_URL', '').strip()
    api_key = os.environ.get('CEREBRAS_API_KEY', '').strip()
    if not url or not api_key:
        raise RuntimeError('Cerebras API is not configured.')

    payload = {
        'prompt': prompt,
        'language': language_code or FALLBACK_LANGUAGE_CODE,
        'temperature': temperature,
        'mode': 'education',
    }
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }

    response = requests.post(url, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    return extract_text_from_response_body(response.json())


def call_gemini_api(body: Dict[str, Any], model: str = 'gemini-2.5-flash') -> str:
    api_key = os.environ.get('GEMINI_API_KEY', '').strip() or globals().get('__api_key', '')
    if not api_key:
        raise RuntimeError('Gemini API key is missing.')

    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}'
    response = requests.post(url, json=body, timeout=30)
    response.raise_for_status()
    return extract_text_from_response_body(response.json())


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

    provider_order = ['gemini', 'cerebras', 'sunbird']
    provider_errors = []
    response_text = ''
    provider_used = 'unavailable'

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
        fallback_details = '; '.join(provider_errors[-3:]) if provider_errors else 'No AI provider is configured.'
        response_text = (
            'The AI service is temporarily unavailable. '
            'Please try again later or verify your Gemini, Cerebras, and Sunbird API settings. '
            f'({fallback_details})'
        )

    return {
        'text': response_text,
        'provider': provider_used,
        'language_code': language_code,
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
