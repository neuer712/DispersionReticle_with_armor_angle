import importlib

from collections import namedtuple


###########################################################
# Whitelist of vehicles with hand-filled armor data, split per
# nation and loaded lazily - only the nation(s) of vehicles
# actually played in a session get imported/parsed.
#
# Deliberately NOT reading armor thickness from vehicle
# descriptor / 3D geometry (see HANDOFF.md - that link was
# never verified against a live client). Vehicles not listed
# here simply don't show the HUD.
###########################################################

###########################################################
# ArmorPlate.slopeDeg sign convention
#
# slopeDeg is SIGNED. There are two physically distinct ways a plate can
# lean away from vertical, and they behave oppositely once shot elevation
# is involved (see armor_math.plateIncidenceDeg - the sin(slope)*sin(elevation)
# term flips sign with slopeDeg):
#
# - POSITIVE slopeDeg: the plate's TOP tucks IN toward the hull interior,
#   its BOTTOM sticks OUT toward the outside/enemy. This is the default,
#   "classic glacis" lean - use it for upper glacis plates, side plates
#   (upper hull sides typically narrow going up the same way), and pike
#   nose cheek plates (their bearingDeg carries the left/right tilt, their
#   slopeDeg still follows this same top-tucks-in convention).
#
# - NEGATIVE slopeDeg: the opposite lean - the plate's BOTTOM tucks in,
#   TOP sticks out. Lower glacis / lower front plates, and the lower part
#   of a hull side, commonly lean this way in real life, forming a "V"
#   crease against the upper plate above them.
#
# Plates are grouped into "upper part" / "lower part" per zone (front,
# side) instead of "main"/"weakspot" - a vehicle with only one part in a
# given zone (e.g. a flat-fronted tank with no distinct upper/lower
# glacis) just has one entry there; there's no separate weakspot flag
# since all plates display the same way regardless.
###########################################################

ArmorPlate = namedtuple("ArmorPlate", ["label", "bearingDeg", "slopeDeg", "nominalMm"])

# safetyThreshold1/2 are per-VEHICLE (not per-plate) mm thresholds used for
# color-coding in the HUD - see armor_math.colorCategoryForAssessment. Both
# None means "no color judgement configured for this vehicle" (always the
# neutral/safe color).
VehicleArmor = namedtuple("VehicleArmor", ["frontPlates", "sidePlates", "safetyThreshold1", "safetyThreshold2"])


def mirroredPair(label, bearingDeg, slopeDeg, nominalMm):
    """
    Convenience for armor that's bilaterally symmetric (true for virtually
    every WoT vehicle) - returns BOTH mirror-image ArmorPlate entries for a
    plate at a given bearing (e.g. bearingDeg=90 also gets a bearingDeg=-90
    twin), so the plate is found regardless of which way the hull is turned.

    This matters once shot elevation is in play (see armor_math.py's
    plateIncidenceDeg): a plate only defined at bearing=90 simply has no
    incidence value at all when the hull is turned left instead of right -
    it's not that its value would be wrong, there's no entry to evaluate.

    No-op (single entry, unchanged) for bearingDeg 0 or 180, which are
    already self-symmetric and would otherwise produce a duplicate.
    """
    plate = ArmorPlate(label=label, bearingDeg=bearingDeg, slopeDeg=slopeDeg, nominalMm=nominalMm)

    if bearingDeg == 0 or abs(bearingDeg) == 180:
        return [plate]

    return [plate, plate._replace(bearingDeg=-bearingDeg)]


_NATION_MODULES = {
    "germany": "dispersionreticle.armorangle.armor_db.germany"
}

_loadedNationDbs = {}


def getVehicleArmor(vehicleInternalName):
    nation, _sep, _tag = vehicleInternalName.partition(":")

    if nation not in _loadedNationDbs:
        moduleName = _NATION_MODULES.get(nation)
        if moduleName is None:
            return None

        module = importlib.import_module(moduleName)
        _loadedNationDbs[nation] = module.ARMOR_DB

    return _loadedNationDbs[nation].get(vehicleInternalName)
