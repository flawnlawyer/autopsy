import json
import re
import requests

ANALYSIS_PROMPT = """\
You are a forensic code analyst. Your job is to find ALL real problems in the code below: security vulnerabilities, logic errors, bugs, performance issues, and dangerous patterns.

Return ONLY a valid JSON object. No markdown. No explanation. No text before or after the JSON.

Required JSON format:
{{
  "summary": "One honest sentence describing the code health and main issues.",
  "issues": [
    {{
      "id": 1,
      "severity": "critical",
      "category": "security",
      "title": "Brief 4-6 word problem name",
      "explanation": "Plain English: what is wrong and why it matters. Write this for a beginner who barely understands code. Be specific about what could go wrong.",
      "snippet": "The exact problematic line(s) of code",
      "fix": "Specific and actionable fix with corrected code example"
    }}
  ]
}}

Severity rules:
- critical: security breach, data exposure, authentication bypass
- high: crashes, data loss, infinite loops, race conditions
- medium: incorrect behavior, wrong output, bad error handling
- low: poor practice, code smell, maintainability issues

Categories: security, logic, performance, quality

If the code has no real problems, return an empty issues array and a positive summary.
Do not invent problems that aren't there.

Language: {language}

Code to analyse:
{code}"""


class OllamaClient:
    def __init__(self, model='llama3', base_url='http://localhost:11434'):
        self.model = model
        self.base_url = base_url.rstrip('/')

    def analyse(self, code, language='Unknown'):
        prompt = ANALYSIS_PROMPT.format(language=language, code=code)
        payload = {
            'model': self.model,
            'prompt': prompt,
            'stream': False,
            'options': {
                'temperature': 0.1,
                'top_p': 0.9,
                'num_predict': 2048,
            },
        }

        try:
            resp = requests.post(
                f'{self.base_url}/api/generate',
                json=payload,
                timeout=180,
            )
            resp.raise_for_status()
            raw_text = resp.json().get('response', '')
        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                'Cannot connect to Ollama. Make sure it is running: ollama serve'
            )
        except requests.exceptions.Timeout:
            raise RuntimeError(
                'Ollama timed out. Try a smaller/faster model.'
            )

        return self._parse_response(raw_text)

    def _parse_response(self, text):
        # 1. Direct parse
        try:
            data = json.loads(text.strip())
            return self._validate(data)
        except Exception:
            pass

        # 2. Extract from ```json ... ``` blocks
        match = re.search(r'```(?:json)?\s*([\s\S]+?)\s*```', text)
        if match:
            try:
                data = json.loads(match.group(1))
                return self._validate(data)
            except Exception:
                pass

        # 3. Find raw JSON object anywhere in response
        match = re.search(r'\{[\s\S]+\}', text)
        if match:
            try:
                data = json.loads(match.group(0))
                return self._validate(data)
            except Exception:
                pass

        # 4. Fallback: model didn't return structured JSON
        return {
            'summary': 'The model returned an unstructured response. Try a larger model like llama3 or mistral.',
            'issues': [
                {
                    'id': 1,
                    'severity': 'low',
                    'category': 'quality',
                    'title': 'Analysis could not be structured',
                    'explanation': (
                        'The AI model did not return valid JSON. '
                        'This usually happens with smaller models. '
                        'Switch to llama3, mistral, or codellama for best results.'
                    ),
                    'snippet': '',
                    'fix': 'Run: ollama pull llama3 — then select llama3 from the model dropdown.',
                }
            ],
        }

    def _validate(self, data):
        if not isinstance(data, dict):
            data = {}

        valid_severities = {'critical', 'high', 'medium', 'low'}
        valid_categories = {'security', 'logic', 'performance', 'quality'}

        issues = []
        for i, raw in enumerate(data.get('issues', []) or []):
            if not isinstance(raw, dict):
                continue
            severity = raw.get('severity', 'medium')
            if severity not in valid_severities:
                severity = 'medium'
            category = raw.get('category', 'quality')
            if category not in valid_categories:
                category = 'quality'
            issues.append({
                'id': i + 1,
                'severity': severity,
                'category': category,
                'title': str(raw.get('title', 'Unnamed issue'))[:80],
                'explanation': str(raw.get('explanation', '')),
                'snippet': str(raw.get('snippet', '')),
                'fix': str(raw.get('fix', '')),
            })

        return {
            'summary': str(data.get('summary', 'Analysis complete.')),
            'issues': issues,
        }
