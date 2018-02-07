#!/usr/bin/env python

import os
import re
import argparse
import logging
from find_peaks import find_peaks
from find_contours import find_contours
from tqdm import tqdm

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

parser = argparse.ArgumentParser()
parser.add_argument("-I", "--input", help="Input directory",
                    default="srtm-tif")
parser.add_argument("-OC", "--output-contours", help="Contours Output directory",
                    default="contours-json")
parser.add_argument("-OP", "--output-peaks", help="Peaks Output directory",
                    default="peaks-json")
parser.add_argument("-i", "--interval",
                    default=10, help="Contours interval in meters, default 10")
parser.add_argument("-t", "--mapnik-config-template",
                    default='contours.xml', help="Template of Mapnik config")
parser.add_argument("-C", "--mapnik-config",
                    default='mapnik-config',
                    help="Mapnik config files directory")
parser.add_argument("-NP", "--no-peaks",
                    default=False,
                    help="Dont generate peaks")
parser.add_argument("-NC", "--no-contours",
                    default=False,
                    help="Dont generate contours")

args = parser.parse_args()

files = os.listdir(args.input)
files = filter(lambda f: os.path.splitext(f)[1].lower() == ".tif", files)
files = sorted(files)

for f in tqdm(files):
    fin = os.path.join(args.input, f)
    name = re.sub(r'(.*?).hgt.tif$', "\\1", f)
    fout = re.sub(r'(.*?).hgt.tif$', "\\1.json", f)

    fout_contours = os.path.join(args.output_contours, fout)
    if not args.no_contours:
        print("Readind contours %s to %s" % (fin, fout_contours))
        find_contours(fin, fout_contours, int(args.interval))

    fout_peaks = os.path.join(args.output_peaks, fout)
    if not args.no_peaks:
        print("Readind peaks %s to %s" % (fin, fout_peaks))
        find_peaks(fin, fout_peaks, int(args.interval), min_prominence=50)

    with open(args.mapnik_config_template) as rh:
        tmpl = str(rh.read())
        tmpl = re.sub(r'\{NAME\}', name, tmpl)
        with open(os.path.join(args.mapnik_config, name + ".xml"), 'w') as wh:
            wh.write(tmpl)
