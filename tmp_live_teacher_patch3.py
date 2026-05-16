from pathlib import Path
base = Path('c:/Users/NIIH/Desktop/learnflow_ai.earn')
settings_path = base / 'learnflow_ai' / 'settings.py'
text = settings_path.read_text(encoding='utf-8')
text = text.replace(
    "    'jazzmin', # Keep Jazzmin just above admin\n",
    "    'jazzmin', # Keep Jazzmin just above admin\n    'channels',\n    'daphne',\n"
)
if "ASGI_APPLICATION = 'learnflow_ai.asgi.application'" not in text:
    text = text.replace(
        "WSGI_APPLICATION = 'learnflow_ai.wsgi.application'\n",
        "WSGI_APPLICATION = 'learnflow_ai.wsgi.application'\nASGI_APPLICATION = 'learnflow_ai.asgi.application'\n\nCHANNEL_LAYERS = {\n    'default': {\n        'BACKEND': 'channels.layers.InMemoryChannelLayer',\n    },\n}\n\n"
    )
settings_path.write_text(text, encoding='utf-8')
print('settings patched')
