import os
import re

# RegEx to match most common emotes/emojis
# Excluding \u2605 (★) and \u25b2 (▲), \u25bc (▼) which are already out of these ranges or explicitly skipped
regex = re.compile(
    r'['
    r'\U0001f300-\U0001f5ff'  # Misc Symbols & Pictographs
    r'\U0001f600-\U0001f64f'  # Emoticons
    r'\U0001f680-\U0001f6ff'  # Transport & Map Symbols
    r'\u2600-\u2604\u2606-\u26ff'  # Misc Symbols (skip 2605 ★)
    r'\u2700-\u27bf'          # Dingbats (✅, ❌, etc)
    r'\U0001f900-\U0001f9ff'  # Supplemental
    r'\U0001fa70-\U0001faff'  # Extended-A
    r'\U0001f100-\U0001f1ff'  # Enclosed Alphanumeric Support (Flags)
    r']'
)

paths = [
    r"e:\BELAJAR\BELAJAR ML\FINANCE\Market OS\frontend\src",
    r"e:\BELAJAR\BELAJAR ML\FINANCE\Market OS\backend"
]

def clean_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Remove emojis
        new_content = regex.sub('', content)
        # Remove Variation Selector-16 which makes chars render as emojis
        new_content = new_content.replace('\ufe0f', '')
        
        if new_content != content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Cleaned: {filepath}")
    except Exception as e:
        print(f"Failed to clean {filepath}: {e}")

for path in paths:
    for root, dirs, files in os.walk(path):
        if 'node_modules' in root or '.venv' in root or '__pycache__' in root:
            continue
        for file in files:
            if file.endswith(('.js', '.jsx', '.py', '.ts', '.tsx')):
                clean_file(os.path.join(root, file))

print("Emote removal complete.")
