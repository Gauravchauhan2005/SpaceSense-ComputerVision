"""
SpaceSense AI — Geometric Angle Calculations

Pure-geometry utilities for computing angles between points, finger joint
angles, hand orientation, and movement direction.  All methods are
stateless and use NumPy for vector math.
Supports Point2D, Point3D, numpy arrays, lists, and dict-based landmarks.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Union

import numpy as np

from backend.models import Point2D, Point3D


def _to_array(pt: Any) -> Optional[np.ndarray]:
    """Convert a point (Point2D, Point3D, np.ndarray, list, tuple) to a 1D float array."""
    if pt is None:
        return None
    if isinstance(pt, np.ndarray):
        return pt.astype(np.float64).flatten()
    if isinstance(pt, (list, tuple)):
        return np.array(pt, dtype=np.float64).flatten()
    if hasattr(pt, "x") and hasattr(pt, "y"):
        if hasattr(pt, "z") and pt.z is not None:
            return np.array([pt.x, pt.y, pt.z], dtype=np.float64)
        return np.array([pt.x, pt.y], dtype=np.float64)
    return None


class AngleCalculator:
    """Collection of static geometry methods.

    All angle results are in degrees unless stated otherwise.
    """

    # ------------------------------------------------------------------
    # Core 3-point angle
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_angle_3points(
        a: Any,
        b: Any,
        c: Any,
    ) -> float:
        """Return the angle at vertex B formed by rays BA and BC.

        Parameters
        ----------
        a, b, c : Point2D | Point3D | np.ndarray | tuple | list | None
            Three points. If any is None or vectors are degenerate (zero-length),
            0.0 is returned.

        Returns
        -------
        float
            Angle in degrees in [0, 180].
        """
        arr_a = _to_array(a)
        arr_b = _to_array(b)
        arr_c = _to_array(c)

        if arr_a is None or arr_b is None or arr_c is None:
            return 0.0

        # Match dimensions (if one is 2D and another 3D, take common slice)
        min_dim = min(len(arr_a), len(arr_b), len(arr_c))
        if min_dim == 0:
            return 0.0

        va = arr_a[:min_dim]
        vb = arr_b[:min_dim]
        vc = arr_c[:min_dim]

        ba = va - vb
        bc = vc - vb

        mag_ba = float(np.linalg.norm(ba))
        mag_bc = float(np.linalg.norm(bc))

        if mag_ba < 1e-9 or mag_bc < 1e-9:
            return 0.0

        cos_theta = float(np.dot(ba, bc)) / (mag_ba * mag_bc)
        # Clamp to valid arccos domain [-1.0, 1.0]
        cos_theta = max(-1.0, min(1.0, cos_theta))
        return float(math.degrees(math.acos(cos_theta)))

    # ------------------------------------------------------------------
    # Finger joint angles
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_finger_angles(
        hand_landmarks: Any,
    ) -> Dict[str, Dict[str, float]]:
        """Compute finger joint angles from 21 hand landmarks.

        Accepts either a list/sequence of landmarks or a dict mapping
        landmark index -> point.

        Returns a dict keyed by finger name with sub-keys for joint angles.
        """
        if not hand_landmarks:
            return {}

        def _get_lm(idx: int) -> Any:
            if isinstance(hand_landmarks, dict):
                return hand_landmarks.get(idx)
            if isinstance(hand_landmarks, (list, tuple)):
                if idx < len(hand_landmarks):
                    return hand_landmarks[idx]
            return None

        calc = AngleCalculator.calculate_angle_3points

        finger_defs = [
            ("thumb", [
                ("CMC", 1, 2, 3),
                ("MCP", 2, 3, 4),
            ]),
            ("index", [
                ("MCP", 5, 6, 7),
                ("PIP", 6, 7, 8),
            ]),
            ("middle", [
                ("MCP", 9, 10, 11),
                ("PIP", 10, 11, 12),
            ]),
            ("ring", [
                ("MCP", 13, 14, 15),
                ("PIP", 14, 15, 16),
            ]),
            ("pinky", [
                ("MCP", 17, 18, 19),
                ("PIP", 18, 19, 20),
            ]),
        ]

        result: Dict[str, Dict[str, float]] = {}
        for finger_name, joints in finger_defs:
            joint_angles: Dict[str, float] = {}
            for joint_label, ia, ib, ic in joints:
                pa, pb, pc = _get_lm(ia), _get_lm(ib), _get_lm(ic)
                if pa is not None and pb is not None and pc is not None:
                    angle = calc(pa, pb, pc)
                    joint_angles[joint_label] = round(angle, 2)
            if joint_angles:
                result[finger_name] = joint_angles

        return result

    # ------------------------------------------------------------------
    # Hand orientation
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_hand_orientation(
        hand_landmarks: Any,
    ) -> Dict[str, Any]:
        """Derive hand orientation from wrist -> middle-MCP vector.

        Supports list, tuple, or dict of landmarks.
        Returns {"rotation_deg": float, "direction": str}
        """
        if not hand_landmarks:
            return {}

        def _get_lm(idx: int) -> Any:
            if isinstance(hand_landmarks, dict):
                return hand_landmarks.get(idx)
            if isinstance(hand_landmarks, (list, tuple)):
                if idx < len(hand_landmarks):
                    return hand_landmarks[idx]
            return None

        wrist = _to_array(_get_lm(0))
        middle_mcp = _to_array(_get_lm(9))

        if wrist is None or middle_mcp is None:
            return {}

        dx = middle_mcp[0] - wrist[0]
        dy = middle_mcp[1] - wrist[1]

        if abs(dx) < 1e-9 and abs(dy) < 1e-9:
            return {"rotation_deg": 0.0, "direction": "up"}

        # In standard screen coordinates (y down), -dy represents upward direction
        angle_rad = math.atan2(-dy, dx)
        rotation_deg = math.degrees(angle_rad) % 360.0

        if 45 <= rotation_deg < 135:
            direction = "up"
        elif 135 <= rotation_deg < 225:
            direction = "left"
        elif 225 <= rotation_deg < 315:
            direction = "down"
        else:
            direction = "right"

        return {
            "rotation_deg": round(rotation_deg, 2),
            "direction": direction,
        }

    # ------------------------------------------------------------------
    # Movement angle
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_movement_angle(
        prev_pos: Any,
        curr_pos: Any,
    ) -> float:
        """Angle of movement from prev_pos to curr_pos in degrees."""
        p1 = _to_array(prev_pos)
        p2 = _to_array(curr_pos)

        if p1 is None or p2 is None:
            return 0.0

        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]

        if abs(dx) < 1e-9 and abs(dy) < 1e-9:
            return 0.0

        return round(float(math.degrees(math.atan2(dy, dx))), 2)

    # ------------------------------------------------------------------
    # Hand from body/frame center
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_hand_from_body_center(
        hand_center: Any,
        frame_center: Any,
    ) -> float:
        """Angle of hand position relative to body/frame center."""
        hc = _to_array(hand_center)
        fc = _to_array(frame_center)

        if hc is None or fc is None:
            return 0.0

        dx = hc[0] - fc[0]
        dy = hc[1] - fc[1]

        if abs(dx) < 1e-9 and abs(dy) < 1e-9:
            return 0.0

        return round(float(math.degrees(math.atan2(dy, dx))), 2)

    # ------------------------------------------------------------------
    # Whole Hand vs Body Symmetry Angle
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_hand_body_angle(
        hand_landmarks: Any,
        face_landmarks: Any = None,
        frame_width: int = 640,
        frame_height: int = 480,
    ) -> Dict[str, Any]:
        """Calculate the geometric angle between the body symmetry reference line
        and the user's whole hand longitudinal axis (wrist to middle fingertip).

        Parameters
        ----------
        hand_landmarks : list or dict
            MediaPipe hand landmarks. Landmark 0 = wrist, 9 = middle MCP, 12 = middle tip.
        face_landmarks : FaceLandmarks or dict or list or None
            Facial landmarks (forehead and chin) to derive the physical body
            symmetry axis. If unavailable, true vertical downwards is used.
        frame_width : int
        frame_height : int

        Returns
        -------
        dict
            - angle_deg: angle between downward symmetry line and whole hand line (0° to 180°)
            - acute_angle_deg: acute angle between the two lines (0° to 90°)
            - lateral_direction: 'left', 'right', or 'aligned'
            - hand_vector: [[wrist_x, wrist_y], [tip_x, tip_y]]
            - symmetry_line: [[sym_x1, sym_y1], [sym_x2, sym_y2]]
            - symmetry_origin: [origin_x, origin_y]
        """
        def _get_lm(idx: int) -> Optional[np.ndarray]:
            if isinstance(hand_landmarks, dict):
                return _to_array(hand_landmarks.get(idx))
            if isinstance(hand_landmarks, (list, tuple)) and idx < len(hand_landmarks):
                return _to_array(hand_landmarks[idx])
            return None

        wrist = _get_lm(0)
        # Use middle fingertip (12), fallback to middle MCP (9), index tip (8), etc.
        tip = None
        for cand_idx in [12, 9, 8, 10, 16, 4]:
            t = _get_lm(cand_idx)
            if t is not None:
                tip = t
                break

        if wrist is None or tip is None:
            return {}

        # 1. Whole hand longitudinal vector (wrist -> fingertip)
        hand_vec = tip[:2] - wrist[:2]
        mag_hand = float(np.linalg.norm(hand_vec))
        if mag_hand < 1e-4:
            return {}

        # 2. Body symmetry line (from forehead towards chin and downwards)
        sym_origin = np.array([float(frame_width) / 2.0, float(frame_height) / 2.0], dtype=np.float64)
        sym_vec = np.array([0.0, 1.0], dtype=np.float64)  # default true downwards vertical

        if face_landmarks is not None:
            forehead = None
            chin = None

            if hasattr(face_landmarks, "forehead") and face_landmarks.forehead is not None:
                forehead = _to_array(face_landmarks.forehead)
            if hasattr(face_landmarks, "chin") and face_landmarks.chin is not None:
                chin = _to_array(face_landmarks.chin)

            if (forehead is None or chin is None) and hasattr(face_landmarks, "all_landmarks"):
                all_lm = face_landmarks.all_landmarks
                if isinstance(all_lm, (list, tuple)) and len(all_lm) > 152:
                    if forehead is None:
                        forehead = _to_array(all_lm[10])
                    if chin is None:
                        chin = _to_array(all_lm[152])

            if (forehead is None or chin is None) and isinstance(face_landmarks, dict):
                fh_raw = face_landmarks.get("forehead")
                if fh_raw is None:
                    fh_raw = face_landmarks.get(10)
                ch_raw = face_landmarks.get("chin")
                if ch_raw is None:
                    ch_raw = face_landmarks.get(152)
                if fh_raw is not None:
                    forehead = _to_array(fh_raw)
                if ch_raw is not None:
                    chin = _to_array(ch_raw)

            if forehead is not None and chin is not None:
                diff = chin[:2] - forehead[:2]
                mag_diff = float(np.linalg.norm(diff))
                if mag_diff > 1e-4:
                    sym_vec = diff / mag_diff
                    sym_origin = chin[:2].copy()

        norm_sym = sym_vec / max(1e-6, float(np.linalg.norm(sym_vec)))
        norm_hand = hand_vec / max(1e-6, mag_hand)

        # 3. Angle between body symmetry axis and whole hand vector
        dot_val = float(np.dot(norm_sym, norm_hand))
        cos_theta = max(-1.0, min(1.0, dot_val))
        angle_deg = float(math.degrees(math.acos(cos_theta)))

        # Acute angle to the symmetry line (0° - 90°)
        acute_deg = angle_deg if angle_deg <= 90.0 else (180.0 - angle_deg)

        # Lateral direction via 2D cross product
        cross_prod = float(norm_sym[0] * norm_hand[1] - norm_sym[1] * norm_hand[0])
        if cross_prod > 0.05:
            lateral = "left"
        elif cross_prod < -0.05:
            lateral = "right"
        else:
            lateral = "aligned"

        # Construct reference line coordinates across frame
        length = float(max(frame_width, frame_height))
        sym_p1 = sym_origin - norm_sym * (length * 0.4)
        sym_p2 = sym_origin + norm_sym * (length * 0.7)

        return {
            "angle_deg": round(angle_deg, 1),
            "acute_angle_deg": round(acute_deg, 1),
            "lateral_direction": lateral,
            "hand_vector": [
                [round(float(wrist[0]), 1), round(float(wrist[1]), 1)],
                [round(float(tip[0]), 1), round(float(tip[1]), 1)],
            ],
            "symmetry_line": [
                [round(float(sym_p1[0]), 1), round(float(sym_p1[1]), 1)],
                [round(float(sym_p2[0]), 1), round(float(sym_p2[1]), 1)],
            ],
            "symmetry_origin": [round(float(sym_origin[0]), 1), round(float(sym_origin[1]), 1)],
        }
