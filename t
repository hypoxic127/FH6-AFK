[33mcommit eff30f8fde14f8f30644d6ce4205a32bfab2075d[m
Author: hypoxic127 <aw1244936857@gmail.com>
Date:   Mon Jun 22 03:11:50 2026 +0800

    fix(upgrade): robust Available Points OCR (multi-frame consensus + confidence vote)
    
    The Available Points reader misread intermittently at low resolution (1600x900
    makes the ROI only ~56x27 px). Replace the "tie -> max" Counter vote with the
    hardened skill-points path:
    - Pool candidates across 3 frames x 4 binarization pipelines, read via
      image_to_data, and vote with engine.ocr._vote_skill_points (0..999 range
      clamp + confidence-weighted) instead of taking the max on ties.
    - Keep 3x CUBIC upscale (measured better than 4x LINEAR on the tiny ROI, which
      pushed the gray pipelines to misread, e.g. 549 -> 349/949).
    - Also switch this module to a live module_ocr.DEBUG_WRITE_FILES lookup so the
      --debug AP dumps actually write; drop the now-unused `import re`.
    
    Verified on a real captured ROI (truth 549): 3/4 pipelines read 549 -> voted 549.
    
    Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>

[1mdiff --git a/macro/upgrade.py b/macro/upgrade.py[m
[1mindex a2f71d6..668fecd 100644[m
[1m--- a/macro/upgrade.py[m
[1m+++ b/macro/upgrade.py[m
[36m@@ -3,7 +3,6 @@[m
 macro/upgrade.py — 车辆加点宏[m
 """[m
 [m
[31m-import re[m
 import time[m
 [m
 import cv2[m
[36m@@ -11,11 +10,14 @@[m [mimport numpy as np[m
 import pytesseract[m
 import vgamepad as vg[m
 [m
[32m+[m[32mimport engine.ocr as module_ocr[m
 from engine.i18n import t[m
[31m-from engine.ocr import DEBUG_WRITE_FILES[m
 from engine.utils import log_info, log_success, log_warning[m
 from macro.core import capture_raw_screenshot, capture_screenshot[m
 [m
[32m+[m[32m# Available Points 多帧共识帧数：低分辨率（如 1600×900，ROI 仅 ~56×27）下抗间歇性单帧误读[m
[32m+[m[32m_AP_CONSENSUS_FRAMES = 3[m
[32m+[m
 [m
 def action_upgrade_car_skills(hwnd, gamepad, min_points=30):[m
     """[m
[36m@@ -69,74 +71,61 @@[m [mdef action_upgrade_car_skills(hwnd, gamepad, min_points=30):[m
     log_info("  -> [5]  A ...")[m
     press(vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=1.2)[m
 [m
[31m-    # === 触发条件 2: 扫描 Available Points ===[m
[31m-    time.sleep(1.0)  # 等待 UI 刷新[m
[32m+[m[32m    # === 触发条件 2: 扫描 Available Points（多帧共识，低分辨率下抗间歇误读）===[m
     available_points = -1[m
     try:[m
[31m-        from collections import Counter[m
[31m-[m
[31m-        raw_img = capture_raw_screenshot(hwnd)[m
[31m-        if raw_img is not None:[m
[32m+[m[32m        candidates: list[tuple[int, float]] = []  # 跨帧累积的 (值, 置信度)[m
[32m+[m[32m        last_w = last_h = 0[m
[32m+[m[32m        for frame_idx in range(_AP_CONSENSUS_FRAMES):[m
[32m+[m[32m            time.sleep(1.0 if frame_idx == 0 else 0.2)  # 首帧等 UI 刷新，后续帧短间隔取多样性[m
[32m+[m[32m            raw_img = capture_raw_screenshot(hwnd)[m
[32m+[m[32m            if raw_img is None:[m
[32m+[m[32m                continue[m
             h, w = raw_img.shape[:2][m
[31m-            ocr_results = [][m
[32m+[m[32m            last_w, last_h = w, h[m
 [m
             # ROI: 数字区域 (h85-88%, w35-38.5%)[m
             roi = raw_img[int(h * 0.85) : int(h * 0.88), int(w * 0.35) : int(w * 0.385)][m
[31m-[m
[31m-            if roi.size > 0:[m
[31m-                gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)[m
[31m-[m
[31m-                # === 主力管线: 灰度阈值（实测最稳定） ===[m
[31m-                pipelines = [][m
[31m-[m
[31m-                # 1. 灰度 threshold 150（test_from_state 测试14验证通过）[m
[31m-                _, t150 = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)[m
[31m-                pipelines.append(("gray_t150", t150))[m
[31m-[m
[31m-                # 2. 灰度 threshold 160[m
[31m-                _, t160 = cv2.threshold(gray, 160, 255, cv2.THRESH_BINARY)[m
[31m-                pipelines.append(("gray_t160", t160))[m
[31m-[m
[31m-                # 3. Otsu 自适应阈值[m
[31m-                _, t_otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[m
[31m-                pipelines.append(("gray_otsu", t_otsu))[m
[31m-[m
[31m-                # 4. HSV 黄色通道（放宽阈值 + 膨胀增粗笔画）[m
[31m-                hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)[m
[31m-                yellow_mask = cv2.inRange(hsv, np.array([15, 40, 100]), np.array([45, 255, 255]))[m
[31m-                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))[m
[31m-                yellow_mask = cv2.morphologyEx(yellow_mask, cv2.MORPH_CLOSE, kernel)[m
[31m-                # 膨胀 1 次增粗抗锯齿导致的细笔画[m
[31m-                yellow_mask = cv2.dilate(yellow_mask, kernel, iterations=1)[m
[31m-                pipelines.append(("hsv_yellow", yellow_mask))[m
[31m-[m
[31m-                # 调试输出[m
[31m-                if DEBUG_WRITE_FILES:[m
[31m-                    cv2.imwrite("debug_ap_roi_raw.png", roi)[m
[31m-                    cv2.imwrite("debug_ap_roi_gray_t150.png", t150)[m
[31m-                    cv2.imwrite("debug_ap_roi_yellow_mask.png", yellow_mask)[m
[31m-[m
[31m-                # 对每个管线执行 OCR（PSM 7 单行模式）[m
[31m-                for label, binary_img in pipelines:[m
[31m-                    padded = cv2.copyMakeBorder(binary_img, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=0)[m
[31m-                    up = cv2.resize(padded, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)[m
[31m-                    up_inv = cv2.bitwise_not(up)[m
[31m-                    text = pytesseract.image_to_string([m
[31m-                        up_inv, config="--psm 7 -c tessedit_char_whitelist=0123456789"[m
[31m-                    ).strip()[m
[31m-                    nums = re.findall(r"\d+", text)[m
[31m-                    if nums:[m
[31m-                        ocr_results.append(int(nums[0]))[m
[31m-[m
[31m-            # 投票（平票取最大值：OCR 更容易漏掉前导数字）[m
[31m-            if ocr_results:[m
[31m-                counter = Counter(ocr_results)[m
[31m-                top_count = counter.most_common(1)[0][1][m
[31m-                tied = [val for val, cnt in counter.items() if cnt == top_count][m
[31m-                available_points = max(tied)[m
[31m-                log_info(t("upgrade.ap_result", pts=available_points, raw=ocr_results, w=w, h=h))[m
[31m-            else:[m
[31m-                log_warning(t("upgrade.ap_no_digit"))[m
[32m+[m[32m            if roi.size == 0:[m
[32m+[m[32m                continue[m
[32m+[m
[32m+[m[32m            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)[m
[32m+[m[32m            # 4 条针对黄色 AP 文字的二值化管线[m
[32m+[m[32m            pipelines = [][m
[32m+[m[32m            _, t150 = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)[m
[32m+[m[32m            pipelines.append(("gray_t150", t150))[m
[32m+[m[32m            _, t160 = cv2.threshold(gray, 160, 255, cv2.THRESH_BINARY)[m
[32m+[m[32m            pipelines.append(("gray_t160", t160))[m
[32m+[m[32m            _, t_otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[m
[32m+[m[32m            pipelines.append(("gray_otsu", t_otsu))[m
[32m+[m[32m            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)[m
[32m+[m[32m            yellow_mask = cv2.inRange(hsv, np.array([15, 40, 100]), np.array([45, 255, 255]))[m
[32m+[m[32m            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))[m
[32m+[m[32m            yellow_mask = cv2.morphologyEx(yellow_mask, cv2.MORPH_CLOSE, kernel)[m
[32m+[m[32m            yellow_mask = cv2.dilate(yellow_mask, kernel, iterations=1)  # 增粗抗锯齿细笔画[m
[32m+[m[32m            pipelines.append(("hsv_yellow", yellow_mask))[m
[32m+[m
[32m+[m[32m            # 调试输出（仅首帧；读取实时全局值，确保 --debug 运行时也能生效）[m
[32m+[m[32m            if module_ocr.DEBUG_WRITE_FILES and frame_idx == 0:[m
[32m+[m[32m                cv2.imwrite("debug_ap_roi_raw.png", roi)[m
[32m+[m[32m                cv2.imwrite("debug_ap_roi_gray_t150.png", t150)[m
[32m+[m[32m                cv2.imwrite("debug_ap_roi_yellow_mask.png", yellow_mask)[m
[32m+[m
[32m+[m[32m            # 每管线：补边 + 3×CUBIC 放大 + 反相 → 置信度 OCR（候选跨帧累积）[m
[32m+[m[32m            # 注：实测在 56×27 的小 ROI 上 3×CUBIC 优于 4×LINEAR（后者会让灰度管线误读 549→349/949）[m
[32m+[m[32m            for _label, binary_img in pipelines:[m
[32m+[m[32m                padded = cv2.copyMakeBorder(binary_img, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=0)[m
[32m+[m[32m                up = cv2.resize(padded, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)[m
[32m+[m[32m                up_inv = cv2.bitwise_not(up)[m
[32m+[m[32m                candidates.extend(module_ocr._ocr_digits_with_conf(up_inv, 7))[m
[32m+[m
[32m+[m[32m        # 范围校验(0..999) + 置信度加权投票（跨帧 × 4 管线候选汇总）[m
[32m+[m[32m        voted = module_ocr._vote_skill_points(candidates)[m
[32m+[m[32m        if voted is not None:[m
[32m+[m[32m            available_points = voted[m
[32m+[m[32m            log_info(t("upgrade.ap_result", pts=available_points, raw=[v for v, _ in candidates], w=last_w, h=last_h))[m
[32m+[m[32m        else:[m
[32m+[m[32m            log_warning(t("upgrade.ap_no_digit"))[m
 [m
         if available_points >= 0 and available_points < min_points:[m
             log_warning(t("upgrade.ap_low", pts=available_points, min=min_points))[m

[33mcommit d0a42704c697ad9d4926b43dd6692b49fb71cf33[m
Author: hypoxic127 <aw1244936857@gmail.com>
Date:   Sat Jun 20 21:09:07 2026 +0800

    docs: remove legacy terms and template matching references across codebase

[1mdiff --git a/macro/upgrade.py b/macro/upgrade.py[m
[1mindex 5732692..a2f71d6 100644[m
[1m--- a/macro/upgrade.py[m
[1m+++ b/macro/upgrade.py[m
[36m@@ -32,7 +32,7 @@[m [mdef action_upgrade_car_skills(hwnd, gamepad, min_points=30):[m
     10. 重复多次 (D-pad Up 1 次 + A)[m
     11. 输入 D-pad Left 1 次[m
     12. 输入 B × 2（退出技能树）[m
[31m-    确保页面与 usepoints.png 模板画面一致[m
[32m+[m[32m    确保已进入技能树升级界面[m
     """[m
     log_info(t("upgrade.start"))[m
     # 宏按键延迟设置，确保 UI 渲染稳定[m

[33mcommit 5cf44389f39f177e155282fde9aea99b316f38f6[m
Author: hypoxic127 <aw1244936857@gmail.com>
Date:   Sat Jun 6 21:02:01 2026 +0800

    feat(i18n): complete bilingual migration for all modules and fix ruff format

[1mdiff --git a/macro/upgrade.py b/macro/upgrade.py[m
[1mindex 1521a12..5732692 100644[m
[1m--- a/macro/upgrade.py[m
[1m+++ b/macro/upgrade.py[m
[36m@@ -11,6 +11,7 @@[m [mimport numpy as np[m
 import pytesseract[m
 import vgamepad as vg[m
 [m
[32m+[m[32mfrom engine.i18n import t[m
 from engine.ocr import DEBUG_WRITE_FILES[m
 from engine.utils import log_info, log_success, log_warning[m
 from macro.core import capture_raw_screenshot, capture_screenshot[m
[36m@@ -33,7 +34,7 @@[m [mdef action_upgrade_car_skills(hwnd, gamepad, min_points=30):[m
     12. 输入 B × 2（退出技能树）[m
     确保页面与 usepoints.png 模板画面一致[m
     """[m
[31m-    log_info("正在执行车辆加点宏...")[m
[32m+[m[32m    log_info(t("upgrade.start"))[m
     # 宏按键延迟设置，确保 UI 渲染稳定[m
 [m
     def press(button, count=1, delay=0.8):[m
[36m@@ -47,7 +48,7 @@[m [mdef action_upgrade_car_skills(hwnd, gamepad, min_points=30):[m
 [m
     # 1. B × 1[m
 [m
[31m-    log_info("  -> 选好车后等待 2.0 秒以确保稳定...")[m
[32m+[m[32m    log_info(t("upgrade.wait_stable"))[m
     time.sleep(2.0)[m
     log_info("  -> [1] B × 1...")[m
     press(vg.XUSB_BUTTON.XUSB_GAMEPAD_B, delay=1.0)[m
[36m@@ -61,7 +62,7 @@[m [mdef action_upgrade_car_skills(hwnd, gamepad, min_points=30):[m
     press(vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=1.2)[m
     # 4. 输入 D-pad Down 7次[m
 [m
[31m-    log_info("  -> [4] 输入 D-pad Down 7次...")[m
[32m+[m[32m    log_info(t("upgrade.step_down7"))[m
     press(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN, count=7, delay=0.8)[m
     # 5.  A[m
 [m
[36m@@ -133,15 +134,15 @@[m [mdef action_upgrade_car_skills(hwnd, gamepad, min_points=30):[m
                 top_count = counter.most_common(1)[0][1][m
                 tied = [val for val, cnt in counter.items() if cnt == top_count][m
                 available_points = max(tied)[m
[31m-                log_info(f"  [Available Points] OCR: {available_points} (读数: {ocr_results}, {w}x{h})")[m
[32m+[m[32m                log_info(t("upgrade.ap_result", pts=available_points, raw=ocr_results, w=w, h=h))[m
             else:[m
[31m-                log_warning("  [Available Points] OCR 未识别到数字！")[m
[32m+[m[32m                log_warning(t("upgrade.ap_no_digit"))[m
 [m
         if available_points >= 0 and available_points < min_points:[m
[31m-            log_warning(f"  ⚠️ Available Points = {available_points} < {min_points}，技能点不足！")[m
[32m+[m[32m            log_warning(t("upgrade.ap_low", pts=available_points, min=min_points))[m
             return available_points[m
     except Exception as e:[m
[31m-        log_warning(f"  [Available Points] OCR 异常: {e}")[m
[32m+[m[32m        log_warning(t("upgrade.ap_error", err=e))[m
 [m
     def _check_cannot_afford(step_name):[m
         """检测 'Cannot Afford Perk' 弹窗并按 A 关闭"""[m
[36m@@ -156,7 +157,7 @@[m [mdef action_upgrade_car_skills(hwnd, gamepad, min_points=30):[m
         _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)[m
         text = pytesseract.image_to_string(thresh, config="--psm 6").strip().lower()[m
         if "cannot" in text and "afford" in text:[m
[31m-            log_warning(f"  ⚠️ [{step_name}] 检测到 'Cannot Afford Perk' 弹窗 (OCR: '{text[:50]}')，按 A 关闭...")[m
[32m+[m[32m            log_warning(t("upgrade.cannot_afford", step=step_name, text=text[:50]))[m
             press(vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=1.0)[m
             return True[m
         return False[m
[36m@@ -166,26 +167,26 @@[m [mdef action_upgrade_car_skills(hwnd, gamepad, min_points=30):[m
     log_info("  -> [6]  A ...")[m
     press(vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=1.2)[m
     if _check_cannot_afford("步骤6"):[m
[31m-        log_warning("  ⚠️ 技能点不足，提前结束加点宏")[m
[32m+[m[32m        log_warning(t("upgrade.afford_fail"))[m
         return available_points[m
     # 7. 输入 D-pad Right 1次[m
 [m
[31m-    log_info("  -> [7] 输入 D-pad Right 1次...")[m
[32m+[m[32m    log_info(t("upgrade.step_right"))[m
     press(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT, delay=0.8)[m
     # 8.  A[m
 [m
     log_info("  -> [8]  A ...")[m
     press(vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=1.2)[m
     if _check_cannot_afford("步骤8"):[m
[31m-        log_warning("  ⚠️ 技能点不足，提前结束加点宏")[m
[32m+[m[32m        log_warning(t("upgrade.afford_fail"))[m
         return available_points[m
     # 9. 重复多次 (D-pad Up 1次 + A)[m
 [m
     afford_failed = False[m
     for j in range(3):[m
[31m-        log_info(f"  -> [9] 循环 {j + 1}/3: 输入 D-pad Up 1次...")[m
[32m+[m[32m        log_info(t("upgrade.loop_up", n=j + 1))[m
         press(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP, delay=0.8)[m
[31m-        log_info(f"  -> [9] 循环 {j + 1}/3: 按 A 确认...")[m
[32m+[m[32m        log_info(t("upgrade.loop_a", n=j + 1))[m
         press(vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=1.2)[m
         if _check_cannot_afford(f"循环{j + 1}"):[m
             afford_failed = True[m
[36m@@ -193,7 +194,7 @@[m [mdef action_upgrade_car_skills(hwnd, gamepad, min_points=30):[m
 [m
     # 10. 输入 D-pad Left 1次[m
 [m
[31m-    log_info("  -> [10] 输入 D-pad Left 1次...")[m
[32m+[m[32m    log_info(t("upgrade.step_left"))[m
     press(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT, delay=0.8)[m
     # 11.  A[m
 [m
[36m@@ -201,5 +202,5 @@[m [mdef action_upgrade_car_skills(hwnd, gamepad, min_points=30):[m
     press(vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=1.5)[m
     if afford_failed:[m
         _check_cannot_afford("步骤11")[m
[31m-    log_success("车辆加点宏执行完毕！页面特征应与 usepoints.png 一致")[m
[32m+[m[32m    log_success(t("upgrade.done"))[m
     return available_points  # 返回剩余点数[m

[33mcommit e3885a9e36439a52b50eb7a6cde0e2a97121a3ab[m
Author: hypoxic127 <aw1244936857@gmail.com>
Date:   Sun May 31 00:36:05 2026 +0800

    fix(lint): resolve all ruff F401/F541 errors (19 issues)
    
    - F541: Remove extraneous f-prefix (build.py, main_bot.py)
    - F401: Remove unused imports across 9 files
    - Re-export imports in macro/core.py annotated with noqa:F401
    - 65 tests pass, 0 regressions

[1mdiff --git a/macro/upgrade.py b/macro/upgrade.py[m
[1mindex 69765a6..1521a12 100644[m
[1m--- a/macro/upgrade.py[m
[1m+++ b/macro/upgrade.py[m
[36m@@ -12,8 +12,7 @@[m [mimport pytesseract[m
 import vgamepad as vg[m
 [m
 from engine.ocr import DEBUG_WRITE_FILES[m
[31m-from engine.utils import log_error, log_info, log_success, log_warning[m
[31m-from engine.utils import press_button as _press_button[m
[32m+[m[32mfrom engine.utils import log_info, log_success, log_warning[m
 from macro.core import capture_raw_screenshot, capture_screenshot[m
 [m
 [m

[33mcommit 0d54894d19327537c0bc0d7a3e1d1d5a5aab668f[m
Author: hypoxic127 <aw1244936857@gmail.com>
Date:   Fri May 29 12:05:12 2026 +0800

    style: apply ruff format to all source files

[1mdiff --git a/macro/upgrade.py b/macro/upgrade.py[m
[1mindex f71588f..69765a6 100644[m
[1m--- a/macro/upgrade.py[m
[1m+++ b/macro/upgrade.py[m
[36m@@ -74,13 +74,14 @@[m [mdef action_upgrade_car_skills(hwnd, gamepad, min_points=30):[m
     available_points = -1[m
     try:[m
         from collections import Counter[m
[32m+[m
         raw_img = capture_raw_screenshot(hwnd)[m
         if raw_img is not None:[m
             h, w = raw_img.shape[:2][m
             ocr_results = [][m
 [m
             # ROI: 数字区域 (h85-88%, w35-38.5%)[m
[31m-            roi = raw_img[int(h * 0.85):int(h * 0.88), int(w * 0.35):int(w * 0.385)][m
[32m+[m[32m            roi = raw_img[int(h * 0.85) : int(h * 0.88), int(w * 0.35) : int(w * 0.385)][m
 [m
             if roi.size > 0:[m
                 gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)[m
[36m@@ -102,9 +103,7 @@[m [mdef action_upgrade_car_skills(hwnd, gamepad, min_points=30):[m
 [m
                 # 4. HSV 黄色通道（放宽阈值 + 膨胀增粗笔画）[m
                 hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)[m
[31m-                yellow_mask = cv2.inRange(hsv,[m
[31m-                                          np.array([15, 40, 100]),[m
[31m-                                          np.array([45, 255, 255]))[m
[32m+[m[32m                yellow_mask = cv2.inRange(hsv, np.array([15, 40, 100]), np.array([45, 255, 255]))[m
                 kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))[m
                 yellow_mask = cv2.morphologyEx(yellow_mask, cv2.MORPH_CLOSE, kernel)[m
                 # 膨胀 1 次增粗抗锯齿导致的细笔画[m
[36m@@ -119,16 +118,13 @@[m [mdef action_upgrade_car_skills(hwnd, gamepad, min_points=30):[m
 [m
                 # 对每个管线执行 OCR（PSM 7 单行模式）[m
                 for label, binary_img in pipelines:[m
[31m-                    padded = cv2.copyMakeBorder(binary_img, 20, 20, 20, 20,[m
[31m-                                                cv2.BORDER_CONSTANT, value=0)[m
[31m-                    up = cv2.resize(padded, None, fx=3, fy=3,[m
[31m-                                    interpolation=cv2.INTER_CUBIC)[m
[32m+[m[32m                    padded = cv2.copyMakeBorder(binary_img, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=0)[m
[32m+[m[32m                    up = cv2.resize(padded, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)[m
                     up_inv = cv2.bitwise_not(up)[m
                     text = pytesseract.image_to_string([m
[31m-                        up_inv,[m
[31m-                        config='--psm 7 -c tessedit_char_whitelist=0123456789'[m
[32m+[m[32m                        up_inv, config="--psm 7 -c tessedit_char_whitelist=0123456789"[m
                     ).strip()[m
[31m-                    nums = re.findall(r'\d+', text)[m
[32m+[m[32m                    nums = re.findall(r"\d+", text)[m
                     if nums:[m
                         ocr_results.append(int(nums[0]))[m
 [m
[36m@@ -156,10 +152,10 @@[m [mdef action_upgrade_car_skills(hwnd, gamepad, min_points=30):[m
             return False[m
         h_img, w_img = resized.shape[:2][m
         # 弹窗区域: h27-83%, w26-82%[m
[31m-        roi = resized[int(h_img*0.27):int(h_img*0.83), int(w_img*0.26):int(w_img*0.82)][m
[32m+[m[32m        roi = resized[int(h_img * 0.27) : int(h_img * 0.83), int(w_img * 0.26) : int(w_img * 0.82)][m
         gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)[m
         _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)[m
[31m-        text = pytesseract.image_to_string(thresh, config='--psm 6').strip().lower()[m
[32m+[m[32m        text = pytesseract.image_to_string(thresh, config="--psm 6").strip().lower()[m
         if "cannot" in text and "afford" in text:[m
             log_warning(f"  ⚠️ [{step_name}] 检测到 'Cannot Afford Perk' 弹窗 (OCR: '{text[:50]}')，按 A 关闭...")[m
             press(vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=1.0)[m
[36m@@ -188,11 +184,11 @@[m [mdef action_upgrade_car_skills(hwnd, gamepad, min_points=30):[m
 [m
     afford_failed = False[m
     for j in range(3):[m
[31m-        log_info(f"  -> [9] 循环 {j+1}/3: 输入 D-pad Up 1次...")[m
[32m+[m[32m        log_info(f"  -> [9] 循环 {j + 1}/3: 输入 D-pad Up 1次...")[m
         press(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP, delay=0.8)[m
[31m-        log_info(f"  -> [9] 循环 {j+1}/3: 按 A 确认...")[m
[32m+[m[32m        log_info(f"  -> [9] 循环 {j + 1}/3: 按 A 确认...")[m
         press(vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=1.2)[m
[31m-        if _check_cannot_afford(f"循环{j+1}"):[m
[32m+[m[32m        if _check_cannot_afford(f"循环{j + 1}"):[m
             afford_failed = True[m
             break[m
 [m
[36m@@ -208,4 +204,3 @@[m [mdef action_upgrade_car_skills(hwnd, gamepad, min_points=30):[m
         _check_cannot_afford("步骤11")[m
     log_success("车辆加点宏执行完毕！页面特征应与 usepoints.png 一致")[m
     return available_points  # 返回剩余点数[m
[31m-[m

[33mcommit 488f653c859c9c5922f3238cf7015f95b7904adc[m
Author: hypoxic127 <aw1244936857@gmail.com>
Date:   Fri May 29 12:04:00 2026 +0800

    fix(lint): auto-fix all ruff errors (I001, F541, F841, E712)
    
    Applied ruff --fix + --unsafe-fixes to resolve 63 lint errors:
    - I001: sorted all import blocks across 15 files
    - F541: removed 40+ extraneous f-string prefixes
    - F841: removed 3 unused variable assignments
    - E712: replaced == True/False with truthiness checks in tests

[1mdiff --git a/macro/upgrade.py b/macro/upgrade.py[m
[1mindex 85b4713..f71588f 100644[m
[1m--- a/macro/upgrade.py[m
[1m+++ b/macro/upgrade.py[m
[36m@@ -3,16 +3,19 @@[m
 macro/upgrade.py — 车辆加点宏[m
 """[m
 [m
[32m+[m[32mimport re[m
 import time[m
[32m+[m
 import cv2[m
 import numpy as np[m
[31m-import vgamepad as vg[m
[31m-from engine.utils import log_info, log_success, log_warning, log_error[m
[31m-from engine.utils import press_button as _press_button[m
[31m-from macro.core import capture_screenshot, capture_raw_screenshot[m
 import pytesseract[m
[31m-import re[m
[32m+[m[32mimport vgamepad as vg[m
[32m+[m
 from engine.ocr import DEBUG_WRITE_FILES[m
[32m+[m[32mfrom engine.utils import log_error, log_info, log_success, log_warning[m
[32m+[m[32mfrom engine.utils import press_button as _press_button[m
[32m+[m[32mfrom macro.core import capture_raw_screenshot, capture_screenshot[m
[32m+[m
 [m
 def action_upgrade_car_skills(hwnd, gamepad, min_points=30):[m
     """[m

[33mcommit 6e585d86e9afec206545fe5c719175db8bb7813d[m
Author: hypoxic127 <aw1244936857@gmail.com>
Date:   Fri May 29 11:53:15 2026 +0800

    refactor(structure): reorganize flat modules into package hierarchy
    
    Project restructured from flat layout to 3-package architecture:
    
    engine/          ← 感知引擎层
      ocr.py         ← module_ocr.py
      state_detect.py← module_state_detect.py
      utils.py       ← utils.py
    
    farm/            ← 刷图状态机
      skills.py      ← module_farm_skills.py
    
    macro/           ← 宏操作层 (unchanged internal structure)
    
    Also:
    - tools/         ← tool_*.py, debug_*.py moved here
    - tests/         ← test_*.py moved here
    - Removed module_macro.py wrapper (main_bot.py now imports directly from macro)
    - Updated all 12 source files with new import paths
    - All 14 files compile-verified

[1mdiff --git a/macro/upgrade.py b/macro/upgrade.py[m
[1mindex f46cc81..85b4713 100644[m
[1m--- a/macro/upgrade.py[m
[1m+++ b/macro/upgrade.py[m
[36m@@ -7,12 +7,12 @@[m [mimport time[m
 import cv2[m
 import numpy as np[m
 import vgamepad as vg[m
[31m-from utils import log_info, log_success, log_warning, log_error[m
[31m-from utils import press_button as _press_button[m
[32m+[m[32mfrom engine.utils import log_info, log_success, log_warning, log_error[m
[32m+[m[32mfrom engine.utils import press_button as _press_button[m
 from macro.core import capture_screenshot, capture_raw_screenshot[m
 import pytesseract[m
 import re[m
[31m-from module_ocr import DEBUG_WRITE_FILES[m
[32m+[m[32mfrom engine.ocr import DEBUG_WRITE_FILES[m
 [m
 def action_upgrade_car_skills(hwnd, gamepad, min_points=30):[m
     """[m

[33mcommit 1f8d72594cbf127591277194bce2dd63784d722f[m
Author: hypoxic127 <aw1244936857@gmail.com>
Date:   Fri May 29 11:46:54 2026 +0800

    chore(git): overhaul .gitignore and purge stale tracked files
    
    - Remove 38 obsolete template PNGs from index (replaced by HSV+OCR detection)
    - Remove stale test files (test_cursor_fix.py, test_draw_regions.py)
    - Remove tool_annotate_roi.py from tracking
    - Add ignore rules for: .agents/, tool_*.py, debug_*.py, test_*.py, templates/, state_references.json, virtualenvs, .env

[1mdiff --git a/macro/upgrade.py b/macro/upgrade.py[m
[1mindex 154fc3e..f46cc81 100644[m
[1m--- a/macro/upgrade.py[m
[1m+++ b/macro/upgrade.py[m
[36m@@ -12,6 +12,7 @@[m [mfrom utils import press_button as _press_button[m
 from macro.core import capture_screenshot, capture_raw_screenshot[m
 import pytesseract[m
 import re[m
[32m+[m[32mfrom module_ocr import DEBUG_WRITE_FILES[m
 [m
 def action_upgrade_car_skills(hwnd, gamepad, min_points=30):[m
     """[m
[36m@@ -75,20 +76,58 @@[m [mdef action_upgrade_car_skills(hwnd, gamepad, min_points=30):[m
             h, w = raw_img.shape[:2][m
             ocr_results = [][m
 [m
[31m-            # 窄 ROI: 只裁数字区域 (h85-88%, w36-38%)[m
[31m-            roi = raw_img[int(h * 0.85):int(h * 0.88), int(w * 0.36):int(w * 0.38)][m
[31m-            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)[m
[31m-[m
[31m-            # 两种阈值 × PSM 7，共 2 次 OCR 投票[m
[31m-            for tname, thresh_img in [[m
[31m-                ("t100", cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY)[1]),[m
[31m-                ("otsu", cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]),[m
[31m-            ]:[m
[31m-                up = cv2.resize(thresh_img, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)[m
[31m-                text = pytesseract.image_to_string(up, config='--psm 7 -c tessedit_char_whitelist=0123456789').strip()[m
[31m-                nums = re.findall(r'\d+', text)[m
[31m-                if nums:[m
[31m-                    ocr_results.append(int(nums[0]))[m
[32m+[m[32m            # ROI: 数字区域 (h85-88%, w35-38.5%)[m
[32m+[m[32m            roi = raw_img[int(h * 0.85):int(h * 0.88), int(w * 0.35):int(w * 0.385)][m
[32m+[m
[32m+[m[32m            if roi.size > 0:[m
[32m+[m[32m                gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)[m
[32m+[m
[32m+[m[32m                # === 主力管线: 灰度阈值（实测最稳定） ===[m
[32m+[m[32m                pipelines = [][m
[32m+[m
[32m+[m[32m                # 1. 灰度 threshold 150（test_from_state 测试14验证通过）[m
[32m+[m[32m                _, t150 = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)[m
[32m+[m[32m                pipelines.append(("gray_t150", t150))[m
[32m+[m
[32m+[m[32m                # 2. 灰度 threshold 160[m
[32m+[m[32m                _, t160 = cv2.threshold(gray, 160, 255, cv2.THRESH_BINARY)[m
[32m+[m[32m                pipelines.append(("gray_t160", t160))[m
[32m+[m
[32m+[m[32m                # 3. Otsu 自适应阈值[m
[32m+[m[32m                _, t_otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[m
[32m+[m[32m                pipelines.append(("gray_otsu", t_otsu))[m
[32m+[m
[32m+[m[32m                # 4. HSV 黄色通道（放宽阈值 + 膨胀增粗笔画）[m
[32m+[m[32m                hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)[m
[32m+[m[32m                yellow_mask = cv2.inRange(hsv,[m
[32m+[m[32m                                          np.array([15, 40, 100]),[m
[32m+[m[32m                                          np.array([45, 255, 255]))[m
[32m+[m[32m                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))[m
[32m+[m[32m                yellow_mask = cv2.morphologyEx(yellow_mask, cv2.MORPH_CLOSE, kernel)[m
[32m+[m[32m                # 膨胀 1 次增粗抗锯齿导致的细笔画[m
[32m+[m[32m                yellow_mask = cv2.dilate(yellow_mask, kernel, iterations=1)[m
[32m+[m[32m                pipelines.append(("hsv_yellow", yellow_mask))[m
[32m+[m
[32m+[m[32m                # 调试输出[m
[32m+[m[32m                if DEBUG_WRITE_FILES:[m
[32m+[m[32m                    cv2.imwrite("debug_ap_roi_raw.png", roi)[m
[32m+[m[32m                    cv2.imwrite("debug_ap_roi_gray_t150.png", t150)[m
[32m+[m[32m                    cv2.imwrite("debug_ap_roi_yellow_mask.png", yellow_mask)[m
[32m+[m
[32m+[m[32m                # 对每个管线执行 OCR（PSM 7 单行模式）[m
[32m+[m[32m                for label, binary_img in pipelines:[m
[32m+[m[32m                    padded = cv2.copyMakeBorder(binary_img, 20, 20, 20, 20,[m
[32m+[m[32m                                                cv2.BORDER_CONSTANT, value=0)[m
[32m+[m[32m                    up = cv2.resize(padded, None, fx=3, fy=3,[m
[32m+[m[32m                                    interpolation=cv2.INTER_CUBIC)[m
[32m+[m[32m                    up_inv = cv2.bitwise_not(up)[m
[32m+[m[32m                    text = pytesseract.image_to_string([m
[32m+[m[32m                        up_inv,[m
[32m+[m[32m                        config='--psm 7 -c tessedit_char_whitelist=0123456789'[m
[32m+[m[32m                    ).strip()[m
[32m+[m[32m                    nums = re.findall(r'\d+', text)[m
[32m+[m[32m                    if nums:[m
[32m+[m[32m                        ocr_results.append(int(nums[0]))[m
 [m
             # 投票（平票取最大值：OCR 更容易漏掉前导数字）[m
             if ocr_results:[m

[33mcommit 8b13f2b472be1ea4e26887cfd9df6340eaae306c[m
Author: hypoxic127 <aw1244936857@gmail.com>
Date:   Wed May 27 03:08:36 2026 +0800

    demo 1.0.1

[1mdiff --git a/macro/upgrade.py b/macro/upgrade.py[m
[1mindex 3184110..154fc3e 100644[m
[1m--- a/macro/upgrade.py[m
[1m+++ b/macro/upgrade.py[m
[36m@@ -75,8 +75,8 @@[m [mdef action_upgrade_car_skills(hwnd, gamepad, min_points=30):[m
             h, w = raw_img.shape[:2][m
             ocr_results = [][m
 [m
[31m-            # 窄 ROI: 只裁数字区域 (排除左侧标签文字和右侧星形图标)[m
[31m-            roi = raw_img[int(h * 0.85):int(h * 0.89), int(w * 0.34):int(w * 0.385)][m
[32m+[m[32m            # 窄 ROI: 只裁数字区域 (h85-88%, w36-38%)[m
[32m+[m[32m            roi = raw_img[int(h * 0.85):int(h * 0.88), int(w * 0.36):int(w * 0.38)][m
             gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)[m
 [m
             # 两种阈值 × PSM 7，共 2 次 OCR 投票[m
[36m@@ -113,14 +113,13 @@[m [mdef action_upgrade_car_skills(hwnd, gamepad, min_points=30):[m
         if resized is None:[m
             return False[m
         h_img, w_img = resized.shape[:2][m
[31m-        # 弹窗标题栏: 画面中部偏下 (25-40% 高度, 25-75% 宽度) 黄绿色横幅[m
[31m-        roi = resized[int(h_img*0.25):int(h_img*0.40), int(w_img*0.25):int(w_img*0.75)][m
[31m-        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)[m
[31m-        # 荧光黄绿色: H=25-45, S>150, V>200[m
[31m-        yellow_mask = cv2.inRange(hsv, np.array([25, 150, 200]), np.array([45, 255, 255]))[m
[31m-        yellow_px = cv2.countNonZero(yellow_mask)[m
[31m-        if yellow_px > 2000:[m
[31m-            log_warning(f"  ⚠️ [{step_name}] 检测到 'Cannot Afford Perk' 弹窗 (黄色: {yellow_px})，按 A 关闭...")[m
[32m+[m[32m        # 弹窗区域: h27-83%, w26-82%[m
[32m+[m[32m        roi = resized[int(h_img*0.27):int(h_img*0.83), int(w_img*0.26):int(w_img*0.82)][m
[32m+[m[32m        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)[m
[32m+[m[32m        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)[m
[32m+[m[32m        text = pytesseract.image_to_string(thresh, config='--psm 6').strip().lower()[m
[32m+[m[32m        if "cannot" in text and "afford" in text:[m
[32m+[m[32m            log_warning(f"  ⚠️ [{step_name}] 检测到 'Cannot Afford Perk' 弹窗 (OCR: '{text[:50]}')，按 A 关闭...")[m
             press(vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=1.0)[m
             return True[m
         return False[m

[33mcommit 7f8bafc4d65f2c797bf06269dd0d8143bfcf30dc[m
Author: hypoxic127 <aw1244936857@gmail.com>
Date:   Tue May 26 23:35:17 2026 +0800

    fix ocr2

[1mdiff --git a/macro/upgrade.py b/macro/upgrade.py[m
[1mindex 6fefb99..3184110 100644[m
[1m--- a/macro/upgrade.py[m
[1m+++ b/macro/upgrade.py[m
[36m@@ -69,30 +69,40 @@[m [mdef action_upgrade_car_skills(hwnd, gamepad, min_points=30):[m
     time.sleep(1.0)  # 等待 UI 刷新[m
     available_points = -1[m
     try:[m
[31m-        # 使用原始分辨率截图，避免缩放导致文字模糊[m
[32m+[m[32m        from collections import Counter[m
         raw_img = capture_raw_screenshot(hwnd)[m
         if raw_img is not None:[m
             h, w = raw_img.shape[:2][m
[31m-            # Available Points 黄色数字精确位置:[m
[31m-            #   y: 85-89% 高度 (底部 Available Points 行)[m
[31m-            #   x: 34-38.5% 宽度 (只截数字，排除右侧星形图标)[m
[31m-            roi_ap = raw_img[int(h * 0.85):int(h * 0.89), int(w * 0.34):int(w * 0.385)][m
[31m-            # 使用 HSV 黄色通道提取 — 数字是黄色 (H=20-45)，精确隔离数字像素[m
[31m-            hsv_ap = cv2.cvtColor(roi_ap, cv2.COLOR_BGR2HSV)[m
[31m-            yellow_mask = cv2.inRange(hsv_ap, np.array([20, 80, 150]), np.array([45, 255, 255]))[m
[31m-            # 反色：Tesseract 期望黑字白底[m
[31m-            inverted_ap = cv2.bitwise_not(yellow_mask)[m
[31m-            # 加边距 + 4 倍放大，提高小字体识别率[m
[31m-            padded_ap = cv2.copyMakeBorder(inverted_ap, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)[m
[31m-            upscaled_ap = cv2.resize(padded_ap, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)[m
[31m-            text_ap = pytesseract.image_to_string(upscaled_ap, config='--psm 7 -c tessedit_char_whitelist=0123456789').strip()[m
[31m-            numbers = re.findall(r'\d+', text_ap)[m
[31m-            if numbers:[m
[31m-                available_points = int(numbers[0])[m
[31m-            log_info(f"  [Available Points] OCR 读取: '{text_ap}' → 解析: {available_points} ({w}x{h})")[m
[31m-            if available_points >= 0 and available_points < min_points:[m
[31m-                log_warning(f"  ⚠️ Available Points = {available_points} < {min_points}，技能点不足！")[m
[31m-                return available_points[m
[32m+[m[32m            ocr_results = [][m
[32m+[m
[32m+[m[32m            # 窄 ROI: 只裁数字区域 (排除左侧标签文字和右侧星形图标)[m
[32m+[m[32m            roi = raw_img[int(h * 0.85):int(h * 0.89), int(w * 0.34):int(w * 0.385)][m
[32m+[m[32m            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)[m
[32m+[m
[32m+[m[32m            # 两种阈值 × PSM 7，共 2 次 OCR 投票[m
[32m+[m[32m            for tname, thresh_img in [[m
[32m+[m[32m                ("t100", cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY)[1]),[m
[32m+[m[32m                ("otsu", cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]),[m
[32m+[m[32m            ]:[m
[32m+[m[32m                up = cv2.resize(thresh_img, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)[m
[32m+[m[32m                text = pytesseract.image_to_string(up, config='--psm 7 -c tessedit_char_whitelist=0123456789').strip()[m
[32m+[m[32m                nums = re.findall(r'\d+', text)[m
[32m+[m[32m                if nums:[m
[32m+[m[32m                    ocr_results.append(int(nums[0]))[m
[32m+[m
[32m+[m[32m            # 投票（平票取最大值：OCR 更容易漏掉前导数字）[m
[32m+[m[32m            if ocr_results:[m
[32m+[m[32m                counter = Counter(ocr_results)[m
[32m+[m[32m                top_count = counter.most_common(1)[0][1][m
[32m+[m[32m                tied = [val for val, cnt in counter.items() if cnt == top_count][m
[32m+[m[32m                available_points = max(tied)[m
[32m+[m[32m                log_info(f"  [Available Points] OCR: {available_points} (读数: {ocr_results}, {w}x{h})")[m
[32m+[m[32m            else:[m
[32m+[m[32m                log_warning("  [Available Points] OCR 未识别到数字！")[m
[32m+[m
[32m+[m[32m        if available_points >= 0 and available_points < min_points:[m
[32m+[m[32m            log_warning(f"  ⚠️ Available Points = {available_points} < {min_points}，技能点不足！")[m
[32m+[m[32m            return available_points[m
     except Exception as e:[m
         log_warning(f"  [Available Points] OCR 异常: {e}")[m
 [m

[33mcommit edcb602490fc1b22a359b8477857c802ebe24575[m
Author: hypoxic127 <aw1244936857@gmail.com>
Date:   Tue May 26 22:59:40 2026 +0800

    fix ocr

[1mdiff --git a/macro/upgrade.py b/macro/upgrade.py[m
[1mindex c301591..6fefb99 100644[m
[1m--- a/macro/upgrade.py[m
[1m+++ b/macro/upgrade.py[m
[36m@@ -73,13 +73,18 @@[m [mdef action_upgrade_car_skills(hwnd, gamepad, min_points=30):[m
         raw_img = capture_raw_screenshot(hwnd)[m
         if raw_img is not None:[m
             h, w = raw_img.shape[:2][m
[31m-             # Available Points 数字精确位置: 86-88% 高度, 33-40% 宽度[m
[31m-            # 基于 1600x900 实际截图校准 (紫色框 E 验证通过)[m
[31m-            roi_ap = raw_img[int(h * 0.86):int(h * 0.88), int(w * 0.33):int(w * 0.40)][m
[31m-            gray_ap = cv2.cvtColor(roi_ap, cv2.COLOR_BGR2GRAY)[m
[31m-            # 使用 OTSU 自适应阈值（固定 150 阈值在单位数时会把噪点识别为 0）[m
[31m-            _, thresh_ap = cv2.threshold(gray_ap, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[m
[31m-            upscaled_ap = cv2.resize(thresh_ap, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)[m
[32m+[m[32m            # Available Points 黄色数字精确位置:[m
[32m+[m[32m            #   y: 85-89% 高度 (底部 Available Points 行)[m
[32m+[m[32m            #   x: 34-38.5% 宽度 (只截数字，排除右侧星形图标)[m
[32m+[m[32m            roi_ap = raw_img[int(h * 0.85):int(h * 0.89), int(w * 0.34):int(w * 0.385)][m
[32m+[m[32m            # 使用 HSV 黄色通道提取 — 数字是黄色 (H=20-45)，精确隔离数字像素[m
[32m+[m[32m            hsv_ap = cv2.cvtColor(roi_ap, cv2.COLOR_BGR2HSV)[m
[32m+[m[32m            yellow_mask = cv2.inRange(hsv_ap, np.array([20, 80, 150]), np.array([45, 255, 255]))[m
[32m+[m[32m            # 反色：Tesseract 期望黑字白底[m
[32m+[m[32m            inverted_ap = cv2.bitwise_not(yellow_mask)[m
[32m+[m[32m            # 加边距 + 4 倍放大，提高小字体识别率[m
[32m+[m[32m            padded_ap = cv2.copyMakeBorder(inverted_ap, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)[m
[32m+[m[32m            upscaled_ap = cv2.resize(padded_ap, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)[m
             text_ap = pytesseract.image_to_string(upscaled_ap, config='--psm 7 -c tessedit_char_whitelist=0123456789').strip()[m
             numbers = re.findall(r'\d+', text_ap)[m
             if numbers:[m

[33mcommit e3a23631f06505c4a447d10f2db6e8b6f3e64017[m
Author: hypoxic127 <aw1244936857@gmail.com>
Date:   Tue May 26 17:23:52 2026 +0800

    fix: OCR misread corrections for Available Points ROI and 1998 year matching
    
    - upgrade.py: fix Available Points ROI from 78-81% to 86-88% height
      (verified with debug screenshot)
    - garage.py: add regex '.?99[8b6]' to catch OCR misreads like w99b/1898
      Also add 'sub' as brand fallback for truncated 'subaru'

[1mdiff --git a/macro/upgrade.py b/macro/upgrade.py[m
[1mindex f6e2a48..c301591 100644[m
[1m--- a/macro/upgrade.py[m
[1m+++ b/macro/upgrade.py[m
[36m@@ -73,9 +73,9 @@[m [mdef action_upgrade_car_skills(hwnd, gamepad, min_points=30):[m
         raw_img = capture_raw_screenshot(hwnd)[m
         if raw_img is not None:[m
             h, w = raw_img.shape[:2][m
[31m-             # Available Points 数字精确位置: 84-88% 高度, 30-45% 宽度[m
[31m-            # 宽度从 28-50% 收窄到 30-45%，避免右侧背景噪点被识别为 "0"[m
[31m-            roi_ap = raw_img[int(h * 0.84):int(h * 0.88), int(w * 0.30):int(w * 0.45)][m
[32m+[m[32m             # Available Points 数字精确位置: 86-88% 高度, 33-40% 宽度[m
[32m+[m[32m            # 基于 1600x900 实际截图校准 (紫色框 E 验证通过)[m
[32m+[m[32m            roi_ap = raw_img[int(h * 0.86):int(h * 0.88), int(w * 0.33):int(w * 0.40)][m
             gray_ap = cv2.cvtColor(roi_ap, cv2.COLOR_BGR2GRAY)[m
             # 使用 OTSU 自适应阈值（固定 150 阈值在单位数时会把噪点识别为 0）[m
             _, thresh_ap = cv2.threshold(gray_ap, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[m

[33mcommit a487eb657ff677408af7ef27e7a2241433d8d187[m
Author: hypoxic127 <aw1244936857@gmail.com>
Date:   Mon May 25 19:55:14 2026 +0800

    chore: cleanup pass - delete unused files, fix garbled comments, add requirements.txt
    
    - Delete image/options/ (5 unused PNGs, 44KB)
    - Remove 3 useless for-range(1) loops in purchase.py
    - Fix 15+ garbled/truncated comments across all macro/ modules
    - Fix broken log_info and error messages
    - Add requirements.txt for reproducible setup

[1mdiff --git a/macro/upgrade.py b/macro/upgrade.py[m
[1mindex f1f4dbd..f6e2a48 100644[m
[1m--- a/macro/upgrade.py[m
[1m+++ b/macro/upgrade.py[m
[36m@@ -31,7 +31,7 @@[m [mdef action_upgrade_car_skills(hwnd, gamepad, min_points=30):[m
     确保页面与 usepoints.png 模板画面一致[m
     """[m
     log_info("正在执行车辆加点宏...")[m
[31m-    # 宏置延确保UI渲[m
[32m+[m[32m    # 宏按键延迟设置，确保 UI 渲染稳定[m
 [m
     def press(button, count=1, delay=0.8):[m
         for k in range(count):[m

[33mcommit a2cadc510f71e20f9754e9fda277555b7390f591[m
Author: hypoxic127 <aw1244936857@gmail.com>
Date:   Mon May 25 19:34:17 2026 +0800

    refactor: split module_macro.py (2400 lines) into macro/ package
    
    Modular structure:
    - macro/core.py       (151 lines) - screenshots, logging, config constants
    - macro/navigation.py (344 lines) - menu navigation, visual brake, return to garage
    - macro/purchase.py   (749 lines) - 5-step Impreza purchase navigation + buy macro
    - macro/garage.py     (706 lines) - garage grid operations, car selection, deletion
    - macro/upgrade.py    (155 lines) - skill point upgrade macro
    - macro/__init__.py   (407 lines) - unified exports + main bot loop
    
    module_macro.py is now a 16-line backward-compatible wrapper.
    All existing imports (main_bot, module_farm_skills, test_from_state) continue
    to work without any changes via 'from macro import *'.

[1mdiff --git a/macro/upgrade.py b/macro/upgrade.py[m
[1mnew file mode 100644[m
[1mindex 0000000..f1f4dbd[m
[1m--- /dev/null[m
[1m+++ b/macro/upgrade.py[m
[36m@@ -0,0 +1,155 @@[m
[32m+[m[32m# -*- coding: utf-8 -*-[m
[32m+[m[32m"""[m
[32m+[m[32mmacro/upgrade.py — 车辆加点宏[m
[32m+[m[32m"""[m
[32m+[m
[32m+[m[32mimport time[m
[32m+[m[32mimport cv2[m
[32m+[m[32mimport numpy as np[m
[32m+[m[32mimport vgamepad as vg[m
[32m+[m[32mfrom utils import log_info, log_success, log_warning, log_error[m
[32m+[m[32mfrom utils import press_button as _press_button[m
[32m+[m[32mfrom macro.core import capture_screenshot, capture_raw_screenshot[m
[32m+[m[32mimport pytesseract[m
[32m+[m[32mimport re[m
[32m+[m
[32m+[m[32mdef action_upgrade_car_skills(hwnd, gamepad, min_points=30):[m
[32m+[m[32m    """[m
[32m+[m[32m    全自动车辆熟练度加点手柄宏：[m
[32m+[m[32m    1. 输入一次 A，等待 10 秒（进入车辆详情/历史）[m
[32m+[m[32m    2. 输入 B（退回）[m
[32m+[m[32m    3. 输入 D-pad Down 1 次[m
[32m+[m[32m    4. 输入 A（进入技能树）[m
[32m+[m[32m    5. 输入 D-pad Down 7 次[m
[32m+[m[32m    6. 等待 1 秒[m
[32m+[m[32m    7. 输入 A（选择超级轮盘）[m
[32m+[m[32m    8. 输入 D-pad Right 1 次[m
[32m+[m[32m    9. 输入 A（确认）[m
[32m+[m[32m    10. 重复多次 (D-pad Up 1 次 + A)[m
[32m+[m[32m    11. 输入 D-pad Left 1 次[m
[32m+[m[32m    12. 输入 B × 2（退出技能树）[m
[32m+[m[32m    确保页面与 usepoints.png 模板画面一致[m
[32m+[m[32m    """[m
[32m+[m[32m    log_info("正在执行车辆加点宏...")[m
[32m+[m[32m    # 宏置延确保UI渲[m
[32m+[m
[32m+[m[32m    def press(button, count=1, delay=0.8):[m
[32m+[m[32m        for k in range(count):[m
[32m+[m[32m            gamepad.press_button(button=button)[m
[32m+[m[32m            gamepad.update()[m
[32m+[m[32m            time.sleep(0.15)[m
[32m+[m[32m            gamepad.release_button(button=button)[m
[32m+[m[32m            gamepad.update()[m
[32m+[m[32m            time.sleep(delay)[m
[32m+[m
[32m+[m[32m    # 1. B × 1[m
[32m+[m
[32m+[m[32m    log_info("  -> 选好车后等待 2.0 秒以确保稳定...")[m
[32m+[m[32m    time.sleep(2.0)[m
[32m+[m[32m    log_info("  -> [1] B × 1...")[m
[32m+[m[32m    press(vg.XUSB_BUTTON.XUSB_GAMEPAD_B, delay=1.0)[m
[32m+[m[32m    # 2. Up × 1[m
[32m+[m
[32m+[m[32m    log_info("  -> [2] Up × 1...")[m
[32m+[m[32m    press(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP, delay=0.8)[m
[32m+[m[32m    # 3.  A[m
[32m+[m
[32m+[m[32m    log_info("  -> [3]  A ...")[m
[32m+[m[32m    press(vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=1.2)[m
[32m+[m[32m    # 4. 输入 D-pad Down 7次[m
[32m+[m
[32m+[m[32m    log_info("  -> [4] 输入 D-pad Down 7次...")[m
[32m+[m[32m    press(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN, count=7, delay=0.8)[m
[32m+[m[32m    # 5.  A[m
[32m+[m
[32m+[m[32m    log_info("  -> [5]  A ...")[m
[32m+[m[32m    press(vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=1.2)[m
[32m+[m
[32m+[m[32m    # === 触发条件 2: 扫描 Available Points ===[m
[32m+[m[32m    time.sleep(1.0)  # 等待 UI 刷新[m
[32m+[m[32m    available_points = -1[m
[32m+[m[32m    try:[m
[32m+[m[32m        # 使用原始分辨率截图，避免缩放导致文字模糊[m
[32m+[m[32m        raw_img = capture_raw_screenshot(hwnd)[m
[32m+[m[32m        if raw_img is not None:[m
[32m+[m[32m            h, w = raw_img.shape[:2][m
[32m+[m[32m             # Available Points 数字精确位置: 84-88% 高度, 30-45% 宽度[m
[32m+[m[32m            # 宽度从 28-50% 收窄到 30-45%，避免右侧背景噪点被识别为 "0"[m
[32m+[m[32m            roi_ap = raw_img[int(h * 0.84):int(h * 0.88), int(w * 0.30):int(w * 0.45)][m
[32m+[m[32m            gray_ap = cv2.cvtColor(roi_ap, cv2.COLOR_BGR2GRAY)[m
[32m+[m[32m            # 使用 OTSU 自适应阈值（固定 150 阈值在单位数时会把噪点识别为 0）[m
[32m+[m[32m            _, thresh_ap = cv2.threshold(gray_ap, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[m
[32m+[m[32m            upscaled_ap = cv2.resize(thresh_ap, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)[m
[32m+[m[32m            text_ap = pytesseract.image_to_string(upscaled_ap, config='--psm 7 -c tessedit_char_whitelist=0123456789').strip()[m
[32m+[m[32m            numbers = re.findall(r'\d+', text_ap)[m
[32m+[m[32m            if numbers:[m
[32m+[m[32m                available_points = int(numbers[0])[m
[32m+[m[32m            log_info(f"  [Available Points] OCR 读取: '{text_ap}' → 解析: {available_points} ({w}x{h})")[m
[32m+[m[32m            if available_points >= 0 and available_points < min_points:[m
[32m+[m[32m                log_warning(f"  ⚠️ Available Points = {available_points} < {min_points}，技能点不足！")[m
[32m+[m[32m                return available_points[m
[32m+[m[32m    except Exception as e:[m
[32m+[m[32m        log_warning(f"  [Available Points] OCR 异常: {e}")[m
[32m+[m
[32m+[m[32m    def _check_cannot_afford(step_name):[m
[32m+[m[32m        """检测 'Cannot Afford Perk' 弹窗并按 A 关闭"""[m
[32m+[m[32m        time.sleep(0.5)[m
[32m+[m[32m        resized, _, _, _, _ = capture_screenshot(hwnd)[m
[32m+[m[32m        if resized is None:[m
[32m+[m[32m            return False[m
[32m+[m[32m        h_img, w_img = resized.shape[:2][m
[32m+[m[32m        # 弹窗标题栏: 画面中部偏下 (25-40% 高度, 25-75% 宽度) 黄绿色横幅[m
[32m+[m[32m        roi = resized[int(h_img*0.25):int(h_img*0.40), int(w_img*0.25):int(w_img*0.75)][m
[32m+[m[32m        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)[m
[32m+[m[32m        # 荧光黄绿色: H=25-45, S>150, V>200[m
[32m+[m[32m        yellow_mask = cv2.inRange(hsv, np.array([25, 150, 200]), np.array([45, 255, 255]))[m
[32m+[m[32m        yellow_px = cv2.countNonZero(yellow_mask)[m
[32m+[m[32m        if yellow_px > 2000:[m
[32m+[m[32m            log_warning(f"  ⚠️ [{step_name}] 检测到 'Cannot Afford Perk' 弹窗 (黄色: {yellow_px})，按 A 关闭...")[m
[32m+[m[32m            press(vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=1.0)[m
[32m+[m[32m            return True[m
[32m+[m[32m        return False[m
[32m+[m
[32m+[m[32m    # 6.  A[m
[32m+[m
[32m+[m[32m    log_info("  -> [6]  A ...")[m
[32m+[m[32m    press(vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=1.2)[m
[32m+[m[32m    if _check_cannot_afford("步骤6"):[m
[32m+[m[32m        log_warning("  ⚠️ 技能点不足，提前结束加点宏")[m
[32m+[m[32m        return available_points[m
[32m+[m[32m    # 7. 输入 D-pad Right 1次[m
[32m+[m
[32m+[m[32m    log_info("  -> [7] 输入 D-pad Right 1次...")[m
[32m+[m[32m    press(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT, delay=0.8)[m
[32m+[m[32m    # 8.  A[m
[32m+[m
[32m+[m[32m    log_info("  -> [8]  A ...")[m
[32m+[m[32m    press(vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=1.2)[m
[32m+[m[32m    if _check_cannot_afford("步骤8"):[m
[32m+[m[32m        log_warning("  ⚠️ 技能点不足，提前结束加点宏")[m
[32m+[m[32m        return available_points[m
[32m+[m[32m    # 9. 重复多次 (D-pad Up 1次 + A)[m
[32m+[m
[32m+[m[32m    afford_failed = False[m
[32m+[m[32m    for j in range(3):[m
[32m+[m[32m        log_info(f"  -> [9] 循环 {j+1}/3: 输入 D-pad Up 1次...")[m
[32m+[m[32m        press(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP, delay=0.8)[m
[32m+[m[32m        log_info(f"  -> [9] 循环 {j+1}/3: 按 A 确认...")[m
[32m+[m[32m        press(vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=1.2)[m
[32m+[m[32m        if _check_cannot_afford(f"循环{j+1}"):[m
[32m+[m[32m            afford_failed = True[m
[32m+[m[32m            break[m
[32m+[m
[32m+[m[32m    # 10. 输入 D-pad Left 1次[m
[32m+[m
[32m+[m[32m    log_info("  -> [10] 输入 D-pad Left 1次...")[m
[32m+[m[32m    press(vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT, delay=0.8)[m
[32m+[m[32m    # 11.  A[m
[32m+[m
[32m+[m[32m    log_info("  -> [11]  A ...")[m
[32m+[m[32m    press(vg.XUSB_BUTTON.XUSB_GAMEPAD_A, delay=1.5)[m
[32m+[m[32m    if afford_failed:[m
[32m+[m[32m        _check_cannot_afford("步骤11")[m
[32m+[m[32m    log_success("车辆加点宏执行完毕！页面特征应与 usepoints.png 一致")[m
[32m+[m[32m    return available_points  # 返回剩余点数[m
[32m+[m
