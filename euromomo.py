#!/usr/bin/env pytho

import re
import sys
import math
import os.path
from PIL import Image
import pytesseract
import datetime
import numpy as np
import argparse
import csv

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (0, 96, 0)
RED   = (193, 5, 52)
BLUE  = (0, 0, 255)

# May change depending on resolution
Y_AXIS_OFF = 72
FIRST_GRAPH_OFF = 83

ALL_COUNTRIES = [
"Austria",
"Belgium",
"Denmark",
"Estonia",
"Finland",
"France",
"Germany (Berlin)",
"Germany (Hesse)",
"Greece",
"Hungary",
"Ireland",
"Italy",
"Luxembourg",
"Malta",
"Netherlands",
"Norway",
"Portugal",
"Spain",
"Sweden",
"Switzerland",
"UK (England)",
"UK (Northern Ireland)",
"UK (Scotland)",
"UK (Wales)",
]

def ocr_country_name(im, VOFF):
    HOFF = Y_AXIS_OFF+2
    VOFF = VOFF+1
    cropped = im.crop( (HOFF, VOFF, HOFF+140, VOFF+21) )
    name = pytesseract.image_to_string(cropped)
    name = name.rstrip("_-— \n")
    if not name:
        # Try with a different mode
        name = pytesseract.image_to_string(cropped, config='--psm 6')
        name = name.rstrip("_-— \n")
    return name

def detect_graph_starts(px, im):
    VOFF = FIRST_GRAPH_OFF
    HOFF = Y_AXIS_OFF
    offs = []
    start, end = None, None
    for i in range(VOFF, im.height): 
        if start is not None and px[HOFF,i] == WHITE: 
            end = i 
            offs.append( (start,end) ) 
            start = None 
        elif start is None and px[HOFF,i] == BLACK: 
            start = i 
    return offs

def detect_zticks(px, ranges):
    # Ticks are one pixel to the left of the y axis
    HOFF = Y_AXIS_OFF-1
    ticks = []
    for i in range(ranges[0], ranges[1]):
        if px[HOFF,i] == BLACK:
            ticks.append(i)
    assert len(ticks) == 4
    return ticks

def detect_xticks(im, px, bottom):
    VOFF = bottom + 5
    ticks = []
    for x in range(Y_AXIS_OFF, im.width):
        if px[x,VOFF] == BLACK:
            ticks.append(x)
    return ticks

def ocr_date(im, bottom, tick):
    global counter
    TOP = bottom + 8
    LEFT = tick - 7
    RIGHT = tick + 7
    BOTTOM = TOP + 50
    dateimg = im.crop( (LEFT, TOP, RIGHT, BOTTOM) )
    dateimg = dateimg.rotate(270, expand=True)
    date = pytesseract.image_to_string(dateimg)
    date = re.sub(r'^[^0-9]*', '', date)
    date = re.sub(r'[^0-9]*$', '', date)
    return date

def detect_graph_width(px, centerline):
    HOFF = Y_AXIS_OFF
    i = HOFF
    while px[i,centerline] != WHITE:
        i += 1
    return HOFF, i

def detect_points(px, x_range, y_range):
    points = []
    for x in range(*x_range):
        # Z-score
        greens = [ y for y in range(*y_range) if px[x,y] == GREEN ]
        # Delay-adjusted Z-score
        blues  = [ y for y in range(*y_range) if px[x,y] == BLUE  ]
        green_score = None
        blue_score = None
        if greens:
            green_score = sum(greens)/len(greens)
        if blues:
            blue_score = sum(blues)/len(blues)
        points.append( (
            x,
            green_score if green_score is not None else float('NaN'),
            blue_score if blue_score is not None else float('NaN')
            )
        )
    return points

def scale_x_time(x, xticks):
    xticks_pixels = [x[0] for x in xticks]
    xticks_pixels = np.asarray(xticks_pixels)

    # Scale the x location of the point to the *nearest* x tick
    # Then use the adjacent tick to scale
    nearest_tick_idx = (np.abs(xticks_pixels - x)).argmin()
    adjacent_tick_idx = nearest_tick_idx - 1 if nearest_tick_idx != 0 else nearest_tick_idx + 1
    
    t1 = xticks[nearest_tick_idx][1]
    t2 = xticks[adjacent_tick_idx][1]
    if t1 > t2: timespan = t1 - t2
    else: timespan = t2 - t1
    
    p1 = xticks[nearest_tick_idx][0]
    p2 = xticks[adjacent_tick_idx][0]
    if p1 > p2: pixelspan = p1 - p2
    else: pixelspan = p2 - p1

    pixel_frac = (x - p1) / pixelspan
    timedelta = pixel_frac * timespan
    x_time = t1 + timedelta

    # These were to help convince myself that the calculation was correct
    # Can be re-enabled to help debug if it turns out it wasn't
    #print("Pixel location %d is closest to tick at index %d (%d)" % (x, nearest_tick_idx, p1))
    #print("Nearest tick time is: %s" % str(t1))
    #print("Time span is: %s" % str(timespan))
    #print("Pixel span is: %d" % pixelspan)
    #print("Pixel fraction is: %f" % pixel_frac)
    #print("Time delta is: %s" % str(timedelta))
    #print("Adjusted x time is: %s" % str(x_time))
    return x_time

def scale_zscore(pt, zticks):
    z_8, z_4, z_0, z_minus_4 = zticks
    # How many pixels is one z?
    pixelspan = z_4 - z_0
    # How many pixels from the x axis is our point?
    delta = pt - z_0
    # each pixelspan = 4 z
    z_score = (delta / pixelspan) * 4
    return z_score

parser = argparse.ArgumentParser(description='Scrape EuroMOMO data from an image')
parser.add_argument('png', help='EuroMOMO PNG for z-score data (from bulletin PDF)')
parser.add_argument('--assume-italy', action='store_true',
        help='In case of OCR failure on country name, assume the missing country is Italy')
args = parser.parse_args()

# Image load
im = Image.open(args.png)
im = im.convert('RGB')
px = im.load()

if not (im.width == 1200 and
        im.height == 2400):
    print("ERROR: This script assumes an input image of 1200x2400!", file=sys.stderr)
    print("ERROR: Your image is %dx%d. You will need to adjust some constants. Aborting." %
            (im.width, im.height), file=sys.stderr)
    sys.exit(1)

# Find the y-axis for each subgraph
# Finland and Switzerland are sometimes omitted
starts = detect_graph_starts(px,im)
COUNTRIES = [ ocr_country_name(im, st) for st,_ in starts ]

# Try to fill in failed OCR. Basically, see if its neighbors
# are found in the full country list, and if so, infer that
# the missing country must be between them.
already_tried_italy = False
for i in range(len(COUNTRIES)):
    if not COUNTRIES[i]:
        print("WARNING: Failed to OCR country name for graph %d" % i, file=sys.stderr)
        if args.assume_italy:
            if not already_tried_italy:
                COUNTRIES[i] = 'Italy'
                print("WARNING: Assuming it's Italy since you said so", file=sys.stderr)
                already_tried_italy = True
                continue
            else:
                print("ERROR: You said to assume it's Italy, but there are multiple "
                      "missing countries. Something is wrong. Aborting!", file=sys.stderr)
                sys.exit(1)

        # Attempt repair (!)
        candidate_1 = None
        candidate_2 = None
        if i-1 > 0:
            try:
                candidate_1 = ALL_COUNTRIES[ALL_COUNTRIES.index(COUNTRIES[i-1])+1]
            except ValueError:
                pass
        if i+1 < len(COUNTRIES):
            try:
                candidate_2 = ALL_COUNTRIES[ALL_COUNTRIES.index(COUNTRIES[i+1])-1]
            except ValueError:
                pass
        if candidate_1 is not None and \
           candidate_2 is not None and \
           candidate_1 == candidate_2:
            COUNTRIES[i] = candidate_1
            print("WARNING: Repair succeeded, guessed %s" % candidate_1, file=sys.stderr)
        else:
            name = "FAILED_OCR_%02d" % i
            COUNTRIES[i] = name
            print("WARNING: Repair failed, using %s" % name, file=sys.stderr)
    elif COUNTRIES[i] not in ALL_COUNTRIES:
        print("WARNING: country name '%s' is not in the list of known countries. OCR error?" % COUNTRIES[i],
                file=sys.stderr)
        ocr_errors = {'Haly': 'Italy'}
        if COUNTRIES[i] in ocr_errors:
            print("WARNING: Repaired common OCR issue %s => %s" % (COUNTRIES[i], ocr_errors[COUNTRIES[i]]),
                    file=sys.stderr)
            COUNTRIES[i] = ocr_errors[COUNTRIES[i]]

country_starts = dict(zip(COUNTRIES, starts))

# Next to the y-axis there are ticks for z scores
# corresponding to 8, 4, 0, -4
country_ticks = { c: detect_zticks(px,st) for c, st in country_starts.items() }

# Pull out the dates
xticks = []
graph_bottom = starts[-1][1]
xtick_locs = detect_xticks(im, px, graph_bottom)
for tick in xtick_locs:
    date = ocr_date(im, graph_bottom, tick)
    # Arbitrary choice here: pick Monday as the day to represent
    # the week as a whole. Dunno if this is correct.
    r = datetime.datetime.strptime(date + '-1', "%Y-%W-%w")
    xticks.append((tick, r))

# Detect chart width using the x axis
# Seems to always be (48, 752), but double-check
country_widths = {}
for c in country_ticks:
    _, _, center, _ = country_ticks[c]
    left, right = detect_graph_width(px, center)
    assert (left,right) == (72, 1157)
    country_widths[c] = (left,right)

country_points = {}
for c in COUNTRIES:
    points = detect_points(px, country_widths[c], country_starts[c])
    country_points[c] = points

# At this point we have:
# - The bounds for each country's graph
# - The green and blue points, in terms of pixel locations
# - The locations of each y tick, where each tick is one z score (std dev)
# - The locations of each x tick in terms of pixels, and the
#   corresponding week as a datetime
# So now we want to use those to output a standardized row for each point
#   country,date,z_score,delay_z_score

# Open CSV and write the header
base, extension = os.path.splitext(args.png)
outfile_name = base + '.csv'
of = open(outfile_name, 'w', newline='')
wr = csv.writer(of)
wr.writerow(['Country', 'Timestamp', 'Timestamp_Px', 'Z_Score', 'Z_Score_Px', 'Delay_Z_Score', 'Delay_Z_Score_Px'])

for c in COUNTRIES:
    widths = country_widths[c]
    starts = country_starts[c]
    zticks = country_ticks[c]
    points = country_points[c]
    
    for x, g, b in points:
        x_time = scale_x_time(x, xticks)
        if not math.isnan(g):
            g_str = str(g)
            g_zscore = str(scale_zscore(g, zticks))
        else:
            g_str = "N/A"
            g_zscore = "N/A"
        if not math.isnan(b):
            b_str = str(b)
            b_zscore = str(scale_zscore(b, zticks))
        else:
            b_str = "N/A"
            b_zscore = "N/A"

        wr.writerow([c, str(x_time), str(x), g_zscore, g_str, b_zscore, b_str])
of.close()
print("INFO: wrote output to %s" % outfile_name, file=sys.stderr)
