"""
시장 과열도 데이터 수집 스크립트
매일 한국시간 22:00에 GitHub Actions가 실행
"""
import json
import sys
from datetime import datetime, timezone, timedelta
import yfinance as yf

KST = timezone(timedelta(hours=9))


def safe_float(value, default=None):
    """None/NaN 안전 처리"""
    try:
        if value is None:
            return default
        f = float(value)
        if f != f:  # NaN
            return default
        return f
    except (TypeError, ValueError):
        return default


def fetch_vix():
    """VIX 변동성 지수"""
    try:
        ticker = yf.Ticker("^VIX")
        hist = ticker.history(period="5d")
        if hist.empty:
            return None
        return safe_float(hist["Close"].iloc[-1])
    except Exception as e:
        print(f"[VIX] 실패: {e}", file=sys.stderr)
        return None


def fetch_sp500():
    """S&P 500 현재가 + 200일 이평선 + 52주 고저"""
    try:
        ticker = yf.Ticker("^GSPC")
        # 1년치 일봉 받아서 200일선 계산
        hist = ticker.history(period="1y")
        if hist.empty or len(hist) < 200:
            return None

        current = safe_float(hist["Close"].iloc[-1])
        ma200 = safe_float(hist["Close"].tail(200).mean())
        high52 = safe_float(hist["High"].max())
        low52 = safe_float(hist["Low"].min())

        if current is None or ma200 is None:
            return None

        ma_pct = ((current - ma200) / ma200) * 100

        return {
            "price": round(current, 2),
            "ma200": round(ma200, 2),
            "ma_pct": round(ma_pct, 2),
            "high52": round(high52, 2) if high52 else None,
            "low52": round(low52, 2) if low52 else None,
        }
    except Exception as e:
        print(f"[S&P 500] 실패: {e}", file=sys.stderr)
        return None


def fetch_sp500_per():
    """
    S&P 500 PER - SPY ETF의 trailingPE 사용
    실패 시 대형주 5종목 평균으로 fallback
    """
    # 시도 1: SPY ETF
    try:
        spy = yf.Ticker("SPY")
        info = spy.info
        pe = safe_float(info.get("trailingPE"))
        if pe and 5 < pe < 100:  # 합리적 범위 검증
            return {"value": round(pe, 2), "source": "SPY"}
    except Exception as e:
        print(f"[PER:SPY] 실패: {e}", file=sys.stderr)

    # 시도 2: VOO ETF
    try:
        voo = yf.Ticker("VOO")
        info = voo.info
        pe = safe_float(info.get("trailingPE"))
        if pe and 5 < pe < 100:
            return {"value": round(pe, 2), "source": "VOO"}
    except Exception as e:
        print(f"[PER:VOO] 실패: {e}", file=sys.stderr)

    # 시도 3: 대형주 5종목 평균
    try:
        tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
        pes = []
        for t in tickers:
            try:
                info = yf.Ticker(t).info
                pe = safe_float(info.get("trailingPE"))
                if pe and 5 < pe < 200:
                    pes.append(pe)
            except Exception:
                continue
        if len(pes) >= 3:
            avg = sum(pes) / len(pes)
            return {"value": round(avg, 2), "source": f"대형주 평균 ({len(pes)}종목)"}
    except Exception as e:
        print(f"[PER:fallback] 실패: {e}", file=sys.stderr)

    return None


# ===== 점수 계산 =====
def score_vix(v):
    if v is None:
        return None
    if v <= 12:
        return 100
    if v >= 35:
        return 0
    return round(100 - ((v - 12) / 23) * 100)


def score_per(v):
    if v is None:
        return None
    if v <= 12:
        return 0
    if v >= 30:
        return 100
    return round(((v - 12) / 18) * 100)


def score_ma(pct):
    if pct is None:
        return None
    if pct <= -10:
        return 0
    if pct >= 15:
        return 100
    return round(((pct + 10) / 25) * 100)


def compute_total(scores):
    """가중평균. None인 항목은 제외하고 비례 재분배"""
    weights = {"fgi": 0.35, "vix": 0.25, "per": 0.25, "ma": 0.15}
    sum_w, sum_s = 0, 0
    for key, w in weights.items():
        s = scores.get(key)
        if s is not None:
            sum_w += w
            sum_s += s * w
    if sum_w == 0:
        return None
    return round(sum_s / sum_w)


def stage_from_score(s):
    if s is None:
        return None
    if s < 25:
        return "fear"
    if s < 50:
        return "neutral"
    if s < 75:
        return "greed"
    return "extreme"


def main():
    print(f"=== 데이터 수집 시작: {datetime.now(KST).isoformat()} ===")

    # 1. 원시 데이터 수집
    vix = fetch_vix()
    sp500 = fetch_sp500()
    per = fetch_sp500_per()

    print(f"VIX: {vix}")
    print(f"S&P 500: {sp500}")
    print(f"PER: {per}")

    # 2. 점수 계산
    vix_score = score_vix(vix)
    ma_score = score_ma(sp500["ma_pct"]) if sp500 else None
    per_score = score_per(per["value"]) if per else None

    # FGI는 VIX + 추세 합성
    fgi_score = None
    fgi_source = None
    if vix_score is not None and ma_score is not None:
        fgi_score = round((vix_score + ma_score) / 2)
        fgi_source = "VIX + 추세 합성"
    elif vix_score is not None:
        fgi_score = vix_score
        fgi_source = "VIX 단독"
    elif ma_score is not None:
        fgi_score = ma_score
        fgi_source = "추세 단독"

    scores = {"fgi": fgi_score, "vix": vix_score, "per": per_score, "ma": ma_score}
    total = compute_total(scores)
    stage = stage_from_score(total)

    print(f"점수 - FGI:{fgi_score} VIX:{vix_score} PER:{per_score} MA:{ma_score}")
    print(f"종합: {total} ({stage})")

    # 3. 결과 저장
    now = datetime.now(KST)
    result = {
        "updated_at": now.isoformat(),
        "updated_date": now.strftime("%Y-%m-%d"),
        "updated_time_kst": now.strftime("%Y-%m-%d %H:%M KST"),
        "total_score": total,
        "stage": stage,
        "components": {
            "fgi": {
                "value": fgi_score,
                "score": fgi_score,
                "source": fgi_source,
                "display": f"{fgi_score} (추정)" if fgi_score else None,
            },
            "vix": {
                "value": vix,
                "score": vix_score,
                "source": "Yahoo Finance ^VIX",
                "display": f"{vix:.2f}" if vix else None,
            },
            "per": {
                "value": per["value"] if per else None,
                "score": per_score,
                "source": per["source"] if per else None,
                "display": f"{per['value']:.1f}" if per else None,
            },
            "ma": {
                "value": sp500["ma_pct"] if sp500 else None,
                "score": ma_score,
                "source": "Yahoo Finance ^GSPC 200일선",
                "display": (
                    f"{'+' if sp500['ma_pct'] >= 0 else ''}{sp500['ma_pct']:.1f}%"
                    if sp500
                    else None
                ),
                "extra": {
                    "price": sp500["price"] if sp500 else None,
                    "ma200": sp500["ma200"] if sp500 else None,
                },
            },
        },
    }

    with open("data/market.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 히스토리 누적 (최근 90일)
    history_path = "data/history.json"
    try:
        with open(history_path, "r", encoding="utf-8") as f:
            history = json.load(f)
    except FileNotFoundError:
        history = []

    today_key = now.strftime("%Y-%m-%d")
    # 오늘 기록 있으면 덮어쓰기
    history = [h for h in history if h["date"] != today_key]
    history.append(
        {
            "date": today_key,
            "score": total,
            "stage": stage,
            "timestamp": now.isoformat(),
        }
    )
    history = sorted(history, key=lambda x: x["date"])[-90:]

    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    print(f"=== 완료. 종합 점수: {total} ({stage}) ===")
    return 0 if total is not None else 1


if __name__ == "__main__":
    sys.exit(main())
