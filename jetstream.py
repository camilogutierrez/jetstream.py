#!/usr/bin/env python3

"""
jetstream.py makes beautiful maps of the atmospheric jet stream.
"""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

__version__ = "0.1"
__author__ = "Geert Barentsen (geert@barentsen.be)"
__copyright__ = "Copyright 2014 Geert Barentsen"

import matplotlib as mpl
mpl.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib import colors
from mpl_toolkits import basemap
from pydap import client
import netCDF4
import numpy as np
import datetime
import argparse
import sys, os

A = {'r': 52/255., 'g': 152/255., 'b': 219/255.}  # blue
B = {'r': 231/255., 'g': 76/255., 'b': 60/255.}   # red
C = {'r': 241/255., 'g': 196/255., 'b': 15/255.}  # orange

COLORMAP = colors.LinearSegmentedColormap('jetstream',
                                          {'red':   [(0.0, 1.0, 1.0),
                                                     (0.25, A['r'], A['r']),
                                                     (0.75, B['r'], B['r']),
                                                     (1.0, C['r'], C['r'])],
                                           'green': [(0.0, 1.0, 1.0),
                                                     (0.25, A['g'], A['g']),
                                                     (0.75, B['g'], B['g']),
                                                     (1.0, C['g'], C['g'])],
                                           'blue':  [(0.0, 1.0, 1.0),
                                                     (0.25, A['b'], A['b']),
                                                     (0.75, B['b'], B['b']),
                                                     (1.0, C['b'], C['b'])],
                                           'alpha': [(0.0, 0.0, 0.0),
                                                     (0.15, 1.0, 1.0),
                                                     (1.0, 1.0, 1.0)]})

class JetStreamMap():

    def __init__(self, lon1=-140, lon2=40, lat1=20, lat2=70):
        self.lon1, self.lon2 = lon1, lon2
        self.lat1, self.lat2 = lat1, lat2

    def render(self, data, vmin=80, vmax=220, title=None):
        # self.fig = plt.figure(figsize=(9, 9*(9/16.)))
        self.fig = plt.figure(figsize=(10, 5))
        self.fig.subplots_adjust(0.05, 0.15, 0.95, 0.88,
                                 hspace=0.0, wspace=0.1)
        self.map = basemap.Basemap(projection='cyl',
                                   llcrnrlon=self.lon1, llcrnrlat=self.lat1,
                                   urcrnrlon=self.lon2, urcrnrlat=self.lat2,
                                   resolution="c", fix_aspect=False)

        self.map.pcolormesh(data.lon, data.lat, data.windspeed,
                            cmap=COLORMAP, vmin=vmin, vmax=vmax, alpha=None)
        self.colorbar = self.map.colorbar(location='bottom',
                                          pad=0.1, size=0.25,
                                          ticks=[100, 150, 200, 250])
        self.colorbar.ax.set_xlabel('Average wind speed at 250 mb (km/h)',
                                    fontsize=16)
        self.map.drawcoastlines(color='#7f8c8d', linewidth=0.5)
        self.map.fillcontinents('#bdc3c7', zorder=0)
        self.fig.text(.05, .91, title, fontsize=24, ha='left')
        return self.fig


class JetStreamData():
    """Abstract base class, in case other data sources turn up"""

    def __init__(self):
        self.load()

    def create_map(self, level, timestr, west, east, south, north):
        if level == 250:
            title = "Jet Stream %s" % timestr
        else:
            title = "Winds %d mb %s" % (level, timestr)

        mymap = JetStreamMap(lon1=west, lon2=east, lat1=south, lat2=north)
        mymap.render(self, title=title)
        return mymap

class ERAJetStreamData(JetStreamData):

    def __init__(self, filename):
        self.data = netCDF4.Dataset(filename)

    def list_levels(self):
        return self.data['level'][:]

    def calc_windspeed(self, idx, level, sensitivity=0):
        # times = netCDF4.num2date(data.variables['time'],
        # data.variables['time'].units)
        # print("times:", times)

        # Find the index for the appropriate pressure level
        for levindex, millibars in enumerate(self.data['level']):
            if millibars == level:
                break
        else:
            raise ValueError("No %d hPa level (maybe check with -L?)" % level)

        lon = self.data.variables['longitude'][:]
        lat = self.data.variables['latitude'][:]

        # Set a sensitivity factor
        if not sensitivity:
            if level == 250:    # jetstream, big winds
                sensitivity = 3.5
            else:                    # anywhere else, the winds are smaller
                sensitivity = 7.5

        windspeed = (sensitivity *
            np.sqrt(self.data.variables['u'][idx][levindex][:]**2
                    + self.data.variables['v'][idx][levindex][:]**2))

        # Only take the first element of the windspeed, the 250 hPa level
        # windspeed = windspeed[day]

        # Shift grid from 0 to 360 => -180 to 180
        windspeed, lon = basemap.shiftgrid(180, windspeed, lon, start=False)

        self.lon, self.lat, self.windspeed = lon, lat, windspeed

def parse_args():
    """Parse commandline arguments."""
    parser = argparse.ArgumentParser()

    parser.add_argument('-', '--threshold', action='store',
                        dest='threshold', type=float, default=0.0,
                        help="Threshold. If 0, will use 3.6 for the jetstream"
                             " and 7.5 for any other level.")
    parser.add_argument('-a', '--area', action='store',
                        dest='area', default='-180,180,-70,74',
                        help="Area to plot: west,east,south,north"
                             " (default: -180,180,-70,74). Doesn't work yet.")
    parser.add_argument('-l', '--level', action='store', dest='level',
                        type=int, default=250,
                        help="Pressure level to plot, in millibars."
                        " 1000 for sea level, 775 for around 7000 feet,"
                        " 250 for the jetstream")
    parser.add_argument('-o', '--outdir', action='store', dest='outdir',
                        default='outdir',
                        help="Output directory (will be created if needed)")
    parser.add_argument('-d', '--dpi', action='store', dest='dpi',
                        type=int, default=100,
                        help="DPI to save images (default 100)")

    parser.add_argument('-L', '--list-levels', action="store_true",
                        default=False, dest='listlevels',
                        help="List levels available in the data file")

    parser.add_argument('datafile',
                        help="The datafile, in netCDF4 format, file.nc")

    return parser.parse_args(sys.argv[1:])

if __name__ == '__main__':
    args = parse_args()

    west, east, south, north = ( float(l.strip())
                                 for l in args.area.split(',') )
    # for North America maybe try -134, -74, 26, 52 ?

    JSdata = ERAJetStreamData(args.datafile)

    if args.listlevels:
        print("Levels available in dataset %s:" % args.datafile)
        for level in JSdata.list_levels():
            print("   ", level)
        sys.exit(0)

    if not os.path.exists(args.outdir):
        os.mkdir(args.outdir)
    elif not  os.path.isdir(args.outdir):
        print("Can't create dir %s: there's a file by that name" % args.outdir)
        sys.exit(1)

    timeunits = JSdata.data['time'].units
    cal = JSdata.data['time'].calendar
    for i, t in enumerate(JSdata.data['time']):
        thedate = netCDF4.num2date(t, units=timeunits, calendar=cal)
        timestr = thedate.strftime("%Y-%m-%d")

        JSdata.calc_windspeed(i, args.level)

        mymap = JSdata.create_map(args.level, timestr, west, east, south, north)

        figname = '%s/%s-%d.png' % (args.outdir, timestr, args.level)
        mymap.fig.savefig(figname, dpi=args.dpi)
        print(figname)
        plt.close()

