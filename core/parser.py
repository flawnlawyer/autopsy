import os
import shutil
import tempfile

SUPPORTED_EXTENSIONS = {
    '.py': 'Python', '.js': 'JavaScript', '.ts': 'TypeScript',
    '.jsx': 'JavaScript', '.tsx': 'TypeScript', '.java': 'Java',
    '.c': 'C', '.cpp': 'C++', '.h': 'C', '.hpp': 'C++',
    '.go': 'Go', '.rs': 'Rust', '.rb': 'Ruby', '.php': 'PHP',
    '.cs': 'C#', '.swift': 'Swift', '.kt': 'Kotlin', '.r': 'R',
    '.sh': 'Shell', '.bash': 'Shell', '.html': 'HTML', '.css': 'CSS',
    '.scss': 'CSS', '.sql': 'SQL', '.lua': 'Lua', '.dart': 'Dart',
    '.ex': 'Elixir', '.zig': 'Zig', '.vue': 'Vue', '.svelte': 'Svelte',
}

SKIP_DIRS = {
    '.git', 'node_modules', '__pycache__', 'venv', '.venv',
    'dist', 'build', '.next', 'vendor', 'target', '.idea',
    'out', '.cache', 'coverage', '.pytest_cache',
}

# Priority files to analyse first in a repo
PRIORITY_FILES = {
    'app.py', 'main.py', 'index.js', 'index.ts', 'main.go',
    'main.rs', 'server.py', 'server.js', 'index.php', 'App.java',
    'main.c', 'main.cpp', 'lib.rs',
}

MAX_CODE_LENGTH = 7500   # total characters sent to Ollama
MAX_PER_FILE = 2000      # max chars per file in a repo


def parse_input(input_type, content):
    if input_type == 'url':
        return _parse_url(content)
    elif input_type == 'paste':
        return _parse_paste(content)
    elif input_type == 'file':
        return _parse_file(content)
    raise ValueError(f'Unknown input type: {input_type}')


# ── GitHub URL ──────────────────────────────────────────────────────────────

def _parse_url(url):
    url = url.strip()
    try:
        import git
    except ImportError:
        raise RuntimeError(
            'GitPython is not installed. Run: pip install gitpython'
        )

    tmpdir = tempfile.mkdtemp()
    try:
        git.Repo.clone_from(url, tmpdir, depth=1)
        files = _collect_files(tmpdir)
        code = _build_code_string(files)
        language = _detect_primary_language(files)
        repo_name = url.rstrip('/').split('/')[-1].replace('.git', '')
        return {
            'source': 'github',
            'name': repo_name,
            'url': url,
            'file_count': len(files),
            'language': language,
            'code': code,
        }
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── Paste ────────────────────────────────────────────────────────────────────

def _parse_paste(code):
    language = _detect_language_heuristic(code)
    lines = code.split('\n')
    return {
        'source': 'paste',
        'name': 'pasted code',
        'line_count': len(lines),
        'language': language,
        'code': code[:MAX_CODE_LENGTH],
    }


# ── File upload ──────────────────────────────────────────────────────────────

def _parse_file(file_obj):
    filename = file_obj.filename or 'unknown'
    ext = os.path.splitext(filename)[1].lower()
    language = SUPPORTED_EXTENSIONS.get(ext, 'Unknown')
    content = file_obj.read().decode('utf-8', errors='ignore')
    return {
        'source': 'file',
        'name': filename,
        'language': language,
        'code': content[:MAX_CODE_LENGTH],
    }


# ── Helpers ──────────────────────────────────────────────────────────────────

def _collect_files(root_dir):
    files = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Skip non-code dirs
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS and not d.startswith('.')
        ]
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue
            fpath = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(fpath, root_dir)
            try:
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().strip()
                if content:
                    files.append({
                        'path': rel_path,
                        'name': fname,
                        'ext': ext,
                        'lang': SUPPORTED_EXTENSIONS[ext],
                        'content': content,
                    })
            except Exception:
                pass

    # Sort: priority files first, then alphabetically
    files.sort(key=lambda f: (
        0 if f['name'] in PRIORITY_FILES else 1,
        f['path']
    ))
    return files


def _build_code_string(files):
    chunks = []
    total = 0
    for f in files:
        header = f'\n=== {f["path"]} ===\n'
        snippet = f['content'][:MAX_PER_FILE]
        chunk = header + snippet
        if total + len(chunk) > MAX_CODE_LENGTH:
            break
        chunks.append(chunk)
        total += len(chunk)
    return '\n'.join(chunks)


def _detect_primary_language(files):
    counts = {}
    for f in files:
        lang = f['lang']
        counts[lang] = counts.get(lang, 0) + 1
    return max(counts, key=counts.get) if counts else 'Unknown'


def _detect_language_heuristic(code):
    c = code[:500]
    if 'def ' in c and ('import ' in c or 'from ' in c):
        return 'Python'
    if ('function ' in c or 'const ' in c or 'let ' in c) and ('=>' in c or 'require' in c or 'import ' in c):
        return 'JavaScript'
    if 'public class ' in c or 'import java.' in c:
        return 'Java'
    if '#include' in c:
        return 'C/C++'
    if 'fn ' in c and ('let mut' in c or 'use std' in c):
        return 'Rust'
    if 'package main' in c or 'func ' in c:
        return 'Go'
    if '<?php' in c:
        return 'PHP'
    if 'using System' in c or 'namespace ' in c:
        return 'C#'
    if 'SELECT ' in c.upper() or 'INSERT ' in c.upper():
        return 'SQL'
    if '<html' in c.lower() or '<!DOCTYPE' in c:
        return 'HTML'
    return 'Unknown'
