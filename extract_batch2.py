"""Extract data from batch 2 PDFs, update schools_data.json, generate HTML reports."""
import PyPDF2, json, os, re, openpyxl

BASE = os.path.dirname(os.path.abspath(__file__))

# Load existing schools (original batch 1 only)
with open(os.path.join(BASE, 'schools_data.json')) as f:
    all_data = json.load(f)

# Keep only batch 1 (original 45)
existing_schools = [s for s in all_data if s.get('batch', 1) == 1]
for s in existing_schools:
    s['batch'] = 1
    if 'pdf_filename' not in s:
        s['pdf_filename'] = None

existing_names = {s['name'] for s in existing_schools}

# Batch 2 PDFs = ones with underscores (new naming convention)
batch2_pdfs = sorted([
    f for f in os.listdir(os.path.join(BASE, 'pdfs'))
    if f.endswith('.pdf') and '_' in f
])

print(f"Found {len(batch2_pdfs)} batch 2 PDFs")

# Load Excel data
excel_data = {}
try:
    wb = openpyxl.load_workbook(os.path.join(BASE, 'TX_Private_Schools_TSA_Analysis.xlsx'))
    ws = wb.active
    for row in ws.iter_rows(min_row=7, max_row=18, values_only=True):
        if row[1]:
            name = str(row[1]).strip()
            excel_data[name] = {
                'metro': row[2],
                'address': row[3],
                'tier': row[4],
                'campus_score': row[5],
                'enrollment': row[6],
                'grades': row[7],
                'sqft': row[8],
                'acres': row[9],
                'has_gym': row[10],
                'year_built': row[11],
                'capacity': row[12],
                'rehab_cost_mid': row[13],
                'zip_median_hhi': row[14],
                'distress_signal': row[15],
                'best_use': row[16],
            }
    print(f"Loaded {len(excel_data)} schools from Excel")
except Exception as e:
    print(f"Excel load error: {e}")


def extract_pdf_text(path):
    with open(path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        return '\n'.join(page.extract_text() for page in reader.pages)


def parse_tier(text):
    m = re.search(r'(Tier \d+ - \w+|Not Viable)', text)
    return m.group(1) if m else 'Tier 3 - Possible'


def parse_metro(text):
    m = re.search(r'Individual Facility Report\s*\n\s*(.+?)\s*\|', text)
    if m:
        return m.group(1).strip()
    return 'TX'


def parse_address_subheader(text):
    """Get address from the line between metro and Methodology."""
    m = re.search(r'Individual Facility Report\s*\n.*?\n(.+?)\nMethodology', text, re.DOTALL)
    if m:
        addr = m.group(1).strip()
        if 'TBD' not in addr and len(addr) > 5 and not addr.endswith(')'):
            # Clean up
            addr = addr.split(';')[0].strip()
            addr = addr.split('Parcel')[0].strip().rstrip(';')
            return addr
    return None


def parse_address_evidence(text):
    """Fallback: get address from Evidence: line."""
    m = re.search(r'Address:\s*(.+?)(?:\.|$|\n)', text)
    if m:
        addr = m.group(1).strip()
        addr = re.sub(r'\[.*?\]\(.*?\)', '', addr).strip().rstrip('.')
        addr = addr.split(';')[0].strip()
        if len(addr) > 10:
            return addr
    return None


def parse_sqft(text):
    m = re.search(r'Building Size\s*\n?\s*([\d,]+)\s*sq\s*ft', text, re.IGNORECASE)
    return int(m.group(1).replace(',', '')) if m else None


def parse_acres(text):
    m = re.search(r'Campus Acreage\s*\n?\s*([\d.]+)\s*acres', text, re.IGNORECASE)
    return float(m.group(1)) if m else None


def parse_year_built(text):
    m = re.search(r'Year Built\s*\n?\s*(\d{4})', text, re.IGNORECASE)
    return m.group(1) if m else None


def parse_gym(text):
    m = re.search(r'Gymnasium\s*\n?\s*(Yes|No|Unknown|Likely)', text, re.IGNORECASE)
    return m.group(1).capitalize() if m else None


def parse_outdoor_space(text):
    m = re.search(r'Outdoor Space\s*\n?\s*(.+)', text, re.IGNORECASE)
    if m:
        val = m.group(1).strip()
        if val.lower() not in ('unknown', 'data not available', ''):
            return val
    return None


def parse_building_size_class(text):
    m = re.search(r'Size Classification\s*\n?\s*(.+)', text, re.IGNORECASE)
    if m:
        val = m.group(1).strip()
        if val.lower() not in ('unknown', 'data not available', ''):
            return val
    return None


def parse_status(text):
    m = re.search(r'2\. Current Status.*?\n(.+?)(?:\nBuilding Condition)', text, re.DOTALL)
    if m:
        return m.group(1).strip()[:200]
    return None


def parse_building_condition(text):
    m = re.search(r'Building Condition:\s*(.+?)(?:\nKnown Issues)', text, re.DOTALL)
    if m:
        return m.group(1).strip()[:200]
    return None


def parse_neighborhood(text):
    m = re.search(r'Neighborhood:\s*(.+?)(?:\n\d\.|\n[A-Z])', text, re.DOTALL)
    if m:
        return m.group(1).strip()[:200]
    return None


def parse_known_issues(text):
    m = re.search(r'Known Issues:\s*(.+?)(?:\nListing|\nNeighborhood)', text, re.DOTALL)
    if m:
        val = m.group(1).strip()[:200]
        if val.lower() not in ('none found', 'no info', 'none', 'none noted'):
            return val
    return None


def parse_indoor_sports(text):
    m = re.search(r'Indoor Sports.*?\n(?:The following sports can be supported:)?\s*\n?((?:[A-Z][\w\s/]+\n?)+)', text)
    if m:
        sports = [s.strip() for s in m.group(1).strip().split('\n') if s.strip() and not s.strip().startswith('Outdoor')]
        return ', '.join(sports)
    return None


def parse_outdoor_sports(text):
    m = re.search(r'Outdoor Sports.*?\n(?:Based on [\d.]+ acres:)?\s*\n?((?:[A-Z][\w\s/&]+\n?)+)', text)
    if m:
        sports = [s.strip() for s in m.group(1).strip().split('\n') if s.strip() and not s.strip().startswith('TSA')]
        return ', '.join(sports)
    return None


def parse_rehab_mid(text):
    m = re.search(r'Midpoint\s*\n?\s*\$?([\d,.]+[MK]?)', text, re.IGNORECASE)
    if m:
        val = m.group(1).replace(',', '')
        if 'M' in val.upper():
            return float(val.upper().replace('M', '')) * 1_000_000
        elif 'K' in val.upper():
            return float(val.upper().replace('K', '')) * 1_000
        return float(val)
    return None


def parse_name_from_filename(pdf_file):
    return pdf_file.replace('.pdf', '').replace('_', ' ').replace(' Report', '').replace(' Closed', '').strip()


new_schools = []

for pdf_file in batch2_pdfs:
    pdf_path = os.path.join(BASE, 'pdfs', pdf_file)
    text = extract_pdf_text(pdf_path)

    name = parse_name_from_filename(pdf_file)
    if name in existing_names:
        print(f"  SKIP: {name}")
        continue

    tier = parse_tier(text)
    metro = parse_metro(text)
    address = parse_address_subheader(text) or parse_address_evidence(text)

    sqft = parse_sqft(text)
    acres = parse_acres(text)
    year_built = parse_year_built(text)
    has_gym = parse_gym(text)
    capacity = None
    rehab_mid = parse_rehab_mid(text)
    demand_score = None

    # Override with Excel data if available
    excel = None
    for ename, edata in excel_data.items():
        if ename.lower() in name.lower() or name.lower() in ename.lower():
            excel = edata
            break
        # Fuzzy match
        name_words = set(name.lower().split())
        excel_words = set(ename.lower().split())
        if len(name_words & excel_words) >= 2:
            excel = edata
            break

    if excel:
        if not address and excel.get('address'):
            address = str(excel['address'])
        if not sqft and excel.get('sqft'):
            sqft = int(excel['sqft'])
        if not acres and excel.get('acres'):
            acres = float(excel['acres'])
        if has_gym in (None, 'Unknown') and excel.get('has_gym'):
            has_gym = str(excel['has_gym'])
        if not year_built and excel.get('year_built'):
            m2 = re.search(r'(\d{4})', str(excel['year_built']))
            if m2:
                year_built = m2.group(1)
        if excel.get('tier'):
            tier = excel['tier']
        if excel.get('capacity'):
            capacity = int(excel['capacity'])
        if excel.get('rehab_cost_mid'):
            rehab_mid = float(excel['rehab_cost_mid'])
        if excel.get('campus_score'):
            demand_score = excel['campus_score']

    school = {
        'name': name,
        'district': metro or 'TX',
        'tier': tier,
        'address': address,
        'lat': None,
        'lon': None,
        'es_free': None, 'es_10k': None, 'es_15k': None, 'es_20k': None, 'es_25k': None,
        'ws_100k': None, 'raw_kids': None,
        'demand_score': demand_score,
        'sqft': sqft,
        'acres': acres,
        'year_built': year_built,
        'has_gym': has_gym,
        'building_size': parse_building_size_class(text),
        'outdoor_space': parse_outdoor_space(text),
        'current_status': parse_status(text),
        'building_condition': parse_building_condition(text),
        'neighborhood': parse_neighborhood(text),
        'known_issues': parse_known_issues(text),
        'indoor_sports': parse_indoor_sports(text),
        'outdoor_sports': parse_outdoor_sports(text),
        'tsa_match': None,
        'capacity': capacity,
        'best_tuition': None, 'students_best': None, 'fill_rate': None,
        'annual_revenue': None,
        'rehab_cost_mid': rehab_mid,
        'payback_years': None,
        'pdf_available': True,
        'pdf_filename': pdf_file,
        'batch': 2,
    }

    new_schools.append(school)
    print(f"  {name} | {tier} | {metro} | {address or 'no address'}")

print(f"\nTotal new schools: {len(new_schools)}")

# Combine
all_schools = existing_schools + new_schools

# Save
with open(os.path.join(BASE, 'schools_data.json'), 'w') as f:
    json.dump(all_schools, f, indent=2)

print(f"Saved {len(all_schools)} schools to schools_data.json")

# List those needing geocoding
needs = [s for s in new_schools if s['address'] and not s['lat']]
print(f"\n{len(needs)} need geocoding")
for s in needs:
    print(f"  {s['name']}: {s['address']}")
