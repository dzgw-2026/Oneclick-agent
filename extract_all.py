import zipfile
import xml.etree.ElementTree as ET

z = zipfile.ZipFile(r'c:\Users\dzgw\Desktop\Oneclick agent\One click analysis.docx')

# === RELATIONSHIPS ===
print("=== RELATIONSHIPS (document.xml.rels) ===")
tree = ET.parse(z.open('word/_rels/document.xml.rels'))
for rel in tree.getroot():
    rid = rel.get('Id', '')
    rtype = rel.get('Type', '').split("/")[-1]
    target = rel.get('Target', '')
    print(f"  Id={rid}  Type={rtype}  Target={target}")

# === CORE METADATA ===
print("\n=== DOCUMENT METADATA (core.xml) ===")
tree = ET.parse(z.open('docProps/core.xml'))
for elem in tree.getroot():
    tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
    if elem.text:
        print(f"  {tag}: {elem.text}")

# === APP METADATA ===
print("\n=== APP METADATA ===")
tree = ET.parse(z.open('docProps/app.xml'))
for elem in tree.getroot():
    tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
    if elem.text:
        print(f"  {tag}: {elem.text}")

# === CUSTOM METADATA ===
print("\n=== CUSTOM METADATA ===")
tree = ET.parse(z.open('docProps/custom.xml'))
for elem in tree.getroot():
    name = elem.get('name', '')
    val = ''
    for child in elem:
        if child.text:
            val = child.text
    print(f"  {name}: {val}")

# === LABEL INFO ===
print("\n=== LABEL INFO ===")
tree = ET.parse(z.open('docMetadata/LabelInfo.xml'))
root = tree.getroot()
for elem in root.iter():
    attrs = ' '.join(f'{k}={v}' for k, v in elem.attrib.items())
    tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
    print(f"  {tag}: {attrs}")

# === FOOTERS ===
for footer in ['word/footer1.xml', 'word/footer2.xml', 'word/footer3.xml']:
    print(f"\n=== {footer} ===")
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    tree = ET.parse(z.open(footer))
    paragraphs = tree.findall('.//w:p', ns)
    for p in paragraphs:
        text = ''.join(node.text for node in p.findall('.//w:t', ns) if node.text)
        if text.strip():
            print(f"  {text}")

# === FULL STRUCTURED TEXT WITH IMAGE POSITIONS ===
print("\n=== FULL STRUCTURED DOCUMENT (text + image positions) ===")
ns = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'pic': 'http://schemas.openxmlformats.org/drawingml/2006/picture',
}
tree = ET.parse(z.open('word/document.xml'))
root = tree.getroot()
paragraphs = root.findall('.//w:p', ns)

for i, p in enumerate(paragraphs):
    # Get paragraph style
    pPr = p.find('w:pPr', ns)
    style = ''
    if pPr is not None:
        pStyle = pPr.find('w:pStyle', ns)
        if pStyle is not None:
            style = f" [Style: {pStyle.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', '')}]"
    
    # Get text
    texts = []
    for run in p.findall('.//w:r', ns):
        for t in run.findall('w:t', ns):
            if t.text:
                texts.append(t.text)
    
    # Check for images
    images = []
    for drawing in p.findall('.//w:drawing', ns):
        # Get image relationship ID
        for blip in drawing.findall('.//' + '{http://schemas.openxmlformats.org/drawingml/2006/main}blip'):
            embed = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed', '')
            images.append(embed)
        # Get alt text / description
        for docPr in drawing.findall('.//' + '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}docPr'):
            name = docPr.get('name', '')
            descr = docPr.get('descr', '')
            if name or descr:
                images.append(f"(name={name}, descr={descr})")
        for docPr in drawing.findall('.//' + '{http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing}docPr'):
            name = docPr.get('name', '')
            descr = docPr.get('descr', '')
            if name or descr:
                images.append(f"(name={name}, descr={descr})")
    
    # Check for hyperlinks
    hyperlinks = []
    for hl in p.findall('w:hyperlink', ns):
        rid = hl.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id', '')
        hl_text = ''.join(t.text for t in hl.findall('.//w:t', ns) if t.text)
        hyperlinks.append(f"[link: rid={rid}, text={hl_text}]")
    
    text = ''.join(texts)
    extra = ''
    if images:
        extra += f" [IMAGES: {', '.join(images)}]"
    if hyperlinks:
        extra += f" [HYPERLINKS: {', '.join(hyperlinks)}]"
    
    if text.strip() or extra:
        print(f"P{i}{style}: {text}{extra}")
    elif style:
        print(f"P{i}{style}: (empty)")

# === FOOTNOTES ===
print("\n=== FOOTNOTES ===")
ns_fn = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
tree = ET.parse(z.open('word/footnotes.xml'))
for fn in tree.findall('.//w:footnote', ns_fn):
    fn_id = fn.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}id', '')
    text = ''.join(t.text for t in fn.findall('.//w:t', ns_fn) if t.text)
    if text.strip():
        print(f"  Footnote {fn_id}: {text}")

# === ENDNOTES ===
print("\n=== ENDNOTES ===")
tree = ET.parse(z.open('word/endnotes.xml'))
for en in tree.findall('.//w:endnote', ns_fn):
    en_id = en.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}id', '')
    text = ''.join(t.text for t in en.findall('.//w:t', ns_fn) if t.text)
    if text.strip():
        print(f"  Endnote {en_id}: {text}")

z.close()
