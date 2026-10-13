#!/usr/bin/env python3
"""驗證 eval/aime_2026.json。

1. 格式：30 題、id 不重複、答案皆為 0–999 整數
2. I-10、I-13：題目文字曾依 AoPS Wiki 官方題目改正，這兩題的答案以獨立程式重算
其餘 28 題的答案依據：MathArena/aime_2026 與 math-ai/aime26 兩份資料逐題一致（2026-10-13 比對）。

用法：python eval/verify_aime_2026.py
"""
import json
import math
import os
from math import comb

HERE = os.path.dirname(os.path.abspath(__file__))


def check_i10():
    """AB=13, BC=14, CA=15；繞外心旋轉使 A'C' ⟂ BC，A' 與 B 在直線 B'C' 兩側；求六邊形 AA'CC'BB' 面積最接近的整數。"""
    B, C, A = (0.0, 0.0), (14.0, 0.0), (5.0, 12.0)
    O = (7.0, 33 / 8)  # 外心

    def rot(P, t):
        x, y = P[0] - O[0], P[1] - O[1]
        c, s = math.cos(t), math.sin(t)
        return (O[0] + c * x - s * y, O[1] + s * x + c * y)

    def side(P, Q, R):
        return (Q[0] - P[0]) * (R[1] - P[1]) - (Q[1] - P[1]) * (R[0] - P[0])

    def area(poly):
        n = len(poly)
        return abs(sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n))) / 2

    base = math.atan2(C[1] - A[1], C[0] - A[0])
    answers = set()
    for k in range(4):
        t = math.pi / 2 - base + k * math.pi / 2
        A1, B1, C1 = rot(A, t), rot(B, t), rot(C, t)
        if abs(A1[0] - C1[0]) > 1e-9:  # A'C' 不垂直於 BC（x 軸）
            continue
        if side(B1, C1, A1) * side(B1, C1, B) < 0:  # A' 與 B 異側
            answers.add(round(area([A, A1, C, C1, B, B1])))
    assert len(answers) == 1, answers
    return answers.pop()


def check_i13():
    """r = 0..501，S_r = Σ_m C(10000, 502m + r)；有幾個 S_r 能被 503 整除。"""
    return sum(1 for r in range(502) if sum(comb(10000, k) for k in range(r, 10001, 502)) % 503 == 0)


def main():
    data = json.load(open(os.path.join(HERE, "aime_2026.json"), encoding="utf-8"))
    qs = {q["id"]: q for q in data["questions"]}
    assert len(qs) == len(data["questions"]) == 30, "應有 30 題且 id 不重複"
    for q in qs.values():
        assert q["grading"] == "exact_int" and isinstance(q["answer"], int) and 0 <= q["answer"] <= 999, q["id"]
    for qid, fn in (("A26-I-10", check_i10), ("A26-I-13", check_i13)):
        got = fn()
        status = "OK" if got == qs[qid]["answer"] else "MISMATCH"
        print(f"{status} {qid}: 程式計算 {got}，題庫答案 {qs[qid]['answer']}")
        assert got == qs[qid]["answer"]
    print("全部通過：30 題格式正確，I-10、I-13 程式驗證一致")


if __name__ == "__main__":
    main()
