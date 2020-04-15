EuroMOMO Data Scraper
=====================

*Note: if all you want is the data, just go have a look at the `csvs`
directory. But read on for important caveats about its accuracy.*

Tool to extract underlying data from EuroMOMO z-score images.

The images were extracted from the PDF bulletins using:

```
pdfimages -all bulletin.pdf prefix
```

(Thanks to [@LoneVoltsAhead](https://twitter.com/LoneVoltsAhead) for pointing me to where to find
previous bulletins in [this tweet](https://twitter.com/LoneVoltsAhead/status/1250121904289177602).)

The image we want is usually the last one in the PDF. Unfortunately
depending on the exact version of the PDF bulletin, the chart we want
may be split into three pieces. In that case I reassembled them using
ImageMagick:

```
convert image1.png image2.png image3.png -append full_image.png
```

The script currently assumes that each image is exactly 1200x2400
pixels, which is true for all the 2020 bulletins so far. A number of
constants in the script will need to be adjusted if this changes. The
script will yell at you and exit if this precondition is violated.

The PDFs and PNGs for the first 14 weeks of 2020 can be found in `pdfs`
and `pngs` directories, respectively.

Usage
-----

```
usage: euromomo.py [-h] [--assume-italy] png

Scrape EuroMOMO data from an image

positional arguments:
  png             EuroMOMO PNG for z-score data (from bulletin PDF)

optional arguments:
  -h, --help      show this help message and exit
  --assume-italy  In case of OCR failure on country name, assume the missing
                  country is Italy
```

Where `png` is a PNG extracted from the PDF bulletin. Output will be
written to a file with the same name as the input, but with `.csv`
instead of `.png`.

For example, to generate a CSV for the first week of 2020:

```
$ python euromomo.py pngs/2020_01.png
WARNING: Failed to OCR country name for graph 10
WARNING: Repair succeeded, guessed Italy
INFO: wrote output to pngs/2020_01.csv
```

As behooves all well-behaved programs, informational messages are sent
to `stderr` so they can be suppressed if desired.

Dependencies
------------

Python 3. Packages: pillow, pytesseract, and numpy.

OCR Issues
----------

A further complication comes from the fact that each report may include
a slightly different set of countries. To deal with this, the script
uses OCR (Tesseract) to read out the country name from each sub-graph.

If the OCR fails in a noticeable way (by returning an empty string) for
a country, the script will attempt to guess the country name by looking
at its (hopefully successfully OCRed) neighbors, and then consulting a
master list of the countries I've seen in the EuroMOMO data so far to
attempt to fill in the missing one based on its position. This is done
fairly conservatively (by making sure that both the predecessor and
successor give the same country name), but it's not foolproof. In the
files I've tested, the only country that ever fails to be identified
properly is Italy. If guessing fails, the country name will be replaced
with FAILED_OCR_x, where x is the 0-indexed position of the graph in the
PNG file.

OCR is also used to read the week numbers (in YYYY-WW format) off the
x-axis tick labels on the bottom. This could be somewhat inaccurate, and
users are strongly advised to double-check that the dates are correct,
in particular.

Other Considerations
--------------------

Reading data from pixels is an inexact science. Many of the "points"
transcribed here are interpolations from whatever plotting package were
originally used. I don't know exactly where the original points are, so
I have just transcribed every pixel along the x-axis. TODO: maybe a
smarter way would be to figure out how many pixels = 1 week, and only
sample those points?

In some cases, there are multiple pixels in a single vertical position
on the x-axis. In such cases, I simply take the average of the values
displayed.

Warranty
--------

None. Use this at your own risk. Please double- and triple-check my work
before trying to use this for something important like, say, pandemic
modeling.

License
-------

Public domain.
