import BigWorld

from dispersionreticle.hooks.aih_hooks import g_oneTickCache


def getFocusedDispersionSize(targetPos):
    playerAvatar = BigWorld.player()
    vehicleDesc = playerAvatar._PlayerAvatar__getDetailedVehicleDescriptor()

    # this doesn't account for arcade view
    # but let's leave it commented as a last resort
    # gunPos = BigWorld.camera().position

    shotDir = targetPos - g_oneTickCache.sniperViewportPosition
    shotDist = shotDir.length

    # gun dispersion per 1m unit
    gunDispersionAngle = vehicleDesc.gun.shotDispersionAngle

    # multiplier that accounts crew, food, etc.
    # PlayerAvatar -> getOwnVehicleShotDispersionAngle
    # PlayerAvatar -> updateTargetingInfo
    # dispersionInfo[0] = shotDispMultiplierFactor
    # dispersionInfo[1] = gunShotDispersionFactorsTurretRotation
    # dispersionInfo[2] = chassisShotDispersionFactorsMovement
    # dispersionInfo[3] = chassisShotDispersionFactorsRotation
    # dispersionInfo[4] = aimingTime
    shotDispMultiplierFactor = playerAvatar._PlayerAvatar__dispersionInfo[0]

    # actual dispersion per 1m unit
    dispersionAngle = gunDispersionAngle * shotDispMultiplierFactor

    dualAccuracy = g_oneTickCache.dualAccuracy
    if dualAccuracy is not None:
        dispersionAngle *= dualAccuracy.getCurrentDualAccuracyFactor()

    # size is diameter that scales with distance
    return 2.0 * shotDist * dispersionAngle


def getFocusedDispersionAngle():
    playerAvatar = BigWorld.player()
    vehicleDesc = playerAvatar._PlayerAvatar__getDetailedVehicleDescriptor()

    # gun dispersion per 1m unit
    shotDispersionAngle = vehicleDesc.gun.shotDispersionAngle

    # multiplier that accounts crew, food, etc.
    # PlayerAvatar -> updateTargetingInfo
    # dispersionInfo[0] = shotDispMultiplierFactor
    # dispersionInfo[1] = gunShotDispersionFactorsTurretRotation
    # dispersionInfo[2] = chassisShotDispersionFactorsMovement
    # dispersionInfo[3] = chassisShotDispersionFactorsRotation
    # dispersionInfo[4] = gunShotDispersionFactorsAfterShot
    # dispersionInfo[5] = aimingTime
    shotDispMultiplierFactor = playerAvatar._PlayerAvatar__dispersionInfo[0]

    # just return actual angle for conic dispersion
    return shotDispersionAngle * shotDispMultiplierFactor
