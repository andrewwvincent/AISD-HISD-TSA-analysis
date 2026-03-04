import json, os, re

with open('schools_data.json') as f:
    schools = json.load(f)

def slug(name):
    return re.sub(r'-+', '-', re.sub(r'[^a-z0-9]+', '-', name.lower())).strip('-')

def fmt(v):
    if v is None: return 'N/A'
    if isinstance(v, float): return f'{v:,.0f}'
    if isinstance(v, int): return f'{v:,}'
    return str(v)

def fmtCurrency(v):
    if v is None: return 'N/A'
    return f'${v:,.0f}'

def fmtPct(v):
    if v is None: return 'N/A'
    return f'{float(v)*100:.0f}%'

TIER_COLORS = {
    'Tier 1 - Excellent': '#16a34a',
    'Tier 2 - Good': '#2563eb',
    'Tier 3 - Possible': '#f59e0b',
    'Tier 4 - Uncertain': '#dc2626',
    'Not Viable': '#6b7280',
}

def make_report(s):
    color = TIER_COLORS.get(s['tier'], '#6b7280')

    es_rows = ''
    for label, key in [('Free (Tuition Factor=1)', 'es_free'), ('$10,000', 'es_10k'),
                        ('$15,000', 'es_15k'), ('$20,000', 'es_20k'), ('$25,000', 'es_25k')]:
        v = s.get(key)
        es_rows += f'<tr><td>{label}</td><td class="num">{fmt(v)}</td></tr>\n'

    prop_rows = ''
    for label, key, fn in [
        ('Building Size', 'sqft', lambda v: f'{v:,} sqft' if v else 'N/A'),
        ('Lot Size', 'acres', lambda v: f'{v} acres' if v else 'N/A'),
        ('Year Built', 'year_built', lambda v: str(v)[:4] if v else 'N/A'),
        ('Has Gym', 'has_gym', lambda v: str(v) if v else 'N/A'),
        ('Building Size Class', 'building_size', lambda v: str(v) if v else 'N/A'),
        ('Outdoor Space', 'outdoor_space', lambda v: str(v) if v else 'N/A'),
    ]:
        val = s.get(key)
        prop_rows += f'<tr><td>{label}</td><td>{fn(val)}</td></tr>\n'

    tuition_html = ''
    if s.get('capacity'):
        pb = s.get('payback_years')
        pb_str = f'{pb:.1f} years' if pb else 'N/A'
        tuition_html = f"""
    <div class="card">
      <h2>Tuition &amp; Revenue Strategy</h2>
      <table>
        <tr><td>Building Capacity</td><td class="num">{fmt(s['capacity'])} students</td></tr>
        <tr><td>Optimal Tuition</td><td>{s.get('best_tuition', 'N/A')}</td></tr>
        <tr><td>Students at Optimal Fill</td><td class="num">{fmt(s.get('students_best'))}</td></tr>
        <tr><td>Fill Rate</td><td class="num">{fmtPct(s.get('fill_rate'))}</td></tr>
        <tr><td>Annual Revenue</td><td class="num">{fmtCurrency(s.get('annual_revenue'))}</td></tr>
        <tr><td>Rehab Cost (Mid)</td><td class="num">{fmtCurrency(s.get('rehab_cost_mid'))}</td></tr>
        <tr><td>Payback Period</td><td class="num">{pb_str}</td></tr>
      </table>
    </div>"""

    sports_html = ''
    if s.get('indoor_sports') or s.get('outdoor_sports'):
        sports_html = f"""
    <div class="card">
      <h2>Sports Viability</h2>
      <div class="detail-section"><h3>Indoor Sports</h3><p>{s.get('indoor_sports', 'N/A')}</p></div>
      <div class="detail-section"><h3>Outdoor Sports</h3><p>{s.get('outdoor_sports', 'N/A')}</p></div>
      <div class="detail-section"><h3>TSA Sport-Specific Match</h3><p>{s.get('tsa_match', 'N/A')}</p></div>
    </div>"""

    notes_html = ''
    for label, key in [('Current Status', 'current_status'), ('Building Condition', 'building_condition'),
                        ('Neighborhood', 'neighborhood'), ('Known Issues', 'known_issues')]:
        val = s.get(key)
        if val:
            notes_html += f'<div class="detail-section"><h3>{label}</h3><p>{val}</p></div>\n'

    notes_card = f'<div class="card"><h2>Site Notes</h2>{notes_html}</div>' if notes_html else ''

    demand_highlight = ''
    if s.get('demand_score') is not None:
        demand_highlight = f'<div class="score-highlight"><div class="score">{s["demand_score"]}</div><div class="label">Demand Score</div></div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{s['name']} - TSA Facility Report</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f3f4f6; color: #1f2937; }}
  .header {{ background: white; padding: 24px 32px; border-bottom: 4px solid {color}; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  .header h1 {{ font-size: 24px; margin-bottom: 4px; }}
  .header .meta {{ color: #6b7280; font-size: 14px; }}
  .tier-badge {{ display: inline-block; padding: 4px 12px; border-radius: 6px; font-size: 13px; font-weight: 600; color: white; background: {color}; margin-top: 8px; }}
  .back-link {{ display: inline-block; margin-bottom: 12px; color: #2563eb; text-decoration: none; font-size: 14px; }}
  .back-link:hover {{ text-decoration: underline; }}
  .container {{ max-width: 960px; margin: 0 auto; padding: 24px; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }}
  @media (max-width: 700px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  .card {{ background: white; border-radius: 10px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 20px; }}
  .card h2 {{ font-size: 16px; margin-bottom: 12px; color: #374151; border-bottom: 1px solid #e5e7eb; padding-bottom: 8px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  td {{ padding: 6px 0; font-size: 14px; border-bottom: 1px solid #f3f4f6; }}
  td:first-child {{ color: #6b7280; }}
  td.num {{ text-align: right; font-weight: 600; font-variant-numeric: tabular-nums; }}
  .score-highlight {{ text-align: center; padding: 16px; background: #f0fdf4; border-radius: 8px; margin-bottom: 16px; }}
  .score-highlight .score {{ font-size: 36px; font-weight: 700; color: {color}; }}
  .score-highlight .label {{ font-size: 12px; color: #6b7280; margin-top: 2px; }}
  .detail-section {{ margin-bottom: 12px; }}
  .detail-section h3 {{ font-size: 13px; font-weight: 600; color: #374151; margin-bottom: 4px; }}
  .detail-section p {{ font-size: 13px; color: #4b5563; line-height: 1.5; }}
</style>
</head>
<body>
<div class="header">
  <div class="container" style="padding:0">
    <a class="back-link" href="../index.html">&larr; Back to Map</a>
    <h1>{s['name']}</h1>
    <div class="meta">{s['district']} &bull; {s.get('address') or 'Address N/A'}</div>
    <span class="tier-badge">{s['tier']}</span>
  </div>
</div>
<div class="container">
  {demand_highlight}
  <div class="grid">
    <div class="card">
      <h2>Enrollment Scores by Tuition</h2>
      <table>{es_rows}</table>
    </div>
    <div class="card">
      <h2>Wealth &amp; Demographics</h2>
      <table>
        <tr><td>Wealth Score ($100k+ AGI)</td><td class="num">{fmt(s.get('ws_100k'))}</td></tr>
        <tr><td>Raw Kids 5-17 (20-min drive)</td><td class="num">{fmt(s.get('raw_kids'))}</td></tr>
      </table>
    </div>
  </div>
  <div class="grid">
    <div class="card">
      <h2>Property Details</h2>
      <table>{prop_rows}</table>
    </div>
    {tuition_html}
  </div>
  {sports_html}
  {notes_card}
</div>
</body>
</html>"""

os.makedirs('reports', exist_ok=True)
for s in schools:
    fname = slug(s['name']) + '.html'
    with open(f'reports/{fname}', 'w', encoding='utf-8') as f:
        f.write(make_report(s))
    print(f'  {fname}')

print(f'\nGenerated {len(schools)} reports')
