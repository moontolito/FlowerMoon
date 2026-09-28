"""Native Tk OpenStreetMap canvas. Bounded viewport tile requests, seven-day cache."""
import base64
import math
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen
from routing import AGENT

def project(lat, lon, zoom):
    lat=max(-85.0511,min(85.0511,lat)); n=256*2**zoom
    return (lon+180)/360*n,(1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*n

def unproject(x,y,zoom):
    n=256*2**zoom
    return math.degrees(math.atan(math.sinh(math.pi*(1-2*y/n)))), x/n*360-180

def wrap_lon(lon):return (lon+180)%360-180

def longitude_center(values):
    ordered=sorted(v%360 for v in values)
    if len(ordered)==1:return wrap_lon(ordered[0])
    gaps=[((ordered[(i+1)%len(ordered)]-v)%360,i) for i,v in enumerate(ordered)]
    gap,i=max(gaps)
    start=ordered[(i+1)%len(ordered)]
    return wrap_lon(start+(360-gap)/2)

def near_x(x,center,zoom):
    world=256*2**zoom
    return center+(x-center+world/2)%world-world/2

class Map(tk.Canvas):
    def __init__(self,parent,colors,cache,on_pick=None,online=True,**kw):
        super().__init__(parent,bg=colors['raised'],highlightthickness=0,**kw)
        self.c=colors; self.cache=Path(cache); self.cache.mkdir(parents=True,exist_ok=True)
        self.on_pick=on_pick; self.online=online; self.zoom=6; self.lat=46.3; self.lon=25
        self.tiles={}; self.pending=set(); self.results=queue.Queue(); self.pool=ThreadPoolExecutor(max_workers=2)
        self.markers=[]; self.geometry=[];self.region=None; self.error=''; self.alive=True; self.redraw_id=None
        self.hazard_visible=False;self.hazard_key=None;self.hazard_image=None;self.hazard_error=''
        self.bind('<Configure>',lambda e:self.schedule())
        self.bind('<ButtonPress-1>',self.press); self.bind('<B1-Motion>',self.drag); self.bind('<ButtonRelease-1>',self.release)
        self.bind('<MouseWheel>',lambda e:self.change_zoom(1 if e.delta>0 else -1))
        self.bind('<Destroy>',self.dispose,add='+'); self.poll_id=self.after(100,self.poll)

    def dispose(self,e):
        if e.widget==self:
            for callback in (self.poll_id,self.redraw_id):
                if callback:
                    try:self.after_cancel(callback)
                    except tk.TclError:pass
            self.alive=False; self.pool.shutdown(wait=False,cancel_futures=True)

    def schedule(self):
        if self.redraw_id: self.after_cancel(self.redraw_id)
        self.redraw_id=self.after(100,self.draw)

    def change_zoom(self,delta):
        self.zoom=max(3,min(18,self.zoom+delta)); self.schedule()

    def press(self,e):
        self.start=(e.x,e.y,self.lat,self.lon); self.moved=False

    def drag(self,e):
        x,y,lat,lon=self.start
        if abs(e.x-x)+abs(e.y-y)>4:self.moved=True
        px,py=project(lat,lon,self.zoom)
        self.lat,self.lon=unproject(px-(e.x-x),py-(e.y-y),self.zoom)
        self.lat=max(-85,min(85,self.lat));self.lon=wrap_lon(self.lon);self.schedule()

    def release(self,e):
        if not self.moved and self.on_pick:
            x,y=project(self.lat,self.lon,self.zoom)
            lat,lon=unproject(x+e.x-self.winfo_width()/2,y+e.y-self.winfo_height()/2,self.zoom)
            self.on_pick(max(-85.0511,min(85.0511,lat)),wrap_lon(lon))

    def set_content(self,markers,geometry=None,fit=True):
        self.markers=markers;self.geometry=(geometry or {}).get('coordinates',[])
        if fit and markers:
            self.lat=max(-85,min(85,sum(p['lat'] for p in markers)/len(markers)));self.lon=longitude_center([p['lon'] for p in markers])
            self.zoom=14 if len(markers)==1 else 6
            if len(markers)>1:
                for z in range(15,3,-1):
                    center=project(self.lat,self.lon,z)[0]
                    pts=[(near_x(project(p['lat'],p['lon'],z)[0],center,z),project(p['lat'],p['lon'],z)[1]) for p in markers]
                    if max(x for x,y in pts)-min(x for x,y in pts)<max(200,self.winfo_width()-100) and max(y for x,y in pts)-min(y for x,y in pts)<max(140,self.winfo_height()-100):
                        self.zoom=z;break
        self.schedule()

    def fetch(self,key):
        z,x,y=key;path=self.cache/f'{z}-{x}-{y}.png'
        try:
            if path.exists() and time.time()-path.stat().st_mtime<7*86400: data=path.read_bytes()
            else:
                req=Request(f'https://tile.openstreetmap.org/{z}/{x}/{y}.png',headers={'User-Agent':AGENT})
                with urlopen(req,timeout=8) as response:data=response.read(2_000_000)
                path.write_bytes(data)
            self.results.put((key,data,None))
        except Exception:
            self.results.put((key,None,'Online map unavailable. Coordinates and saved routes remain accessible.'))

    def set_region(self,region):
        self.region=region;self.schedule()

    def set_hazard(self,enabled):
        self.hazard_visible=bool(enabled);self.schedule()

    def draw_hazard(self,w,h,ox,oy):
        import gem_hazard
        key=(self.zoom,ox,oy,w,h)
        if key!=self.hazard_key:
            self.hazard_error=''
            try:
                from PIL import ImageTk
                self.hazard_image=ImageTk.PhotoImage(gem_hazard.overlay(self.zoom,ox,oy,w,h),master=self)
            except Exception as error:
                self.hazard_image=None;self.hazard_error='Seismic layer unavailable: '+str(error)
            self.hazard_key=key
        if self.hazard_image:self.create_image(0,0,image=self.hazard_image,anchor='nw',tags='seismic-hazard')

    def hazard_legend(self,w,h):
        import gem_hazard
        if self.hazard_error:
            self.create_rectangle(5,48,min(w-5,420),100,fill=self.c['surface'],outline=self.c['border'])
            self.create_text(12,55,text=self.hazard_error,anchor='nw',width=min(w-24,395),fill=self.c['warning'])
            return
        columns=2 if w>=560 else 1
        rows=6 if columns==2 else 11
        boxheight=rows*15+66;boxwidth=536 if columns==2 else min(w-16,350)
        if w<360 or h<boxheight+110:
            self.create_text(10,60,text='GEM 2023.1 · PGA (g) · rock · 475 years\nPGA bands and names: open Value details.',anchor='nw',fill=self.c['text'],tags='seismic-legend');return
        y=h-boxheight-61
        self.create_rectangle(8,y,8+boxwidth,y+boxheight,fill=self.c['surface'],outline=self.c['border'],tags='seismic-legend')
        self.create_text(16,y+8,text='GEM 2023.1 · PGA (g) · rock · 475 years',anchor='nw',fill=self.c['text'],font=('Segoe UI',9,'bold'))
        self.create_text(16,y+25,text='Relative PGA · application labels',anchor='nw',fill=self.c['secondary'],font=('Segoe UI',8))
        for i,((interval,name),(_,rgb)) in enumerate(zip(gem_hazard.band_labels(),gem_hazard.PALETTE)):
            x=16+(i//rows)*268;yy=y+45+(i%rows)*15
            label=interval+' · '+name
            self.create_rectangle(x,yy,x+13,yy+10,fill='#%02x%02x%02x'%rgb,outline=self.c['border'])
            self.create_text(x+18,yy+5,text=label,anchor='w',fill=self.c['text'],font=('Segoe UI',8))
        self.create_text(16,y+boxheight-10,text='© GEM · CC BY-NC-SA 4.0',anchor='w',fill=self.c['secondary'],font=('Segoe UI',8))

    def poll(self):
        if not self.alive:return
        changed=False
        while not self.results.empty():
            key,data,error=self.results.get();self.pending.discard(key)
            if data:
                try:self.tiles[key]=tk.PhotoImage(master=self,data=base64.b64encode(data))
                except tk.TclError:self.error='Invalid map image.';self.tiles[key]=None
            else:self.error=error;self.tiles[key]=None
            changed=True
        if len(self.tiles)>150:
            for key in list(self.tiles)[:50]:del self.tiles[key]
        if changed:self.draw()
        self.poll_id=self.after(150,self.poll)

    def draw(self):
        if not self.alive:return
        self.redraw_id=None;self.delete('all')
        w,h=self.winfo_width(),self.winfo_height();cx,cy=project(self.lat,self.lon,self.zoom)
        ox,oy=cx-w/2,cy-h/2;n=2**self.zoom
        for tx in range(math.floor(ox/256),math.floor((ox+w)/256)+1):
            for ty in range(math.floor(oy/256),math.floor((oy+h)/256)+1):
                if not 0<=ty<n:continue
                key=(self.zoom,tx%n,ty);x,y=tx*256-ox,ty*256-oy
                if self.tiles.get(key):self.create_image(x,y,image=self.tiles[key],anchor='nw')
                else:
                    self.create_rectangle(x,y,x+256,y+256,outline=self.c['border'])
                    if self.online and key not in self.tiles and key not in self.pending:
                        self.pending.add(key);self.pool.submit(self.fetch,key)
        if self.hazard_visible:self.draw_hazard(w,h,ox,oy)
        if self.region and self.region.get('status')=='ready':
            shape=self.region['geometry'];polygons=[shape['coordinates']] if shape['type']=='Polygon' else shape['coordinates']
            for polygon in polygons:
                for ring in polygon:
                    points=[];previous=cx
                    for lon,lat,*_ in ring:
                        x,y=project(lat,lon,self.zoom);x=near_x(x,previous,self.zoom);previous=x;points.extend((x-ox,y-oy))
                    if len(points)>=4:self.create_line(*points,fill=self.c['primary'],width=3,dash=(7,3),tags='delivery-region')
        if self.geometry:
            for a,b in zip(self.geometry,self.geometry[1:]):
                ax,ay=project(a[1],a[0],self.zoom);bx,by=project(b[1],b[0],self.zoom)
                ax=near_x(ax,cx,self.zoom);bx=near_x(bx,ax,self.zoom)
                self.create_line(ax-ox,ay-oy,bx-ox,by-oy,fill=self.c['primary'],width=4)
        for i,p in enumerate(self.markers):
            x,y=project(p['lat'],p['lon'],self.zoom);x=near_x(x,cx,self.zoom)-ox;y-=oy
            self.create_oval(x-7,y-7,x+7,y+7,fill=self.c['primary'],outline='white',width=2)
            self.create_text(x+11,y-14,text=p.get('label',str(i+1)),anchor='w',fill=self.c['text'],font=('Segoe UI',10,'bold'))
        if self.error or not self.online:
            self.create_rectangle(0,0,w,42,fill=self.c['surface'],outline='')
            self.create_text(12,20,text=self.error or 'Offline test mode · no map downloads',anchor='w',width=max(100,w-24),fill=self.c['secondary'])
        if any(abs(p['lat'])>85.0511 for p in self.markers):
            self.create_text(12,52,text='Polar region: Mercator cannot display latitudes above ±85°. Coordinates remain valid.',anchor='w',width=max(100,w-24),fill=self.c['warning'])
        if self.hazard_visible:self.hazard_legend(w,h)
        if self.region:
            text=('Delivery region: '+self.region['name']+' · geoBoundaries gbOpen / ADM1') if self.region.get('status')=='ready' else 'Delivery region boundary unavailable'
            self.create_rectangle(0,h-53,w,h-25,fill=self.c['surface'],outline='')
            self.create_text(10,h-39,text=text,anchor='w',fill=self.c['primary'],font=('Segoe UI',9,'bold'),width=max(100,w-20))
        self.create_rectangle(0,h-25,w,h,fill=self.c['surface'],outline='')
        self.create_text(10,h-12,text='© OpenStreetMap contributors · openstreetmap.org/copyright',anchor='w',fill=self.c['secondary'],font=('Segoe UI',9))
