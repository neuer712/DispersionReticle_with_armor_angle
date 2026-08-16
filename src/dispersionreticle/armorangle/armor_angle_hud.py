import logging

import BigWorld

from dispersionreticle.armorangle import armor_math
from dispersionreticle.armorangle.armor_db import getVehicleArmor
from dispersionreticle.armorangle.armor_db.tier_thresholds import TIER_SAFETY_THRESHOLDS
from dispersionreticle.settings.config_param import g_configParams

logger = logging.getLogger(__name__)

_TICK_INTERVAL_SECONDS = 0.1

_NEUTRAL_COLOUR = (220, 220, 220, 255)

# maps armor_math color categories to actual GUI.Text colours - kept here
# since armor_math.py stays GUI/BigWorld-free
_COLOUR_SAFE = (70, 120, 230, 255)

_COLOURS_BY_CATEGORY = {
    armor_math.COLOR_DANGER: (230, 60, 60, 255),
    armor_math.COLOR_WARNING: (230, 210, 60, 255),
    armor_math.COLOR_SAFE: _COLOUR_SAFE,
    # same blue as COLOR_SAFE, not purple - in practice purple and red were
    # too easy to mix up in peripheral vision while actually playing
    armor_math.COLOR_RICOCHET: _COLOUR_SAFE,
}

# each slot in armor_math.UI_SLOTS is its OWN GUI.Text component at a FIXED
# screen position - a slot with nothing to show is just hidden
# (.visible = False), it never reflows or shifts other slots around.
#
# position is a plain FIXED screen location (armor-angle.position-x/-y in
# config, clip-space [-1,1]), NOT dynamically anchored to the reticle -
# an earlier attempt projected the gun's 3D world position onto screen
# every tick to track the reticle, but that's a different point than the
# reticle (which stays at a fixed screen spot in both sniper and arcade
# view - the CAMERA moves/rotates to keep it there, the reticle itself
# doesn't get computed via world-space projection) and in sniper mode the
# camera IS approximately at the gun's position, making that projection
# degenerate - text flew around wildly, confirmed in a live test. Fixed
# screen position side-steps this entirely.

# unverified/needs live tuning - clip-space units (same [-1,1] space as
# GUI.Text.position), not pixels
_COLUMN_SPACING = 0.10
_ROW_SPACING = 0.05


class _ArmorAngleHud(object):
    """
    Plain-text HUD (GUI.Text, not Flash) showing armor incidence angle for
    a whitelisted vehicle in a fixed grid at a fixed screen position,
    assuming the current aim direction as the hypothetical incoming shot
    direction. Slot position alone identifies which plate a number belongs
    to, so no plate label is shown - just the numbers.

    NOTE: GUI.Text property names used here (.font, .colour, .position,
    .visible, .text) and GUI.addRoot() are BigWorld's native GUI binding.
    This codebase never used them before this feature, so they are
    unverified against a live client. Any mismatch will surface as a
    single logged error rather than a silent no-op or a spam of errors.
    """

    def __init__(self):
        self._textComponents = None  # dict: slotKey -> GUI.Text, or None until created
        self._callbackId = None
        self._loggedMissingVehicleNames = set()
        self._loggedApiIssue = False
        self._loggedTierValue = False

    def start(self):
        if not g_configParams.armorAngleEnabled():
            return

        if self._callbackId is not None:
            return

        self._ensureTextComponents()
        if self._textComponents is not None:
            self._scheduleNextTick()

    def stop(self):
        if self._callbackId is not None:
            BigWorld.cancelCallback(self._callbackId)
            self._callbackId = None

        self._hideAll()

    def refreshFromConfigReload(self):
        if not g_configParams.armorAngleEnabled():
            self.stop()
            return

        player = BigWorld.player()
        if player is not None and hasattr(player, "gunRotator"):
            self.start()
        else:
            self.stop()

    def _hideAll(self):
        if self._textComponents is None:
            return
        for text in self._textComponents.values():
            text.visible = False

    def _ensureTextComponents(self):
        if self._textComponents is not None:
            return

        try:
            import GUI

            baseX = g_configParams.armorAnglePositionX()
            baseY = g_configParams.armorAnglePositionY()

            components = {}
            for slotKey, col, row in armor_math.UI_SLOTS:
                text = GUI.Text("")
                text.font = "default_small.font"
                text.colour = _NEUTRAL_COLOUR
                text.multiline = True
                text.visible = False
                text.position = (baseX + col * _COLUMN_SPACING, baseY + row * _ROW_SPACING, 0)

                GUI.addRoot(text)

                components[slotKey] = text

            self._textComponents = components
        except Exception:
            logger.error("[ArmorAngle] Failed to create GUI.Text HUD components. "
                        "This client's GUI.Text API likely differs from what this feature expects.",
                        exc_info=True)

    def _scheduleNextTick(self):
        self._callbackId = BigWorld.callback(_TICK_INTERVAL_SECONDS, self._tick)

    def _tick(self):
        self._callbackId = None

        try:
            self._updateOnce()
        except Exception:
            if not self._loggedApiIssue:
                self._loggedApiIssue = True
                logger.error("[ArmorAngle] Failed to update armor angle HUD, disabling further updates this battle. "
                            "This likely means one of the game APIs this feature depends on "
                            "(gunRotator.turretYaw/gunPitch, vehicleTypeDescriptor, GUI.Text) "
                            "doesn't match what was expected for this client version.",
                            exc_info=True)
            self._hideAll()
            return

        self._scheduleNextTick()

    def _updateOnce(self):
        if self._textComponents is None or not g_configParams.armorAngleEnabled():
            self._hideAll()
            return

        player = BigWorld.player()
        if player is None or not hasattr(player, "gunRotator"):
            self._hideAll()
            return

        vehicleTypeDescriptor = getattr(player, "vehicleTypeDescriptor", None)
        if vehicleTypeDescriptor is None:
            self._hideAll()
            return

        if getattr(vehicleTypeDescriptor.type, "classTag", None) == "SPG":
            self._hideAll()
            return

        vehicleName = vehicleTypeDescriptor.type.name
        armor = getVehicleArmor(vehicleName)
        if armor is None:
            if vehicleName not in self._loggedMissingVehicleNames:
                self._loggedMissingVehicleNames.add(vehicleName)
                logger.info("[ArmorAngle] vehicle not in whitelist: %s", vehicleName)
            self._hideAll()
            return

        tier = getattr(vehicleTypeDescriptor.type, "level", None)
        if not self._loggedTierValue:
            self._loggedTierValue = True
            logger.info("[ArmorAngle] vehicleTypeDescriptor.type.level = %r (verify this is the tier 1-10)", tier)

        alphaSignedDeg = armor_math.normalizeYawSignedDeg(player.gunRotator.turretYaw)
        elevationSignedDeg = armor_math.normalizeElevationSignedDeg(player.gunRotator.gunPitch)
        vehicleAssessment = armor_math.assessVehicle(alphaSignedDeg, elevationSignedDeg, armor)

        bySlot = {}
        for assessment in vehicleAssessment["front"]:
            bySlot[armor_math.classifyFrontPlate(assessment.plate)] = assessment
        for assessment in vehicleAssessment["side"]:
            bySlot[armor_math.classifySidePlate(assessment.plate)] = assessment

        debugMode = g_configParams.armorAngleDebugMode()
        threshold1, threshold2 = armor_math.resolveSafetyThresholds(armor, tier, TIER_SAFETY_THRESHOLDS)

        for slotKey, _col, _row in armor_math.UI_SLOTS:
            text = self._textComponents[slotKey]
            assessment = bySlot.get(slotKey)

            if assessment is None:
                text.visible = False
                continue

            category = armor_math.colorCategoryForAssessment(assessment, threshold1, threshold2)

            text.colour = _COLOURS_BY_CATEGORY.get(category, _NEUTRAL_COLOUR)
            text.text = _formatPlateText(assessment, debugMode)
            text.visible = True


def _formatPlateText(assessment, debugMode):
    if not debugMode:
        if assessment.apRicochet:
            return "RICOCHET"
        if assessment.approxEffectiveMm is not None:
            return "%d" % int(round(assessment.approxEffectiveMm))
        return "-"

    status = "RICOCHET" if assessment.apRicochet else "PEN"

    if assessment.approxEffectiveMm is not None:
        effText = "~%dmm" % int(round(assessment.approxEffectiveMm))
    else:
        effText = "-"

    return "%d\n%s %s" % (int(round(assessment.incidenceDeg)), status, effText)


g_armorAngleHud = _ArmorAngleHud()
