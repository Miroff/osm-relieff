#!/usr/bin/env python3

from tqdm import tqdm
import logging
from osgeo import gdal
import geojson
from shapely.geometry import Polygon, LineString
from shapely import ops
from shapely.strtree import STRtree
from shapely.validation import explain_validity
from geojson import Point, Feature, FeatureCollection
from operator import attrgetter
from skimage.measure import find_contours
from skimage.filters import gaussian
from skimage import img_as_float
from scipy.ndimage.filters import gaussian_filter
import numpy as np
import cv2


logger = logging.getLogger()


def adjust_peak(nda, polygon):
    coords = np.array(map(lambda a: (a[1], a[0]), polygon.exterior.coords))
    con_mask = np.zeros((nda.shape[0], nda.shape[1], 1), np.uint8)
    cv2.drawContours(con_mask, [coords.astype(int)], 0, 255, -1)

    #Compensate coordinates conversion to integer
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    con_mask = cv2.dilate(con_mask, kernel, iterations=1)

    fg = cv2.bitwise_and(nda, nda, mask=con_mask)
    argmax = fg.argmax()
    max_pos = np.unravel_index(argmax, fg.shape)

    # dbg = np.zeros((nda.shape[0], nda.shape[1], 3), np.uint8)
    # cv2.drawContours(dbg, [coords.astype(int)], -1, (0,255,0), 1)
    #
    # cv2.imshow('image', con_mask)
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()

    peak = Point(max_pos) #(max_pos[1], max_pos[0])
    peak.ele = nda[max_pos]
    return peak


def find_summits(nda, contours, min_prominence):
    print("Building contours tree")
    contour_tree = STRtree(contours)

    print("Finding potential summits")
    summits = []

    for p in tqdm(contours):
        # Heuristic to reduce
        if p.area > 1000:
            continue

        inner = contour_tree.query(p)
        inner = filter(lambda inner_contour: inner_contour.ele > p.ele, inner)
        inner = sorted(inner, key=attrgetter('ele'), reverse=True)

        miss = False
        for c in inner:
            if p.contains(c):
                miss = True
                break
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

        if key:
            peak = adjust_peak(nda, s)
            peak.prominence = peak.ele - key.ele
            if peak.prominence > min_prominence:
                result.append(peak)

    print("Found %d summits" % len(result))
    return result


def summits_to_features(summits):
    return map(summit_to_feature, summits)


def summit_to_feature(summit):
    return Feature(geometry=summit, properties={
            'ele': summit.ele,
            'prominence': summit.prominence
        })


def find_peaks(fin, fout, interval=5, min_prominence=50):
    ds = gdal.Open(fin)
    nda = ds.ReadAsArray().astype(float)
    nda = nda + 0.5
    # TODO: Debug remove
    # nda = nda[:500, :500]

    transform = ds.GetGeoTransform()
    xOrigin = transform[0]
    yOrigin = transform[3]
    pixelWidth = transform[1]
    pixelHeight = transform[5]

    def project(geom):
        point = geom.coordinates

        latlon = (xOrigin + (point[1] * pixelWidth) + pixelWidth / 2,
                  yOrigin + (point[0] * pixelHeight) + pixelHeight / 2)

        p = Point(latlon)
        p.ele = geom.ele
        p.prominence = geom.prominence
        return p

    w = nda.shape[0] - 1
    h = nda.shape[1] - 1
    bbox = LineString([
        [0, 0],
        [0, h],
        [w, h],
        [w, 0],
        [0, 0]
    ])

    def contour_to_polygon(ele):
        def doJob(contour):
            contour = list(contour)
            if (len(contour) < 3):
                logger.warn("Contour contains less than 3 points")
                return None
            ls = LineString(contour)
            if ls.is_ring:
                polygon = Polygon(ls)
            else:
                lss = ls.union(bbox)
                result, dangles, cuts, invalids = ops.polygonize_full(lss)
                if dangles or cuts or invalids:
                    print contour
                    print result
                    print dangles
                    print cuts
                    print invalids
                    logger.warn("Invalid geometry")
                    exit()

                if len(result) != 2:
                    logger.warn("Sanity check 1")
                    exit()

                r1 = result[0].exterior.intersection(ls)
                r2 = result[1].exterior.intersection(ls)

                if r1.geoms[0].coords[0:2] == ls.coords[0:2]:
                    polygon = r1
                elif r2.geoms[0].coords[0:2] == ls.coords[0:2]:
                    polygon = r2
                else:
                    logger.warn("Sanity check 2")
                    exit()

            if not polygon.is_valid:
                logger.warn("Polygon is not valid")
                return None

            # TODO: Use actual maximum from DEM here
            polygon.ele = ele - 0.5
            return polygon
        return doJob

    h0 = (int(nda.min()) / interval) * interval + interval
    h1 = (int(nda.max()) / interval) * interval + interval

    # print("Blurring image")
    # nda = gaussian_filter(nda, 3)
    print("Calculating polygon contours")
    contours = []
    for ele in tqdm(xrange(h0, h1, interval)):
        contours = contours + filter(lambda a: a, map(contour_to_polygon(ele), find_contours(nda, ele)))

    print("Found %d polygons" % len(contours))

    summits = map(project, find_summits(nda, contours, min_prominence))

    features = FeatureCollection(summits_to_features(summits))

    with open(fout, 'w') as fh:
        fh.write(geojson.dumps(features))
