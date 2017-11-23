#!/usr/bin/env python3

from osgeo import gdal

from skimage import measure
from shapely.geometry import LineString
from geojson import Feature, FeatureCollection
from tqdm import tqdm

import logging
import geojson

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def read_contours(file, interval):
    logger.info("Start finding contours in every %d meters" % (interval))
    ds = gdal.Open(file)
    nda = ds.ReadAsArray().astype(float)
    # Add half of meter to avoid skeleton geometries
    # when contour matches to a center of a pixel
    nda = nda + 0.5

    transform = ds.GetGeoTransform()
    xOrigin = transform[0]
    yOrigin = transform[3]
    pixelWidth = transform[1]
    pixelHeight = transform[5]

    def project(point):
        return (xOrigin + (point[1] * pixelWidth) + pixelWidth / 2,
                yOrigin + (point[0] * pixelHeight) + pixelHeight / 2)

    h0 = (int(nda.min()) / interval) * interval + interval
    h1 = (int(nda.max()) / interval) * interval + interval

    features = []
    for height in tqdm(xrange(h0, h1, interval)):
        contours = measure.find_contours(nda, height)
        for contour in contours:
            geometry = LineString(map(project, contour))
            feature = Feature(geometry=geometry, properties={'ele': height})
            features.append(feature)

    logger.info("Finding contours complete. %d contours was found" % (len(features)))
    return FeatureCollection(features)


def find_contours(fin, fout, interval):
    logger.info("Processing %s into %s" % (fin, fout))
    features = read_contours(fin, interval)
    with open(fout, 'w') as fh:
        fh.write(geojson.dumps(features))


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    # logger.addHandler(logging.ConsoleHandler())
    # logger.setLevel(logging.INFO)

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Input DEM file in GeoTIFF or any other raster format supported by GDAL")
    parser.add_argument("output", help="Output GeoJSON file")
    parser.add_argument("-i", "--interval", default=10, help="Contours interval in meters, default 10")
    args = parser.parse_args()

    find_contours(args.input, args.output, args.interval)

# if __main__ == '__main':
# # TODO: Accept single file only
# for f in ['N51E087.hgt.tif']:  # os.listdir("srtm-tif"):
#     fin = os.path.join("srtm-tif", f)
#     fout = re.sub(r'(.*?).hgt.tif$', "\\1.json", f)
#     fout = os.path.join("contours-json", fout)
#     print("Readind %s to %s" % (fin, fout))
#
#     features = read_contours(fin)
#
