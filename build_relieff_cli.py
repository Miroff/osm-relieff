#!/usr/bin/env python

import os
import re
import argparse
import logging
from find_contours import find_contours
from tqdm import tqdm

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

parser = argparse.ArgumentParser()
parser.add_argument("-I", "--input", help="Input directory",
                    default="srtm-tif")
parser.add_argument("-O", "--output", help="Output directory",
                    default="contours-json")
parser.add_argument("-i", "--interval",
                    default=10, help="Contours interval in meters, default 10")
args = parser.parse_args()

files = os.listdir(args.input)
files = filter(lambda f: os.path.splitext(f)[1].lower() == ".tif", files)
files = sorted(files)

for f in tqdm(files):
    fin = os.path.join(args.input, f)
    fout = re.sub(r'(.*?).hgt.tif$', "\\1.json", f)
    fout = os.path.join(args.output, fout)
    print("Readind %s to %s" % (fin, fout))
    find_contours(fin, fout, int(args.interval))
#
#     features = read_contours(fin)
#chmod
