"""Debounced address lookup for map clicks; never changes selected coordinates."""
import threading
import places


class MapAddressLookup:
    def __init__(self,app):
        self.app=app;self.timers={};self.serial={};self.alive=True

    def selected(self,target,lat,lon):
        app=self.app
        name,coords=(app.origin_name,app.origin_coords) if target=='origin' else (app.dest_name,app.dest_coords)
        expected=(name.get(),coords.get())
        number=self.serial[target]=self.serial.get(target,0)+1
        if target in self.timers:app.after_cancel(self.timers.pop(target))
        record='departureAddressLookup' if target=='origin' else 'destinationAddressLookup'
        base=dict(source=places.SOURCE,sourceUrl=places.DOCS,coordinates=expected[1],requestedCoordinates=dict(lat=lat,lon=lon))
        app.site[record]=dict(base,status='unavailable' if app.offline else 'loading',detail='Address lookup is disabled in offline mode.' if app.offline else 'Looking up the selected map point address…')
        if app.offline:return
        def current():
            return self.alive and self.serial.get(target)==number and expected==(name.get(),coords.get())
        def done(result):
            if not current():return
            app.site[record]=dict(base,**result)
            if result.get('status')=='ready':
                app.apply_map_address(target,result['label'])
                app.status.set(('Departure' if target=='origin' else 'Destination')+' address found · Photon / OpenStreetMap. Selected coordinates retained.')
            else:
                app.status.set('Address unavailable for this map point. Selected coordinates are retained; you can still calculate the route.')
                app.state.save();app.refresh_site_window()
        def start():
            self.timers.pop(target,None)
            if not current():return
            def work():
                try:result=places.reverse(lat,lon)
                except Exception:result=dict(status='unavailable',detail='Address service unavailable. Try selecting the point again; exact coordinates are retained.')
                app.site_jobs.put((done,result,None))
            threading.Thread(target=work,daemon=True).start()
        self.timers[target]=app.after(450,start)

    def close(self):
        self.alive=False
        for timer in self.timers.values():self.app.after_cancel(timer)
        self.timers.clear()
