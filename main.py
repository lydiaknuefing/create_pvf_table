#!/usr/bin/env python3

import argparse
import csv
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

ODF_NS = {
    'office': 'urn:oasis:names:tc:opendocument:xmlns:office:1.0',
    'style': 'urn:oasis:names:tc:opendocument:xmlns:style:1.0',
    'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0',
    'table': 'urn:oasis:names:tc:opendocument:xmlns:table:1.0',
    'fo': 'urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0',
    'draw': 'urn:oasis:names:tc:opendocument:xmlns:drawing:1.0',
    'svg': 'urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0',
    'loext': 'urn:org:documentfoundation:names:experimental:office:xmlns:loext:1.0',
    'xlink': 'http://www.w3.org/1999/xlink',
    'dc': 'http://purl.org/dc/elements/1.1/',
    'meta': 'urn:oasis:names:tc:opendocument:xmlns:meta:1.0',
    'number': 'urn:oasis:names:tc:opendocument:xmlns:datastyle:1.0',
    'presentation': 'urn:oasis:names:tc:opendocument:xmlns:presentation:1.0',
    'ooo': 'http://openoffice.org/2004/office',
    'ooow': 'http://openoffice.org/2004/writer',
    'oooc': 'http://openoffice.org/2004/calc',
    'dom': 'http://www.w3.org/2001/xml-events',
    'xforms': 'http://www.w3.org/2002/xforms',
    'xsd': 'http://www.w3.org/2001/XMLSchema',
    'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
    'field': 'urn:openoffice:names:experimental:ooo-ms-interop:xmlns:field:1.0',
    'formx': 'urn:openoffice:names:experimental:ooxml-odf-interop:xmlns:form:1.0',
    'math': 'http://www.w3.org/1998/Math/MathML',
    'form': 'urn:oasis:names:tc:opendocument:xmlns:form:1.0',
    'script': 'urn:oasis:names:tc:opendocument:xmlns:script:1.0',
    'grddl': 'http://www.w3.org/2003/g/data-view#',
    'css3t': 'http://www.w3.org/TR/css3-text/',
    'xhtml': 'http://www.w3.org/1999/xhtml',
    'of': 'urn:oasis:names:tc:opendocument:xmlns:of:1.2',
    'tableooo': 'http://openoffice.org/2009/table',
    'calcext': 'urn:org:documentfoundation:names:experimental:calc:xmlns:calcext:1.0',
    'officeooo': 'http://openoffice.org/2009/office',
    'rpt': 'http://openoffice.org/2005/report',
    'dr3d': 'urn:oasis:names:tc:opendocument:xmlns:dr3d:1.0',
    'chart': 'urn:oasis:names:tc:opendocument:xmlns:chart:1.0',
    'drawooo': 'http://openoffice.org/2010/draw',
    'anim': 'urn:oasis:names:tc:opendocument:xmlns:animation:1.0',
    'smil': 'urn:oasis:names:tc:opendocument:xmlns:smil-compatible:1.0',
}


def _register_namespaces(xml_bytes):
    for prefix, uri in ODF_NS.items():
        try:
            ET.register_namespace(prefix, uri)
        except ValueError:
            pass
    for prefix, uri in re.findall(r'xmlns:(\w+)="([^"]*)"', xml_bytes.decode('utf-8', errors='replace')):
        try:
            ET.register_namespace(prefix, uri)
        except ValueError:
            pass


def _T(prefix, localname):
    return f'{{{ODF_NS[prefix]}}}{localname}'


def _serialize_xml(root):
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding='unicode').encode('utf-8')


def parse_csv(filepath):
    with open(filepath, newline='') as f:
        reader = csv.reader(f)
        headers = [h.strip() for h in next(reader)]
        values = [v.strip() for v in next(reader)]

    phase_labels = []
    fractions = []
    for i, header in enumerate(headers[1:], 1):
        label = re.sub(r'\s+Fraction\s*$', '', header.strip(), flags=re.IGNORECASE)
        phase_labels.append(label)
        fractions.append(float(values[i]))
    return phase_labels, fractions


def modify_odt_content(xml_bytes, phase_labels, fractions):
    _register_namespaces(xml_bytes)
    root = ET.fromstring(xml_bytes)

    # Add Arial font face if missing
    font_decls = root.find(_T('office', 'font-face-decls'))
    if font_decls is not None:
        has_arial = any(
            e.get(_T('style', 'name')) == 'Arial'
            for e in font_decls.findall(_T('style', 'font-face'))
        )
        if not has_arial:
            arial = ET.SubElement(font_decls, _T('style', 'font-face'))
            arial.set(_T('style', 'name'), 'Arial')
            arial.set(_T('svg', 'font-family'), 'Arial')

    auto_styles = root.find(_T('office', 'automatic-styles'))

    # Colors that are wrong in the template and must be corrected
    odt_color_fixes = {
        'Table1.A5': '#0000ff',  # Phase 3
        'Table1.A6': '#00ffff',  # Phase 4
        'Table1.A7': '#ff00ff',  # Phase 5
    }

    for style_el in auto_styles.findall(_T('style', 'style')):
        name = style_el.get(_T('style', 'name'))
        family = style_el.get(_T('style', 'family'))

        if name == 'Table1.A' and family == 'table-column':
            props = style_el.find(_T('style', 'table-column-properties'))
            if props is not None:
                props.set(_T('style', 'column-width'), '0.25in')

        if name in odt_color_fixes and family == 'table-cell':
            cell_props = style_el.find(_T('style', 'table-cell-properties'))
            if cell_props is not None:
                cell_props.set(_T('fo', 'background-color'), odt_color_fixes[name])

        if name.startswith('Table1.C') and family == 'table-cell':
            cell_props = style_el.find(_T('style', 'table-cell-properties'))
            if cell_props is not None:
                cell_props.set(_T('fo', 'padding-right'), '0.3in')

    def _add_para_style(name, align):
        s = ET.SubElement(auto_styles, _T('style', 'style'))
        s.set(_T('style', 'name'), name)
        s.set(_T('style', 'family'), 'paragraph')
        s.set(_T('style', 'parent-style-name'), 'Table_20_Contents')
        pp = ET.SubElement(s, _T('style', 'paragraph-properties'))
        pp.set(_T('fo', 'text-align'), align)
        tp = ET.SubElement(s, _T('style', 'text-properties'))
        tp.set(_T('style', 'font-name'), 'Arial')
        tp.set(_T('fo', 'font-size'), '11pt')
        tp.set(_T('style', 'font-size-asian'), '11pt')
        tp.set(_T('style', 'font-size-complex'), '11pt')

    _add_para_style('P_PVF_B', 'center')
    _add_para_style('P_PVF_C', 'end')

    def set_cell_text(cell, text, style):
        for child in list(cell):
            if child.tag == _T('text', 'p'):
                cell.remove(child)
        p = ET.SubElement(cell, _T('text', 'p'))
        p.set(_T('text', 'style-name'), style)
        p.text = text

    office_text = root.find(_T('office', 'body')).find(_T('office', 'text'))
    table_el = office_text.find(_T('table', 'table'))
    rows = table_el.findall(_T('table', 'table-row'))

    header_cells = rows[0].findall(_T('table', 'table-cell'))
    set_cell_text(header_cells[1], 'Phase', 'P_PVF_B')
    set_cell_text(header_cells[2], 'Vol [%]', 'P_PVF_C')

    for i, row in enumerate(rows[1:]):
        cells = row.findall(_T('table', 'table-cell'))
        if i < len(phase_labels):
            set_cell_text(cells[1], phase_labels[i], 'P_PVF_B')
        if i < len(fractions):
            set_cell_text(cells[2], f'{fractions[i] * 100:.4f}', 'P_PVF_C')

    for row in rows[len(phase_labels) + 1:]:
        table_el.remove(row)

    return _serialize_xml(root)


def modify_odp_content(xml_bytes, phase_labels, fractions):
    _register_namespaces(xml_bytes)
    root = ET.fromstring(xml_bytes)

    auto_styles = root.find(_T('office', 'automatic-styles'))

    odp_color_fixes = {
        'ce6': '#0000ff',  # Phase 3
        'ce7': '#00ffff',  # Phase 4
        'ce9': '#800000',  # Phase 6
    }

    for style_el in auto_styles.findall(_T('style', 'style')):
        name = style_el.get(_T('style', 'name'))
        family = style_el.get(_T('style', 'family'))

        if name == 'co1' and family == 'table-column':
            props = style_el.find(_T('style', 'table-column-properties'))
            if props is not None:
                props.set(_T('style', 'column-width'), '0.831cm')

        if name in odp_color_fixes and family == 'table-cell':
            gp = style_el.find(_T('loext', 'graphic-properties'))
            if gp is not None:
                gp.set(_T('draw', 'fill-color'), odp_color_fixes[name])

        # Update font size 10pt -> 11pt in all text-property elements
        for tp in style_el.findall('.//' + _T('style', 'text-properties')):
            for attr in (
                _T('fo', 'font-size'),
                _T('style', 'font-size-asian'),
                _T('style', 'font-size-complex'),
            ):
                if tp.get(attr) == '10pt':
                    tp.set(attr, '11pt')

    # Paragraph styles for column alignment; 0.762cm = 0.3in right margin for col C
    for name, align, margin_right in [('P_B', 'center', None), ('P_C', 'right', '0.762cm')]:
        s = ET.SubElement(auto_styles, _T('style', 'style'))
        s.set(_T('style', 'name'), name)
        s.set(_T('style', 'family'), 'paragraph')
        pp = ET.SubElement(s, _T('style', 'paragraph-properties'))
        pp.set(_T('fo', 'text-align'), align)
        if margin_right:
            pp.set(_T('fo', 'margin-right'), margin_right)

    def set_cell_text(cell, text, para_style):
        for child in list(cell):
            if child.tag == _T('text', 'p'):
                cell.remove(child)
        p = ET.SubElement(cell, _T('text', 'p'))
        p.set(_T('text', 'style-name'), para_style)
        span = ET.SubElement(p, _T('text', 'span'))
        span.set(_T('text', 'style-name'), 'T2')
        span.text = text

    office_presentation = root.find(_T('office', 'body')).find(_T('office', 'presentation'))
    draw_page = office_presentation.find(_T('draw', 'page'))

    table = None
    for frame in draw_page.findall(_T('draw', 'frame')):
        t = frame.find(_T('table', 'table'))
        if t is not None:
            table = t
            break

    if table is None:
        sys.exit('Error: could not find table in ODP content.xml')

    rows = table.findall(_T('table', 'table-row'))

    header_cells = rows[0].findall(_T('table', 'table-cell'))
    set_cell_text(header_cells[1], 'Phase', 'P_B')
    set_cell_text(header_cells[2], 'Vol [%]', 'P_C')

    for i, row in enumerate(rows[1:]):
        cells = row.findall(_T('table', 'table-cell'))
        if i < len(phase_labels):
            set_cell_text(cells[1], phase_labels[i], 'P_B')
        if i < len(fractions):
            set_cell_text(cells[2], f'{fractions[i] * 100:.4f}', 'P_C')

    for row in rows[len(phase_labels) + 1:]:
        table.remove(row)

    return _serialize_xml(root)


def fill_odf(template_path, output_path, phase_labels, fractions, modify_fn):
    with zipfile.ZipFile(template_path, 'r') as zin:
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == 'content.xml':
                    data = modify_fn(data, phase_labels, fractions)
                zout.writestr(item, data)


def main():
    parser = argparse.ArgumentParser(
        description='Populate a phase volume fraction table in a LibreOffice document.'
    )
    parser.add_argument('csv_file', help='Input CSV file with phase fractions')
    parser.add_argument(
        '--format', choices=['writer', 'impress'], required=True,
        help='Output format: writer (.odt) or impress (.odp)',
    )
    args = parser.parse_args()

    csv_path = Path(args.csv_file)
    if not csv_path.exists():
        sys.exit(f'Error: file not found: {csv_path}')

    phase_labels, fractions = parse_csv(csv_path)
    stem = csv_path.stem

    if args.format == 'writer':
        template = SCRIPT_DIR / 'phasevoltable_empty.odt'
        output = Path.cwd() / f'table_{stem}.odt'
        fill_odf(template, output, phase_labels, fractions, modify_odt_content)
    else:
        template = SCRIPT_DIR / 'phasevoltable_empty.odp'
        output = Path.cwd() / f'table_{stem}.odp'
        fill_odf(template, output, phase_labels, fractions, modify_odp_content)

    print(f'Created: {output}')


if __name__ == '__main__':
    main()
