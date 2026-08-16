# GENERATED FILE - DO NOT EDIT BY HAND
#
# Regenerate with generate_armor_db.py (build_wotmod.py already does this
# automatically as its first step). Source of truth: armor_data/vehicles.json

from dispersionreticle.armorangle.armor_db import ArmorPlate, VehicleArmor, mirroredPair


ARMOR_DB = {
    # internal name CONFIRMED from python.log on 2026-08-16 (training room test).
    # mm/slope values still TODO verify against Tankopedia.
    'germany:G04_PzVI_Tiger_I': VehicleArmor(
        frontPlates=(
            [ArmorPlate(label='front', bearingDeg=0, slopeDeg=10, nominalMm=100)]
        ),
        sidePlates=(
            mirroredPair(label='side upper', bearingDeg=90, slopeDeg=0, nominalMm=80) +
            mirroredPair(label='side lower', bearingDeg=90, slopeDeg=0, nominalMm=60)
        ),
        safetyThreshold1=None,
        safetyThreshold2=None
    ),

    # internal name CONFIRMED from python.log on 2026-08-17 (training room test).
    # mm/slope values hand-filled by the user directly, then sign-corrected (lower glacis and
    # side lower flipped negative relative to upper) after a live elevation test - confirmed correct.
    'germany:G16_PzVIB_Tiger_II': VehicleArmor(
        frontPlates=(
            [ArmorPlate(label='upper glacis', bearingDeg=0, slopeDeg=50, nominalMm=160)] +
            [ArmorPlate(label='lower glacis', bearingDeg=0, slopeDeg=-50, nominalMm=100)]
        ),
        sidePlates=(
            mirroredPair(label='side upper', bearingDeg=90, slopeDeg=25, nominalMm=80) +
            mirroredPair(label='side lower', bearingDeg=90, slopeDeg=0, nominalMm=80)
        ),
        safetyThreshold1=None,
        safetyThreshold2=None
    ),

    # UNVERIFIED GUESS - both the internal name and the mm/slope values.
    # Never seen in python.log, never live-tested.
    'germany:G65_E_75': VehicleArmor(
        frontPlates=(
            [ArmorPlate(label='front', bearingDeg=0, slopeDeg=15, nominalMm=150)]
        ),
        sidePlates=(
            mirroredPair(label='side upper', bearingDeg=90, slopeDeg=0, nominalMm=80) +
            mirroredPair(label='side lower', bearingDeg=90, slopeDeg=0, nominalMm=80)
        ),
        safetyThreshold1=None,
        safetyThreshold2=None
    ),

}
