"""Local GEM 2023.1 PGA raster; no API, no colour-to-value inference.

The deliberately narrow TIFF reader accepts this verified uncompressed, single
band Float64 GeoTIFF only. Unsupported layouts fail explicitly instead of being
guessed. Numeric lookup needs only the Python standard library.
"""
from pathlib import Path
from functools import lru_cache
import hashlib,json,math,struct

SOURCE='GEM Global Seismic Hazard Map 2023.1'
URL='https://zenodo.org/records/8409647'
LICENSE_URL='https://creativecommons.org/licenses/by-nc-sa/4.0/'
FILENAME='v2023_1_pga_475_rock_3min.tif'
DATA=Path(__file__).resolve().parents[1]/'assets'/'datasets'/'gem-gshm-2023.1'
METHOD='gem-2023.1-containing-cell-v1'
PALETTE=[(0.01,(255,255,255)),(.02,(215,227,238)),(.03,(181,202,255)),
         (.05,(143,179,255)),(.08,(127,151,255)),(.13,(171,207,99)),
         (.20,(232,245,158)),(.35,(255,250,20)),(.55,(255,209,33)),
         (.90,(255,163,10)),(1.50,(255,76,0))]
PGA_MEANING='PGA shows how strongly the ground could shake at a location during an earthquake, with a higher value meaning stronger expected shaking.'
PGA_LEVELS=('Very low','Low','Low to moderate','Moderate','Moderately elevated',
            'Elevated','High','Very high','Extremely high','Exceptional','Very exceptional')


def pga_level(value):
    """User-approved display bands, not a GEM/code/damage classification."""
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:return None
    for (upper,_),name in zip(PALETTE[:-1],PGA_LEVELS[:-1]):
        if value<upper:return name
    return PGA_LEVELS[-1]


def format_pga(value):
    # Increase precision near a boundary rather than displaying a rounded value
    # that appears to belong to a different band from the actual source value.
    text=f'{value:.3f}'
    for precision in (6,9,12,17):
        if pga_level(float(text))==pga_level(value):break
        text=f'{value:.{precision}g}'
    return text


def band_labels():
    return [(f'{0 if i==0 else PALETTE[i-1][0]:.2f}–{PALETTE[i][0]:.2f}' if i<10 else '≥0.90',name)
            for i,name in enumerate(PGA_LEVELS)]


def level_details(value):
    name=pga_level(value)
    return ('PGA display level: '+(name or 'Not available')+'.\n'
        'These are user-approved application labels for relative PGA, not official GEM, national-code, earthquake-magnitude or building-damage categories. '
        'Applied to the unrounded destination raster value. Lower bounds are inclusive and upper bounds are exclusive; 0.90 g and above uses Very exceptional.\n'
        +'\n'.join(interval+' g: '+label for interval,label in band_labels()))


@lru_cache(maxsize=4)
def _metadata(path,mtime,size,manifest_text):
    manifest=json.loads(manifest_text)
    with open(path,'rb') as f:
        checksum=hashlib.file_digest(f,'sha256').hexdigest()
        if checksum!=manifest['sha256']:raise ValueError('GEM raster checksum differs from the installed dataset.')
        f.seek(0);header=f.read(8)
        if header[:4]!=b'II*\x00':raise ValueError('Unsupported GEM TIFF header.')
        f.seek(struct.unpack('<I',header[4:])[0]);count=struct.unpack('<H',f.read(2))[0]
        if count>100:raise ValueError('Unsupported TIFF directory.')
        entries=[struct.unpack('<HHI4s',f.read(12)) for _ in range(count)]
        tags={};types={1:('B',1),2:('c',1),3:('H',2),4:('I',4),12:('d',8)}
        for tag,kind,n,raw in entries:
            if kind not in types:continue
            fmt,bytes_per=types[kind];length=n*bytes_per
            if length>1000000:raise ValueError('Unsupported TIFF metadata size.')
            if length<=4:content=raw[:length]
            else:f.seek(struct.unpack('<I',raw)[0]);content=f.read(length)
            tags[tag]=struct.unpack('<'+fmt*n,content)
        if any(tags.get(k)!=v for k,v in {256:(7200,),257:(3000,),258:(64,),259:(1,),277:(1,),278:(1,),339:(3,)}.items()):
            raise ValueError('Unsupported GEM raster layout; expected the supplied 2023.1 Float64 raster.')
        keys=tags[34735];geo={keys[i]:keys[i+1:i+4] for i in range(4,len(keys),4)}
        if geo.get(2048)!=(0,1,4326) or geo.get(1025)!=(0,1,1):
            raise ValueError('Expected WGS84 / EPSG:4326 PixelIsArea raster.')
        width,height=tags[256][0],tags[257][0];offsets=tags[273]
        if len(offsets)!=height or any(o!=offsets[0]+i*width*8 for i,o in enumerate(offsets)):
            raise ValueError('Unsupported TIFF strip layout.')
        if offsets[-1]+width*8>size:raise ValueError('Incomplete GEM raster.')
        sx,sy,_=tags[33550];px,py,_,west,north,_=tags[33922]
        if (px,py)!=(0,0) or sx<=0 or sy<=0:raise ValueError('Unsupported raster transform.')
        nodata=float(b''.join(tags[42113]).rstrip(b'\x00'))
        return dict(width=width,height=height,west=west,north=north,sx=sx,sy=sy,
                    offset=offsets[0],nodata=nodata,sha256=checksum)


def metadata(folder=None):
    folder=Path(folder) if folder else DATA
    path=folder/FILENAME;stat=path.stat()
    manifest=(folder/'manifest.json').read_text(encoding='utf-8')
    return path,_metadata(str(path),stat.st_mtime_ns,stat.st_size,manifest)


def lookup(point,folder=None):
    result=dict(status='unavailable',value=None,unit='g',source=SOURCE,sourceUrl=URL,
        version='2023.1',methodVersion=METHOD,requestedCoordinates=dict(point),
        returnPeriodYears=475,probabilityOfExceedance='10% in 50 years',
        referenceGround='Reference rock; Vs30 760–800 m/s',license='CC BY-NC-SA 4.0',
        licenseUrl=LICENSE_URL,sampling='Containing raster cell; no additional interpolation')
    try:
        lat,lon=float(point['lat']),float(point['lon'])
        if not math.isfinite(lat+lon) or not -90<=lat<=90 or not -180<=lon<=180:
            raise ValueError('Invalid destination coordinates.')
        path,m=metadata(folder)
        if lon==180:lon=-180
        col=math.floor((lon-m['west'])/m['sx']);row=math.floor((m['north']-lat)/m['sy'])
        result.update(fileName=FILENAME,sha256=m['sha256'],resolutionDegrees=[m['sx'],m['sy']],
                      coverage='Raster extent: 180°W to 180°E, approximately 60°S to 89.99°N; NoData cells excluded.')
        if not 0<=row<m['height'] or not 0<=col<m['width']:
            result.update(status='outside_coverage',message='Destination lies outside the GEM 2023.1 raster extent.');return result
        with path.open('rb') as f:
            f.seek(m['offset']+(row*m['width']+col)*8)
            value=struct.unpack('<d',f.read(8))[0]
        result.update(row=row,column=col,gridLatitude=m['north']-(row+.5)*m['sy'],
                      gridLongitude=m['west']+(col+.5)*m['sx'])
        if not math.isfinite(value) or value==m['nodata'] or value<0:
            result.update(status='no_data',message='No PGA value in the destination cell. Neighbouring cells are not substituted.');return result
        result.update(status='ready',value=value,message='PGA read from the local GEM raster for the delivery destination.')
    except (OSError,ValueError,KeyError,TypeError,struct.error) as error:
        result['message']='Local GEM dataset unavailable: '+str(error)
    return result


def current(site):
    """Never present a saved result against different destination coordinates."""
    from domain import coordinates
    data=site.get('seismicHazard',{})
    try:point=coordinates(site.get('destinationCoordinates',''))
    except ValueError:return {}
    return data if data.get('requestedCoordinates')==point and data.get('methodVersion')==METHOD else {}


def details(data):
    text=(f'{SOURCE}. PGA in g; 10% probability of exceedance in 50 years '
          '(approximately 475-year return period). Reference rock: Vs30 760–800 m/s.\n'
          'Destination lookup uses the containing raster cell in EPSG:4326; no colour scanning or additional interpolation. '
          'GEM interpolated the raster from model points spaced approximately 6 km using inverse-distance weighting. '
          'This is modelled hazard, not an on-site measurement or national design ag. No TB, TC, TD or S is derived from PGA.\n')
    if data.get('gridLatitude') is not None:
        text+=f"Cell centre: {data['gridLatitude']:.6f}, {data['gridLongitude']:.6f}; row {data['row']}, column {data['column']} (zero-based).\n"
    if data.get('value') is not None:text+=f"Raster cell PGA: {data['value']:.8g} g (unrounded source value is retained in saved data).\n"
    if data.get('resolutionDegrees'):
        text+='Cell size (longitude / latitude): '+ ' / '.join(f'{v:.8f}°' for v in data['resolutionDegrees'])+'.\n'
    text+=data.get('message','Select a destination to read the local raster.')+'\n'
    text+='Source file: '+FILENAME+'\n'
    if data.get('sha256'):text+='SHA-256: '+data['sha256']+'\n'
    return text+level_details(data.get('value'))+'\n© GEM Foundation 2023. CC BY-NC-SA 4.0; commercial use requires a GEM agreement. '+LICENSE_URL


def overlay(zoom,ox,oy,width,height,folder=None):
    """Viewport only, bounded to 512 px per side; transparent for NoData.

    Basemap coordinates are Web Mercator; numeric data remains WGS84. This
    display resampling is independent of the destination-cell lookup.
    """
    import numpy as np
    from PIL import Image
    path,m=metadata(folder)
    grid=np.memmap(path,mode='r',dtype='<f8',offset=m['offset'],shape=(m['height'],m['width']))
    w=max(1,min(512,int(width)));h=max(1,min(512,int(height)));world=256*2**zoom
    x=ox+(np.arange(w)+.5)*width/w;y=oy+(np.arange(h)+.5)*height/h
    lons=(x/world*360)%360-180
    lats=np.degrees(np.arctan(np.sinh(np.pi*(1-2*y/world))))
    cols=np.floor((lons-m['west'])/m['sx']).astype(int)
    rows=np.floor((m['north']-lats)/m['sy']).astype(int)
    valid=(rows[:,None]>=0)&(rows[:,None]<m['height'])&(cols[None,:]>=0)&(cols[None,:]<m['width'])
    values=grid[np.clip(rows,0,m['height']-1)[:,None],np.clip(cols,0,m['width']-1)[None,:]]
    valid&=np.isfinite(values)&(values>=0)&(values!=m['nodata'])
    colours=np.array([c for _,c in PALETTE]+[(255,76,0)],dtype=np.uint8)
    indices=np.searchsorted([v for v,_ in PALETTE],values,side='right')
    rgba=np.zeros((h,w,4),dtype=np.uint8);rgba[:,:,:3]=colours[indices];rgba[:,:,3]=np.where(valid,110,0)
    return Image.fromarray(rgba).resize((int(width),int(height)),Image.Resampling.NEAREST)
