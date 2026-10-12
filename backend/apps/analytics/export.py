"""Small OOXML exporter: every text cell is an inline string, never a formula."""
from io import BytesIO
import json
from zipfile import ZipFile, ZIP_DEFLATED
from xml.sax.saxutils import escape


def workbook(rows):
    headings = ["day", "kind", "region", "district", "ward", "category", "metric", "value"]
    values = [headings]
    for row in rows:
        for metric, value in sorted(row["metrics"].items()):
            values.append([*(row.get(name) for name in headings[:6]), metric, json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value])
    content = []
    for index, cells in enumerate(values, 1):
        content.append(f'<row r="{index}">' + "".join(f'<c r="{chr(65 + column)}{index}" t="inlineStr"><is><t xml:space="preserve">{escape(str(value) if value is not None else "")}</t></is></c>' for column, value in enumerate(cells)) + "</row>")
    stream = BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        archive.writestr("_rels/.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Market" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        archive.writestr("xl/worksheets/sheet1.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + "".join(content) + '</sheetData></worksheet>')
    return stream.getvalue()
