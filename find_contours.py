#!/usr/bin/env python3

from osgeo import gdal
from skimage.measure import find_contours
from scipy.ndimage import maximum_filter
from affine import Affine
from math import floor


import json
import numpy as np
import matplotlib.pyplot as plt


ds = gdal.Open('srtm-tif/N50E087.hgt.tif')
nda = ds.ReadAsArray()

transform = ds.GetGeoTransform()
xOrigin = transform[0]
yOrigin = transform[3]
pixelWidth = transform[1]
pixelHeight = transform[5]

def project(point):
    return (xOrigin + (point[1] * pixelWidth) + pixelWidth / 2, yOrigin + (point[0] * pixelHeight) + pixelHeight / 2)

interval = 10

h0 = (nda.min() / interval) * interval + interval
h1 = (nda.max() / interval) * interval + interval

features = []
for height in xrange(h0, h1, interval):
    contours = find_contours(nda, height)
    for contour in contours:

        coords = map(project, contour)

        features.append({
            'type': 'Feature',
            'geometry': {
                'type': 'LineString',
                'coordinates': coords
            },
            'properties': {
                'ele': height
            }
        })

print(json.dumps({'type': 'FeatureCollection', 'features': features}))
