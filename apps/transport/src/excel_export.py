"""Populate the packaged Excel template, retaining its formatting and formulas.

No external dependency required on the end user's machine. Both typed values and
cached results are written; Excel is asked to recalculate when inputs change.
"""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import xml.etree.ElementTree as ET
from domain import calculate,cash
from site_overview import rows as site_rows
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
    if not rows:raise ValueError('No distances to export.')
    if len(rows)>100:raise ValueError('Maximum 100 deliveries in this version.')
    template=Path(__file__).resolve().parents[1]/'assets'/'calculation_template.xlsx'
    with ZipFile(template) as z:parts={n:z.read(n) for n in z.namelist()}
    calc=ET.fromstring(parts['xl/worksheets/sheet1.xml']);source=ET.fromstring(parts['xl/worksheets/sheet2.xml'])
    labels={'B3':'Loaded rate (EUR/km)','E3':'Fixed costs: permits, escort, tolls, crane and other costs per trip.','B4':'Empty rate (EUR/km)','B5':'Fixed costs (EUR/trip)','E5':'Yellow = editable assumptions. One product per trip. Confirm return distance separately.','B6':'Markup on cost','B7':'VAT','A12':'No.','B12':'Destination','C12':'One-way km','D12':'Products','E12':'Trips','F12':'Return km/trip','G12':'Positioning km/trip','H12':'Billable km','I12':'Cost EUR','J12':'Net EUR','K12':'VAT EUR','L12':'Total EUR'}
    for cell,value in labels.items():put(calc,cell,value)
    put(source,'B1','Transport routes and vehicle configurations');put(source,'B2','Source: Valhalla route response and the selected vehicle profile. Proposed routes require carrier and permit verification.')
    headings=['No.','Product','Vehicle','Departure','Destination','One-way km','Driving hours','Total length m','Total width m','Total height m','Total weight t','Axles','Max t/axle','Route date','Profile type','Assumptions / coordinates','Total product quantity']
    for col,value in zip('ABCDEFGHIJKLMNOPQ',headings):put(source,col+'4',value)
    for n,k in enumerate(('loaded','empty','fixed','markup','vat'),3):put(calc,f'C{n}',rates[k]/100 if k in ('markup','vat') else rates[k])
    total=0
    for i,row in enumerate(rows):
        s=i+5;r=i+13;d=row['loaded'];c=calculate(row,rates);total+=c['total']
        notes=f"{row.get('notes','')} Origin {row['origin']['lat']}, {row['origin']['lon']}; destination {row['destination']['lat']}, {row['destination']['lon']}. Server: {row['server']}"
        values=[i+1,row['product']['name'],row['vehicle']['name'],row['origin']['name'],row['destination']['name'],row['distance_km'],row['hours'],d['length'],d['width'],d['height'],d['weight'],d['axle_count'],d['axle_load'],row['calculated_at'],'Unconfirmed example' if row['vehicle']['example'] else 'User input',notes,row['product']['quantity']]
        for col,v in zip('ABCDEFGHIJKLMNOPQ',values):put(source,f'{col}{s}',v)
        for col,v in [('A',i+1),('B',row['destination']['name']),('C',row['distance_km']),('E',row['quantity']),('H',c['billable_km']),('I',c['cost']),('J',c['net']),('K',c['vat']),('L',c['total'])]:put(calc,f'{col}{r}',v if rates['loaded']>0 or col in 'ABCEH' else '',True)
        for col,v in [('D',row['quantity']),('F',row['return_km']),('G',row['position_km'])]:put(calc,f'{col}{r}',v)
    put(calc,'C9',cash(total) if rates['loaded']>0 else 'Rate missing',True)
    for formula in calc.iter(tag('f')):
        if formula.text:formula.text=formula.text.replace('Rute!','Routes!').replace('Tarif lipsă','Rate missing')
    parts['xl/worksheets/sheet1.xml']=ET.tostring(calc,encoding='utf-8',xml_declaration=True);parts['xl/worksheets/sheet2.xml']=ET.tostring(source,encoding='utf-8',xml_declaration=True)
    workbook=ET.fromstring(parts['xl/workbook.xml']);cp=workbook.find(tag('calcPr'))
    sheets=workbook.find(tag('sheets'));sheets[0].set('name','Transport');sheets[1].set('name','Routes')
    add_site_sheet(parts,workbook,rows)
    if cp is None:cp=ET.SubElement(workbook,tag('calcPr'))
    cp.set('fullCalcOnLoad','1');cp.set('forceFullCalc','1');cp.set('calcMode','auto');parts['xl/workbook.xml']=ET.tostring(workbook,encoding='utf-8',xml_declaration=True)
    # Drop obsolete calculation chain if exported by a future template generator.
    if 'xl/calcChain.xml' in parts:raise ValueError('Incompatible template: pre-existing calculation chain.')
    target=Path(path);temp=target.with_suffix(target.suffix+'.tmp')
    with ZipFile(temp,'w',ZIP_DEFLATED) as z:
        for name,data in parts.items():z.writestr(name,data)
    temp.replace(target)

def add_site_sheet(parts,workbook,deliveries):
    sheet=ET.Element(tag('worksheet'))
    views=ET.SubElement(sheet,tag('sheetViews'));view=ET.SubElement(views,tag('sheetView'),workbookViewId='0')
    ET.SubElement(view,tag('pane'),ySplit='3',topLeftCell='A4',activePane='bottomLeft',state='frozen')
    columns=ET.SubElement(sheet,tag('cols'))
    for i,width in enumerate((12,45,27,43,25,35,32,65,95),1):ET.SubElement(columns,tag('col'),min=str(i),max=str(i),width=str(width),customWidth='1')
    ET.SubElement(sheet,tag('sheetData'))
    put(sheet,'A1','Site & Environment — delivery destination data')
    put(sheet,'A2','Climate uses historical reanalysis grids; elevation uses a DSM; seismic/snow/wind values use destination zoning polygons. Route metrics are labelled separately.')
    for col,label in zip('ABCDEFGHI',['Delivery','Delivery address','Coordinates (lat, lon)','Parameter','Value','Source','Location / reference','Source URL','Source details']):put(sheet,col+'3',label)
    line=4
    for index,delivery in enumerate(deliveries,1):
        site=delivery.get('siteConditions')
        if not site:continue
        from site_conditions import migrate
        site=migrate(site)
        for item in site_rows(site):
            if item['section']:continue
            values=[index,site.get('destinationAddress',''),site.get('destinationCoordinates',''),item['label'],item['value'],item['source'],item['reference'],item['url'],item['detail']]
            for col,value in zip('ABCDEFGHI',values):put(sheet,col+str(line),value)
            line+=1
    if line>4:ET.SubElement(sheet,tag('autoFilter'),ref='A3:I'+str(line-1))
    parts['xl/worksheets/sheet3.xml']=ET.tostring(sheet,encoding='utf-8',xml_declaration=True)
    relns='http://schemas.openxmlformats.org/package/2006/relationships'
    rels=ET.fromstring(parts['xl/_rels/workbook.xml.rels']);ident='FlowerMoonSiteEnvironment'
    ET.SubElement(rels,'{'+relns+'}Relationship',Id=ident,Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet',Target='/xl/worksheets/sheet3.xml')
    parts['xl/_rels/workbook.xml.rels']=ET.tostring(rels,encoding='utf-8',xml_declaration=True)
    ET.SubElement(workbook.find(tag('sheets')),tag('sheet'),{'name':'Site & Environment','sheetId':'3','{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id':ident})
    types=ET.fromstring(parts['[Content_Types].xml'])
    ET.SubElement(types,'{http://schemas.openxmlformats.org/package/2006/content-types}Override',PartName='/xl/worksheets/sheet3.xml',ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml')
    parts['[Content_Types].xml']=ET.tostring(types,encoding='utf-8',xml_declaration=True)
