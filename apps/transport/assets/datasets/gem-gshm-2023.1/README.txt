GEM GLOBAL SEISMIC HAZARD MAP version 2023.1
 
Copyright (C) 2023 GEM Foundation 

This product is made available under a Creative Commons CC BY-NC-SA 4.0. You 
should have received a LICENSE.txt file along with this product, describing the
terms of the license.  If you did not, please contact the GEM Foundation at 
licensing@globalquakemodel.org

If you have any questions please contact the GEM Foundation at: 
licensing@globalquakemodel.org

For further information on GEM Foundation seismic hazard and risk maps, please 
visit https://www.globalquakemodel.org/gem

------OVERVIEW------

The  Global Earthquake Model (GEM) Global Seismic Hazard Map (version 2023.1)
depicts the geographic distribution of the Peak Ground Acceleration (PGA) in 
terms of fraction of the acceleration of gravity, with a 10% probability of 
being exceeded in 50 years, computed for reference rock conditions (shear wave
velocity, Vs30, of 760-800 m/s). The map was created by collating maps computed
using national and regional probabilistic seismic hazard models developed by 
various institutions and projects, in collaboration with GEM Foundation 
scientists.

The OpenQuake engine, an open-source seismic hazard and risk calculation 
software developed principally by the GEM Foundation, was used to calculate the
hazard values. A smoothing methodology was applied to homogenise hazard values
along the model borders (Pagani et al., 2018). The map is based on a database 
of hazard models described using the OpenQuake engine data format (NRML); those
models implemented initially in other software formats were converted into 
NRML. While translating these models, various checks were performed to test the
compatibility between the original and new results computed using the OpenQuake
engine. Overall the differences between the original and translated model 
results are small notwithstanding some diversity in modelling methodologies 
implemented in different hazard modelling software. Some areas in the map (e.g.
Greenland) are currently not covered by an openly accessible hazard model. Due
to possible model limitations, regions portrayed with low hazard may still 
experience potentially damaging earthquakes. The raster is prepared by 
interpolating values calculated at points with ~6 km spacing using inverse 
distance weighting of nearest neighbours. The raster values will differ most 
from these original values in areas where hazard changes rapidly.

Technical details on the compilation of the hazard maps and the underlying 
models - including updates to model components made by GEM - are available at
https://hazard.openquake.org/

------COLOR SCHEMA------

The following is the color palette used by the GEM Foundation in the poster and
PNG versions of the Global Seismic Hazard Map. Users are encouraged to use the
same palette when presenting depictions of the map covering the globe in their
applications. 

PGA Range   |   RGB
0.00-0.01   |	255/255/255
0.01-0.02   |	215/227/238
0.02-0.03   | 	181/202/255
0.03-0.05   |	143/179/255
0.05-0.08   |	127/151/255
0.08-0.13   |	171/207/99
0.13-0.20   |	232/245/158
0.20-0.35   |	255/250/20
0.35-0.55   |	255/209/33
0.55-0.90   |	255/163/10
0.90-1.50   |	255/76/0
