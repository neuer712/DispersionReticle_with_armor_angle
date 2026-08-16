"""
Local dev build script - regenerates src/dispersionreticle/armorangle/armor_db/*.py from
armor_data/vehicles.json (see generate_armor_db.py), compiles src/ to .pyc
with Python 2.7 (must match the game's embedded interpreter - magic number
03f3, verified against an installed release build of this exact mod) and
packages a .wotmod zip (STORED, no compression, per the game's loader
requirement).

Usage:
    C:\\Python27\\python.exe build_wotmod.py [path-to-DispersionReticleFlash.swf]

If the swf path is omitted, defaults to DispersionReticleFlash.swf sitting
next to this script (also gitignored) - this feature never touched Flash,
so reusing an already-compiled swf from an existing release is correct.

Layout (reverse-engineered from pruszko.dispersion_reticle_3.1.9.wotmod,
already installed on this machine - used as ground truth instead of guessing):
    meta.xml
    res/scripts/client/dispersionreticle/**/*.pyc
    res/scripts/client/gui/mods/mod_DispersionReticle.pyc
    res/gui/dispersionreticle/imgs/*
    res/gui/dispersionreticle/translations/*.json
    res/gui/flash/DispersionReticleFlash.swf
"""
import compileall
import os
import sys
import zipfile

import generate_armor_db

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src")
GUI_SRC = os.path.join(SRC, "gui")
BUILD_DIR = os.path.join(ROOT, "build")

MOD_ID = "com.github.pruszko.dispersionreticle"
MOD_NAME = "DispersionReticle"
MOD_VERSION = "3.1.10-armor-angle"
MOD_DESCRIPTION = "Adds additional reticle representing focused gun dispersion. (+ armor angle HUD, local build)"

# fixed filename regardless of MOD_VERSION (which still goes into meta.xml)
# so deploy.bat can find the output without globbing/guessing. Lives under
# build/ (gitignored) rather than the repo root, to keep build output out
# of the way of tracked source.
OUTPUT_WOTMOD = os.path.join(BUILD_DIR, "pruszko.dispersion_reticle_dev.wotmod")

META_XML = """<root>
   <id>%s</id>
   <version>%s</version>
   <name>%s</name>
   <description>%s</description>
</root>
""" % (MOD_ID, MOD_VERSION, MOD_NAME, MOD_DESCRIPTION)


def cleanStrayPyc():
    for dirpath, _dirnames, filenames in os.walk(SRC):
        for filename in filenames:
            if filename.endswith(".pyc"):
                os.remove(os.path.join(dirpath, filename))


def compileAll():
    # compile_dir returns 1 (truthy) on full success in Python 2.7
    success = compileall.compile_dir(SRC, quiet=1)
    if not success:
        raise SystemExit("py_compile failed, see output above")


def buildZip(swfPath):
    if not os.path.isfile(swfPath):
        raise SystemExit("Flash file not found: %s" % swfPath)

    if not os.path.isdir(BUILD_DIR):
        os.makedirs(BUILD_DIR)

    if os.path.exists(OUTPUT_WOTMOD):
        os.remove(OUTPUT_WOTMOD)

    zf = zipfile.ZipFile(OUTPUT_WOTMOD, "w", zipfile.ZIP_STORED)
    try:
        zf.writestr("meta.xml", META_XML)

        packageRoot = os.path.join(SRC, "dispersionreticle")
        for dirpath, _dirnames, filenames in os.walk(packageRoot):
            for filename in filenames:
                if not filename.endswith(".pyc"):
                    continue
                fullPath = os.path.join(dirpath, filename)
                relPath = os.path.relpath(fullPath, SRC)
                arcName = "res/scripts/client/" + relPath.replace(os.sep, "/")
                zf.write(fullPath, arcName)

        entryPyc = os.path.join(SRC, "mod_DispersionReticle.pyc")
        zf.write(entryPyc, "res/scripts/client/gui/mods/mod_DispersionReticle.pyc")

        for dirpath, _dirnames, filenames in os.walk(GUI_SRC):
            for filename in filenames:
                fullPath = os.path.join(dirpath, filename)
                relPath = os.path.relpath(fullPath, GUI_SRC)
                arcName = "res/gui/" + relPath.replace(os.sep, "/")
                zf.write(fullPath, arcName)

        zf.write(swfPath, "res/gui/flash/DispersionReticleFlash.swf")
    finally:
        zf.close()

    print("Built: %s" % OUTPUT_WOTMOD)


if __name__ == "__main__":
    swfArg = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "DispersionReticleFlash.swf")

    generate_armor_db.generateAll()
    cleanStrayPyc()
    compileAll()
    buildZip(swfArg)
    cleanStrayPyc()
