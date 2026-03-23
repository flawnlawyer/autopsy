from flask import Flask, render_template, request, jsonify
import os
import requests
from core.parser import parse_input
from core.ollama_client import OllamaClient
from core.report import build_report

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

OLLAMA_BASE = os.environ.get('OLLAMA_HOST', 'http://localhost:11434')


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/models')
def get_models():
    try:
        resp = requests.get(f'{OLLAMA_BASE}/api/tags', timeout=5)
        models = [m['name'] for m in resp.json().get('models', [])]
        return jsonify({'models': models, 'status': 'online'})
    except Exception as e:
        return jsonify({'models': [], 'status': 'offline', 'error': str(e)})


@app.route('/api/analyse', methods=['POST'])
def analyse():
    try:
        input_type = request.form.get('type', 'paste')
        model = request.form.get('model', 'llama3')

        if input_type == 'url':
            content_data = parse_input('url', request.form.get('content', ''))
        elif input_type == 'paste':
            code = request.form.get('content', '').strip()
            if not code:
                return jsonify({'error': 'No code provided'}), 400
            content_data = parse_input('paste', code)
        elif input_type == 'file':
            uploaded = request.files.get('file')
            if not uploaded:
                return jsonify({'error': 'No file uploaded'}), 400
            content_data = parse_input('file', uploaded)
        else:
            return jsonify({'error': 'Invalid input type'}), 400

        if not content_data.get('code', '').strip():
            return jsonify({'error': 'No code found to analyse'}), 400

        client = OllamaClient(model=model, base_url=OLLAMA_BASE)
        raw_analysis = client.analyse(content_data['code'], content_data['language'])
        report = build_report(content_data, raw_analysis)

        return jsonify(report)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("🔬 Autopsy is running at http://localhost:5000")
    app.run(debug=True, port=5000)
