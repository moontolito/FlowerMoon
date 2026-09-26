"""Populate the packaged Excel template, retaining its formatting and formulas.

No external dependency required on the end user's machine. Both typed values and
cached results are written; Excel is asked to recalculate when inputs change.
"""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import xml.etree.ElementTree as ET
from domain import calculate,cash
NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
ET.register_namespace('',NS)
def tag(n):return '{'+NS+'}'+n

def put(root,ref,value,keep_formula=False):
    data=root.find(tag('sheetData'));rownum=int(''.join(x for x in ref if x.isdigit()))
    row=next((r for r in data if int(r.attrib['r'])==rownum),None)
    if row is None:
        row=ET.Element(tag('row'),r=str(rownum));data.append(row);data[:]=sorted(data,key=lambda r:int(r.attrib['r']))
    cell=next((c for c in row if c.attrib.get('r')==ref),None)
    if cell is None:cell=ET.SubElement(row,tag('c'),r=ref)
    for child in list(cell):
        if not(keep_formula and child.tag==tag('f')):cell.remove(child)
    cell.attrib.pop('t',None)
    if isinstance(value,(int,float)):
        ET.SubElement(cell,tag('v')).text=str(value)
    elif keep_formula:
        cell.set('t','str');ET.SubElement(cell,tag('v')).text=str(value)
    else:
        cell.set('t','inlineStr');inline=ET.SubElement(cell,tag('is'));ET.SubElement(inline,tag('t')).text=str(value)
    def index(c):
        result=0
        for ch in ''.join(x for x in c.attrib['r'] if x.isalpha()):result=result*26+ord(ch)-64
        return result
    row[:]=sorted(row,key=index)

def export_workbook(path,rows,rates):
    if not rows:raise ValueError('Nu există distanțe pentru export.')
    if len(rows)>100:raise ValueError('Maximum 100 livrări în această versiune.')
    template=Path(__file__).resolve().parent/'assets'/'calculation_template.xlsx'
    with ZipFile(template) as z:parts={n:z.read(n) for n in z.namelist()}
    calc=ET.fromstring(parts['xl/worksheets/sheet1.xml']);source=ET.fromstring(parts['xl/worksheets/sheet2.xml'])
    for n,k in enumerate(('loaded','empty','fixed','markup','vat'),3):put(calc,f'C{n}',rates[k]/100 if k in ('markup','vat') else rates[k])
    total=0
    for i,row in enumerate(rows):
        s=i+5;r=i+13;d=row['loaded'];c=calculate(row,rates);total+=c['total']
        notes=f"{row.get('notes','')} Origine {row['origin']['lat']}, {row['origin']['lon']}; destinație {row['destination']['lat']}, {row['destination']['lon']}. Server: {row['server']}"
        values=[i+1,row['product']['name'],row['vehicle']['name'],row['origin']['name'],row['destination']['name'],row['distance_km'],row['hours'],d['length'],d['width'],d['height'],d['weight'],d['axle_count'],d['axle_load'],row['calculated_at'],'Exemplu neconfirmat' if row['vehicle']['example'] else 'Date utilizator',notes,row['product']['quantity']]
        for col,v in zip('ABCDEFGHIJKLMNOPQ',values):put(source,f'{col}{s}',v)
        for col,v in [('A',i+1),('B',row['destination']['name']),('C',row['distance_km']),('E',row['quantity']),('H',c['billable_km']),('I',c['cost']),('J',c['net']),('K',c['vat']),('L',c['total'])]:put(calc,f'{col}{r}',v if rates['loaded']>0 or col in 'ABCEH' else '',True)
        for col,v in [('D',row['quantity']),('F',row['return_km']),('G',row['position_km'])]:put(calc,f'{col}{r}',v)
    put(calc,'C9',cash(total) if rates['loaded']>0 else 'Tarif lipsă',True)
    parts['xl/worksheets/sheet1.xml']=ET.tostring(calc,encoding='utf-8',xml_declaration=True);parts['xl/worksheets/sheet2.xml']=ET.tostring(source,encoding='utf-8',xml_declaration=True)
    workbook=ET.fromstring(parts['xl/workbook.xml']);cp=workbook.find(tag('calcPr'))
    if cp is None:cp=ET.SubElement(workbook,tag('calcPr'))
    cp.set('fullCalcOnLoad','1');cp.set('forceFullCalc','1');cp.set('calcMode','auto');parts['xl/workbook.xml']=ET.tostring(workbook,encoding='utf-8',xml_declaration=True)
    # Drop obsolete calculation chain if exported by a future template generator.
    if 'xl/calcChain.xml' in parts:raise ValueError('Șablon incompatibil: lanț de calcul preexistent.')
    target=Path(path);temp=target.with_suffix(target.suffix+'.tmp')
    with ZipFile(temp,'w',ZIP_DEFLATED) as z:
        for name,data in parts.items():z.writestr(name,data)
    temp.replace(target)
