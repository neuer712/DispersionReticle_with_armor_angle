import logging

from AvatarInputHandler import aih_global_binding, _BINDING_ID
from aih_constants import GUN_MARKER_TYPE, GUN_MARKER_FLAG

from dispersionreticle.hooks.aih_hooks import g_oneTickCache
from dispersionreticle.utils import overrideIn, isClientWG
from dispersionreticle.utils.reticle_registry import ReticleRegistry


logger = logging.getLogger(__name__)


class _Descriptors(object):
    gunMarkersFlags = aih_global_binding.bindRO(_BINDING_ID.GUN_MARKERS_FLAGS)
    clientMarkerDataProvider = aih_global_binding.bindRO(_BINDING_ID.CLIENT_GUN_MARKER_DATA_PROVIDER)
    serverMarkerDataProvider = aih_global_binding.bindRO(_BINDING_ID.SERVER_GUN_MARKER_DATA_PROVIDER)


_descriptors = _Descriptors()


def _areBothModesEnabled():
    return _isClientModeEnabled() and _isServerModeEnabled()


def _isClientModeEnabled():
    return _descriptors.gunMarkersFlags & GUN_MARKER_FLAG.CLIENT_MODE_ENABLED


def _isServerModeEnabled():
    return _descriptors.gunMarkersFlags & GUN_MARKER_FLAG.SERVER_MODE_ENABLED


if isClientWG():
    from gui.armor_flashlight.battle_controller import ArmorFlashlightBattleController
    from aih_constants import GunMarkerState

    # make sure to invoke armor flashlight state update only for client reticle,
    # when both client and server reticles are displayed
    # otherwise, when "Use server aim" is checked (and in some condition even with unchecked),
    # armor flashlight starts flickering
    #
    # reproducible scenarios, when hook is not present:
    # - "Use server aim" is checked and at most focused reticle is enabled -> armor flashlight starts flickering
    # - "Use server aim" is unchecked and at most focused reticle is enabled -> armor flashlight is normal
    # - "Use server aim" is unchecked and some server reticle is enabled -> armor flashlight starts flickering
    #    but only during aim focusing - after aim focused, it stops flickering

    @overrideIn(ArmorFlashlightBattleController)
    def _updateVisibilityState(func, self, markerType, gunMarkerState, *args, **kwargs):
        # revert gunAimingCircleSize to original form, before being altered in gun marker controllers
        # by reticleSizeMultiplier, so armor flashlight stays independent of it
        reticleSizeMultiplier = ReticleRegistry.getReticleSizeMultiplierFor(gunMarkerType=markerType)

        if reticleSizeMultiplier >= 0.001:
            gunMarkerState = gunMarkerState  # type: GunMarkerState

            initialSize = gunMarkerState.size / reticleSizeMultiplier
            gunMarkerState = gunMarkerState._replace(size=initialSize)

        if g_oneTickCache.areBothModesEnabled:
            if markerType == GUN_MARKER_TYPE.CLIENT:
                func(self, markerType, gunMarkerState, *args, **kwargs)
        else:
            func(self, markerType, gunMarkerState, *args, **kwargs)

    # dirty hack
    #
    # I don't know how much other mods overrides _setShootingParams method,
    # but I don't want to override it just to replace markerDataProvider
    #
    # so - we will sneakily replace serverMarkerDataProvider for clientMarkerDataProvider when
    # both modes are enabled, so armor flashlight will follow client reticle instead of server reticle
    def serverMarkerDataProvider_property(self):
        if _areBothModesEnabled():
            return _descriptors.clientMarkerDataProvider
        else:
            return _descriptors.serverMarkerDataProvider

    ArmorFlashlightBattleController.serverMarkerDataProvider = property(serverMarkerDataProvider_property)
