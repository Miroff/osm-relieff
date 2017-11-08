#!/usr/bin/env python

import os
import re

min_ele = 0
max_ele = 4000
step_ele = 10
base_dir = 'srtm-tif'
base2_dir = 'srtm-tif-reprojected'
dest_dir = 'contours'

heights = " ".join([str(x) for x in xrange(min_ele, max_ele + step_ele, step_ele)])

for f in os.listdir(base_dir):
    base_file = re.sub(r'(.*?).hgt.tif$', "\\1", f)
    print("gdalwarp  -t_srs EPSG:3785 -r bilinear %s %s" % (os.path.join(base_dir, f), os.path.join(base2_dir, f)))
    cmd = "gdal_contour -a ele -fl %s %s %s" % (heights, os.path.join(base2_dir, f), os.path.join(dest_dir, base_file))
    print(cmd)
