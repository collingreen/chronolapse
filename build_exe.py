"""
requires resourcehacker
    http://www.angusj.com/resourcehacker/ or
    https://portableapps.com/apps/utilities/resource-hacker-portable
"""
import os
import shutil
import subprocess
import sys
import PyInstaller.__main__

PACKAGE_NAME = 'chronolapse'
RESOURCE_HACKER_EXE = os.path.join(
    'ResourceHackerPortable',
    'ResourceHackerPortable.exe'
)
INTERMEDIATE_EXE_NAME = "{}_intermediate".format(PACKAGE_NAME)
ICON_PATH = 'chronolapse.ico'

OTHER_FILES = [
    'chronolapse.ico',
    'chronolapse_24.ico',
    'README.md',
    'LICENSE'
]

def create_exe(this_dir, exe_name):
    print("Deleting old build artifacts")
    try:
        shutil.rmtree(os.path.join(this_dir, "build"))
    except: pass
    try:
        shutil.rmtree(os.path.join(this_dir, "dist"))
    except: pass
    try:
        os.unlink(os.path.join(this_dir, "{}.spec".format(PACKAGE_NAME)))
    except: pass

    pyinstaller_config = [
        '--name=%s' % exe_name,
        '--onefile',
        #'--windowed',
        # this breaks pyinstaller, not sure why
        #'--icon=%s%s.' % (os.path.join(this_dir, ICON_PATH), os.pathsep),
        os.path.join(this_dir, 'chronolapse.py'),
    ]

    print("Building EXE")
    PyInstaller.__main__.run(pyinstaller_config)

def copy_other_files(this_dir, dist_dir):
    for f in OTHER_FILES:
        shutil.copy2(
            os.path.join(this_dir, f),
            os.path.join(dist_dir, f)
        )

def modify_icon(exe_path, new_icon_path, new_exe_path):
    print("Updating Icon")
    # THIS DOESNT ALWAYS SHOW UP IN EXPLORER
    command = "{} -open {} -save {} -action addoverwrite -res {} -mask ICONGROUP,MAINICON,".format(
        RESOURCE_HACKER_EXE,
        os.path.join("dist", exe_path),
        os.path.join("dist", new_exe_path),
        new_icon_path
    )
    print("command: {}".format(command))
    subprocess.call(command, shell=True)
    os.unlink(os.path.join("dist", exe_path))

if __name__ == '__main__':
    should_modify_icon = sys.platform == 'win32'
    if should_modify_icon:
        exe_name = INTERMEDIATE_EXE_NAME
    else:
        exe_name = PACKAGE_NAME

    this_dir = os.path.dirname(os.path.abspath(__file__))

    create_exe(this_dir, exe_name)
    copy_other_files(this_dir, 'dist')

    if should_modify_icon:
        modify_icon(
            '{}.exe'.format(exe_name),
            ICON_PATH,
            '{}.exe'.format(PACKAGE_NAME)
        )