import logging

from VehicleGunRotator import VehicleGunRotator

from dispersionreticle.armorangle.armor_angle_hud import g_armorAngleHud
from dispersionreticle.settings.config import g_config
from dispersionreticle.utils import overrideIn

logger = logging.getLogger(__name__)


###########################################################
# Ties the armor angle HUD lifecycle to the same
# VehicleGunRotator start/stop hooks that the rest of this
# mod already uses to detect "player currently controls a
# vehicle's gun" (see vehicle_gun_rotator_hooks.py).
###########################################################

@overrideIn(VehicleGunRotator)
def start(func, self):
    func(self)

    g_armorAngleHud.start()
    g_config.onConfigReload += g_armorAngleHud.refreshFromConfigReload


@overrideIn(VehicleGunRotator)
def stop(func, self):
    g_config.onConfigReload -= g_armorAngleHud.refreshFromConfigReload
    g_armorAngleHud.stop()

    func(self)
