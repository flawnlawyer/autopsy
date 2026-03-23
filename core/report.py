from datetime import datetime, timezone

SEVERITY_WEIGHTS = {
    'critical': 30,
    'high': 15,
    'medium': 6,
    'low': 2,
}

RISK_LEVELS = [
    (0,  15,  'Healthy',   '#3dbc7a'),
    (16, 35,  'Unstable',  '#d4a842'),
    (36, 60,  'Critical',  '#f06030'),
    (61, 85,  'Fatal',     '#e8334a'),
    (86, 100, 'D.O.A.',    '#c0192a'),
]


def build_report(content_data, analysis):
    issues = analysis.get('issues', [])
    score = _calculate_score(issues)
    label, color = _get_risk_level(score)
    breakdown = _breakdown(issues)

    return {
        'meta': {
            'source':      content_data.get('source', 'unknown'),
            'name':        content_data.get('name', 'unknown'),
            'language':    content_data.get('language', 'Unknown'),
            'file_count':  content_data.get('file_count'),
            'line_count':  content_data.get('line_count'),
            'analysed_at': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
            'total_issues': len(issues),
        },
        'risk': {
            'score':     score,
            'label':     label,
            'color':     color,
            'breakdown': breakdown,
        },
        'summary': analysis.get('summary', ''),
        'issues':  issues,
    }


def _calculate_score(issues):
    total = sum(SEVERITY_WEIGHTS.get(i.get('severity', 'low'), 2) for i in issues)
    return min(100, total)


def _get_risk_level(score):
    for low, high, label, color in RISK_LEVELS:
        if low <= score <= high:
            return label, color
    return 'D.O.A.', '#c0192a'


def _breakdown(issues):
    counts = {}
    for issue in issues:
        cat = issue.get('category', 'quality')
        counts[cat] = counts.get(cat, 0) + 1
    return counts
