Chronolapse
===========

Chronolapse makes it easy to record screenshots and 
camera captures on a schedule then combine them 
into timelapse videos. Chronolapse provides the tools
for capturing the images, lightly processing them,
adding optional 'picture in picture', rendering the
images into video, and adding audio. 

Chronolapse uses MEncoder to render the captured images
into video - make sure you have MEncoder installed and on
your path. Alternatively, you can select the MEncoder
executable on the Chronolapse video tab. Additionally,
Chronolapse can save image files in either timestamp
format or sequential integer format so the resulting
images can be combined using other external tools like
VirtualDub.


Chronolapse 2.0 is a rewrite of the original
Chronolapse codebase with generally cleaner code, 
much better configuration control, some new functionality,
and some old, unused features pruned away.

Most significantly, Chronolapse 2.0 uses the OpenCV 
library to support webcam captures on all platforms.



Command Line Options
--------------------

- -a / --autostart
    Automatically starts capturing immediately

- -b / --background
    Starts Chronolapse in the background without showing
    the frame at all. You can open the Chronolapse window
    from the taskbar on supported systems.

- --config_file
    The location of the configuration file. If not found, a new
    one will be created at this location. This must be writable.
    Defaults to 'chronolapse.config'

- --sequential_image_format 
    Sets the format string for sequential image filenames
    using python's string formatting and passing in the next
    integer number.
    Defaults to '%05d'

- --timestamp_filename_format
    Sets the format string for rendering timestamps on images
    using python's datetime.strftime function.
    Defaults to '%Y-%m-%d %H:%M:%S'

- -v / --verbose
    Increases command line output

- -d / --debug
    Greatly increases command line output. Helpful for debugging.


Configuration Hacks
-------------------

Some configuration is only exposed via Chronolapse's configuration
file, which defaults to chronolapse.config in the chronolapse
folder. The file is a simple json file - you can carefully edit
it by hand (you may want to use a json formatter to make it
easier on yourself).

The configuration file contains a top level key 'chronolapse' and
a long list of simple key: values underneath it. 

Example:

```
{
    "chronolapse": {
        "use_webcam': true
    }
}
```

Most of the configuration keys are automatically handled by the
user interface and will be overwritten when you change them in
Chronolapse itself. However, there are several advanced options 
that can only be changed by editing the configuration.

*Changing Camera*

OpenCV does not do a great job of enumerating the available 
capture devices, but it is possible to manually specify the
device number you wish to use by editing the
`webcam_device_number`
field. The default device number is 0.


