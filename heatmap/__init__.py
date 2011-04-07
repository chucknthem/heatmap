# vim: ai ts=4 sts=4 et sw=4
#heatmap.py v1.1 20110402
from PIL import Image,ImageChops
import os
import random
import math
import sys
import colorschemes

KML_START = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Folder> """
KML_OVERLAY = """
    <GroundOverlay>
      <Icon>
        <href>%s</href>
      </Icon>
      <LatLonBox>
        <north>%2.16f</north>
        <south>%2.16f</south>
        <east>%2.16f</east>
        <west>%2.16f</west>
        <rotation>0</rotation>
      </LatLonBox>
    </GroundOverlay>"""
KML_TIMESPAN_OVERLAY = """
    <GroundOverlay>
      <name>%s</name>
      <TimeSpan>
        <begin>%s</begin>
        <end>%s</end>
      </TimeSpan>
      <Icon>
        <href>%s</href>
      </Icon>
      <LatLonBox>
        <north>%2.16f</north>
        <south>%2.16f</south>
        <east>%2.16f</east>
        <west>%2.16f</west>
        <rotation>0</rotation>
      </LatLonBox>
    </GroundOverlay>"""
KML_END = """</Folder></kml>"""

KML = KML_START + KML_OVERLAY + KML_END

class Heatmap:
    """
    Create heatmaps from a list of 2D coordinates.
    
    Coordinates autoscale to fit within the image dimensions, so if there are 
    anomalies or outliers in your dataset, results won't be what you expect. 

    The output is a PNG with transparent background, suitable alone or to overlay another
    image or such.  You can also save a KML file to use in Google Maps if x/y coordinates
    are lat/long coordinates. Make your own wardriving maps or visualize the footprint of 
    your wireless network.  
 
    Most of the magic starts in heatmap(), see below for description of that function.
    """
    def __init__(self):
        self.minXY = ()
        self.maxXY = ()

    def _init(self, dotsize, opacity, size, scheme):
        self.dotsize = dotsize
        self.opacity = opacity
        self.size = size
        # Actual size of the image where heatmap points can be in to
        # ensure that dots fit inside the image.
        self.actual_size = (size[0] - dotsize, size[1] - dotsize)
        if scheme not in self.schemes():
            tmp = "Unknown color scheme: %s.  Available schemes: %s"  % (scheme, self.schemes())
            raise Exception(tmp)

        self.colors = colorschemes.schemes[scheme]
        self.dot = self._buildDot(self.dotsize)
    
    def heatmap(self, points, fout, dotsize=150, opacity=128, size=(1024,1024), scheme="classic"):
        """
        points  -> an iterable list of tuples, where the contents are the 
                   x,y coordinates to plot. e.g., [(1, 1), (2, 2), (3, 3)]
        fout    -> output file for the PNG
        dotsize -> the size of a single coordinate in the output image in 
                   pixels, default is 150px.  Tweak this parameter to adjust 
                   the resulting heatmap.
        opacity -> the strength of a single coordiniate in the output image.  
                   Tweak this parameter to adjust the resulting heatmap.
        size    -> tuple with the width, height in pixels of the output PNG 
        scheme  -> Name of color scheme to use to color the output image.
                   Use schemes() to get list.  (images are in source distro)
        """
        
        self._init(dotsize, opacity, size, scheme)

        self.imageFile = fout
        self.minXY, self.maxXY = self._ranges(points)

        img = Image.new('L', self.size, 255)
        for x,y in points:
            img.paste(0, self._translate([x,y]), self.dot)

        img.save("bw.png", "PNG")

        img = self._colorize(img, self.size, self.colors)

        img.save(fout, "PNG")


    def animated_heatmapKML(self, points_list, fout, dotsize=150, opacity=128, size=(1024,1024), scheme="classic"):
        self._init(dotsize, opacity, size, scheme)
        
        i = 0
        kml = KML_START
        for start, end, points in points_list:
            self.minXY, self.maxXY = self._ranges(points)

            img = Image.new('L', self.size, 255)
            for x,y in points:
                img.paste(0, self._translate([x,y]), self.dot)


            img = self._colorize(img, self.size, self.colors)
            imgfile = "%s%d.png" % (fout, i)
            img.save(imgfile, "PNG")

            kml += self.make_timespan_overlay(imgfile, start, end)
            i += 1

        kml += KML_END
        file(fout, "w").write(kml)
            
    def _get_kml_coords(self):
        """Return the north, south, east, west coordinates to map our data
        points onto google earth."""

        # We have to extend the maxXY and minXY coordinates of the data set 
        # to take into account the image's real size.

        # Calculate the percent difference between half a dotsize
        # and the actual_size. Then multiply that by maxXY - minXY to get the offset.
        # The offset is the number we have to add or subtract to maxXY and minXY to
        # account for the difference between image size and actual_size.
        offsetx = self.dotsize / 2.0 / float(self.actual_size[0])
        offsety = self.dotsize / 2.0 / float(self.actual_size[1])

        offsetx = offsetx * (self.maxXY[0] - self.minXY[0])
        offsety = offsety * (self.maxXY[1] - self.minXY[1])

        north = self.maxXY[1] + offsety
        south = self.minXY[1] - offsety
        east = self.maxXY[0] + offsetx
        west = self.minXY[0] - offsetx
        return (north, south, east, west)

    def make_timespan_overlay(self, img_file, begin, end):
        (north, south, east, west) = self._get_kml_coords()
        return KML_TIMESPAN_OVERLAY % (begin + " - " + end, begin, end, img_file, north, south, east, west)

    def saveKML(self, kmlFile):
        """ 
        Saves a KML template to use with google earth.  Assumes x/y coordinates 
        are lat/long, and creates an overlay to display the heatmap within Google
        Earth.

        kmlFile ->  output filename for the KML.
        """

        tilePath = os.path.basename(self.imageFile)
        (north, south, east, west) = self._get_kml_coords()
        
        bytes = KML % (tilePath, north, south, east, west)
        file(kmlFile, "w").write(bytes)

    def schemes(self):
        """
        Return a list of available color scheme names.
        """
        return colorschemes.schemes.keys() 

    def _buildDot(self, size):
        """ builds a temporary image that is plotted for 
            each point in the dataset"""
        img = Image.new("RGBA", (size,size), (0, 0, 0, 0))
        md = 0.5*math.sqrt( (size/2.0)**2 + (size/2.0)**2 )
        for x in xrange(size):
            for y in xrange(size):
                d = math.sqrt( (x - size/2.0)**2 + (y - size/2.0)**2 )
                rgbVal = int(200*d/md + 50)
                rgba = (0,0,0, 255 - rgbVal)
                img.putpixel((x,y), rgba)
        return img

    def _colorize(self, img, size, colors):
        """ use the colorscheme selected to color the 
            image densities  """
        w,h = img.size
        imgnew = Image.new('RGBA', size, (255, 255, 255, 0))
        imgpix = img.load()
        imgnewpix = imgnew.load()
        for x in xrange(w):
            for y in xrange(h):
                pix = imgpix[x,y]
                if isinstance(pix, (list, tuple)):
                    pix = pix[3]
                rgba = list(colors[pix])
                if pix <= 254: 
                    alpha = self.opacity
                    rgba.append(alpha)
                else:
                    rgba = (255, 255, 255, 0)

                imgnewpix[x,y] = tuple(rgba)
        return imgnew
            
    def _ranges(self, points):
        """ walks the list of points and finds the 
        max/min x & y values in the set """
        minX = points[0][0]; minY = points[0][1]
        maxX = minX; maxY = minY
        for x,y in points:
            minX = min(x, minX)
            minY = min(y, minY)
            maxX = max(x, maxX)
            maxY = max(y, maxY)
            
        return ((minX, minY), (maxX, maxY))

    def _untranslate(self, data_point):
        """ Translates x,y coordinates from pixel offsets into 
        data coordinates.
        This is the inverse function of self._translate"""

        x = data_point[0]
        y = data_point[1]

        x = x / float(self.actual_size[0])
        y = 1 - y / float(self.actual_size[1])
        
        x = x * (self.maxXY[0] - self.minXY[0]) + self.minXY[0]
        y = y * (self.maxXY[1] - self.minXY[1]) + self.minXY[1]
        return (x, y)

    def _translate(self, point):
        """ Translates x,y coordinates from data set into 
        pixel offsets.
        This is the inverse function of self._untranslate"""
        x = point[0]
        y = point[1]

        #normalize points into range (0 - 1)...
        x = (x - self.minXY[0]) / float(self.maxXY[0] - self.minXY[0])
        y = (y - self.minXY[1]) / float(self.maxXY[1] - self.minXY[1])

        #...and then map into our image size...
        x = int(x*(self.actual_size[0]))
        y = int((1-y)*(self.actual_size[1]))
         
        # The upper-left corner of our dot is placed at
        # the x,y coordinate we provide. 
        # we care about their center.  shift up and left so
        # the center of the dot is at the point we expect.
        # x = x - self.dotsize / 2
        # y = y - self.dotsize / 2
        # Then we need to account for the actual size of the image
        # that gets placed in the center of the image size
        # specified by the user. the actual image size is the image
        # minus half a dot size at on each edge, so the lines above 
        # and below cancel out.
        # x = x + self.dotsize / 2
        # y = y + self.dotsize / 2

        return (x,y)

if __name__ == "__main__":
    pts = []
    for x in xrange(400):
        pts.append((random.random(), random.random() ))

    print "Processing %d points..." % len(pts)

    hm = Heatmap()
    hm.heatmap(pts, "classic.png") 
