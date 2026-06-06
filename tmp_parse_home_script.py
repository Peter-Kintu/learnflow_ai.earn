from pathlib import Path
import subprocess
p = Path('aiapp/templates/aiapp/home.html')
text = p.read_text('utf-8')
start = text.find('<script')
end = text.rfind('</script>')
if start == -1 or end == -1:
    print('NO_SCRIPT')
    raise SystemExit(1)
script = text[text.find('>', start)+1:end]
Path('tmp_home_script.js').write_text(script, encoding='utf-8')
result = subprocess.run(['node', 'tmp_home_script.js'], capture_output=True, text=True)
print('returncode', result.returncode)
print('stderr:')
print(result.stderr)
print('stdout:')
print(result.stdout)
