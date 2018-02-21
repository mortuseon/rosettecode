from PIL import Image, ImageDraw
import numpy as np
import sys
import math
import os
import glob
import time

#todo

# Open image given filename

outputDir = "C:\Users\Hanne\Documents\Edinburgh\Malaria\RosetteCode\output\\" # NOTE don't forget to end with \\
csvFile = ""
errFile = ""
testDir = ""

#converting to array 
def generateSortedArray(imArr, width, height):
    # First, generate an array of the brightness values
    # Should be stored in tuple as follows:
    # (xCoord, yCoord, brightness)
    tempArray = []
    for x in range(0, height):
        for y in range(0, width):
            tempTup = (x, y, imArr[x,y])
            tempArray.append(tempTup)

    # Then sort it
    # NOTE: May be much faster to sort it as we build it
    tempArray.sort(key=lambda tup: tup[2])
    tempArray.reverse()

    return tempArray
    
# threshold on parameter - choose dynamically?
# Tidy up by denoising?

# Recycle EB code to identify bright spot centers (trophy)

#EB function to identify EB candidates copied below:
    #should comment out things like fillholes, won't need for higher-resolution image like rosetting 
    #can skip all stack-related functions, won't need MaxProj, will instead take tempArray directly
    #haven't defined detection thresholds yet - should this be dynamic? 
    #replace all references to EBs with 'trophs' 

def getCandidateEBs(eqMaxproj):

    # Created (new) temporary image 'object' from the 2D array equalised stack ('max projection') and defines as 'temp'. Converts temp to luminosity only* could remove
    # Converts...back to array (grey) and copies it
    temp = Image.fromarray(eqMaxproj)
    if convertFlag:
        temp = temp.convert('I')
    gray = temp.convert('L')

    thresholded = np.asarray(gray).copy()

    # Create 'blobs' by setting all pixels with brightness <detectionThreshold as 0 (black) and all >detectionThreshold as white (255)
    thresholded[thresholded < detectionThresholdVal] = 0
    thresholded[thresholded >= detectionThresholdVal] = 255

    ogThresholded = thresholded

    # Clean up thresholded image by filling small gaps and removing lone pixels
    # (Note the order of operations below have been defined arbitrarily)
    #thresholded = fillHoles(thresholded, 2)
    #thresholded = fillHoles(thresholded, 2)
    #thresholded = removeNoise(thresholded,2)               
    #thresholded = fillHoles(thresholded, 3)
    #thresholded = removeNoise(thresholded,3)        
    
    #  Initialises empty array for ebs (later returned)
    ebs = []

    # Iterates across every pixel in (resized!) image - all 512 of them!
        #image size here will be different, and not square...resize? 
    for y in range (0, 512):
        for x in range (0, 512):
            # Ignores those set to zero (black) by threshold and continues reading
            if thresholded[y, x] == 0:
                continue
            elif y == 511:
                continue
            elif thresholded[y+1, x] == 0:
                continue
            else:

                # min and max co-ordinates define the boundaries of the pixels. yTemp and xTemp save temporary co-ordinates which iterate through each pixel
                # the above prevents x and y being changed before their neighbours are known
                minx = x
                maxx = x
                miny = y
                maxy = y

                yTemp = y
                xTemp = x
                
                rightFound = False
                leftFound = False
                bottomFound = False
                
                #  Starting from the top edge, expand the bounding box left, right, and down until it encompasses the EB
                while not (rightFound and leftFound and bottomFound):
                    
                    # Expand to the right
                    yTemp = miny
                    while yTemp <= maxy:

                        if maxx + 1 == 512:
                            rightFound = True
                            break
                            
                        if thresholded[yTemp, maxx + 1] == 255:
                            maxx += 1
                            bottomFound = False
                            yTemp = miny
                            continue
                        elif yTemp == maxy:
                            rightFound = True

                        yTemp += 1
                    
                    # Expand to the left
                    yTemp = miny
                    while yTemp <= maxy:

                        if minx == 0:
                            leftFound = True
                            break

                        if thresholded[yTemp, minx - 1] == 255:
                            minx -= 1
                            bottomFound = False
                            yTemp = miny
                            continue
                        elif yTemp == maxy:
                            leftFound = True
                            
                        yTemp += 1

                        
                    # Expand to the bottom
                    xTemp = minx
                    while xTemp <= maxx:

                        if maxy == 511:
                            bottomFound = True
                            break

                        if thresholded[maxy + 1, xTemp] == 255:
                            maxy += 1
                            leftFound = False
                            rightFound = False
                            xTemp = minx
                            continue
                        elif xTemp == maxx:
                            bottomFound = True
                            
                        xTemp += 1
                    

                # Ignore if it's an edge boi
                if maxx == 511 or maxy == 511 or minx == 0:
                    print "DISREGARDING: EB at edge of image, coordinates " + str(minx) + ", " + str(miny)
                    continue

                # Defines box size (width and height via x and y co-ordinates on either side). Radius via dividing by 2
                hDist = (maxx - minx + 1) / 2.0
                vDist = (maxy - miny + 1) / 2.0

                # Makes halfBoxWidth the largest dimension, whether that be horizontal or vertical
                halfBoxWidth = hDist if hDist > vDist else vDist

                estArea = (halfBoxWidth * halfBoxWidth) * math.pi

                # Get actual area of EB for comparison to check how spherical it is
                areaSum = 0
                for i in range(miny, maxy + 1):
                    for j in range(minx, maxx + 1):
                        if(thresholded[i][j] == 255):
                            areaSum += 1

                # Replace thresholded image with new image in which the EB is erased, to prevent the algorithm identifying a 'new' EB at each row (which is actually the same EB)
                thresholded = eraseEB(thresholded, minx, miny, maxx, maxy)

                # defined above as arbitrary minimum size of EB, below which identified spots are ignored/not boxed
                if halfBoxWidth < minBoxWidth:
                    print "DISREGARDING: undersized candidate EB at coordinates " + str(minx) + ", " + str(miny)
                    continue

                if halfBoxWidth >= maxBoxWidth:
                    print "DISREGARDING: oversized candidate EB"
                    continue

                # Check difference of area to expected area to assess circularity
                # If perfect match, score is 1
                print "maxx: %d; minx: %d; maxy: %d; miny: %d" % (maxx, minx, maxy, miny)
                print "radius: %d; hDist: %.1f; vDist: %.1f; estArea: %.2f, areaSum: %d" % (halfBoxWidth, hDist, vDist, estArea, areaSum)
                circularity = 1.0 - math.fabs((float(areaSum) / float(estArea)) - 1.0)
                if circularity < minCircularity:
                    print "DISREGARDING: EB at " + str(minx) + ", " + str(miny) + " non-circular with score %f (may be overlap)" % circularity
                    continue

                # Store diameter before scaling box by margin
                ebDiam = halfBoxWidth * 4
                
                if (ebDiam * 16) > 1000:
                    print "DISREGARDING: suspected RB of size %dnm" % (ebDiam * 16)
                    continue

                # Increases boxwidth by our defined safety margin (defined above as 1.5 i.e. 50% larger than native box size)
                halfBoxWidth *= boxMargin

                # Finds centre of each co-ordinate
                centerX = (minx + maxx) / 2
                centerY = (miny + maxy) / 2

                # Subtract centre from the boxwidth to find origin for box margin
                xOrigin = centerX - halfBoxWidth
                yOrigin = centerY - halfBoxWidth

                # TODO do this more neatly.. avoids crashing on negative index
                if xOrigin < 0 or yOrigin < 0:
                    print "DISREGARDING: Edge boy"
                    continue

                # Multiply by two to get the full box width
                boxWidth = halfBoxWidth * 2

                # Multiply all coords by 2 to translate to full-size (1024x1024) coords
                # Note that the EB analysis performed on full 1024x1024 img
                # Identification performed on 512x512 in interest of speed
                boxWidth *= 2
                xOrigin *= 2
                yOrigin *= 2

                # Initialises empty 'dictionary'
                thisEB = {}
                # Defines EB 'id' (number) as order in which it is identified - allows unique naming
                thisEB['id'] = len(ebs)
                # int de-floats. Defines values in dictionary (defines object properties) such as xmin as those identified above, can be used to draw box, identify centre
                thisEB['xMin'] = int(xOrigin)
                thisEB['yMin'] = int(yOrigin)
                thisEB['xMax'] = min(int(xOrigin + boxWidth), 1023)
                thisEB['yMax'] = min(int(yOrigin + boxWidth), 1023)
                thisEB['pixelSize'] = ebDiam
                thisEB['pixelArea'] = areaSum
                thisEB['circularity'] = circularity
                thisEB['size'] = ebDiam * 16

                # appends EB dictionary with pertinent information/properties to the list 'ebs' which is returned below, can thus be analysed
                ebs.append(thisEB)
                print "Found an EB at coordinates " + str(int(xOrigin)) + ", " + str(int(yOrigin))

    outImg = Image.fromarray(ogThresholded)
    rgbimg = Image.new("RGB", outImg.size)
    rgbimg.paste(outImg)

   #probably won't need this, as this is polarity-related
    draw = ImageDraw.Draw(rgbimg)
    for eb in ebs:
        draw.line((eb['xMin'],eb['yMin'],eb['xMax'],eb['yMin']),fill="red",width=1)
        draw.line((eb['xMax'],eb['yMin'],eb['xMax'],eb['yMax']),fill="red",width=1)
        draw.line((eb['xMax'],eb['yMax'],eb['xMin'],eb['yMax']),fill="red",width=1)
        draw.line((eb['xMin'],eb['yMax'],eb['xMin'],eb['yMin']),fill="red",width=1)
    del draw

    return ebs


#RBC identification - count clusters
    #add to count

#Troph (bright spot) identification
    #based on size of spot
    #...and circularity (?)
    #likely to be on edge of RBC
    #add to count

#Compare locations 

#'Rosette' - count when troph + cluster are co-localised
#Compare independent troph count with rosette count - ////rosette percentage////