"""獨立驗證 eval/questions.json 的標準答案。

每題都用與題目無關的程式（暴力或直接計算）重新求解，
並與 JSON 中的 answer 比對。修改或新增題目後務必重新執行：

    python3 eval/verify_answers.py
"""
import heapq
import itertools
import json
import math
from fractions import Fraction
from pathlib import Path

import numpy as np

Q = json.loads((Path(__file__).parent / "questions.json").read_text(encoding="utf-8"))
items = {q["id"]: q for s in Q["sets"].values() for q in s}


# ---------- easy ----------
def e1():
    for x in range(4, 5000, 4):
        r = x - x // 4
        if r % 3 == 0 and r - r // 3 - 45 == 105:
            return x


def e2():
    return sum(1 for i in range(1, 1001) if i % 3 and i % 5 and i % 7)


def e3():
    tot = [(a, b) for a in range(1, 7) for b in range(1, 7) if 6 in (a, b)]
    return str(Fraction(sum(1 for p in tot if sum(p) >= 10), len(tot)))


def e4():
    sols = []
    for liar in "甲乙丙":
        lie = {p: p == liar for p in "甲乙丙"}
        says = {"甲": lie["乙"], "乙": not lie["丙"], "丙": not lie["丙"]}
        if all(says[p] != lie[p] for p in "甲乙丙"):
            sols.append(liar)
    assert len(sols) == 1
    return sols[0]


def ref_compress(s):
    out, i = [], 0
    while i < len(s):
        j = i
        while j < len(s) and s[j] == s[i]:
            j += 1
        out.append(s[i] + (str(j - i) if j - i > 1 else ""))
        i = j
    c = "".join(out)
    return c if len(c) < len(s) else s


def e6():
    x = 0
    for i in range(1, 21):
        if i % 3 == 0 or i % 5 == 0:
            x ^= i
    return x


def e8():
    bits = 10.5 * 2**30 * 8
    return round(bits / 150e6)


# ---------- hard ----------
def h1():
    pat = "HHTH"
    n = len(pat)

    def nxt(state, c):
        s = pat[:state] + c
        for k in range(min(len(s), n), -1, -1):
            if s.endswith(pat[:k]):
                return k

    A, b = np.zeros((n, n)), np.ones(n)
    for s in range(n):
        A[s, s] += 1
        for c in "HT":
            t = nxt(s, c)
            if t < n:
                A[s, t] -= 0.5
    return round(np.linalg.solve(A, b)[0])


def zeros(n):
    c, p = 0, 5
    while p <= n:
        c += n // p
        p *= 5
    return c


def h2(target=2028):
    exact = [n for n in range(1, 20000) if zeros(n) == target]
    if exact:
        return {"possible": True, "n": exact[0]}
    return {"possible": False, "n": next(n for n in range(1, 20000) if zeros(n) >= target)}


def h3():
    return sum(1 for t in itertools.permutations(range(10), 4) if t[0] != 0 and sum(t) == 15)


def h4():
    a = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5, 8, 9, 7, 9]
    L, C = [1] * len(a), [1] * len(a)
    for i in range(len(a)):
        for j in range(i):
            if a[j] < a[i]:
                if L[j] + 1 > L[i]:
                    L[i], C[i] = L[j] + 1, C[j]
                elif L[j] + 1 == L[i]:
                    C[i] += C[j]
    m = max(L)
    return {"length": m, "count": sum(c for l, c in zip(L, C) if l == m)}


def h5():
    people, majors, drinks = "甲乙丙丁", ["資工", "電機", "數學", "物理"], ["咖啡", "茶", "牛奶", "果汁"]
    sols = []
    for P in itertools.permutations(people):
        for M in itertools.permutations(majors):
            for D in itertools.permutations(drinks):
                seat = {p: i for i, p in enumerate(P)}
                mj = dict(zip(P, M))
                dr = dict(zip(P, D))
                sm = {m: i for i, m in enumerate(M)}
                sd = {d: i for i, d in enumerate(D)}
                ok = (
                    abs(seat["甲"] - sm["資工"]) == 1
                    and sd["牛奶"] == sm["數學"] + 1
                    and mj["乙"] != "物理" and dr["乙"] != "咖啡"
                    and seat["丙"] in (0, 3)
                    and D[0] != "茶"
                    and sm["電機"] < seat["丁"]
                    and dr["丙"] == "果汁"
                    and abs(sd["咖啡"] - sd["茶"]) == 1
                    and mj["丁"] != "資工"
                    and sm["物理"] == 3
                    and D[sm["數學"]] != "果汁"
                    and seat["乙"] > seat["甲"]
                )
                if ok:
                    sols.append((P, M, D))
    assert len(sols) == 1, f"解不唯一：{len(sols)}"
    P, M, D = sols[0]
    k = M.index("數學")
    return {"person": P[k], "drink": D[k]}


def h6():
    E = [("A", "B", 4), ("A", "C", 2), ("B", "C", 1), ("B", "D", 5), ("C", "D", 8), ("C", "E", 10),
         ("D", "E", 2), ("D", "F", 6), ("E", "F", 2), ("E", "G", 5), ("F", "G", 3), ("F", "H", 7),
         ("G", "H", 1), ("B", "E", 8)]
    G = {}
    for u, v, w in E:
        G.setdefault(u, []).append((v, w))
        G.setdefault(v, []).append((u, w))
    dist = {k: math.inf for k in G}
    cnt = {k: 0 for k in G}
    dist["A"], cnt["A"] = 0, 1
    pq = [(0, "A")]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for v, w in G[u]:
            if d + w < dist[v]:
                dist[v], cnt[v] = d + w, cnt[u]
                heapq.heappush(pq, (dist[v], v))
            elif d + w == dist[v]:
                cnt[v] += cnt[u]
    return {"distance": dist["H"], "count": cnt["H"]}


def h7():
    return round(80 * math.log2(1 + 10 ** (20 / 10)))


def ref_evaluate(s):
    s = s.replace(" ", "")
    i = 0

    def tdiv(a, b):
        q = abs(a) // abs(b)
        return q if (a >= 0) == (b > 0) else -q

    def expr():
        nonlocal i
        v = term()
        while i < len(s) and s[i] in "+-":
            op = s[i]
            i += 1
            t = term()
            v = v + t if op == "+" else v - t
        return v

    def term():
        nonlocal i
        v = fac()
        while i < len(s) and s[i] in "*/":
            op = s[i]
            i += 1
            f = fac()
            v = v * f if op == "*" else tdiv(v, f)
        return v

    def fac():
        nonlocal i
        if s[i] == "-":
            i += 1
            return -fac()
        if s[i] == "(":
            i += 1
            v = expr()
            i += 1
            return v
        j = i
        while i < len(s) and s[i].isdigit():
            i += 1
        return int(s[j:i])

    return expr()


def check_tests(qid, fn):
    for t in items[qid]["tests"]:
        got = fn(*t["input"])
        assert got == t["expected"], f"{qid} 測資 {t['input']}：參考解 {got!r} ≠ 標準 {t['expected']!r}"
    return "ok"


checks = {
    "E1": e1, "E2": e2, "E3": e3, "E4": e4, "E6": e6, "E8": e8,
    "H1": h1, "H2": h2, "H3": h3, "H4": h4, "H5": h5, "H6": h6, "H7": h7,
}

failed = 0
for qid, f in checks.items():
    got, want = f(), items[qid]["answer"]
    status = "OK " if got == want else "FAIL"
    failed += status == "FAIL"
    print(f"[{status}] {qid}: computed={got!r} answer={want!r}")

for qid, fn in [("E5", ref_compress), ("H8", ref_evaluate)]:
    try:
        print(f"[OK ] {qid}: 所有測資與參考解一致 ({check_tests(qid, fn)})")
    except AssertionError as e:
        failed += 1
        print(f"[FAIL] {e}")

e7 = items["E7"]["answer"]
assert e7 == {"date": "10/09", "time": "14:30", "room": "E305", "attendees": 12 + 2, "rsvp_deadline": "10/07"}
print("[OK ] E7: 欄位與原文一致（人工規則檢查）")

print("\n全部通過" if not failed else f"\n{failed} 題不一致")
raise SystemExit(1 if failed else 0)
