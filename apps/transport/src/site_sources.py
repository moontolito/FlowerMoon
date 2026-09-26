"""Optional location lookups; failure never becomes an engineering value."""
import math
import elevation
from site_environment import geography,standards,service


def route_samples(geometry,budget=512):
    points=geometry.get('coordinates',[])
    if len(points)<2:return [],0
    lengths=[];total=0
    for a,b in zip(points,points[1:]):
        lat1,lat2=math.radians(a[1]),math.radians(b[1]);dl=math.radians(b[1]-a[1]);dn=math.radians(b[0]-a[0])
        h=math.sin(dl/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dn/2)**2
        distance=6371000*2*math.asin(min(1,math.sqrt(h)));lengths.append(distance);total+=distance
    count=min(budget,max(2,math.ceil(total/500)+1));spacing=total/(count-1);shape=[];index=0;start=0
    for i in range(count):
        target=spacing*i
        while index<len(lengths)-1 and start+lengths[index]<target:start+=lengths[index];index+=1
        a,b=points[index],points[index+1];fraction=min(1,max(0,(target-start)/lengths[index])) if lengths[index] else 0
        lon=a[0]+fraction*((b[0]-a[0]+180)%360-180)
        shape.append({'lat':a[1]+fraction*(b[1]-a[1]),'lon':(lon+180)%360-180})
    return shape,spacing

def lookup(server, destination, geometry=None):
    result={}
    shape,spacing=route_samples(geometry) if geometry else ([],0)
    dem=elevation.samples([destination]+shape)
    result['elevationAnalysis']=dem
    result['siteAltitude']=dem['values'][0]
    result['siteAltitudeSource']=elevation.SOURCE
    result['siteAltitudeDetail']='Surface elevation includes vegetation and buildings; EGM2008 vertical datum. Verify against a site survey.'
    if dem['values'][0] is None:result['siteAltitudeDetail']='Copernicus GLO-90 did not return a value. '+'; '.join(dem.get('errors',[]))
    heights=dem['values'][1:]
    if shape and len(heights)>=2 and all(v is not None for v in heights):
        result['altitude']=(max(heights),elevation.SOURCE+f' · maximum of {len(shape)} samples at approximately {spacing:.0f} m spacing; peaks between samples require verification')
    elif not shape:
        result['altitude']=(dem['values'][0],elevation.SOURCE+' · destination elevation, not the route maximum')
    else:
        result['altitude']=(None,elevation.SOURCE+' · incomplete profile; route maximum is unavailable')
    result['altitudeStatus']='VERIFY'
    result['coastalDistance']=geography.coast(destination)
    result['locationContext']=service.context(destination)
    result['zoning']=standards.lookup(destination,result.get('siteAltitude'))
    return result
