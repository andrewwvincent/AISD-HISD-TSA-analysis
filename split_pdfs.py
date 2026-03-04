import PyPDF2, re, json, os

with open('schools_data.json') as f:
    schools = json.load(f)

def slug(name):
    return re.sub(r'-+', '-', re.sub(r'[^a-z0-9]+', '-', name.lower())).strip('-')

# Explicit mapping for ambiguous names
EXPLICIT_MAP = {
    "Franklin Elementary (former site)": "franklin-elementary-former-site",
    "Franklin Elementary School": "franklin-elementary-school",
    "Middle College High School At Hcc Gulfton": "middle-college-high-school-at-hcc-gulfton",
    "Gulfton Middle College (Middle College HS at HCC": "gulfton-middle-college-middle-college-hs-at-hcc-gulfton",
}

STOP_WORDS = {'school', 'elementary', 'middle', 'high', 'academy', 'at', 'the',
              'of', 'note', 'not', 'this', 'address', 'current', 'former', 'site'}

def distinctive_words(name):
    words = set(re.sub(r'[^a-z0-9\s]', '', name.lower()).split())
    return words - STOP_WORDS

def match_school(pdf_name):
    # Check explicit map first
    for key, val in EXPLICIT_MAP.items():
        if key.lower() in pdf_name.lower() or pdf_name.lower() in key.lower():
            return val

    pdf_words = distinctive_words(pdf_name)
    best_match = None
    best_score = 0
    for s in schools:
        s_words = distinctive_words(s['name'])
        overlap = len(pdf_words & s_words)
        if overlap > best_score:
            best_score = overlap
            best_match = s
    if best_match and best_score >= 1:
        return slug(best_match['name'])
    return None

pdfs = [
    'TSA_Report_Tier1_Excellent.pdf',
    'TSA_Report_Tier2_Good.pdf',
    'TSA_Report_Tier3_Possible.pdf',
    'TSA_Report_Tier4_NotViable.pdf',
]

os.makedirs('pdfs', exist_ok=True)
generated = {}

for pdf_file in pdfs:
    print(f'\n=== {pdf_file} ===')
    with open(pdf_file, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        num_pages = len(reader.pages)

        sections = []
        for i in range(num_pages):
            text = reader.pages[i].extract_text()
            lines = text.split('\n')
            for j, line in enumerate(lines):
                line = line.strip()
                if re.match(r'^(Tier [1-4] - |Not Viable)', line) and j + 1 < len(lines):
                    next_line = lines[j + 1].strip()
                    if any(w in next_line for w in ['School', 'Elementary', 'Middle', 'Academy',
                                                     'High', 'College', 'Americas', 'Montessori']):
                        sections.append((i, next_line))
                        break

        for idx, (start_page, school_name) in enumerate(sections):
            end_page = sections[idx + 1][0] if idx + 1 < len(sections) else num_pages

            matched_slug = match_school(school_name)
            if not matched_slug:
                print(f'  WARNING: No match for "{school_name}"')
                continue

            writer = PyPDF2.PdfWriter()
            for p in range(start_page, end_page):
                writer.add_page(reader.pages[p])

            out_file = f'pdfs/{matched_slug}.pdf'
            with open(out_file, 'wb') as out:
                writer.write(out)

            generated[matched_slug] = end_page - start_page
            print(f'  {matched_slug}.pdf ({end_page - start_page} pages) <- "{school_name}"')

print(f'\nGenerated {len(generated)} PDFs')
all_slugs = set(slug(s['name']) for s in schools)
missing = all_slugs - set(generated.keys())
if missing:
    print(f'Missing ({len(missing)}): {sorted(missing)}')
    print('(These schools have no dedicated PDF sections)')
