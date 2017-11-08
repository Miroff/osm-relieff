# osm-relieff

Create contour tiles for OSM based maps 
https://www.geos.ed.ac.uk/homes/wam/ChaudMackTrans2008.pdf

Pseudocode of the algorithm
1. Smooth the detailed input DTM using Landserf with a kernel size of 25*25
2. Create contours at 5m interval from the smoothed DTM;
3. Create summit points: Within each highest contour (contour that does not contain any other
contour) create a point geometry to store highest elevation within that contour;
4. Calculate the prominence of each contour
4a For each summit find the key contour i.e. the lowest elevation closed contour that
enrciles the summit in question and does not contain any other summit higher than
the given summit;
4b. Subtract the elevation of the key contour from the elevation of the summit (this is
the prominence of the summit);
5. Model the morphology in terms of morphometric classification of the input DTM using
Landserf with mulit-scale option and a range of kernel sizes from 3*3 to 51*51;
6. Convert the morphometric regions (5) to polygons;
7. Remove all polygons classified as plane regions;
8. Calculate the extent of each summit:
 8a. Select the key contour of the given summit
8b Calculate the total area intersection of this contour with all the interacting
morphometric polygons (7).
8c Calculate the percentage of varabilty by dividing the area of 8b by the area of the
contour.
8d. If area of stage 8b is less then MMC then select the next higher contour for the
given summit and repeat 8b-8d until the area becomes larger than or equal to MMC.
This contour is the extent of the summit.
9. Assign parent and child relationships
9a. For a given summit ‘A’, if the first next highest summit whose key contour
‘b’contains summit ‘A’ and whose extent found from step 8d also contains summit A
then this is assigned as the parent of summit ‘A’. 

# TODO:
* CLI for find-contours
* document baseline toolchain
* find peaks 
* Fix mapnik style to adjust contours density based on zoom level
