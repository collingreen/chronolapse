"""
    chronolapse.py
    @author: Collin "Keeyai" Green
    @url: keeyai.com, collingreen.com, chronolapse.com
    @summary:
        ChronoLapse is a tool for making timelapses.
        CL can save both screenshots and webcam captures, and can even do them both
        at the same time so they are 'synced' together. In addition to saving the
        images, CL has some processing tools to compile your images into video,
        create a picture-in-picture effect, and resize images.
    @license: MIT license
"""

VERSION = '2.0.0alpha'

import wx
import wx.lib.masked as masked
import logging

from easyconfig import EasyConfig

import cv2
import os, sys, shutil, argparse
import time, datetime

import tempfile
import textwrap

import math
import subprocess
import urllib, urllib2

import threading

from PIL import Image, ImageDraw, ImageFont

from chronolapsegui import *

"""

TODO:
    X replace optparse with argparse
    X remove all xml everywhere
    X add sequential/integer filenames to config persistence
    X make sequential/integer filename options work
    X VERIFY all fields get saved and updated correctly
    X remove all pickle everywhere
    X fix config file being written to wherever the current working dir is!

    X make video codec stay selected
    X add command line for sequential image format (defaults to %05d)
    X remove adjust frame

    X remove keeyai.com
    X add file menu -> quit
    X use logging module

    X support selecting cameras -- openCV doesn't do this well - exposed as config
    X opencv camera captures
    X sequential timestamps overwriting when only cam (no screenshot)

    X better timestamp options
    - update icons
    X clean up windows branching code

    - Variables in save paths %YEAR%, %MONTH%, %DAY%, %HOUR%, %MINUTE%, %SECOND%
    - Ability to enter Video Length and get FPS calculated
    - Verify multi monitor + subscreen timestamps are still visible (expect they are cut off)
    - Verify height setting controls the height of the input, not the distance from the bottom of the screen
-- Version 2.0.0

    - encode to gif - visvis.vvmovie.images2gif import writeGif
    - use existence of specified local file to prevent captures
    - chronoslices
-- Version 2.1.0

    - UI to select multiple cameras at once
    - pip function, optional prefix (ie, one camera output at a time)
-- Version 2.2.0


--
    - move and reimplement version check - use google analytics
    - add donate menu
    - add donate level in title bar
    - package with better MEncoder





    - test autostart
    - test all functionality
    - clean up code everywhere possible
    - better encoding options - not MEncoder? better compilation of MEncoder?
        -- write own simple encoder?

"""





ON_WINDOWS = sys.platform.startswith('win')


class ChronoFrame(chronoFrame):

    def __init__(self, *args, **kwargs):
        chronoFrame.__init__(self, *args, **kwargs)

        # parse command line arguments
        self.parseArguments()

        # parse saved configuration file
        self.loadConfiguration()

        # set up the rest of the application
        self.setup()

    def parseArguments(self):

        parser = argparse.ArgumentParser()

        # -a, --autostart
        parser.add_argument("-a", "--autostart",
                help="Automatically start capturing as soon as Chronolapse opens",
                action="store_true")

        # -b, --background
        parser.add_argument("-b", "--background",
                    help="Start Chronolapse in the background",
                    action="store_true")

        # configuration file location
        parser.add_argument("--config_file",
                help="The location of the Chronolapse configuration file",
                default="chronolapse.config")

        # sequential image format
        parser.add_argument('--sequential_image_format',
                help="Sets the format string for sequential image file names",
                default='%05d')

        parser.add_argument('--timestamp_filename_format',
                help="Sets the format string for timestamp image file names",
                default='%Y-%m-%d %H:%M:%S')

        # --verbose and --debug
        parser.add_argument("-v", "--verbose",
                            help="Increase output verbosity",
                            action="store_true")
        parser.add_argument("-d", "--debug",
                            help="Increase output verbosity to maximum",
                            action="store_true")

        # parse the command line arguments
        self.settings = parser.parse_args()

        # set verbosity on the logging module
        if self.settings.debug:
            logging.basicConfig(level=logging.DEBUG)
            logging.debug("Verbosity set to DEBUG")

        elif self.settings.verbose:
            logging.basicConfig(level=logging.INFO)
            logging.info("Verbosity set to INFO")

        logging.debug("Parsed command line options")

    def _bindUI(self, field, key, section='chronolapse'):
        """
        Creates a two way binding for the UI element and the given
        section/key in the config.
        """
        logging.debug("Binding %s[%s] to %s" % (section, key, str(field)))
        if hasattr(field, 'SetValue'):


            # if field is a checkbox, treat it differently
            if hasattr(field, 'IsChecked'):
                # on checkbox events, update the config
                self.Bind(wx.EVT_CHECKBOX,
                        lambda event: self.updateConfig(
                                        {key: field.IsChecked()}, from_ui=True),
                        field)

            else:
                # on text events, update the config
                self.Bind(wx.EVT_TEXT,
                        lambda event: self.updateConfig(
                                        {key: field.GetValue()}, from_ui=True),
                        field)

            # on config changes, update the UI
            self.config.add_listener(
                section, key, lambda x: field.SetValue(x))

        elif hasattr(field, 'SetStringSelection'):

            # on Selection
            self.Bind(wx.EVT_COMBOBOX,
                    lambda event: self.updateConfig(
                            {key: field.GetStringSelection()}, from_ui=True),
                    field)

            # on config changes, update the UI
            self.config.add_listener(
                section, key, lambda x: field.SetStringSelection(str(x)))

    def updateConfig(self, config, section='chronolapse', from_ui=False):

        if from_ui:
            logging.debug("Updating config from UI: %s" % str(config))
        else:
            logging.debug("Updating config: %s" % str(config))
        self.config.updateBatch(section, config, notify=not from_ui)

    def getConfig(self, key, section='chronolapse', default=None):
        return self.config.get(section, key, default=default)

    def loadConfiguration(self):
        logging.debug(
            "Loading configuration file: %s" % self.settings.config_file)

        config_file_path = os.path.abspath(self.settings.config_file)

        self.config = EasyConfig(config_file_path, defaults={
            'chronolapse': {
                'frequency': '60',

                'use_screenshot': True,
                'screenshot_timestamp': True,
                'screenshot_timestamp_format': '%Y-%m-%d %H:%M:%S',
                'screenshot_save_folder': 'screenshots',
                'screenshot_prefix': 'screen_',
                'screenshot_format': 'jpg',
                'screenshot_dual_monitor': False,

                'screenshot_subsection': False,
                'screenshot_subsection_top': '0',
                'screenshot_subsection_left': '0',
                'screenshot_subsection_width': '800',
                'screenshot_subsection_height': '600',

                'use_webcam': False,
                'webcam_timestamp': True,
                'webcam_timestamp_format': '%Y-%m-%d %H:%M:%S',
                'webcam_save_folder': 'webcam',
                'webcam_prefix': 'cam_',
                'webcam_format': 'jpg',
                'webcam_timestamp_top': 10,
                'webcam_timestamp_left': 10,
                'webcam_timestamp_red': 255,
                'webcam_timestamp_green': 255,
                'webcam_timestamp_blue': 255,
                'webcam_device_number': 0,

                'filename_format': 'timestamp',

                'pip_main_folder': '',
                'pip_pip_folder': '',
                'pip_output_folder': '',
                'pip_size': 'Small',
                'pip_position': 'Top-Right',
                'pip_ignore_unmatched': True,

                'video_source_folder': '',
                'video_output_folder': '',
                'video_format': '',
                'video_codec': 'mpeg4',
                'video_framerate': '10',
                'mencoder_path': 'mencoder',

                'audio_source_video': '',
                'audio_source': '',
                'audio_output_folder': '',

                'last_update': time.strftime('%Y-%m-%d'),
                'update_check_frequency': 604800
            }
        })

        # look for existing config file - load it if possible
        if os.path.exists(self.settings.config_file):
            try:
                self.config.load()
                logging.debug("Loaded config")
            except IOError, e:
                logging.error("Failed to load Config File: %s" % str(e))
                self.showWarning(
                    "Failed to Load Config",
                    "Failed to Load Configuration File. " \
                        + "Please check your file permissions."
                )
                self.Close()

        # bind all the ui fields to the config manager
        logging.debug("Binding events")
        self._bindUI(self.frequencytext, 'frequency')
        self._bindUI(self.screenshotcheck, 'use_screenshot')
        self._bindUI(self.webcamcheck, 'use_webcam')

        self._bindUI(self.pipmainimagefoldertext, 'pip_main_folder')
        self._bindUI(self.pippipimagefoldertext, 'pip_pip_folder')
        self._bindUI(self.pipoutputimagefoldertext, 'pip_output_folder')
        self._bindUI(self.pipsizecombo, 'pip_size')
        self._bindUI(self.pippositioncombo, 'pip_position')
        self._bindUI(self.pipignoreunmatchedcheck, 'pip_ignore_unmatched')

        self._bindUI(self.videosourcetext, 'video_source_folder')
        self._bindUI(self.videodestinationtext, 'video_output_folder')
        self._bindUI(self.videocodeccombo, 'video_codec')
        self._bindUI(self.videoframeratetext, 'video_framerate')
        self._bindUI(self.mencoderpathtext, 'mencoder_path')

        self._bindUI(self.audiosourcevideotext, 'audio_source_video')
        self._bindUI(self.audiosourcetext, 'audio_source')
        self._bindUI(self.audiooutputfoldertext, 'audio_output_folder')

        # bind fps
        self.Bind(
            wx.EVT_TEXT,
            self.recalculateVideoLength,
            self.videoframeratetext
        )
        # calculate video length now
        self.recalculateVideoLength()

        # create custom binding for filename format
        self.Bind(wx.EVT_RADIOBUTTON ,
                    lambda event: self.updateConfig(
                        {'filename_format':
                            'timestamp'
                                if self.filename_format_timestamp.GetValue()
                                else 'sequential'},
                        from_ui=True),
                    self.filename_format_timestamp)
        self.Bind(wx.EVT_RADIOBUTTON ,
                    lambda event: self.updateConfig(
                        {'filename_format':
                            'timestamp'
                                if self.filename_format_timestamp.GetValue()
                                else 'sequential'},
                        from_ui=True),
                    self.filename_format_sequential)

        # on config changes, update the UI
        self.config.add_listener(
            'chronolapse',
            'filename_format',
            lambda x:
                self.filename_format_timestamp.SetValue(x == 'timestamp')
        )
        self.config.add_listener(
            'chronolapse',
            'filename_format',
            lambda x:
                self.filename_format_sequential.SetValue(x == 'sequential')
        )

    def setup(self):

        # bind OnClose method
        self.Bind(wx.EVT_CLOSE, self.OnClose)

        # save path to folder where chronolapse is currently running
        self.CHRONOLAPSEPATH = os.path.dirname( os.path.abspath(sys.argv[0]))

        # set X to close to taskbar -- windows only
        # http://code.activestate.com/recipes/475155/
        self.TBFrame = TaskBarFrame(None, self, -1, " ", self.CHRONOLAPSEPATH)
        self.TBFrame.Show(False)

        # webcam
        self.cam = None

        # image countdown
        self.countdown = 60
        try:
            self.countdown = float(self.getConfig('frequency', default=60))
        except ValueError:
            pass

        # create timer
        self.timer = Timer(self.timerCallBack)

        # constants
        self.VERSION = VERSION
        self.DOCFILE = 'manual.html'
        self.VERSION_CHECK_PATH = 'http://chronolapse.com/versioncheck/'

        # fill in codecs available
        video_codecs = [
            'mpeg4', 'msmpeg4', 'msmpeg4v2', 'wmv1', 'mjpeg', 'h263p']
        self.videocodeccombo.SetItems(video_codecs)
        self.videocodeccombo.SetStringSelection(
            self.getConfig('video_codec', default=video_codecs[0])
        )
        # check version
        self.checkVersion()

        # load icon - #TODO: embed with base64?
        if ON_WINDOWS:
            icon_file = os.path.join(self.CHRONOLAPSEPATH, 'chronolapse.ico')
        else:
            icon_file = os.path.join(self.CHRONOLAPSEPATH, 'chronolapse_24.ico')

        if os.path.isfile(icon_file):
            self.SetIcon(wx.Icon(icon_file, wx.BITMAP_TYPE_ICO))
        else:
            logging.warning( 'Could not find %s' % icon_file)

        # autostart
        if self.settings.autostart:
            self.startCapturePressed(None)

    def doShow(self, *args, **kwargs):
        if self.settings.background:
            logging.debug("Starting minimized")
            self.TBFrame.set_icon_action_text(True)
            #self.ShowWithoutActivating(*args, **kwargs)
        else:
            logging.debug("Showing main frame")
            self.Show(*args, **kwargs)

    def OnClose(self, event):
        try:
            if hasattr(self, 'TBFrame') and self.TBFrame:
                self.TBFrame.kill(event)
        except: pass

        event.Skip()

    def startTimer(self):

        # set countdown
        self.countdown = float(self.frequencytext.GetValue())

        # start timer - if frequency < 1 second, use small increments
        # otherwise, 1 second will be plenty fast
        if self.countdown < 1:
            self.timer.Start( self.countdown * 1000)
        else:
            self.timer.Start(1000)

    def stopTimer(self):
        self.timer.Stop()

    def timerCallBack(self):

        # decrement timer
        self.countdown -= 1

        # adjust progress bar
        self.progresspanel.setProgress(1- (self.countdown / float(self.frequencytext.GetValue())))

        # on countdown
        if self.countdown <= 0:
            self.capture()      # take screenshot and webcam capture
            self.countdown = float(self.frequencytext.GetValue()) # reset timer

    def fileBrowser(self, message, defaultFile=''):
        dlg = wx.FileDialog(self, message, defaultFile=defaultFile,
                        style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
        else:
            path = ''
        dlg.Destroy()
        return path

    def saveFileBrowser(self, message, defaultFile=''):
        dlg = wx.FileDialog(self, message, defaultFile=defaultFile,
                        style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
        else:
            path = ''
        dlg.Destroy()
        return path

    def dirBrowser(self, message, defaultpath):
        # show dir dialog
        dlg = wx.DirDialog(
            self, message=message,
            defaultPath= defaultpath,
            style=wx.DD_DEFAULT_STYLE)

        # Show the dialog and retrieve the user response.
        if dlg.ShowModal() == wx.ID_OK:
            # load directory
            path = dlg.GetPath()

        else:
            path = ''

        # Destroy the dialog.
        dlg.Destroy()

        return path

    def capture(self):

        # get filename from time
        if self.getConfig('filename_format') == 'timestamp':
            filename = time.strftime(
                                self.settings.timestamp_filename_format)

            # use microseconds if capture speed is less than 1
            if self.countdown < 1:
                filename = str( time.time() )

        # get sequential filename
        else:
            highest_number = 0
            if self.getConfig('use_screenshot'):
                screenshot_file_list = os.listdir(
                                os.path.abspath(
                                    self.getConfig('screenshot_save_folder')
                                )
                            )

                prefix = self.getConfig('screenshot_prefix')
                for fname in screenshot_file_list:
                    base, extension = os.path.splitext(fname)
                    if base.startswith(prefix):
                        numeric_base = base[len(prefix):]
                        try:
                            highest_number = max(highest_number, int(numeric_base))
                        except ValueError, e:
                            # ignore files that are not parsable as numbers
                            pass

            if self.getConfig('use_webcam'):
                webcam_file_list = os.listdir(
                            os.path.abspath(
                                self.getConfig('webcam_save_folder')
                            )
                        )

                prefix = self.getConfig('webcam_prefix')
                for fname in webcam_file_list:
                    base, extension = os.path.splitext(fname)
                    if base.startswith(prefix):
                        numeric_base = base[len(prefix):]
                        try:
                            highest_number = max(highest_number, int(numeric_base))
                        except ValueError, e:
                            # ignore files that are not parsable as numbers
                            pass

            # create sequential filename
            filename = (self.settings.sequential_image_format %
                            (highest_number + 1))

        logging.debug('Capturing - ' + filename)

        # if screenshots
        if self.getConfig('use_screenshot'):
            # take screenshot
            self.saveScreenshot(filename)

        # if webcam
        if self.getConfig('use_webcam'):

            # take webcam shot
            self.saveWebcam(filename)

        return filename

    def saveScreenshot(self, filename):
        timestamp = self.getConfig('screenshot_timestamp')
        folder = self.getConfig('screenshot_save_folder')
        prefix = self.getConfig('screenshot_prefix')
        file_format = self.getConfig('screenshot_format')

        rect = None
        if self.getConfig('screenshot_subsection'):
            if (self.getConfig('screenshot_subsection_top') > 0 and
                self.getConfig('screenshot_subsection_left') > 0 and
                self.getConfig('screenshot_subsection_width') > 0 and
                self.getConfig('screenshot_subsection_height') > 0):
                rect = wx.Rect(
                        int(self.getConfig('screenshot_subsection_top')),
                        int(self.getConfig('screenshot_subsection_left')),
                        int(self.getConfig('screenshot_subsection_width')),
                        int(self.getConfig('screenshot_subsection_height'))
                    )

        img = self.takeScreenshot(rect, timestamp)
        self.saveImage(img, filename, folder, prefix, file_format)

    def takeScreenshot(self, rect = None, timestamp=False):
        """Takes a screenshot of the screen at give pos & size (rect).
        Code from Andrea -
    http://lists.wxwidgets.org/pipermail/wxpython-users/2007-October/069666.html
        """

        # use whole screen if none specified
        if not rect:
            #width, height = wx.DisplaySize()
            #rect = wx.Rect(0,0,width,height)

            x, y, width, height = wx.Display().GetGeometry()
            rect = wx.Rect(x,y,width,height)

            try:
                # use two monitors if checked and available
                if (self.getConfig('screenshotdualmonitor')
                    and wx.Display_GetCount() > 0):
                    second = wx.Display(1)
                    x2, y2, width2, height2 = second.GetGeometry()

                    x3 = min(x,x2)
                    y3 = min(y, y2)
                    width3 = max(x+width, x2+width2) - x3
                    height3 = max(height-y3, height2-y3)

                    rect = wx.Rect(x3, y3, width3, height3)
            except Exception, e:
                self.warning(
                    "Exception while attempting to capture second "
                    + "monitor: %s" % repr(e))

        #Create a DC for the whole screen area
        dcScreen = wx.ScreenDC()

        #Create a Bitmap that will later on hold the screenshot image
        #Note that the Bitmap must have a size big enough to hold the screenshot
        #-1 means using the current default colour depth
        bmp = wx.EmptyBitmap(rect.width, rect.height)

        #Create a memory DC that will be used for actually taking the screenshot
        memDC = wx.MemoryDC()

        #Tell the memory DC to use our Bitmap
        #all drawing action on the memory DC will go to the Bitmap now
        memDC.SelectObject(bmp)

        #Blit (in this case copy) the actual screen on the memory DC
        #and thus the Bitmap
        memDC.Blit( 0,      #Copy to this X coordinate
            0,              #Copy to this Y coordinate
            rect.width,     #Copy this width
            rect.height,    #Copy this height
            dcScreen,       #From where do we copy?
            rect.x,         #What's the X offset in the original DC?
            rect.y          #What's the Y offset in the original DC?
            )

        # write timestamp on image
        if timestamp:
            try:
                stamp = time.strftime(self.getConfig('screenshot_timestamp_format'))
            except ValueError:
                logging.error("Invalid screenshot timestamp format")
                return

            if self.countdown < 1:
                now = time.time()
                micro = str(now - math.floor(now))[0:4]
                stamp = stamp + micro

            memDC.DrawText(stamp, 20, rect.height-30)

        #Select the Bitmap out of the memory DC by selecting a new
        #uninitialized Bitmap
        memDC.SelectObject(wx.NullBitmap)

        return bmp

    def saveImage(self, bmp, filename, folder, prefix, format='jpg'):
        # convert
        img = bmp.ConvertToImage()

        # save
        if format == 'gif':
            fileName = os.path.join(folder,"%s%s.gif" % (prefix, filename))
            img.SaveFile(fileName, wx.BITMAP_TYPE_GIF)

        elif format == 'png':
            fileName = os.path.join(folder,"%s%s.png" % (prefix, filename))
            img.SaveFile(fileName, wx.BITMAP_TYPE_PNG)

        else:
            fileName = os.path.join(folder,"%s%s.jpg" % (prefix, filename))
            img.SaveFile(fileName, wx.BITMAP_TYPE_JPEG)

    def saveWebcam(self, filename):
        timestamp = self.getConfig('webcam_timestamp')
        timestamp_format = self.getConfig('webcam_timestamp_format')
        folder = self.getConfig('webcam_save_folder')
        prefix = self.getConfig('webcam_prefix')
        file_format = self.getConfig('webcam_format')

        self.takeWebcam(
            filename, folder, prefix, file_format, timestamp, timestamp_format)

    def getWebcamCapture(self):
        # get the device number from config
        device_number = self.getConfig('webcam_device_number')

        # turn on camera, capture, turn off
        cam = cv2.VideoCapture(device_number)
        # first read from opencv cam seems unreliable
        result, image = cam.read()
        result, image = cam.read()
        cam.release()

        if result:
            return image
        return None

    def takeWebcam(self,
        filename, folder,
        prefix, file_format='jpg',
        use_timestamp=False, timestamp_format=None):

        # build filepath
        filepath = os.path.join(
                    folder,"%s%s.%s" % (prefix, filename, file_format))

        # get image from webcam
        image = self.getWebcamCapture()

        if image is None:
            logging.warning("No image returned from camera")
            return None

        # write timestamp as necessary
        if use_timestamp:

            # if no format passed in, get from config
            if timestamp_format is None:
                timestamp_format = self.getConfig('webcam_timestamp_format')

            # build timestamp
            stamp = None
            try:
                stamp = time.strftime(timestamp_format)
            except ValueError:
                logging.error("Invalid timestamp format")

            if stamp:

                logging.debug("Writing timestamp %s" % stamp)

                top = self.getConfig('webcam_timestamp_top')
                left = self.getConfig('webcam_timestamp_left')

                # convert to pil image
                converted = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(converted)
                r,g,b = (self.getConfig('webcam_timestamp_red'),
                            self.getConfig('webcam_timestamp_green'),
                            self.getConfig('webcam_timestamp_blue'))
                draw = ImageDraw.Draw(pil_image)
                #font = ImageFont.truetype("sans-serif.ttf", 16)
                font = ImageFont.load_default()
                #draw.text((0, 0), stamp, (255,255,255), font=font)
                draw.text( (top, left), stamp, fill=(255,255,255), font=font)
                pil_image.save(filepath)

        else:
            logging.debug("Not writing timestamp")

            # write file
            cv2.imwrite(filepath, image)

        return filepath

    def showWarning(self, title, message):
        dlg = wx.MessageDialog(self, message, title, wx.OK | wx.ICON_ERROR)
        dlg.ShowModal()
        dlg.Destroy()

    def screenshotConfigurePressed(self, event):
        dlg = ScreenshotConfigDialog(self)

        # save reference to this
        self.screenshotdialog = dlg

        # set current options in dlg
        dlg.dualmonitorscheck.SetValue(
                self.getConfig('screenshot_dual_monitor', default=False))

        dlg.subsectioncheck.SetValue(
                        self.getConfig('screenshot_subsection', default=False))
        dlg.subsectiontop.SetValue(
                            str(self.getConfig('screenshot_subsection_top')))
        dlg.subsectionleft.SetValue(
                            str(self.getConfig('screenshot_subsection_left')))
        dlg.subsectionwidth.SetValue(
                            str(self.getConfig('screenshot_subsection_width')))
        dlg.subsectionheight.SetValue(
                            str(self.getConfig('screenshot_subsection_height')))

        # call this to toggle subsection option enabled/disabled
        dlg.Bind(wx.EVT_CHECKBOX, self.subsectionchecked)
        self.subsectionchecked()

        dlg.timestampcheck.SetValue(self.getConfig('screenshot_timestamp'))
        dlg.screenshot_timestamp_format.SetValue(
                                    self.getConfig('screenshot_timestamp_format'))
        dlg.screenshotprefixtext.SetValue(self.getConfig('screenshot_prefix'))
        dlg.screenshotsavefoldertext.SetValue(
                                    self.getConfig('screenshot_save_folder'))
        dlg.screenshotformatcombo.SetStringSelection(
                                        self.getConfig('screenshot_format'))

        if dlg.ShowModal() == wx.ID_OK:

            # save dialog info
            self.updateConfig({
                'screenshot_timestamp': dlg.timestampcheck.IsChecked(),
                'screenshot_timestamp_format': dlg.screenshot_timestamp_format.GetValue(),
                'screenshot_prefix': dlg.screenshotprefixtext.GetValue(),
                'screenshot_save_folder': dlg.screenshotsavefoldertext.GetValue(),
                'screenshot_format': dlg.screenshotformatcombo.GetStringSelection(),

                'screenshot_dual_monitor': dlg.dualmonitorscheck.IsChecked(),
                'screenshot_subsection': dlg.subsectioncheck.IsChecked(),
                'screenshot_subsection_top': dlg.subsectiontop.GetValue(),
                'screenshot_subsection_left': dlg.subsectionleft.GetValue(),
                'screenshot_subsection_width': dlg.subsectionwidth.GetValue(),
                'screenshot_subsection_height': dlg.subsectionheight.GetValue()
            })

        dlg.Destroy()

    def webcamConfigurePressed(self, event):
        dlg = WebcamConfigDialog(self)

        if dlg.has_cam:
            # set current options in dlg
            dlg.webcamtimestampcheck.SetValue(
                                            self.getConfig('webcam_timestamp'))
            dlg.webcam_timestamp_format.SetValue(
                                    self.getConfig('webcam_timestamp_format'))
            dlg.webcamprefixtext.SetValue(self.getConfig('webcam_prefix'))
            dlg.webcamsavefoldertext.SetValue(
                                        self.getConfig('webcam_save_folder'))
            dlg.webcamformatcombo.SetStringSelection(
                                                self.getConfig('webcam_format'))

            if dlg.ShowModal() == wx.ID_OK:

                logging.debug("Saving webcam folder %s" % dlg.webcamsavefoldertext.GetValue())

                # save dialog info
                self.updateConfig({
                    'webcam_timestamp': dlg.webcamtimestampcheck.IsChecked(),
                    'webcam_timestamp_format': dlg.webcam_timestamp_format.GetValue(),
                    'webcam_prefix': dlg.webcamprefixtext.GetValue(),
                    'webcam_save_folder': dlg.webcamsavefoldertext.GetValue(),
                    'webcam_format': dlg.webcamformatcombo.GetStringSelection()
                })

        dlg.Destroy()

    def startCapturePressed(self, event): # wxGlade: chronoFrame.<event_handler>
        text = self.startbutton.GetLabel()

        # update video length
        self.recalculateVideoLength()

        if text == 'Start Capture':

            use_screenshot = self.getConfig('use_screenshot')
            screenshot_folder = os.path.abspath(
                                    self.getConfig('screenshot_save_folder')
                                )

            use_webcam = self.getConfig('use_webcam')
            webcam_folder = os.path.abspath(
                                    self.getConfig('webcam_save_folder')
                                )

            # check that screenshot and webcam folders are available
            if use_screenshot:

                # check screenshot save folder
                if not os.access(screenshot_folder, os.W_OK):
                    self.showWarning('Cannot Write to Screenshot Folder',
                    ("""Error: Cannot write to screenshot folder %s.
Please add write permission and try again.""") % screenshot_folder)
                    return False

            if use_webcam:
                if not os.access(webcam_folder, os.W_OK):
                    self.showWarning('Cannot Write to Webcam Folder',
                        ("""Error: Cannot write to webcam folder %s.
Please add write permission and try again.""") % webcam_folder)
                    return False

            # disable config buttons, frequency
            self.screenshotcheck.Disable()
            self.screenshotconfigurebutton.Disable()
            self.configurewebcambutton.Disable()
            self.webcamcheck.Disable()
            self.frequencytext.Disable()
            self.filename_format_timestamp.Disable()
            self.filename_format_sequential.Disable()

            # change start button text to stop capture
            self.startbutton.SetLabel('Stop Capture')

            # start timer
            if float(self.getConfig('frequency')) > 0:
                self.startTimer()

        elif text == 'Stop Capture':

            # enable config buttons, frequency
            self.screenshotcheck.Enable()
            self.screenshotconfigurebutton.Enable()
            self.configurewebcambutton.Enable()
            self.webcamcheck.Enable()
            self.frequencytext.Enable()
            self.filename_format_timestamp.Enable()
            self.filename_format_sequential.Enable()

            # change start button text to start capture
            self.startbutton.SetLabel('Start Capture')

            # stop timer
            self.stopTimer()

    def forceCapturePressed(self, event):
        # save a capture right now
        self.capture()

    def pipMainImageBrowsePressed(self, event):
        path = self.dirBrowser('Select folder containing main images',
                    self.pipmainimagefoldertext.GetValue())

        if path != '':
            self.updateConfig({'pip_main_folder': path})

    def pipPipImageBrowsePressed(self, event):
        path = self.dirBrowser('Select folder containing PIP images',
                                        self.pippipimagefoldertext.GetValue())

        if path != '':
            self.updateConfig({'pip_pip_folder': path})

    def pipOutputBrowsePressed(self, event):
        path = self.dirBrowser('Select save folder for PIP images',
                                    self.pipoutputimagefoldertext.GetValue())

        if path != '':
            self.updateConfig({'pip_output_folder': path})

            if not os.access( path, os.W_OK):
                self.showWarning("Permission Error",
                    "Error: the PIP output path %s is not writable. "
                    + "Please set write permissions and try again." % path)

    def createPipPressed(self, event): # wxGlade: chronoFrame.<event_handler>

        # make sure output file is writable
        if not os.access( self.pipoutputimagefoldertext.GetValue(), os.W_OK):
            self.showWarning('Permission Error',
            'Error: Output file is not writable. Please check your ' +
            ' permissions and try again.')
            return False

        # get pip settings
        sourcefolder = self.pipmainimagefoldertext.GetValue()
        pipfolder = self.pippipimagefoldertext.GetValue()
        outfolder = self.pipoutputimagefoldertext.GetValue()

        # pip size and position
        pipsizestring = self.pipsizecombo.GetStringSelection()
        pippositionstring = self.pippositioncombo.GetStringSelection()

        # sort files - match up by sorting so prefixes work
        sourcefiles = os.listdir(sourcefolder)
        sourcefiles.sort()
        pipfiles = os.listdir(pipfolder)
        pipfiles.sort()

        logging.debug('Creating PIP')

        # progress dialog
        progressdialog = wx.ProgressDialog(
                        'PIP Progress',
                        'Processing Images',
                        maximum=len(sourcefiles),
                        parent=self,
                        style =
                            wx.PD_CAN_ABORT | wx.PD_APP_MODAL |
                             wx.PD_ELAPSED_TIME | wx.PD_REMAINING_TIME)

        # for all images in main folder
        count = 0
        for i in xrange( min(len(sourcefiles), len(pipfiles))):
            sourcefile = sourcefiles[i]
            pipfile = pipfiles[i]

            # update progress dialog
            count += 1
            cancel, somethingelse = progressdialog.Update(
                                            count, 'Processing %s'%sourcefile)
            # update progress dialog
            if not cancel:
                progressdialog.Destroy()
                break

            try:
                # open with PIL -- will skip non-images
                source = Image.open(os.path.join(sourcefolder, sourcefile))
                pip = Image.open(os.path.join(pipfolder, pipfile))

                # get pip size - sides
                if pippositionstring == 'Left' or pippositionstring == 'Right':
                    if pipsizestring == 'Small':
                        pipsize = ( source.size[0] / 4, source.size[1])
                    elif pipsizestring == 'Medium':
                        pipsize = ( source.size[0] / 3, source.size[1])
                    else:
                        pipsize = ( source.size[0] / 2, source.size[1])

                # get pip size - top/bottom
                elif pippositionstring == 'Top' or pippositionstring == 'Bottom':
                    if pipsizestring == 'Small':
                        pipsize = ( source.size[0], source.size[1] / 4)
                    elif pipsizestring == 'Medium':
                        pipsize = ( source.size[0], source.size[1] / 3)
                    else:
                        pipsize = ( source.size[0], source.size[1] / 2)

                # get pip size - corners
                else:
                    if pipsizestring == 'Small':
                        pipsize = ( source.size[0] / 4, source.size[1] / 4)
                    elif pipsizestring == 'Medium':
                        pipsize = ( source.size[0] / 3, source.size[1] / 3)
                    else:
                        pipsize = ( source.size[0] / 2, source.size[1] / 2)

                # resize pip
                pip.thumbnail(pipsize)

                # paste on main - left
                if pippositionstring == 'Left':
                    source.paste(pip, (0,0))

                # paste on main - Right
                elif pippositionstring == 'Right':
                    source.paste(pip, ( source.size[0]-pip.size[0], 0))

                # paste on main - top
                elif pippositionstring == 'Top':
                    source.paste(pip, (0,0))

                # paste on main - bottom
                elif pippositionstring == 'Bottom':
                    source.paste(pip, (0, source.size[1]-pip.size[1]))

                # paste on main - top right
                elif pippositionstring == 'Top-Right':
                    source.paste(pip, ( source.size[0]-pip.size[0], 0))

                # paste on main - bottom right
                elif pippositionstring == 'Bottom-Right':
                    source.paste(
                        pip,
                        (source.size[0]-pip.size[0], source.size[1]-pip.size[1])
                    )

                # paste on main - bottom left
                elif pippositionstring == 'Bottom-Left':
                    source.paste(pip, (0, source.size[1]-pip.size[1]))

                # paste on main - top left
                elif pippositionstring == 'Top-Left':
                    source.paste(pip, (0, 0))

                # save in destination
                outpath = os.path.join( outfolder, sourcefiles[i])
                source.save( outpath)

                # modify creation time to match source file
                ctime = os.path.getctime(os.path.join(sourcefolder, sourcefile))
                os.utime(outpath, (ctime, ctime))

            except Exception, e:
                pass

        progressdialog.Destroy()

    def videoSourceBrowsePressed(self, event):
        path = self.dirBrowser(
                    'Select folder containing source images',
                    self.videosourcetext.GetValue()
                )

        if path != '':
            self.updateConfig({'video_source_folder': path})

        # recalculate length of video
        self.recalculateVideoLength()

    def videoDestinationBrowsePressed(self, event):
        path = self.dirBrowser(
                    'Select save folder for video ',
                    self.videodestinationtext.GetValue())

        if path != '':
            self.updateConfig({'video_output_folder': path})

            if not os.access( path, os.W_OK):
                self.showWarning("Permission Error",
                    'Error: the video output path %s is not writable. '
                    + "Please set write permissions and try again." % path)

    def framerateTextChanged(self, event):
        self.recalculateVideoLength()
        event.Skip()

    def recalculateVideoLength(self, event=None):
        logging.debug("Recalculating Video Length")

        sourcepath = self.getConfig('video_source_folder')

        seconds = 0
        if sourcepath:
            numfiles = 0
            # get number of files in source dir
            for f in os.listdir(sourcepath):
                if os.path.isfile(os.path.join(sourcepath,f)):
                    numfiles += 1

            # framerate
            try:
                framerate = int(self.videoframeratetext.GetValue())
            except ValueError:
                framerate = 0

            if numfiles == 0 or framerate == 0:
                self.movielengthlabel.SetLabel(
                                            "Estimated Movie Length: 0 m 0 s")
                return

            # divide by frames/second to get seconds
            seconds = numfiles/framerate

        minutes = seconds//60
        seconds = seconds%60

        # change label
        self.movielengthlabel.SetLabel(
                    "Estimated Movie Length: %d m %d s" % (minutes, seconds))

        if event:
            event.Skip()

    def mencoderPathBrowsePressed(self, event):
        # file browser
        dlg = wx.FileDialog(
                    self, 'Select MEncoder Executable', self.CHRONOLAPSEPATH)
        result = dlg.ShowModal()
        if result == wx.ID_OK:
            path = dlg.GetPath()
            self.mencoderpathtext.SetValue(path)
        dlg.Destroy()

    def createVideoPressed(self, event):
        # check that paths are valid
        sourcefolder = self.videosourcetext.GetValue()
        destfolder = self.videodestinationtext.GetValue()

        if not os.path.isdir(sourcefolder):
            self.showWarning('Source folder invalid',
                            'The video source folder is invalid')
            return False

        # check that destination folder exists and is writable
        if not os.access( destfolder, os.W_OK):
            self.showWarning(
                'Permission Denied',
                ('The output folder %s is not writable. Please change the ' +
                'permissions and try again.') % destfolder
            )
            return False

        # check mencoder path
        mencoderpath = self.mencoderpathtext.GetValue()
        if mencoderpath == 'mencoder':
            self.showWarning(
                'MEncoder path not set',
                'Chronolapse uses MEncoder to process video. Either point to ' +
                'MEncoder directly or ensure it is on your path.'
            )

        elif not os.path.isfile(mencoderpath):
            # look for mencoder
            if not os.path.isfile(
                            os.path.join(self.CHRONOLAPSEPATH, 'mencoder')):
                self.showWarning(
                    'MEncoder Not Found',
                    'Chronolapse uses MEncoder to process video, but could ' +
                    'not find mencoder'
                )
                return False
            elif ON_WINDOWS:
                mencoderpath = os.path.join(self.CHRONOLAPSEPATH, 'mencoder')

        fps = self.videoframeratetext.GetValue()
        try:
            fps = int(fps)
        except:
            self.showWarning(
                'Frame Rate Invalid',
                'The frame rate setting is invalid. Frame rate must be ' +
                'a positive integer'
            )
            return False


        # get dimensions of first image file
        found = False
        count = 0
        sourcefiles = os.listdir(sourcefolder)
        while not found and count < len(sourcefiles):
            count += 1
            try:
                imagepath = os.path.join(sourcefolder, sourcefiles[count])
                img = Image.open(imagepath)
                found = True
                width, height = img.size

                imagepath = imagepath.lower()
                if imagepath.endswith(('.gif')):
                    imagetype = 'gif'
                    path = '*.gif'
                elif imagepath.endswith('.png'):
                    imagetype = 'png'
                    path = '*.png'
                else:
                    imagetype = 'jpg'

                    index = imagepath.rfind('.')
                    if index > 0:
                        path = '*.%s'%imagepath[index+1:]
                    else:
                        path = '*.jpg'

                #path = os.path.join(sourcefolder, path)

            except:
                pass

        if not found:
            self.showWarning(
                'No Images Found',
                'No images were found in the source folder %s' % sourcefolder
            )
            return False

        # get video type from select box
        #format = '-of %s' % self.videoformatcombo.GetStringSelection()

        # get codec from select box
        codec = self.videocodeccombo.GetStringSelection()

        # get output file name --- create in source folder then
        # move because of ANOTHER mencoder bug
        timestamp = time.strftime('%Y-%m-%d_%H-%M-%S')
        out_extension = 'avi'

        output_filename = os.path.join(
                                destfolder,
                                'timelapse_%s.%s' % (timestamp, out_extension)
                            )
        source_filename = os.path.join(
                                sourcefolder,
                                'timelapse_%s.%s' % (timestamp, out_extension)
                            )

        # if either file already exists
        count = 1
        while(
            os.path.isfile(output_filename)
            or os.path.isfile(source_filename)):

            count += 1
            output_filename = os.path.join(
                    destfolder,
                    'timelapse_%s_%d.%s' % (timestamp, count, out_extension)
                )
            source_filename = os.path.join(
                    destfolder,
                    'timelapse_%s_%d.%s' % (timestamp, count, out_extension)
                )

        # change cwd to image folder to stop mencoder bug
        try:
            os.chdir(sourcefolder)
        except Exception, e:
            self.showWarning(
                'CWD Error',
                "Could not change current directory. %s" % str(e)
            )
            return False

        # create progress dialog
        progressdialog = wx.ProgressDialog(
                                'Encoding Progress', 'Encoding - Please Wait')
        progressdialog.Pulse('Encoding - Please Wait')

        # run mencoder with options from GUI
##         mf://%s -mf w=%d:h=%d:fps=%s:type=%s -ovc lavc -lavcopts vcodec=%s:mbd=2:trell %s -oac copy -o %s' % (
##        path, width, height, fps, imagetype, codec, format, outfile ))
        # http://web.njit.edu/all_topics/Prog_Lang_Docs/html/mplayer/encoding.html

##        if codec == 'uncompressed':
##            command = '"%s" mf://%s -mf fps=%s -ovc rawrgb -o %s' % (
##                    mencoderpath, path, fps, outfile )
##            command = '"%s" mf://fps=%s:type=png  -ovc rawrgb -o %s \*.png' % (mencoderpath, fps, outfile)
##        else:

        command = ('"%s" mf://%s -mf fps=%s -ovc lavc -lavcopts vcodec=%s -o %s'
                        % (mencoderpath, path, fps, codec, output_filename))

        logging.debug("Calling: %s"%command)

        self.returncode = None
        self.mencodererror = 'Unknown'
        mencoderthread = threading.Thread(
                None, self.runMencoderInThread, 'mencoderthread', (command,))
        mencoderthread.start()

        while self.returncode is None:
            time.sleep(.5)
            progressdialog.Pulse()

        # mencoder error
        if self.returncode > 0:
            progressdialog.Destroy()

            self.showWarning(
                    'MEncoder Error',
                    "Error while encoding video. Check the MEncoder console " +
                    "or try a different codec"
            )
            return

        # move video file to destination folder
        logging.debug("Moving file from %s to %s" % (
                            os.path.join(sourcefolder, output_filename),
                            os.path.join(destfolder, output_filename))
                    )
        shutil.move(
            os.path.join(sourcefolder, output_filename),
            os.path.join(destfolder, output_filename)
        )

        progressdialog.Destroy()

        dlg = wx.MessageDialog(
            self,
            'Encoding Complete!\nFile saved as %s' %
                            os.path.join(destfolder, output_filename),
            'Encoding Complete',
            style=wx.OK
        )
        dlg.ShowModal()
        dlg.Destroy()

    def runMencoderInThread(self, command):
        #proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE,stderr=subprocess.PIPE)

        logging.debug('Running mencoder in thread')
        #proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  #      mencoder mf://*.jpg -mf w=800:h=600:fps=25:type=jpg -ovc lavc -lavcopts vcodec=mpeg4:mbd=2:trell -oac copy -o output.avi

        try:
            if ON_WINDOWS:
                proc = subprocess.Popen(command, close_fds=True)
            else:
                proc = subprocess.Popen(command, close_fds=True, shell=True,
                                stdout=subprocess.PIPE,stderr=subprocess.PIPE)

            stdout, stderr = proc.communicate()
            self.mencodererror = stderr
            self.returncode = proc.returncode
        except Exception, e:
            self.mencodererror = repr(e)
            self.returncode = 1

    def audioSourceVideoBrowsePressed(self, event):
        path = self.fileBrowser('Select video source',
                    self.audiosourcevideotext.GetValue())

        if path != '':
            self.updateConfig({'audio_source_video': path})

    def audioSourceBrowsePressed(self, event):
        path = self.fileBrowser('Select audio source',
                    self.audiosourcetext.GetValue())

        if path != '':
            self.updateConfig({'audio_source': path})

            if not os.access( path, os.W_OK):
                self.showWarning("Permission Error",
                    'Error: the video output path %s is not writable. '
                    + 'Please set write permissions and try again.' % path)

    def audioOutputFolderBrowsePressed(self, event):
        path = self.dirBrowser('Select save folder for new video ',
                    self.audiooutputfoldertext.GetValue())

        if path != '':
            self.updateConfig({'audio_output_folder': path})

            if not os.access( path, os.W_OK):
                self.showWarning("Permission Error",
                    'Error: the video output path %s is not writable. '
                    + 'Please set write permissions and try again.' % path)

    def createAudioPressed(self, event):

        # check that paths are valid
        videosource = self.audiosourcevideotext.GetValue()
        videofolder = os.path.dirname(videosource)
        videobase = os.path.basename(videosource)
        audiosource = self.audiosourcetext.GetValue()
        destfolder = self.audiooutputfoldertext.GetValue()

        if not os.path.isfile(videosource):
            self.showWarning(
                'Video path invalid',
                'The source video path appears is invalid')
            return False

        if not os.path.isfile(audiosource):
            self.showWarning(
                    'Audio path invalid',
                    'The source audio path appears is invalid')
            return False

        # check that destination folder exists and is writable
        if not os.access( destfolder, os.W_OK):
            self.showWarning('Permission Denied',
                'The output folder %s is not writable. Please change '
                + 'the permissions and try again.' % destfolder)
            return False

        # check mencoder path
        mencoderpath = self.mencoderpathtext.GetValue()
        if not os.path.isfile(mencoderpath):
            # look for mencoder
            if not os.path.isfile(
                        os.path.join(self.CHRONOLAPSEPATH, 'mencoder')):
                self.showWarning(
                    'MEncoder Not Found',
                 'Chronolapse uses MEncoder to process video, but could '
                 + 'not find it. Please add MEncoder to your path.')
                return False
            else:
                mencoderpath = os.path.join(self.CHRONOLAPSEPATH, 'mencoder')

        # make sure video name has no spaces
        if videobase.find(' ') != -1:

            try:
                # copy audio to video source folder
                logging.debug('Creating temporary file for video')
                handle, safevideoname = tempfile.mkstemp(
                                '_deleteme' + os.path.splitext(videobase)[1],
                                'chrono_',
                                videofolder)
                os.close(handle)
                logging.debug('Copying video file to %s' % safevideoname)
                shutil.copy(videosource, safevideoname)
            except Exception, e:
                self.showWarning('Temp Audio Error',
                                "Exception while copying audio to video "
                                + "folder: %s" % repr(e))
        else:
            # no spaces, use this
            safevideoname = videobase

        # get output file name
        # create in source folder then move bc of ANOTHER mencoder bug
        outfile = "%s-audio%s" % (
                        os.path.splitext(safevideoname)[0],
                        os.path.splitext(safevideoname)[1]
                    )
        if os.path.isfile(os.path.join(destfolder, outfile)):
            count = 2
            while os.path.isfile(
                    os.path.join(
                        destfolder,
                        "%s-audio%d%s" % (
                                        os.path.splitext(safevideoname)[0],
                                        count,
                                        os.path.splitext(safevideoname)[1]
                                    )
                    )
                ):
                count += 1
            outfile = "%s-audio%d%s" % (
                                        os.path.splitext(safevideoname)[0],
                                        count,
                                        os.path.splitext(safevideoname)[1]
                                    )

        # change cwd to video folder to stop mencoder bug
        try:
            logging.debug('Changing directory to %s' % videofolder)
            os.chdir( videofolder)
        except Exception, e:
            self.showWarning('CWD Error',
                            "Could not change current directory. %s" % repr(e))

            # delete temp video file
            if safevideoname != videobase:
                try:
                    os.remove(safevideoname)
                except:
                    pass

            return False

        newaudiopath = ''
        try:
            # copy audio to video source folder
            logging.debug('Creating temporary file for audio')
            handle, newaudiopath = tempfile.mkstemp(
                                '_deleteme' + os.path.splitext(audiosource)[1],
                                'chrono_',
                                videofolder)
            os.close(handle)
            logging.debug('Copying audio file to %s' % newaudiopath)
            shutil.copy(audiosource, newaudiopath)
        except Exception, e:
            self.showWarning('Temp Audio Error',
                "Exception while copying audio to video folder: %s" % repr(e))

        # create progress dialog
        progressdialog = wx.ProgressDialog(
                                'Dubbing Progress', 'Dubbing - Please Wait')
        progressdialog.Pulse('Dubbing - Please Wait')

        # mencoder -ovc copy -audiofile silent.mp3 -oac copy input.avi -o output.avi
        command = '"%s" -ovc copy -audiofile %s -oac copy %s -o %s' % (
        mencoderpath, os.path.basename(newaudiopath), safevideoname, outfile )

        logging.debug("Calling: %s"%command)
        #proc = subprocess.Popen(
            #command, shell=True, stdout=subprocess.PIPE,stderr=subprocess.PIPE)

        proc = subprocess.Popen(command, close_fds=True)

        stdout, stderr = proc.communicate()
        returncode = proc.returncode

        # mencoder error
        if returncode > 0:
            progressdialog.Destroy()
            self.showWarning('MEncoder Error', stderr)

            # delete temporary audio file
            if newaudiopath != '':
                try:
                    os.remove(newaudiopath)
                except Exception, e:
                    logging.debug(
                        'Exception while deleting temp audio file %s: %s' % (
                                                        newaudiopath, repr(e)))

            # delete temp video file
            if safevideoname != videobase:
                try:
                    os.remove(safevideoname)
                except:
                    pass

            return

        # move video file to destination folder
        if videofolder != destfolder:
            logging.debug(
                    "Moving file from %s to %s" % (
                                os.path.join(videodir,outfile),
                                os.path.join(destfolder, outfile))
                        )
            shutil.move(
                os.path.join(os.path.dirname(videosource),outfile),
                os.path.join(destfolder, outfile)
            )

        progressdialog.Destroy()

        # delete temporary audio file
        if newaudiopath != '':
            try:
                os.remove(newaudiopath)
            except Exception, e:
                logging.debug('Exception while deleting temp audio file %s: %s'
                                                 % (newaudiopath, repr(e)))

        # delete temp video file
        if safevideoname != videobase:
            try:
                os.remove(safevideoname)
            except:
                pass

        dlg = wx.MessageDialog(self, 'Dubbing Complete!\nFile saved as %s'
                                        % os.path.join(destfolder, outfile),
                                        'Dubbing Complete', style=wx.OK)
        dlg.ShowModal()
        dlg.Destroy()

    def instructionsMenuClicked(self, event):
        path = os.path.join(self.CHRONOLAPSEPATH, self.DOCFILE)
        if os.path.isfile(path):
            wx.LaunchDefaultBrowser(path)

    def aboutMenuClicked(self, event):
        info = wx.AboutDialogInfo()
        info.Name = "Chronolapse"
        info.Version = self.VERSION
        info.Copyright = '(C) 2008-2014 Collin Green'

        description = """Chronolapse (CL) is a tool for creating time lapses on windows using
screen captures, webcam captures, or both at the same time. CL also provides
some rudimentary tools for resizing images and creating picture-in-picture
(PIP) effects. Finally, CL provides
a front end to mencode to take your series of images and turn them into a movie."""

        info.Description = '\n'.join(textwrap.wrap(description, 70))
        info.WebSite = ("http://chronolapse.com/", "Chronolapse")
        info.Developers = [ 'Collin "Keeyai" Green']

        if os.path.isfile( os.path.join( self.CHRONOLAPSEPATH, 'license.txt')):
            licensefile = file(
                            os.path.join(
                                self.CHRONOLAPSEPATH,
                                'license.txt'
                            ),
                            'r')
            licensetext = licensefile.read()
            licensefile.close()
        else:
            licensetext = 'License file not found. Please contact the ' + \
                            'developers for a copy of the license.'

        licensetext.replace('\n', ' ')
        info.License = '\n'.join(textwrap.wrap(licensetext,70))

        # Then we call wx.AboutBox giving it that info object
        wx.AboutBox(info)

    def iconClose(self, event):
        logging.debug('Closing from taskbar')
        self.Close(True)

    def checkVersion(self):
        try:
            # if it has been more than a week since the last check
            last_update = self.getConfig('last_update')

            # convert for comparison?
            parsedtime = time.mktime(time.strptime( last_update, '%Y-%m-%d'))

            # calculate time since last update
            timesince = time.mktime(time.localtime()) - parsedtime

            if timesince > self.getConfig("update_check_frequency"):
                # show popup to confirm user wants to allow update checks
                dlg = wx.MessageDialog(self,
                        "Do you want Chronolapse to check for updates now?",
                       'Check for Updates?',
                       wx.YES_NO
                       )
                choice = dlg.ShowModal()
                dlg.Destroy()

                # if user wants to check
                if choice == wx.ID_YES:

                    # check URL
                    request = urllib2.Request(
                                self.VERSION_CHECK_PATH,
                                urllib.urlencode([('version',self.VERSION)]))
                    page = urllib2.urlopen(request)

                    #parse page
                    content = page.read()

                    version_info = None
                    try:
                        version_info = json.loads(content)
                    except: pass

                    if version_info:
                        version = version_info.get('version', None)
                        url = version_info.get('url', None)
                        update_date = version_info.get('update_date', None)

                        if version:
                            version_info = self.get_version_info(version)
                            this_version = self.get_version_info(self.VERSION)

                            update_available = self.compare_version_info(
                                                    version_info, this_version)
                            if update_available:
                                versionmessage = """
A new version of Chronolapse is available.
Your current version is %s. The latest available version is %s.
You can download the new version at:
%s""" % (self.VERSION, version, url)
                                dlg = wx.MessageDialog(self, versionmessage,
                                               'A new version is available',
                                               wx.OK | wx.ICON_INFORMATION
                                               )
                                dlg.ShowModal()
                                dlg.Destroy()

                            # otherwise notify user and set last_update
                            else:
                                dlg = wx.MessageDialog(self,
                                            "Chronolapse is up to date",
                                            "Chronolapse is up to date",
                                            wx.OK | wx.ICON_INFORMATION)
                                dlg.ShowModal()
                                dlg.Destroy()

            # reset update time
            self.updateConfig({'last_update': time.strftime('%Y-%m-%d')})

        except Exception, e:
            self.showWarning(
                'Failed to check version',
                'Failed to check version. %s' % str(e))

    def get_version_info(self, version_string):
        # try parsing version
        version_split = version_string.split('.')

        build, major, minor, rev = 0, 0, 0, 0
        if len(version_split) == 3:
            build, major, minor = version_split
        elif len(version_split) == 4:
            build, major, minor, rev = version_split

        return dict(
            build = build,
            major = major,
            minor = minor,
            rev = rev)

    def compare_version_info(self, version_info, this_version):
        for field in ['build', 'major', 'minor', 'rev']:
            if version_info[field] > this_version[field]:
                return True
            elif version_info[field] < this_version[field]:
                return False
        return False

    def subsectionchecked(self, event=None):
        if self.screenshotdialog.subsectioncheck.IsChecked():
            self.screenshotdialog.subsectiontop.Enable()
            self.screenshotdialog.subsectionleft.Enable()
            self.screenshotdialog.subsectionwidth.Enable()
            self.screenshotdialog.subsectionheight.Enable()
        else:
            self.screenshotdialog.subsectiontop.Disable()
            self.screenshotdialog.subsectionleft.Disable()
            self.screenshotdialog.subsectionwidth.Disable()
            self.screenshotdialog.subsectionheight.Disable()

    def exitMenuClicked(self, event):  # wxGlade: chronoFrame.<event_handler>
        self.Close()


class ScreenshotConfigDialog(screenshotConfigDialog):
    def __init__(self, *args, **kwargs):
        screenshotConfigDialog.__init__(self, *args, **kwargs)

    def screenshotSaveFolderBrowse(self, event):
        # dir browser
        path = self.GetParent().dirBrowser(
                            'Select folder where screenshots will be saved',
                            self.GetParent().getConfig('screenshot_save_folder')
                        )

        if path is not '':
            self.GetParent().updateConfig({'screenshot_save_folder': path})
            self.screenshotsavefoldertext.SetValue(path)


class WebcamConfigDialog(webcamConfigDialog):
    def __init__(self,  *args, **kwargs):
        webcamConfigDialog.__init__(self, *args, **kwargs)

        # get cam
        self.has_cam = False
        try:
            image = self.GetParent().getWebcamCapture()
            self.has_cam = True
        except Exception, e:
            self.GetParent().showWarning(
                        'No Webcam Found', 'Could not initialize camera.')
            logging.error(repr(e))
            self.GetParent().webcamcheck.SetValue(False)

    def webcamSaveFolderBrowse(self, event):
        # dir browser
        path = self.GetParent().dirBrowser(
                    'Select folder where webcam shots will be saved',
                    self.GetParent().getConfig('webcam_save_folder'))

        if path is not '':
            self.webcamsavefoldertext.SetValue(path)
            self.GetParent().updateConfig({'webcam_save_folder': path})

    def testWebcamPressed(self, event):
        if self.has_cam:
            self.temppath = tempfile.mkstemp('.jpg')[1]
            self.temppath = self.temppath[:-4]
            # takeWebcam automatically appends the extension again

            # create a popup with the image
            dlg = WebcamPreviewDialog(self)
            dlg.ShowModal()
            dlg.Destroy()

            # remove the temp file
            try:
                os.unlink(self.temppath + '.jpg')
            except Exception, e:
                logging.warning(
                "Failed to delete temp file %s: %s" % (self.temppath, repr(e)))


class WebcamPreviewDialog(webcamPreviewDialog):

    def __init__(self, *args, **kwargs):
        webcamPreviewDialog.__init__(self, *args, **kwargs)
        self.parent = self.GetParent().GetParent()
        self.timer = Timer(self.callback)
        self.timer.Start(250)

        self.temppath = self.GetParent().temppath

        self.previewokbutton.Bind(wx.EVT_BUTTON, self.close)

    def close(self, event=None):
        self.timer.Stop()
        self.previewbitmap.SetBitmap(wx.NullBitmap)
        del self.timer
        if event:
            event.Skip()

    def callback(self):
        try:
            path = self.parent.takeWebcam(
                        os.path.basename(self.temppath),
                        os.path.dirname(self.temppath),
                        ''
                    )

            # try this so WX doesnt freak out if the file isnt a bitmap
            pilimage = Image.open(path)
            myWxImage = wx.EmptyImage( pilimage.size[0], pilimage.size[1] )
            myWxImage.SetData( pilimage.convert( 'RGB' ).tostring() )
            bitmap = myWxImage.ConvertToBitmap()

            self.previewbitmap.SetBitmap(bitmap)
            self.previewbitmap.CenterOnParent()

        except Exception, e:
            logging.debug(
                    "Exception while showing camera preview: %s" % repr(e))


class Timer(wx.Timer):
    """Timer class"""
    def __init__(self, callback):
        wx.Timer.__init__(self)
        self.callback = callback

    def Notify(self):
        self.callback()


class ProgressPanel(wx.Panel):

    def __init__(self, *args, **kwds):
        wx.Panel.__init__(self, *args, **kwds)
        self.Bind(wx.EVT_PAINT, self.OnPaint)

        self.progress = 0

    def setProgress(self, progress):
        self.progress = progress

        dc = wx.WindowDC(self)
        dc.SetPen(wx.Pen(wx.Colour(0,0,255,255)))
        dc.SetBrush(wx.Brush(wx.Colour(0,0,255,220)))

        # build rect
        width,height = self.GetSizeTuple()
        size = max(2, (width-10)*self.progress)
        rect = wx.Rect(5,8, size ,5)

        # draw rect
        dc.Clear()
        dc.DrawRoundedRectangleRect(rect, 2)

    def OnPaint(self, evt):
        # this doesnt appear to work at all...
        width,height = self.GetSizeTuple()

        # get drawing canvas
        dc = wx.PaintDC(self)

        dc.SetPen(wx.Pen(wx.Colour(0,0,255,255)))
        dc.SetBrush(wx.Brush(wx.Colour(0,0,255,220)))

        # build rect
        size = max(2, (width-10)*self.progress)
        rect = wx.Rect(5,8, size ,5)

        # draw rect
        dc.Clear()
        dc.BeginDrawing()
        dc.DrawRoundedRectangleRect(rect, 2)
        dc.EndDrawing()


class TaskBarIcon(wx.TaskBarIcon):

    def __init__(self, parent, MainFrame, workingdir):
        wx.TaskBarIcon.__init__(self)
        self.parentApp = parent
        self.MainFrame = MainFrame
        self.wx_id = wx.NewId()

        if ON_WINDOWS:
            icon_file = os.path.join(
                            os.path.abspath(workingdir),
                            'chronolapse.ico'
                        )
        else:
            icon_file = os.path.join(
                            os.path.abspath(workingdir),
                            'chronolapse_24.ico'
                        )
        self.SetIcon(wx.Icon(icon_file, wx.BITMAP_TYPE_ICO), 'Chronolapse')
        self.CreateMenu()

    def toggle_window_visibility(self, event):
        if self.MainFrame.IsIconized() or not self.MainFrame.IsShown():
            self.set_window_visible_on(event)
        else:
            self.set_window_visible_off(event)

    def set_window_visible_off(self, event):
        self.MainFrame.Show(False)
        self.set_icon_action_text(True)

    def set_window_visible_on(self, event):
        self.MainFrame.Iconize(False)
        self.MainFrame.Show(True)
        self.MainFrame.Raise()
        self.set_icon_action_text(False)

    def set_icon_action_text(self, minimized=True):
        if minimized:
            self.menu.FindItemById(self.wx_id).SetText("Restore")
        else:
            self.menu.FindItemById(self.wx_id).SetText("Minimize")

    def iconized(self, event):
        # bound on non-windows only
        if self.MainFrame.IsIconized():
            logging.debug("Main Frame Is Iconized")
            self.set_icon_action_text(True)
            self.MainFrame.Show(False)
        else:
            logging.debug("Main Frame Is Not Iconized")
            self.set_icon_action_text(False)
            self.MainFrame.Show(True)
            self.MainFrame.Raise()

    def CreateMenu(self):
        self.Bind(wx.EVT_TASKBAR_RIGHT_UP, self.ShowMenu)
        self.Bind(wx.EVT_TASKBAR_LEFT_DCLICK, self.toggle_window_visibility)
        self.Bind(wx.EVT_MENU, self.toggle_window_visibility, id=self.wx_id)
        self.Bind(wx.EVT_MENU, self.MainFrame.iconClose, id=wx.ID_EXIT)
        if ON_WINDOWS:
            self.MainFrame.Bind(wx.EVT_ICONIZE, self.set_window_visible_off)
        else:
            self.MainFrame.Bind(wx.EVT_ICONIZE, self.iconized)
        self.menu=wx.Menu()
        self.menu.Append(self.wx_id, "Minimize","...")
        self.menu.AppendSeparator()
        self.menu.Append(wx.ID_EXIT, "Close Chronolapse")

    def ShowMenu(self,event):
        self.PopupMenu(self.menu)
##        if self.MainFrame.IsShown() and not self.MainFrame.IsIconized():
##            self.menu.FindItemById(self.wx_id).SetText("Minimize")
##        else:
##            self.menu.FindItemById(self.wx_id).SetText("Restore")


class TaskBarFrame(wx.Frame):
    def __init__(self, parent, MainFrame, id, title, workingdir):
        wx.Frame.__init__(self, parent, -1, title, size = (1, 1),
            style=wx.FRAME_NO_TASKBAR|wx.NO_FULL_REPAINT_ON_RESIZE)
        self.tbicon = TaskBarIcon(self, MainFrame, workingdir)
        self.Show(True)
        self.MainFrame = MainFrame

    def kill(self, event):
        event.Skip()
        self.tbicon.RemoveIcon()
        self.tbicon.Destroy()
        self.Close()

    def toggle_window_visibility(self, event):
        self.tbicon.toggle_window_visibility(event)

    def set_icon_action_text(self, minimized):
        self.tbicon.set_icon_action_text(minimized)


# run it!
if __name__ == "__main__":
    app = wx.App(0)
    chronoframe = ChronoFrame(None, -1, "")
    app.SetTopWindow(chronoframe)
    chronoframe.doShow()
    app.MainLoop()