"""Write the bundled XLSX template using Python standard library only."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape
import math
import re
import xml.etree.ElementTree as ET
import zipfile

NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
Q='{'+NS+'}'
ET.register_namespace('x',NS)
ET.register_namespace('r','http://schemas.openxmlformats.org/officeDocument/2006/relationships')


def text_value(value):
    return ''.join(c for c in str(value) if ord(c)>=32 or c in '\t\n\r')


def excel_time(value):
    if isinstance(value,(int,float)) and math.isfinite(value):return value
    if isinstance(value,str):
        try:
            date=datetime.fromisoformat(value.replace('Z','+00:00'))
            if date.tzinfo:date=date.astimezone(timezone(timedelta(hours=8))).replace(tzinfo=None)
            return (date-datetime(1899,12,30)).total_seconds()/86400
        except ValueError:pass
    return None


def export(rows, output, author):
    template=Path(__file__).resolve().parents[1]/'assets/templates/application-ledger.xlsx'
    with zipfile.ZipFile(template) as archive:parts={name:archive.read(name) for name in archive.namelist()}
    sheet=ET.fromstring(parts['xl/worksheets/sheet1.xml']);grid=sheet.find(Q+'sheetData')
    formats={int(r.get('r')):deepcopy(r) for r in grid if int(r.get('r')) in (5,6)}
    for row in list(grid):
        if int(row.get('r'))>=5:grid.remove(row)
    for number,record in enumerate(rows or [{}],5):
        row=deepcopy(formats[5 if number%2 else 6]);row.set('r',str(number))
        progress=record.get('follow_up')
        if isinstance(progress,(int,float)):progress=(datetime(1899,12,30)+timedelta(days=progress)).strftime('%Y-%m-%d')
        elif isinstance(progress,dict):progress='原有公式：'+progress.get('formula','')
        values=[record.get('company'),record.get('position'),record.get('location'),record.get('time'),record.get('agent'),record.get('recipients'),record.get('progress'),progress,record.get('notes'),record.get('id')]
        existing={re.match('[A-Z]+',c.get('r')).group():c for c in row}
        for column,value in enumerate(values,1):
            letter=chr(64+column);cell=existing.get(letter)
            if cell is None:cell=ET.SubElement(row,Q+'c')
            cell.set('r',letter+str(number));cell.attrib.pop('t',None)
            for child in list(cell):cell.remove(child)
            if value is None or value=='':continue
            numeric=excel_time(value) if column==4 else None
            if numeric is not None:ET.SubElement(cell,Q+'v').text=str(numeric)
            else:
                cell.set('t','inlineStr');text=ET.SubElement(ET.SubElement(cell,Q+'is'),Q+'t')
                text.set('{http://www.w3.org/XML/1998/namespace}space','preserve');text.text=text_value(value)
        lines=1
        for column,width in {1:23,2:27,6:36,8:28,9:43}.items():
            count=sum(max(1,math.ceil(sum(2 if ord(c)>255 else 1 for c in line)/width)) for line in str(values[column-1] or '').split('\n'))
            lines=max(lines,count)
        row.set('ht',str(max(22,lines*12+4)));row.set('customHeight','1');grid.append(row)
    end=max(5,len(rows)+4)
    dimension=sheet.find(Q+'dimension')
    if dimension is not None:dimension.set('ref',f'A1:J{end}')
    for validation in sheet.findall(Q+'dataValidations/'+Q+'dataValidation'):
        if validation.get('sqref','').startswith('G5:'):validation.set('sqref',f'G5:G{max(200,end)}')
    for conditional in sheet.findall(Q+'conditionalFormatting'):
        if conditional.get('sqref','').startswith('G5:'):conditional.set('sqref',f'G5:G{max(200,end)}')
    parts['xl/worksheets/sheet1.xml']=ET.tostring(sheet,encoding='utf-8',xml_declaration=True)
    table=ET.fromstring(parts['xl/tables/table1.xml']);table.set('ref',f'A4:J{end}');table.find(Q+'autoFilter').set('ref',f'A4:J{end}')
    parts['xl/tables/table1.xml']=ET.tostring(table,encoding='utf-8',xml_declaration=True)
    parts['docProps/core.xml']=('<?xml version="1.0" encoding="utf-8"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:creator>'+escape(author)+'</dc:creator><cp:lastModifiedBy>'+escape(author)+'</cp:lastModifiedBy></cp:coreProperties>').encode('utf-8')
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,value in parts.items():archive.writestr(name,value)
