#!/usr/bin/env python3
from operator import attrgetter
import logging

from tqdm import tqdm
import matplotlib.pyplot as plt
from descartes import PolygonPatch

from skimage.measure import find_contours
import numpy as np
import cv2

from osgeo import gdal
from shapely.geometry import Polygon, LineString, MultiPolygon
from shapely import ops
import geojson
from geojson import Point, Feature, FeatureCollection


logger = logging.getLogger()


def adjust_peak(nda, polygon):
    coords = np.array(map(lambda a: (a[1], a[0]), polygon.exterior.coords))
    con_mask = np.zeros((nda.shape[0], nda.shape[1], 1), np.uint8)
    cv2.drawContours(con_mask, [coords.astype(int)], 0, 255, -1)

    # Compensate coordinates conversion to integer
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    con_mask = cv2.dilate(con_mask, kernel, iterations=1)

    fg = cv2.bitwise_and(nda, nda, mask=con_mask)
    argmax = fg.argmax()
    max_pos = np.unravel_index(argmax, fg.shape)

    peak = Point(max_pos)
    peak.ele = nda[max_pos]
    peak.contour = polygon
    return peak


def build_hierarchy(elevations, polygons):
    logger.info("Building hierarchy")
    summits = []
    for high, low in tqdm(zip(elevations, elevations[1:])):
        ele, top = filter(lambda p: p[0] == high, polygons)[0]
        ele, bottom = filter(lambda p: p[0] == low, polygons)[0]

        for tp in top:
            tp.ele = high
            for bp in bottom:
                bp.ele = low

            if not hasattr(tp, 'children'):
                tp.children = []

            parents = filter(lambda bp: bp.contains(tp), bottom)

            if len(parents) == 0:
                continue

            if len(parents) > 1:
                print(parents)
                raise Exception("Peak is in more than one lower contour")

            parent = parents[0]
            tp.parent = parent
            if not hasattr(parent, 'children'):
                parent.children = []
            if not hasattr(tp, 'key_ele'):
                tp.key_ele = high

            if not hasattr(parent, 'key_ele'):
                parent.key_ele = 0

            if parent.key_ele < tp.key_ele:
                parent.key_ele = tp.key_ele

            parent.children.append(tp)
            summits.append((high, tp))

    roots = []
    for ele, summit in summits:
        if not summit.children:
            roots.append(summit)

    return roots


def find_summits(nda, elevations, polygons, min_prominence):
    candidates = build_hierarchy(elevations, polygons)
    candidates = filter(lambda a: not hasattr(a, "touches_edge"), candidates)

    logger.info("Found %d summit candidates" % len(candidates))
    summits = []
    candidates = map(lambda polygon: adjust_peak(nda, polygon), tqdm(candidates))
    logger.info("Adjusted peaks height")
    peaks = sorted(candidates, key=attrgetter('ele'), reverse=True)
    for i, peak in tqdm(enumerate(peaks)):
        key = peak.contour
        path = [key]

        #TODO: Not sure this condition is correct
        while hasattr(key, 'parent') and key.parent.key_ele <= peak.ele and not hasattr(key, "touches_edge"):
            key = key.parent
            path.append(key)

        if peak.ele - key.ele > min_prominence and peak.ele > key.key_ele:
            logger.info("Peak #%d, elevation %f contour elevation %f (%f)" % (i, peak.ele, key.key_ele, key.ele))

            peak.prominence = peak.ele - key.ele
            peak.index_in_session = i
            summits.append(peak)

            for k in path:
                k.key_ele = peak.ele

    logger.info("Found %d summits" % len(summits))

    return summits


def summits_to_features(summits):
    return map(summit_to_feature, summits)


def summit_to_feature(summit):
    return Feature(geometry=summit, properties={
            'ele': summit.ele,
            'prominence': summit.prominence,
            'index_in_session': summit.index_in_session
        })


def debug_render(geom):
    fig, ax = plt.subplots()
    ax.add_patch(PolygonPatch(geom, fc='#aa0000'))
    ax.grid()
    ax.axis('equal')
    plt.show()


def merge_lines(lines, bbox):
    convex = ops.cascaded_union(lines).union(bbox)
    convex = filter(lambda l: bbox.contains(l), convex)

    polygons = []
    lines = list(lines)
    while lines:
        line = lines.pop()
        merged = [line]

        first = line.coords[0]
        last = line.coords[-1]
        while first != last:
            nxt = filter(lambda l: l.coords[0] == last, lines)
            if len(nxt) > 1:
                raise Exception("More then one line in lines list")
            if len(nxt) == 1:
                line = nxt[0]
                merged.append(line)
                lines.remove(line)
                last = line.coords[-1]
                continue
            nxt = filter(lambda l: l.coords[0] == last, convex)
            if len(nxt) > 1:
                raise Exception("More then one line in lines list")
            if len(nxt) == 1:
                line = nxt[0]
                merged.append(line)
                convex.remove(line)
                last = line.coords[-1]
                continue
            else:
                raise Exception("Cannot find next line")

        result, dangles, cuts, invalids = ops.polygonize_full(merged)
        if len(result) != 1:
            raise Exception("Merged lines should produce a single polygon")
        polygon = result[0]
        polygons.append(polygon)

    return polygons


def contour_to_polygon(contours, bbox):
    result = MultiPolygon()
    lines = []
    for contour in contours:
        contour = list(contour)
        if (len(contour) < 3):
            continue
            #raise Exception("Contour contains less than 3 points")

        ls = LineString(contour)
        if ls.is_ring:
            result = result.union(Polygon(ls))
        else:
            lines.append(ls)

    if lines:
        multi = MultiPolygon(merge_lines(lines, bbox))
        # I have no idea why this polyon is negative :(
        multi = Polygon(bbox).difference(multi)
        result = result.union(multi)

    return result


def find_peaks(fin, fout, interval=5, min_prominence=30):
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

    def project(geom):
        point = geom.coordinates

        latlon = (xOrigin + (point[1] * pixelWidth) + pixelWidth / 2,
                  yOrigin + (point[0] * pixelHeight) + pixelHeight / 2)

        p = Point(latlon)
        p.ele = geom.ele
        p.prominence = geom.prominence
        p.index_in_session = geom.index_in_session
        return p

    w = nda.shape[0] - 1
    h = nda.shape[1] - 1
    bbox = LineString([
        [0, 0],
        [w, 0],
        [w, h],
        [0, h],
        [0, 0]
    ])

    h0 = (int(nda.min()) / interval) * interval + interval
    h1 = (int(nda.max()) / interval) * interval + interval
    elevations = range(h1, h0, -interval)

    # print("Blurring image")
    # nda = gaussian_filter(nda, 3)
    logger.info("Calculating polygon contours")
    polygons = []
    for ele in tqdm(elevations):
        contours = find_contours(nda, ele)

        polygon = contour_to_polygon(contours, bbox)
        pp = []
        if type(polygon) == Polygon:
            pp = [polygon]
        elif type(polygon) == MultiPolygon:
            pp = list(polygon.geoms)
        else:
            raise Exception("Unexpected object type")
        # pair = (ele, [polygon])

        for p in pp:
            if p.touches(bbox):
                p.touches_edge = True

        polygons.append((ele, pp))

    logger.info("Found %d polygons" % len(polygons))

    summits_px = find_summits(nda, elevations, polygons, min_prominence)

    summits = map(project, summits_px)

    features = FeatureCollection(summits_to_features(summits))

    with open(fout, 'w') as fh:
        fh.write(geojson.dumps(features))
