import math

from collections import namedtuple


###########################################################
# Pure math for "current aim direction as assumed incoming
# shot direction" armor angle / ricochet estimation.
#
# No BigWorld/game imports here on purpose - keep it testable
# and reviewable in isolation from the game API surface.
#
# See HANDOFF.md for the original derivation (vertical side
# plates only, unsigned hull angle). This generalizes it to
# an arbitrary armor plate defined by a fixed (bearingDeg,
# slopeDeg) pair relative to the hull - see plateIncidenceDeg.
###########################################################

AP_RICOCHET_THRESHOLD_DEG = 70.0
HEAT_RICOCHET_THRESHOLD_DEG = 85.0

# flat, caliber-agnostic shell normalization applied only when a shot
# does NOT ricochet - see approxEffectiveThicknessMm. Real WoT scales
# this up for oversized calibers vs thin plates, but that needs a known
# incoming caliber, which this defensive-only tool deliberately doesn't
# assume (see HANDOFF.md's original design decision).
FLAT_NORMALIZATION_DEG = 5.0

# below this cosine, treat effective thickness as unbounded/meaningless
# rather than dividing by a near-zero number
_MIN_COS_FOR_EFFECTIVE_THICKNESS = 0.05

# CONFIRMED WRONG by training-room test on 2026-08-17 (Tiger II upper glacis
# and side main both behaved backwards when elevating the gun) and flipped
# from the original +1.0 guess. So: positive gunPitch = gun pointing DOWN
# (depression), negative = UP (elevation) - opposite of the "common" pitch
# convention this was originally guessed from.
#
# How this was diagnosed/could be re-verified: on a vehicle with a
# backward-sloped front plate (e.g. Tiger II, 50deg slope), elevate the gun
# (aim upward) while pointed roughly at the hull's own front (alpha near 0).
# With the correct sign, the front plate's incidence angle should go DOWN
# (more dangerous) as you elevate - a shot arriving from above hits a
# backward-leaning plate more perpendicularly, like rain hitting a sloped
# roof more directly the closer the rain comes from straight overhead.
GUN_PITCH_ELEVATION_SIGN = -1.0


def normalizeYawSignedDeg(turretYawRadians):
    """
    Normalizes turretYaw (radians, may come in any range) to a SIGNED
    angle in (-180, 180] degrees between hull forward axis and current
    aim direction. Positive = aim direction is toward hull's right side.
    """
    wrapped = math.atan2(math.sin(turretYawRadians), math.cos(turretYawRadians))
    return math.degrees(wrapped)


def normalizeElevationSignedDeg(gunPitchRadians):
    """
    Converts gunPitch (radians) to a signed elevation angle in degrees,
    positive = assumed shot direction points upward. See
    GUN_PITCH_ELEVATION_SIGN for the (unverified) sign convention.
    """
    return GUN_PITCH_ELEVATION_SIGN * math.degrees(gunPitchRadians)


def normalizeAngleDeg(angleDeg):
    """Wraps an arbitrary angle in degrees to (-180, 180]."""
    wrapped = (angleDeg + 180.0) % 360.0 - 180.0
    if wrapped <= -180.0:
        wrapped += 360.0
    return wrapped


def plateIncidenceDeg(alphaSignedDeg, bearingDeg, slopeDeg, elevationSignedDeg=0.0):
    """
    True incidence angle (from plate normal) for a plate at a fixed
    bearing (yaw offset from hull forward, signed - 0 = front, +90 =
    right side, -90 = left side, etc.) and slope (fixed tilt from
    vertical), given the current signed hull-to-aim-line yaw angle and
    an optional signed elevation angle (vertical component of the
    assumed shot direction, positive = shot direction points upward).

    Exact (no further approximation) for this plate model: both the plate
    normal and the shot direction are built from two fixed rotations each
    (a "tilt" then a "yaw" of an initially-forward-pointing unit vector),
    so this is a plain 3D dot product of two unit vectors, not a flat-plane
    shortcut:

        N = (cos(b)cos(s), sin(b)cos(s), sin(s))                # plate normal
        L = (cos(a)cos(e), sin(a)cos(e), sin(e))                 # shot direction
        cos(incidence) = N . L = cos(s)cos(e)cos(a - b) + sin(s)sin(e)

    in hull-local (forward, right, up) coordinates. At elevationSignedDeg=0
    this reduces exactly to the flat-trajectory formula used previously
    (cos(s) * cos(a - b)).

    Remaining known simplification: this still doesn't account for the
    tank's OWN hull being tilted by terrain (a vehicle parked on a slope
    has its local "up" no longer aligned with world-up) - see HANDOFF.md.
    That's a separate effect from shot elevation and is not modeled here.

    Returns None if the plate faces away from the shot direction entirely
    (incidence >= 90 degrees, i.e. it isn't the plate that would be hit).
    """
    yawDiff = normalizeAngleDeg(alphaSignedDeg - bearingDeg)

    slopeRad = math.radians(slopeDeg)
    elevationRad = math.radians(elevationSignedDeg)

    cosIncidence = (math.cos(slopeRad) * math.cos(elevationRad) * math.cos(math.radians(yawDiff))
                    + math.sin(slopeRad) * math.sin(elevationRad))
    cosIncidence = max(-1.0, min(1.0, cosIncidence))

    if cosIncidence <= 0.0:
        return None

    return math.degrees(math.acos(cosIncidence))


def isForcedRicochet(incidenceDeg, isHeat=False):
    if incidenceDeg is None:
        return None

    threshold = HEAT_RICOCHET_THRESHOLD_DEG if isHeat else AP_RICOCHET_THRESHOLD_DEG
    return incidenceDeg > threshold


def approxEffectiveThicknessMm(nominalMm, incidenceDeg, apRicochet):
    """
    Rough approximation only: nominalMm / cos(incidence - normalization).

    - if the shot would ricochet, there's no penetration attempt at all,
      so there's no effective thickness to show (returns None)
    - otherwise, applies a flat 5 degree normalization (FLAT_NORMALIZATION_DEG)
      before the cosine, since the incoming shell's caliber (and thus the
      real caliber-scaled normalization bonus) is unknown - see HANDOFF.md's
      "known simplifications" section
    """
    if incidenceDeg is None or apRicochet:
        return None

    normalizedIncidence = max(0.0, incidenceDeg - FLAT_NORMALIZATION_DEG)

    cosIncidence = math.cos(math.radians(normalizedIncidence))
    if cosIncidence < _MIN_COS_FOR_EFFECTIVE_THICKNESS:
        return None

    return nominalMm / cosIncidence


PlateAssessment = namedtuple("PlateAssessment", [
    "plate", "incidenceDeg", "apRicochet", "approxEffectiveMm"
])


def assessPlate(alphaSignedDeg, elevationSignedDeg, plate):
    """
    plate is an armor_db.ArmorPlate (bearingDeg, slopeDeg, nominalMm, ...).
    Returns a PlateAssessment, or None if the plate faces away from the
    aim line entirely (not the one that would be hit).
    """
    incidenceDeg = plateIncidenceDeg(alphaSignedDeg, plate.bearingDeg, plate.slopeDeg, elevationSignedDeg)
    if incidenceDeg is None:
        return None

    apRicochet = isForcedRicochet(incidenceDeg, isHeat=False)
    approxEffectiveMm = approxEffectiveThicknessMm(plate.nominalMm, incidenceDeg, apRicochet)

    return PlateAssessment(
        plate=plate,
        incidenceDeg=incidenceDeg,
        apRicochet=apRicochet,
        approxEffectiveMm=approxEffectiveMm
    )


def assessPlates(alphaSignedDeg, elevationSignedDeg, plates):
    """Assesses a list of ArmorPlate, dropping any that face away."""
    assessments = [assessPlate(alphaSignedDeg, elevationSignedDeg, plate) for plate in plates]
    return [assessment for assessment in assessments if assessment is not None]


def assessVehicle(alphaSignedDeg, elevationSignedDeg, vehicleArmor):
    """
    vehicleArmor is an armor_db.VehicleArmor (frontPlates, sidePlates).
    Returns {"front": [PlateAssessment, ...], "side": [PlateAssessment, ...]}.
    """
    return {
        "front": assessPlates(alphaSignedDeg, elevationSignedDeg, vehicleArmor.frontPlates),
        "side": assessPlates(alphaSignedDeg, elevationSignedDeg, vehicleArmor.sidePlates)
    }


###########################################################
# UI slot classification (armor_angle_hud.py's fixed grid layout).
#
# Kept here rather than in armor_angle_hud.py specifically so it's
# testable without BigWorld - see reference_screenshots/2_hoped_positions.jpg
# for the layout this maps onto:
#
# row 1 (5 across): left side upper, left pike, front upper, right pike, right side upper
# row 2 (3, aligned under their row-1 counterparts): left side lower, front lower, right side lower
###########################################################

# (slotKey, columnIndex, rowIndex) - rowIndex 0 = row 1, -1 = row 2 (below row 1)
UI_SLOTS = (
    ("left_side_upper", -2, 0),
    ("left_pike", -1, 0),
    ("front_upper", 0, 0),
    ("right_pike", 1, 0),
    ("right_side_upper", 2, 0),
    ("left_side_lower", -2, -1),
    ("front_lower", 0, -1),
    ("right_side_lower", 2, -1),
)


def classifyFrontPlate(plate):
    if plate.bearingDeg == 0:
        return "front_lower" if "lower" in plate.label.lower() else "front_upper"
    return "right_pike" if plate.bearingDeg > 0 else "left_pike"


def classifySidePlate(plate):
    isLower = "lower" in plate.label.lower()
    if plate.bearingDeg > 0:
        return "right_side_lower" if isLower else "right_side_upper"
    return "left_side_lower" if isLower else "left_side_upper"


###########################################################
# Color category per plate, based on a per-VEHICLE pair of safety
# thresholds (mm of approxEffectiveMm), not per-plate - the idea is a
# single "is this comfortable for my current tier" judgement call, reused
# across whichever plate happens to be showing. Returns a category name,
# not a color - armor_angle_hud.py maps that to an actual GUI.Text colour,
# keeping this module GUI/BigWorld-free.
#
# category rules:
# - ricochet always wins, regardless of thresholds: "ricochet"
# - no thresholds configured for this vehicle (either is None): "safe"
#   (blue) unconditionally - no judgement to make
# - normal case (safetyThreshold1 <= safetyThreshold2):
#     mm < threshold1              -> "danger"  (red)
#     threshold1 <= mm < threshold2 -> "warning" (yellow)
#     mm >= threshold2             -> "safe"    (blue)
# - degenerate/inverted case (safetyThreshold1 > safetyThreshold2):
#   the "yellow band" would be empty/backwards, so just split in two
#   using threshold1 alone: mm < threshold1 -> "danger", else -> "safe"
###########################################################

COLOR_DANGER = "danger"
COLOR_WARNING = "warning"
COLOR_SAFE = "safe"
COLOR_RICOCHET = "ricochet"


def resolveSafetyThresholds(vehicleArmor, tier, tierSafetyThresholds):
    """
    Per-vehicle thresholds (vehicleArmor.safetyThreshold1/2) win if BOTH are
    set (an explicit override for that specific vehicle). Otherwise falls
    back to a per-tier default from tierSafetyThresholds (a {tier: (t1, t2)}
    dict, e.g. armor_db.tier_thresholds.TIER_SAFETY_THRESHOLDS - passed in
    rather than imported here to keep this module independent of armor_db).

    Returns (threshold1, threshold2), either of which may be None if
    nothing applies (no vehicle override AND no tier entry/tier unknown) -
    colorCategoryForAssessment already treats None as "no judgement, always
    safe/blue".
    """
    if vehicleArmor.safetyThreshold1 is not None and vehicleArmor.safetyThreshold2 is not None:
        return vehicleArmor.safetyThreshold1, vehicleArmor.safetyThreshold2

    if tier is None:
        return None, None

    return tierSafetyThresholds.get(tier, (None, None))


def colorCategoryForAssessment(assessment, safetyThreshold1, safetyThreshold2):
    if assessment.apRicochet:
        return COLOR_RICOCHET

    if safetyThreshold1 is None or safetyThreshold2 is None:
        return COLOR_SAFE

    mm = assessment.approxEffectiveMm
    if mm is None:
        return COLOR_SAFE

    if safetyThreshold1 <= safetyThreshold2:
        if mm < safetyThreshold1:
            return COLOR_DANGER
        if mm < safetyThreshold2:
            return COLOR_WARNING
        return COLOR_SAFE
    else:
        return COLOR_DANGER if mm < safetyThreshold1 else COLOR_SAFE
