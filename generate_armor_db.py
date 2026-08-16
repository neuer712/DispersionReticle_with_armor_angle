"""
Generic codegen - reads
armor_data/vehicles.json and writes
src/dispersionreticle/armorangle/armor_db/<nation>.py for each top-level
nation key in the JSON, and reads armor_data/tier_thresholds.json and
writes src/dispersionreticle/armorangle/armor_db/tier_thresholds.py.

JSON is the source of truth now - the generated .py files under armor_db/
get OVERWRITTEN every time this runs (which build_wotmod.py does
automatically), so don't hand-edit them, edit the JSON instead.

vehicles.json schema (per vehicle, keyed by internal name e.g. "germany:G04_..."):
    {
        "notes": "free text, emitted as a Python comment above the entry (optional)",
        "safetyThreshold1": <mm or null>,
        "safetyThreshold2": <mm or null>,
        "frontPlates": [ {"label": str, "bearingDeg": num, "slopeDeg": num,
                           "nominalMm": num, "mirror": bool}, ... ],
        "sidePlates": [ ... same shape ... ]
    }
"mirror: true" emits a mirroredPair(...) call (both left/right entries);
"mirror: false" emits a single ArmorPlate(...).

A vehicle's own safetyThreshold1/2 (if BOTH set) override the per-tier
default from tier_thresholds.json - see armor_math.resolveSafetyThresholds.

tier_thresholds.json schema: {"<tier 1-10>": [threshold1 or null, threshold2 or null], ...}

Usage:
    C:\\Python27\\python.exe generate_armor_db.py
"""
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
VEHICLES_JSON_PATH = os.path.join(ROOT, "armor_data", "vehicles.json")
TIER_THRESHOLDS_JSON_PATH = os.path.join(ROOT, "armor_data", "tier_thresholds.json")
OUTPUT_DIR = os.path.join(ROOT, "src", "dispersionreticle", "armorangle", "armor_db")

HEADER = '''# GENERATED FILE - DO NOT EDIT BY HAND
#
# Regenerate with generate_armor_db.py (build_wotmod.py already does this
# automatically as its first step). Source of truth: armor_data/vehicles.json

from dispersionreticle.armorangle.armor_db import ArmorPlate, VehicleArmor, mirroredPair


ARMOR_DB = {
'''


def formatPlate(plate, indent):
    # str() the label to avoid an unnecessary u'...' prefix in the generated
    # source - json.load gives unicode strings in Python 2, but these are
    # always plain ASCII labels
    args = "label=%r, bearingDeg=%r, slopeDeg=%r, nominalMm=%r" % (
        str(plate["label"]), plate["bearingDeg"], plate["slopeDeg"], plate["nominalMm"])

    if plate.get("mirror"):
        return "%smirroredPair(%s)" % (indent, args)
    return "%s[ArmorPlate(%s)]" % (indent, args)


def formatPlateList(plates, indent):
    if not plates:
        return "[]"

    parts = [formatPlate(p, indent + "    ") for p in plates]
    return "(\n" + " +\n".join(parts) + "\n" + indent + ")"


def formatVehicle(vehicleKey, vehicle):
    lines = []

    notes = vehicle.get("notes")
    if notes:
        for noteLine in notes.split("\n"):
            lines.append("    # %s\n" % noteLine)

    lines.append("    %r: VehicleArmor(\n" % str(vehicleKey))
    lines.append("        frontPlates=%s,\n" % formatPlateList(vehicle.get("frontPlates", []), "        "))
    lines.append("        sidePlates=%s,\n" % formatPlateList(vehicle.get("sidePlates", []), "        "))
    lines.append("        safetyThreshold1=%r,\n" % vehicle.get("safetyThreshold1"))
    lines.append("        safetyThreshold2=%r\n" % vehicle.get("safetyThreshold2"))
    lines.append("    ),\n\n")

    return "".join(lines)


def generateNationModule(vehicles):
    parts = [HEADER]
    for vehicleKey in sorted(vehicles.keys()):
        parts.append(formatVehicle(vehicleKey, vehicles[vehicleKey]))
    parts.append("}\n")
    return "".join(parts)


def generateVehicleModules():
    with open(VEHICLES_JSON_PATH, "r") as f:
        data = json.load(f)

    for nationKey in sorted(data.keys()):
        moduleSource = generateNationModule(data[nationKey])
        outputPath = os.path.join(OUTPUT_DIR, "%s.py" % nationKey)

        with open(outputPath, "w") as f:
            f.write(moduleSource)

        print("Generated %s (%d vehicles)" % (outputPath, len(data[nationKey])))


def generateTierThresholdsModule():
    with open(TIER_THRESHOLDS_JSON_PATH, "r") as f:
        data = json.load(f)

    lines = [
        "# GENERATED FILE - DO NOT EDIT BY HAND\n",
        "#\n",
        "# Regenerate with generate_armor_db.py (build_wotmod.py already does this\n",
        "# automatically as its first step). Source of truth: armor_data/tier_thresholds.json\n",
        "\n",
        "# {tier: (safetyThreshold1, safetyThreshold2)} - see armor_math.resolveSafetyThresholds.\n",
        "# A None entry, or a missing tier key, means no tier-level default applies.\n",
        "TIER_SAFETY_THRESHOLDS = {\n",
    ]

    for tierKey in sorted(data.keys(), key=int):
        threshold1, threshold2 = data[tierKey]
        lines.append("    %s: (%r, %r),\n" % (int(tierKey), threshold1, threshold2))

    lines.append("}\n")

    outputPath = os.path.join(OUTPUT_DIR, "tier_thresholds.py")
    with open(outputPath, "w") as f:
        f.write("".join(lines))

    print("Generated %s (%d tiers)" % (outputPath, len(data)))


def generateAll():
    if not os.path.isdir(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    generateVehicleModules()
    generateTierThresholdsModule()


if __name__ == "__main__":
    generateAll()
