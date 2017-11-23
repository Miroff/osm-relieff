#!/usr/bin/env python3

from tqdm import tqdm
import logging
from osgeo import gdal
import geojson
from shapely.geometry import Polygon, LineString
from geojson import Feature, FeatureCollection
from shapely.strtree import STRtree
from operator import attrgetter
from skimage.measure import find_contours
from skimage.filters import gaussian
from skimage import img_as_float
from scipy.ndimage.filters import gaussian_filter
import numpy as np

logger = logging.getLogger()


def find_summits(contours, min_prominence=0):
    print("Building contours tree")
    contour_tree = STRtree(contours)

    print("Finding potential summits")
    summits = []

    for p in tqdm(contours):
        # Heuristic to reduce
        if p.area > 0.000002:
            continue

        inner = contour_tree.query(p)
        inner = filter(lambda a: a.ele > p.ele, inner)
        inner = sorted(inner, key=attrgetter('ele'), reverse=True)

        # print(p.ele, map(lambda a: a.ele, inner))
        # TODO: Optimize!!!
        miss = False
        for c in inner:
            # print("\t", c.ele, p.ele)
            if p.contains(c):
                miss = True
                break
        # inner = filter(lambda c: c != p and p.contains(c), inner)

        # print("%f found %d\%d" % (p.area, len(inner), a))

        if not miss:
            summits.append(p)

    print("Found %d potential summits" % len(summits))
    summit_tree = STRtree(summits)

    result = []
    for s in tqdm(summits):
        point = s.representative_point()
        outer = contour_tree.query(point)
        outer = filter(lambda a: a.ele < s.ele, outer)
        outer = sorted(outer, key=attrgetter('ele'), reverse=True)

        key = None
        for contour in outer:
            concurents = summit_tree.query(contour)
            concurents = filter(lambda peak: peak.ele > s.ele, concurents)

            miss = False
            for peak in concurents:
                if contour.contains(peak):
                    miss = True
                    break

            if not miss:
                key = contour
            else:
                break

        if key and s.ele - key.ele > min_prominence:
            centroid = s.centroid
            centroid.ele = s.ele
            centroid.prominence = s.ele - key.ele
            result.append(centroid)

    print("Found %d summits" % len(result))
    return result


def summits_to_features(summits):
    return map(summit_to_feature, summits)


def summit_to_feature(summit):
    return Feature(geometry=summit, properties={'ele': summit.ele, 'prominence': summit.prominence})

# summits = summits_to_features(find_summits(contours))
# print(map(lambda a: a, summits))


def find_peaks(fin, fout, interval=5):
    ds = gdal.Open(fin)
    nda = ds.ReadAsArray().astype(float)
    nda = nda + 0.5
    # TODO: Debug remove
    #nda = nda[:1000, :1000]

    transform = ds.GetGeoTransform()
    xOrigin = transform[0]
    yOrigin = transform[3]
    pixelWidth = transform[1]
    pixelHeight = transform[5]

    def project(point):
        return (xOrigin + (point[1] * pixelWidth) + pixelWidth / 2, yOrigin + (point[0] * pixelHeight) + pixelHeight / 2)

    def contour_to_polygon(ele):
        def doJob(contour):
            if (len(contour) < 3):
                return None
            ls = LineString(map(project, contour))
            if not ls.is_ring:
                return None

            polygon = Polygon(ls)
            if not polygon.is_valid:
                logger.warn("Polygon is not valid")
                return None

            # TODO: Use actual maximum from DEM here
            polygon.ele = ele - 0.5
            return polygon
        return doJob

    h0 = (int(nda.min()) / interval) * interval + interval
    h1 = (int(nda.max()) / interval) * interval + interval

    #print("Blurring image")
    #nda = gaussian_filter(nda, 3)

    print("Calculating polygon contours")
    contours = []
    for ele in tqdm(xrange(h0, h1, interval)):
        contours = contours + filter(lambda a: a, map(contour_to_polygon(ele), find_contours(nda, ele)))

    print("Found %d polygons" % len(contours))

    summits = FeatureCollection(summits_to_features(find_summits(contours)))

    with open(fout, 'w') as fh:
        fh.write(geojson.dumps(summits))

find_peaks('srtm-tif/N51E086.hgt.tif', 'peaks-json/N51E086.json')
