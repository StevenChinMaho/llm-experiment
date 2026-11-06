"""產生並獨立驗證 E5（計算工具）題目的標準答案。

每題都用與評估腳本無關的精確計算（整數、Fraction、高精度 Decimal）求解。
需要四捨五入的題目，另外確認答案離 .5 夠遠，避免捨入方式造成歧義。

    python3 eval/verify_e5.py          # 驗證 eval/e5_questions.json
    python3 eval/verify_e5.py --write  # 把計算結果寫回 JSON 的 answer 欄位
"""
import json
import math
import sys
from decimal import Decimal, getcontext
from fractions import Fraction
from pathlib import Path

getcontext().prec = 80
PATH = Path(__file__).parent / "e5_questions.json"


def round_checked(x):
    """四捨五入到整數；離 .5 太近就報錯（代表題目該換數字）。"""
    x = Fraction(x)
    frac = x - math.floor(x)
    assert abs(frac - Fraction(1, 2)) > Fraction(1, 100), f"{float(x)} 太接近 .5"
    return math.floor(x + Fraction(1, 2))


def d2f(d):
    return Fraction(d)


def t1():  # 240 Mbps 傳 23.7 GiB
    return round_checked(Fraction(237, 10) * 2**30 * 8 / (240 * 10**6))


def t2():  # Shannon：160 MHz、27 dB
    snr = Decimal(10) ** Decimal("2.7")
    cap = Decimal(160) * (1 + snr).ln() / Decimal(2).ln()
    return round_checked(d2f(cap))


def t3():  # 未壓縮影片大小（GiB）
    bits = 3840 * 2160 * 30 * 60 * 97 * 60
    return round_checked(Fraction(bits, 8 * 2**30))


def t4():  # 複利
    return round_checked(1234567 * Fraction(10375, 10000) ** 17)


def t5():
    return 987654321 * 123456789


def t6():  # 平方和，用迴圈直接加總，不用公式
    return sum(i * i for i in range(1, 98766))


def t7():  # 用重複平方的自寫版本，不靠內建 pow 三參數
    r, b, e, m = 1, 7, 12345, 1000003
    while e:
        if e & 1:
            r = r * b % m
        b = b * b % m
        e >>= 1
    return r


def t8():  # C(60,25)，用 Pascal 三角形
    row = [1]
    for _ in range(60):
        row = [1] + [row[i] + row[i + 1] for i in range(len(row) - 1)] + [1]
    return row[25]


def t9():
    r = 1
    for _ in range(23):
        r *= 17
    return r


def t10():
    return int("DEADBEEF", 16) * int("CAFEBABE", 16)


def t11():  # BDP 換算成封包數，無條件進位
    bdp_bytes = Fraction(25, 10) * 10**9 * Fraction(734, 10000) / 8
    return math.ceil(bdp_bytes / 1460)


def t12():  # 本息平均攤還每月付款
    r = Fraction(2185, 100000) / 12
    q = (1 + r) ** 360
    return round_checked(8450000 * r * q / (q - 1))


SOLVERS = {f"T{i}": f for i, f in enumerate((t1, t2, t3, t4, t5, t6, t7, t8, t9, t10, t11, t12), 1)}


def main():
    data = json.loads(PATH.read_text(encoding="utf-8"))
    bad = 0
    for q in data["questions"]:
        got = SOLVERS[q["id"]]()
        if "--write" in sys.argv:
            q["answer"] = got
        ok = q.get("answer") == got
        bad += not ok
        print(f"{'OK ' if ok else 'BAD'} {q['id']:4s} {got}")
    assert len(data["questions"]) == len(SOLVERS)
    if "--write" in sys.argv:
        PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        print("已寫回", PATH)
    print("全部相符" if not bad else f"{bad} 題不符")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
