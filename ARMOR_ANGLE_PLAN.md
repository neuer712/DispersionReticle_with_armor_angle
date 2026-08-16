# Armor Angle HUD v2 — Normalization, Multi-Plate Geometry, More Vehicles, UI Repositioning

*(English plan followed by full Chinese plan — 英文计划后附完整中文计划)*

---

## STATUS AS OF 2026-08-17 — what's actually been done

**Track A (calc/data engine) — done, live-tested, working:**
- AP-only + flat 5deg normalization (ricochet check still uses the raw, un-normalized angle)
- Generalized `armor_math.plateIncidenceDeg(alpha, bearingDeg, slopeDeg, elevationSignedDeg)` to a
  true 3D dot product (`cos(incidence) = cos(slope)cos(elevation)cos(alpha-bearing) + sin(slope)sin(elevation)`),
  independently verified against a literal vector cross/dot-product implementation, not just re-derived math
- Shot **elevation** (vertical angle, from `gunRotator.gunPitch`) added on top of yaw - same exact
  vector-dot-product model, not an approximation bolted onto the flat case
- Verified the 5deg normalization rotates within the TRUE (shot, plate-normal) 3D plane, not a
  flattened horizontal/vertical shortcut (proved via Rodrigues' rotation, independent of the
  production code path)
- `armor_db.py` split into a lazily-loaded per-nation package (`armor_db/germany.py` etc.) - only
  the nation(s) of vehicles actually played this session get imported
- `mirroredPair()` helper: every non-axis-aligned plate (sides, future pike cheeks) is stored as an
  explicit left+right pair, fixing a real bug where turning the hull one way made the whole side
  section vanish (there was simply no data entry for that bearing, not a wrong value)
- Signed `slopeDeg` convention adopted: positive = top tucks into the hull / bottom sticks out
  (upper glacis, side upper, pike cheeks default); negative = the opposite lean (lower glacis, side
  lower). No `isWeakspot` flag anymore - just "upper part" / "lower part" per zone, some vehicles
  only have one part in a given zone
- `GUN_PITCH_ELEVATION_SIGN` flipped to `-1.0` after a live test showed it was backwards (confirmed:
  positive `gunRotator.gunPitch` = gun pointing DOWN, not up as originally guessed)
- Live-verified data: Tiger I (`germany:G04_PzVI_Tiger_I`) and Tiger II (`germany:G16_PzVIB_Tiger_II`)
  internal names confirmed via `python.log`; Tiger II mm/slope values hand-filled by the user
  directly (not a memory guess) and confirmed correct in-game after the sign fixes above.
  E-75's internal name is still an unverified guess.
- Real-machine benchmark (Python 2.7.18, worst-case 8-plate vehicle): ~9 microseconds per
  `assessVehicle()` call, i.e. a complete non-issue at the 10Hz HUD refresh rate this mod uses

**Track B (UI) — layout just implemented, NOT yet live-tested:**
- Moved from a single fixed-corner multiline text block to **8 independent `GUI.Text` components**,
  each at a fixed grid position anchored below the reticle (row 1: left side upper / left pike /
  front upper / right pike / right side upper; row 2, aligned under their row-1 counterparts: left
  side lower / front lower / right side lower)
- Slot assignment (`armor_math.classifyFrontPlate`/`classifySidePlate`/`UI_SLOTS`) is
  content-addressed (bearing sign + "upper"/"lower" in the label), not list-position-addressed, so
  a plate appearing/disappearing (facing away) never shifts any other slot's position - verified
  with a regression test that explicitly checks a surviving plate's slot is identical whether or
  not a sibling plate is currently shown
- Anchor point: gun aim point (`AimingSystems.getPlayerGunMat(...).translation`) projected via
  `AvatarInputHandler.cameras.projectPoint(...)`, the same technique `dispersion_reticle_flash.py`
  already uses for marker positioning - **unverified in a live client**, same risk category as the
  original `GUI.Text` API guess
- No font-size distinction and no color-coding yet (both deliberately deferred, per the user's
  request) - but each slot already being its own component means both are easy to add later without
  restructuring anything
- `armor-angle.position-x`/`position-y` config keys are repurposed from "absolute screen position"
  to "small offset from the reticle" - existing config.json files still have the OLD absolute-position
  values written to disk and need manual updating (new code defaults are 0.0 / -0.15, but defaults
  only apply when a key is absent, not when it's already present with an old value)

---

## PART 1 — ENGLISH PLAN

### Context

The MVP (single front/side-upper/side-lower plate, fixed-corner text, AP+HEAT both shown, no
normalization) is confirmed working end-to-end in a real training-room test today: `python.log`
showed the HUD computing and updating correctly for a Tiger I once the whitelist key was corrected
to `germany:G04_PzVI_Tiger_I`. Two screenshots at `reference_screenshots/1_demo.jpg` (current output)
and `reference_screenshots/2_hoped_positions.jpg` (hand-annotated target layout) confirm the pipeline
works but needs four follow-up improvements. The user asked to tackle them as two tracks:
- **Track A (this round): #1 normalization, #3 general plate geometry, #4 more vehicles + lazy loading**
- **Track B (next round): #2 UI repositioning/coloring** — sketched here, implemented separately

One real bug was also spotted by inspecting `1_demo.jpg`: the Chinese labels render as blank space
(`(  )`, `: 22 AP: HEAT: ~108mm` instead of `装甲提示: 正面: 22° AP:击穿 ...`). This EU client's
`default_small.font` has no CJK glyphs — `settings/translations.py` already has a comment about this
exact EU-client Chinese-glyph problem for AS3/Scaleform. Fix: switch the HUD's hardcoded text to
ASCII/English labels. Bundled into Track A since it touches the same formatting function anyway.

### Track A scope (implement this round)

#### A1. AP-only + 5° flat normalization (issue #1)

Drop HEAT entirely from the HUD (still keep it as a generic capability in `armor_math.py` if cheap,
but the HUD only computes/shows AP). Ricochet check keeps using the **raw** incidence angle (geometry
only, unaffected by normalization — this matches how WoT itself separates the ricochet check from
the penetration/normalization step). Normalization only applies when the shot does NOT ricochet:

```
rawIncidence = plateIncidenceDeg(...)             # unchanged, see A3
apRicochet   = rawIncidence > 70.0                  # unchanged threshold, raw angle

if apRicochet:
    effectiveMm = None                              # ricochet -> no penetration attempt, no mm to show
else:
    normalizedIncidence = max(0.0, rawIncidence - 5.0)   # flat 5 deg, caliber-agnostic (per user's simplification)
    effectiveMm = nominalMm / cos(radians(normalizedIncidence))
```

This replaces `approxEffectiveThicknessMm` with a version that takes the normalization branch into
account, and drops the `isHeat` parameter usage from the HUD call sites (function stays generic).

#### A3. General per-plate geometry via bearing + slope (issue #3)

**Answer to "vector or approximation?": neither is needed as a runtime 3D vector — a closed-form
formula is exact for this model.** Derivation (hull frame: x=forward, y=right, z=up; plate normal at
fixed bearing β from hull forward and slope φ from vertical; shot direction assumed horizontal, at
signed yaw angle α from hull forward — flat-trajectory assumption, unchanged from before):

```
N = (cos(β)cos(φ), sin(β)cos(φ), sin(φ))      # plate normal in hull frame
L = (cos(α), sin(α), 0)                        # assumed shot direction, horizontal only
cos(incidence) = N·L = cos(φ) * cos(α - β)     # exact, for ANY fixed bearing/slope pair
```

This is a strict generalization of the current `combineWithSlope` (which is the β=0/90° special case)
— same formula, same accuracy, now parameterized. This is what makes pike/cheek plates (bearing ≠
0/90°) work with the exact same function as flat front/side plates. Remaining known simplification
(unchanged from MVP, still worth 1 line in comments): shot direction is treated as horizontal, i.e.
gun pitch / terrain slope is still ignored — going further would require real 3D vectors and is out
of scope per the original HANDOFF.md simplification list.

Implementation: replace `frontYawIncidenceDeg`/`sideYawIncidenceDeg`/`combineWithSlope` with:
```python
def plateIncidenceDeg(alphaSignedDeg, bearingDeg, slopeDeg):
    yawDiff = normalizeAngleDeg(alphaSignedDeg - bearingDeg)  # wrap to [-180, 180]
    if abs(yawDiff) > 90.0:
        return None  # plate faces away entirely, not the one hit
    cosIncidence = cos(radians(yawDiff)) * cos(radians(slopeDeg))
    return degrees(acos(clamp(-1, cosIncidence, 1)))
```
Note this now needs **signed** alpha (not the old `abs()`-folded `normalizeYawToDeg`), because bearing
is signed too (left cheek = -25°, right cheek = +25°) and because Track B needs to know which side
is "facing the enemy". `normalizeYawToDeg` becomes `normalizeYawSignedDeg` (range (-180, 180]).

Data model change in `armor_db.py`:
```python
ArmorPlate = namedtuple("ArmorPlate", ["label", "bearingDeg", "slopeDeg", "nominalMm", "isWeakspot"])
VehicleArmor = namedtuple("VehicleArmor", ["frontPlates", "sidePlates"])
```
`frontPlates`/`sidePlates` are lists (1 entry for a simple flat tank like Tiger I; up to 2-4 for
pike-nose tanks later). `isWeakspot` marks the "thin/lower" side plate for Track B's smaller-font
treatment. Which plates are "active"/displayed for a given alpha is a Track B concern (rendering
picks among the assessed list); Track A's job is to make `assessPlate`-equivalent work correctly for
an arbitrary list of plates, e.g.:
```python
def assessVehicle(alphaSignedDeg, vehicleArmor):
    return {
        "front": [assessPlate(alphaSignedDeg, p) for p in vehicleArmor.frontPlates],
        "side":  [assessPlate(alphaSignedDeg, p) for p in vehicleArmor.sidePlates]
    }
```
where `assessPlate` returns `None`-incidence entries filtered out naturally (plate facing away).

For Tiger I specifically (uniform 100mm front, no distinct upper/lower difference) — matches user's
note that repeated identical front plates should collapse to one: `frontPlates=[ArmorPlate("front",
bearingDeg=0, slopeDeg=10, nominalMm=100, isWeakspot=False)]`, a single-entry list, nothing new to
collapse. The "collapse if near-identical" rule only matters once we add a tank with distinct
upper/lower glacis — no code needed now, just don't add a second entry when the vehicle doesn't have
a materially different plate. Sides get 2 entries (upper=not weakspot, lower=weakspot) for all three
current whitelist tanks, consistent with today's behavior.

#### A4. More vehicles + lazy per-nation loading (issue #4)

Split `armor_db.py` into a package:
```
armorangle/armor_db/__init__.py        # registry + lazy loader + getVehicleArmor()
armorangle/armor_db/germany.py         # ARMOR_DB dict for German vehicles only
armorangle/armor_db/ussr.py            # (add as vehicles are filled in)
...
```
`__init__.py`:
```python
_NATION_MODULES = {"germany": "dispersionreticle.armorangle.armor_db.germany", ...}
_loadedNationDbs = {}   # nation -> dict, populated lazily

def getVehicleArmor(vehicleInternalName):
    nation, _, tag = vehicleInternalName.partition(":")
    if nation not in _loadedNationDbs:
        if nation not in _NATION_MODULES:
            return None
        module = importlib.import_module(_NATION_MODULES[nation])
        _loadedNationDbs[nation] = module.ARMOR_DB
    return _loadedNationDbs[nation].get(vehicleInternalName)
```
This means only the nation(s) of vehicles actually played in a session get imported/parsed — for a
dict-of-namedtuples this is a micro-optimization (each nation module is a few KB), but it's the
right shape for scaling to "every tank" without a startup cost spike, and it directly matches what
the user asked for ("每一局只加载当前需要的"). `getVehicleArmor()`'s call site in
`armor_angle_hud.py` is unchanged (same function signature).

Vehicle data to add this round: keep the 3 already-listed (fix nothing further needed for Tiger I,
already confirmed correct name; Tiger II / E-75 names still marked UNVERIFIED, ask user to test-drive
them and report the `[ArmorAngle] vehicle not in whitelist: ...` log line same as last time). Adding
a broader vehicle set (e.g. all German/Soviet heavies) is straightforward repetition of the same
per-plate data shape once the model lands — can grow the list incrementally over time, doesn't block
this round's code changes.

### Track B sketch (next round, NOT implemented this pass)

- Anchor the HUD below the reticle instead of a fixed screen corner, by reusing the exact technique
  `dispersion_reticle_flash.py` already uses for marker positioning: `aih_hooks.getSniperViewportPosition()`
  (gun/reticle 3D point) → `cameras.projectPoint(...)` (from `AvatarInputHandler.cameras`) → clip-space
  x/y, then offset downward by a configurable margin.
- Layout: one centered slot for "front" (1 or 2 numbers side by side if a future tank has distinct
  cheek + glacis both active), same font size as today; on the side actually facing the aim direction
  (sign of `alphaSignedDeg` relative to each side plate's bearing) show that side's plates stacked:
  main plate at the same font size as front, weakspot plate smaller, directly below.
  Which side (left/right of the front slot) mirrors which side of the hull is facing the aim line.
- Color: pink = ricochet/safe, yellow = penetrates/dangerous — deliberately different from the
  native armor-flashlight red/green convention to avoid subconscious mix-ups. Exact rule to confirm
  with user before implementing: is it a strict 1:1 mapping to `apRicochet` boolean, or does "safe"
  also cover comfortably-thick non-ricochet values? Defaulting to strict `apRicochet` boolean mapping
  unless told otherwise, since anything fancier needs an assumed enemy caliber (explicitly out of
  scope per the original design decision).
- `GUI.Text` likely needs per-plate-group coloring, which may mean 2-3 separate `GUI.Text` components
  (front / side-main / side-weak) instead of one multiline block, since a single component only has
  one `.colour`. To be confirmed once building this track.

### Files touched this round (Track A)

New:
- `src/dispersionreticle/armorangle/armor_db/__init__.py` (replaces current `armor_db.py`)
- `src/dispersionreticle/armorangle/armor_db/germany.py`

Modified:
- `src/dispersionreticle/armorangle/armor_math.py` — signed yaw normalization, `plateIncidenceDeg`,
  drop `frontYawIncidenceDeg`/`sideYawIncidenceDeg`/old `combineWithSlope`, AP-only effective-mm with
  5° normalization, `assessPlate`/`assessVehicle` reshaped for plate lists
- `src/dispersionreticle/armorangle/armor_angle_hud.py` — consume the new list-shaped assessment,
  drop HEAT from formatted text, switch labels to ASCII/English (glyph-rendering fix)
- Delete old `src/dispersionreticle/armorangle/armor_db.py` (superseded by the package)

### Verification

- Re-run the same kind of standalone regression script used for the MVP (`armor_math.py` has zero
  BigWorld deps), extended to cover: signed-yaw wraparound, `plateIncidenceDeg` at non-0/90 bearings
  against hand-computed values, the 5°-normalization branch, and the "ricochet -> no mm" branch.
  Run under the already-installed Python 2.7.18 (confirmed byte-identical `.pyc` magic number to the
  shipped mod).
- `build_wotmod.py` (already in repo root, gitignored) rebuilds the `.wotmod`; reinstall into
  `mods/2.3.1.2/` (game must be fully closed first — the file gets locked while running, as seen
  last time) and re-test Tiger I in a training room, checking `python.log` for `[ArmorAngle]` lines
  and eyeballing the on-screen numbers against hand-computed expected values for a couple of known
  turret angles.

---

## 截至 2026-08-17 的进度状态——实际做了什么

**A 组（计算/数据引擎）——已完成，训练房实测通过：**
- 只算 AP + 固定 5° 转正（跳弹判定仍然用原始、未转正的入射角）
- 把 `armor_math.plateIncidenceDeg(alpha, bearingDeg, slopeDeg, elevationSignedDeg)` 推广成了真正的
  三维点积（`cos(入射角) = cos(倾角)cos(俯仰角)cos(偏航角-方位角) + sin(倾角)sin(俯仰角)`），并且用
  一套完全独立的"字面三维向量叉乘/点积"实现做了交叉验证，不只是重新推了一遍同一套数学
- 加入了弹道**俯仰角**（垂直方向角度，来自 `gunRotator.gunPitch`）——用的是跟偏航角完全同一套向量
  点积模型，不是在平面情形上打补丁的近似
- 验证过 5° 转正确实是在真实的（弹道方向, 装甲板法线）三维平面内转的，不是压平到水平/竖直方向的
  捷径（用罗德里格旋转公式独立证明过，跟正式代码路径无关）
- `armor_db.py` 拆成了按国家惰性加载的包（`armor_db/germany.py` 等）——只有这局真正开过的国家才会
  被 import
- 加了 `mirroredPair()` 工具函数：所有不在正前/正后方位角上的装甲板（侧面、以后的箭簇装甲）现在都
  显式存成左右两条——修复了一个真 bug：车体往一个方向转的时候整个侧面装甲区域会消失（不是数值算
  错，是压根没有对应方位角的数据条目）
- 采用了带符号的 `slopeDeg` 约定：正数=上收下伸（首上、侧上、箭簇装甲默认都是这个方向）；负数=
  反过来（首下、侧下）。不再有 `isWeakspot` 字段——只按"上部/下部"分区，有的车某个区只有一部分
- `GUN_PITCH_ELEVATION_SIGN` 训练房实测发现猜反了，已改成 `-1.0`（确认：`gunRotator.gunPitch`
  正值实际上是向下压炮，不是最初猜的向上抬）
- 实测确认的数据：虎式（`germany:G04_PzVI_Tiger_I`）和虎王（`germany:G16_PzVIB_Tiger_II`）的内部
  车名都通过 `python.log` 核实过；虎王的装甲厚度/倾角是用户直接手填的真实数据（不是我凭记忆猜的），
  上面这些符号修复完之后也在游戏里确认对了。E75 的内部车名还是没验证过的猜测
- 真机跑分（Python 2.7.18，最坏情况8面装甲车）：`assessVehicle()` 每次调用约9微秒，在本 mod
  10Hz 的 HUD 刷新频率下完全不是问题

**B 组（UI）——布局刚实现，还没有实测：**
- 从"固定角落的单块多行文字"改成了 **8 个独立的 `GUI.Text` 组件**，每个都在准心下方的固定网格
  位置上（第一排：左侧上装甲/左箭簇装甲/首上装甲/右箭簇装甲/右侧上装甲；第二排，跟第一排对应列
  对齐：左侧下装甲/首下装甲/右侧下装甲）
- 槽位归属（`armor_math.classifyFrontPlate`/`classifySidePlate`/`UI_SLOTS`）是按内容找槽位（方位角
  正负号 + label 里有没有"upper"/"lower"），不是按列表顺序找槽位——所以某块装甲板出现/消失（背对）
  永远不会挤动别的槽位。写了回归测试专门验证：某块装甲板不管旁边那块装甲板显示不显示，自己的槽位
  都是同一个
- 锚点：炮口瞄准点（`AimingSystems.getPlayerGunMat(...).translation`）经
  `AvatarInputHandler.cameras.projectPoint(...)` 投影得到——这跟 `dispersion_reticle_flash.py` 定位
  标记点用的是同一套技术——**还没在真实客户端验证过**，风险等级跟当初的 `GUI.Text` API 猜测一样
- 暂时没做字体大小区分也没做变色（按你的要求先不做），但每个槽位已经是独立组件了，以后要加这两个
  都不需要重新搭架子
- `armor-angle.position-x`/`position-y` 这两个配置项的含义从"绝对屏幕位置"改成了"相对准心的小幅
  偏移"——已经存在的 config.json 文件里还是旧的绝对位置数值，需要手动改一下（新的代码默认值是
  0.0 / -0.15，但默认值只在配置文件里没有这个 key 的时候才生效，已经写过的值不会自动被新默认值
  覆盖）

---

## PART 2 — 中文计划

### 背景

MVP 版本(单一正面板+侧上+侧下，固定角落文字，AP/HEAT 都显示，不含转正)今天已经在真实训练房里
跑通并核实过:把白名单车名改成 `germany:G04_PzVI_Tiger_I` 后，`python.log` 显示虎式的数值正确计算
并刷新。`reference_screenshots/1_demo.jpg`(当前实际效果)和 `reference_screenshots/2_hoped_positions.jpg`
(手工标注的目标布局)两张截图确认了整条链路是通的，但需要四项后续改进。你要求分两组攻克:
- **A 组(这一轮做)**:1 转正、3 通用装甲板几何、4 更多车辆数据+按需加载
- **B 组(下一轮做)**:2 UI 位置/配色重排 — 本计划先画草图，具体实现放到下一轮单独做

顺带在 `1_demo.jpg` 里发现一个真 bug:中文标签渲染成了空白(`(  )`、`: 22 AP: HEAT: ~108mm`，本该是
`装甲提示: 正面: 22° AP:击穿 ...`)。这台 EU 客户端的 `default_small.font` 没有中文字形——
`settings/translations.py` 里本来就有一条注释专门提到 EU 客户端中文字形这个坑。修复方式:把 HUD 里
硬编码的文字换成 ASCII/英文标签。这个修复顺手并入 A 组，因为改的是同一处拼字符串的函数。

### A 组范围(这一轮实现)

#### A1. 只算 AP + 固定 5° 转正(问题1)

HUD 完全不再显示 HEAT(`armor_math.py` 里可以继续保留通用的 HEAT 支持，不浪费之前写的代码，但 HUD
只算/只显示 AP)。跳弹判定继续用**原始**入射角(纯几何判断，不受转正影响——这跟 WoT 本身"跳弹判定"
和"穿深/转正计算"是两个独立步骤的设计一致)。转正只在**不跳弹**的情况下才生效:

```
原始入射角 = plateIncidenceDeg(...)                # 见 A3，不变
AP是否跳弹  = 原始入射角 > 70.0                       # 阈值不变，用原始角度判断

如果跳弹:
    等效厚度 = None                                  # 跳弹=不会真正穿深判定，没有等效厚度可显示
否则:
    转正后入射角 = max(0.0, 原始入射角 - 5.0)          # 固定5度，不看口径(按你说的简化方案)
    等效厚度 = 标称厚度 / cos(radians(转正后入射角))
```

这会替换掉现在的 `approxEffectiveThicknessMm`，改成带转正分支的版本；HUD 调用处不再传 `isHeat`
参数(函数本身仍保留通用性)。

#### A3. 用"方位角+倾角"做通用装甲板几何(问题3)

**关于"向量还是近似"的答案:两个都不用在运行时算真·三维向量——这个模型下有一个精确的闭式公式，
不是近似。** 推导(车体坐标系:x=车头方向，y=车右方向，z=车顶方向；装甲板法线由固定的方位角 β
[相对车头方向的水平偏转] 和倾角 φ [相对垂直方向的后倾角] 决定；假设来袭弹道是水平的，来袭方向相对
车头的有符号偏航角是 α——这个"水平弹道"假设跟之前一样，没有变):

```
N = (cos(β)cos(φ), sin(β)cos(φ), sin(φ))      # 装甲板法线(车体坐标系)
L = (cos(α), sin(α), 0)                        # 假想来袭方向，仅水平分量
cos(入射角) = N·L = cos(φ) * cos(α - β)         # 对任意固定的(方位角,倾角)组合都精确成立
```

这其实是现在 `combineWithSlope`(β 固定为 0°/90° 的特例)的严格推广——公式、精度完全一样，只是把
方位角参数化了。这就是为什么箭簇/侧斜装甲板(方位角不是 0°/90°)能用跟正面/侧面完全同一套函数处理。
唯一保留的已知简化(跟 MVP 一样，值得留一行注释):来袭方向按水平处理，也就是还是不管炮的俯仰角/
地形坡度——再往下做就要上真三维向量了，超出了 HANDOFF.md 原本列的简化范围。

实现:把 `frontYawIncidenceDeg`/`sideYawIncidenceDeg`/旧版 `combineWithSlope` 替换成:
```python
def plateIncidenceDeg(alphaSignedDeg, bearingDeg, slopeDeg):
    yawDiff = normalizeAngleDeg(alphaSignedDeg - bearingDeg)  # 折算到 [-180, 180]
    if abs(yawDiff) > 90.0:
        return None  # 装甲板完全背对，不是被打中的那块
    cosIncidence = cos(radians(yawDiff)) * cos(radians(slopeDeg))
    return degrees(acos(clamp(-1, cosIncidence, 1)))
```
注意这里需要**带符号**的 alpha(不能再用旧的 `abs()` 折叠版 `normalizeYawToDeg`)，因为方位角本身
也是带符号的(左斜面=-25°，右斜面=+25°)，而且 B 组需要知道"到底哪一侧朝着假想敌人"。
`normalizeYawToDeg` 改名/改造成 `normalizeYawSignedDeg`(值域 (-180, 180])。

`armor_db.py` 数据结构改动:
```python
ArmorPlate = namedtuple("ArmorPlate", ["label", "bearingDeg", "slopeDeg", "nominalMm", "isWeakspot"])
VehicleArmor = namedtuple("VehicleArmor", ["frontPlates", "sidePlates"])
```
`frontPlates`/`sidePlates` 都是列表(虎式这种平板车只有1项；未来箭簇装甲车最多2-4项)。`isWeakspot`
标记"薄/下方"的侧面板，给 B 组做小字号用。给定某个 alpha 时到底显示列表里哪几块，是 B 组(渲染层)
的事——A 组要做的是让"assessPlate"式的计算对任意长度的装甲板列表都能正确工作，比如:
```python
def assessVehicle(alphaSignedDeg, vehicleArmor):
    return {
        "front": [assessPlate(alphaSignedDeg, p) for p in vehicleArmor.frontPlates],
        "side":  [assessPlate(alphaSignedDeg, p) for p in vehicleArmor.sidePlates]
    }
```
入射角算出 `None` 的条目(装甲板完全背对)自然会被过滤掉。

虎式这种正面处处 100mm、没有首上首下区别的车:按你说的"重复数值不用重复显示"，`frontPlates=[
ArmorPlate("front", bearingDeg=0, slopeDeg=10, nominalMm=100, isWeakspot=False)]`，单条目列表，
没什么可折叠的。"数值接近就合并显示"这条规则只有加入首上/首下明显不同的车时才用得上——现在不用
写任何折叠逻辑，只是"没有明显差异的车就不要多填一条"。侧面目前三台白名单车都是2条(侧上=主装甲，
侧下=弱点)，跟现在的行为一致。

#### A4. 更多车辆数据 + 按国家按需加载(问题4)

把 `armor_db.py` 拆成一个包:
```
armorangle/armor_db/__init__.py        # 注册表 + 按需加载器 + getVehicleArmor()
armorangle/armor_db/germany.py         # 只放德系车的 ARMOR_DB 字典
armorangle/armor_db/ussr.py            # (以后按需添加)
...
```
`__init__.py`:
```python
_NATION_MODULES = {"germany": "dispersionreticle.armorangle.armor_db.germany", ...}
_loadedNationDbs = {}   # nation -> dict，惰性填充

def getVehicleArmor(vehicleInternalName):
    nation, _, tag = vehicleInternalName.partition(":")
    if nation not in _loadedNationDbs:
        if nation not in _NATION_MODULES:
            return None
        module = importlib.import_module(_NATION_MODULES[nation])
        _loadedNationDbs[nation] = module.ARMOR_DB
    return _loadedNationDbs[nation].get(vehicleInternalName)
```
效果是:一局里只会真正 import/解析你这局开的车所在的那个国家模块——对于"字典套 namedtuple"这种
数据量级，省下来的内存/解析时间其实是很小的优化(每个国家模块也就几 KB)，但这是"以后扩展到全部
坦克"该有的正确形状，避免启动时一次性加载所有国家造成成本尖峰，也直接对应你说的"每一局只加载当前
需要的"。`armor_angle_hud.py` 里调用 `getVehicleArmor()` 的地方不用改(函数签名不变)。

这一轮要补的车辆数据:先保留现有 3 台(虎式的名字已经训练房实测确认对了，不用再改；虎王/E75 的名字
仍然标记"未验证"，等你哪天顺手开这两台车进训练房，把 `[ArmorAngle] vehicle not in whitelist: ...`
那行日志发我，跟上次一样)。加更大范围的车辆(比如德系/苏系所有重坦)是模型定下来之后照着同样的
"装甲板列表"格式重复填数据的体力活——可以之后慢慢滚动补充，不卡这一轮的代码改动。

### B 组草图(下一轮做，这一轮不实现)

- 让 HUD 锚定在准心下方，而不是固定屏幕角落，具体复用 `dispersion_reticle_flash.py` 里已经在用
  的那套标记定位技术:`aih_hooks.getSniperViewportPosition()`(炮口/准心的3D点)→
  `cameras.projectPoint(...)`(来自 `AvatarInputHandler.cameras`)→ clip 空间 x/y，再往下偏移一个
  可配置的边距。
- 布局:正中一个"正面"槽位(平时1个数字，未来箭簇装甲车如果斜面+首上同时"朝向"敌人可以并排显示2
  个)，字号跟现在一样；在真正朝向假想敌人的那一侧(由 `alphaSignedDeg` 相对每块侧装甲板方位角的
  符号决定)显示该侧的装甲板，堆叠显示:主装甲板字号跟正面一样，弱点装甲板字号更小，紧贴在下面。
  显示在正面槽位左边还是右边，跟车体实际哪一侧朝向瞄准线保持镜像一致。
- 配色:粉色=跳弹/安全，黄色=击穿/危险——特意跟游戏原生装甲探照灯的红/绿配色区分开，避免下意识
  看混。具体规则需要实现前跟你确认一下:是严格 1:1 绑定 `apRicochet` 布尔值，还是"够厚的非跳弹值"
  也算安全？在你没有进一步说明之前，我会先按严格绑定 `apRicochet` 布尔值来做，因为更精细的判断
  需要假设敌方口径，这跟最初"不假设来袭口径"的设计决定是冲突的，超出范围。
- `GUI.Text` 大概率需要按"装甲板分组"分别上色，这可能意味着要建 2-3 个独立的 `GUI.Text` 组件
  (正面/侧面主装甲/侧面弱点)而不是一整块多行文字，因为一个组件只有一个 `.colour`。具体做法等
  真正动手做 B 组的时候再定。

### 这一轮(A组)改动的文件

新增:
- `src/dispersionreticle/armorangle/armor_db/__init__.py`(取代现在的 `armor_db.py`)
- `src/dispersionreticle/armorangle/armor_db/germany.py`

修改:
- `src/dispersionreticle/armorangle/armor_math.py`——带符号偏航角归一化、新增 `plateIncidenceDeg`、
  删掉 `frontYawIncidenceDeg`/`sideYawIncidenceDeg`/旧版 `combineWithSlope`、AP-only 等效厚度(含5°
  转正)、`assessPlate`/新增 `assessVehicle` 改造成支持装甲板列表
- `src/dispersionreticle/armorangle/armor_angle_hud.py`——消费新的列表型评估结果、HUD 文字去掉
  HEAT、标签换成 ASCII/英文(修字形不显示的 bug)
- 删除旧的 `src/dispersionreticle/armorangle/armor_db.py`(被新的包取代)

### 验证方式

- 沿用 MVP 时那套独立回归测试脚本的思路(`armor_math.py` 零 BigWorld 依赖)，扩展覆盖:带符号偏航角
  的环绕处理、`plateIncidenceDeg` 在非 0°/90° 方位角下跟手工算的值对比、5° 转正分支、"跳弹→无等效
  厚度"分支。用已经装好的 Python 2.7.18 跑(之前已确认编译出的 `.pyc` magic number 跟正式发布版
  逐字节一致)。
- `build_wotmod.py`(仓库根目录，已 gitignore)重新打包 `.wotmod`；重新装进 `mods/2.3.1.2/`(游戏
  必须先完全关闭——上次验证过运行中文件会被锁住)，进训练房用虎式重新测一遍，核对 `python.log` 里
  的 `[ArmorAngle]` 行，并挑几个已知炮塔角度手工核算一遍屏幕上显示的数字对不对。
