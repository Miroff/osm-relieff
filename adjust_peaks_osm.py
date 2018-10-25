import geojson
import json
import requests
from shapely.strtree import STRtree
from shapely.geometry import Point
from pyproj import Proj, transform

import sys
reload(sys)
sys.setdefaultencoding('utf-8')

latlonProj = Proj(init='epsg:4326')
# TODO: Use more suitable mercator here to more uniform distance calculations
xyProj = Proj(init='epsg:3857')


def read_file(file):
    with open(file) as fh:

        peaks_json = geojson.loads(fh.read())

        peaks = []
        for peak in peaks_json.features:
            lon, lat = peak.geometry.coordinates
            p = Point(transform(latlonProj, xyProj, lon, lat))
            p.ele = peak.geometry.ele
            p.prominence = peak.geometry.prominence
            peaks.append(p)
        return peaks


def read_overpass(bbox):
    url = 'https://overpass-api.de/api/interpreter'
    data = """[out:json][timeout:25];
(
node["natural"="peak"](%d,%d,%d,%d);
);
// print results
out meta;""" % bbox
    res = requests.post(url, data=data)
    peaks_osm = json.loads(res.text)
    peaks = []
    for peak in peaks_osm['elements']:
        p = Point(transform(latlonProj, xyProj, peak['lon'], peak['lat']))
        p.tags = peak['tags']
        p.id = peak['id']
        p.version = peak['version']
        if 'ele' in p.tags:
            p.ele = p.tags['ele']
        else:
            p.ele = None
        peaks.append(p)
    return peaks

def adjust(osm_peak, new_position):
    #print <node id='346364767' action='delete' timestamp='2009-02-16T21:34:44+00:00' user='dankarran' visible='true' lat='51.5076698' lon='-0.1278143' />
    x = new_position.coords[0][0]
    y = new_position.coords[0][1]
    lon, lat = transform(xyProj, latlonProj, x, y)
    print "<node id=\"%s\" version=\"%d\" action=\"modify\" visible=\"true\" lat=\"%f\" lon=\"%f\">" % (osm_peak.id, osm_peak.version, lat, lon)
    for k in osm_peak.tags:
        print "  <tag k=\"%s\" v=\"%s\" />" % (k, osm_peak.tags[k])
    if 'ele' not in osm_peak.tags:
        print "  <tag k=\"ele\" v=\"%0.1f\" />" % new_position.ele
    print "</node>"

def append(id, new_position):
    x = new_position.coords[0][0]
    y = new_position.coords[0][1]
    lon, lat = transform(xyProj, latlonProj, x, y)
    print "<node id=\"%d\" action=\"create\" visible=\"true\" lat=\"%f\" lon=\"%f\" >" % (id, lat, lon)
    print "  <tag k=\"natural\" v=\"peak\" />"
    print "  <tag k=\"ele\" v=\"%0.1f\" />" % new_position.ele
    print "  <tag k=\"source\" v=\"srtm-adjust\" />"
    print "</node>"

#TODO get bbox from sqare name
bbox = (51, 86, 52, 87)
srtm = read_file('peaks-json/N51E086.json')
osm = read_overpass(bbox)

osm_tree = STRtree(osm)

osm_id_placeholder = -1
#TODO argument of a function
merge_radius_m = 150

#TODO: write XML to file instead of stdout
print """<?xml version='1.0' encoding='UTF-8'?>
<osm version='0.6' generator='JOSM'>"""
for peak in srtm:
    candidates = osm_tree.query(peak.buffer(merge_radius_m))
    candidates = sorted(candidates, cmp=lambda a, b: cmp(a.distance(peak), b.distance(peak)))
    if candidates:
        best_choice = candidates[0]
        adjust(best_choice, peak)
    else:
        append(osm_id_placeholder, peak)
        osm_id_placeholder = osm_id_placeholder - 1

print "</osm>"

#1. Exist in OSM, exist in SRTM - adjust
#2. Exist in OSM, not exist in SRTM - ?warning?
#3. Not exist in OSM, exist in SRTM - append
