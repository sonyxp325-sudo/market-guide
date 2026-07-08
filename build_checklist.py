#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_checklist.py  —  Phase 1
watchlist.json(입력) + pykrx/yfinance(데이터) -> checklist.output.json(B카드 출력)

자동화 범위(Phase 1):
  - 가격/OHLC: KR=pykrx, US=yfinance
  - 환율: yfinance KRW=X
  - 기술적 지표: ta 라이브러리로 직접 계산(RSI, SMA50, SMA200) -> 소스 불일치 없음
  - 수급(KR): pykrx 투자자별 순매수(외국인/기관) 최근 추세
  - 매크로: 지수(KOSPI/NASDAQ) 일간 등락
  - 삼성형 custom_signals(진정 체크리스트) 자동 판정
  - 확신도 = 신호 일치도 × 데이터 신뢰도

아직 사람/LLM 몫(Phase 4에서 교체):
  - reason 서술은 지금은 규칙 기반 템플릿. narrate()에서 Claude/Gemini API로 교체 예정.
  - 펀더멘털 심층 판단(논리 훼손 여부 등)은 valuation 숫자 표시까지만.
"""

import json, sys, datetime as dt
from pathlib import Path

import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator

WATCHLIST = Path(__file__).with_name("watchlist.json")
OUTPUT    = Path(__file__).with_name("checklist.output.json")

KOSPI_CODE, KOSDAQ_CODE, NASDAQ_TK = "1001", "2001", "^IXIC"

# ---------------------------------------------------------------- helpers
def _daterange(days_back=400):
    today = dt.date.today()
    start = today - dt.timedelta(days=days_back)
    return start.strftime("%Y%m%d"), today.strftime("%Y%m%d")

def rsi_sma(close: pd.Series):
    """close 시리즈에서 RSI(14), SMA50, SMA200을 계산."""
    out = {}
    try:
        out["rsi"] = round(float(RSIIndicator(close, 14).rsi().iloc[-1]), 1)
    except Exception:
        out["rsi"] = None
    for w in (50, 200):
        try:
            out[f"sma{w}"] = round(float(SMAIndicator(close, w).sma_indicator().iloc[-1]), 2)
        except Exception:
            out[f"sma{w}"] = None
    return out

# ---------------------------------------------------------------- KR (pykrx)
def kr_ohlcv(ticker):
    from pykrx import stock
    f, t = _daterange()
    df = stock.get_market_ohlcv(f, t, ticker)          # 컬럼: 시가 고가 저가 종가 거래량
    df = df.rename(columns={"시가": "open", "고가": "high", "저가": "low",
                            "종가": "close", "거래량": "volume"})
    return df

def kr_index(code):
    from pykrx import stock
    f, t = _daterange(days_back=15)
    return stock.get_index_ohlcv(f, t, code).rename(columns={"종가": "close"})

def kr_foreign_flow(ticker, ndays=5):
    """최근 ndays 외국인/기관 순매수(값). 반환: [(date, 외국인, 기관), ...] 최신 마지막."""
    from pykrx import stock
    f, t = _daterange(days_back=20)
    # detail=True -> 투자자 유형별 컬럼(외국인, 기관합계 등)
    df = stock.get_market_trading_value_by_date(f, t, ticker, detail=True)
    rows = []
    for idx, r in df.tail(ndays).iterrows():
        foreign = float(r.get("외국인", r.get("외국인합계", 0)) or 0)
        inst    = float(r.get("기관합계", r.get("기관", 0)) or 0)
        rows.append((str(idx.date() if hasattr(idx, "date") else idx), foreign, inst))
    return rows

# ---------------------------------------------------------------- US (yfinance)
def us_history(ticker, period="1y"):
    import yfinance as yf
    df = yf.Ticker(ticker).history(period=period, auto_adjust=False)
    df = df.rename(columns=str.lower)   # open high low close volume
    return df

def us_info(ticker):
    import yfinance as yf
    try:
        info = yf.Ticker(ticker).info
    except Exception:
        info = {}
    return {
        "trailing_pe": info.get("trailingPE"),
        "forward_pe":  info.get("forwardPE"),
        "ps":          info.get("priceToSalesTrailing12Months"),
    }

def fx_usdkrw():
    import yfinance as yf
    try:
        h = yf.Ticker("KRW=X").history(period="5d")
        return round(float(h["Close"].iloc[-1]), 2)
    except Exception:
        return None

# ---------------------------------------------------------------- layer eval
def eval_technical(tech):
    rsi = tech.get("rsi")
    if rsi is None:
        return "🟡", "지표 계산 불가"
    if rsi < 30:  return "🟢", f"RSI {rsi} 과매도권"
    if rsi > 70:  return "🔴", f"RSI {rsi} 과매수권"
    return "🟡", f"RSI {rsi} 중립"

def eval_supply_demand(market, flow):
    if market != "KR" or not flow:
        return "🟡", "수급데이터 제한(미국) 또는 없음"
    f_today = flow[-1][1]
    f_prev  = flow[-2][1] if len(flow) > 1 else 0
    if f_today > 0:
        return "🟢", "외국인 순매수 전환"
    # 순매도지만 강도 완화?
    if f_prev < 0 and f_today > f_prev:
        return "🟡", "외국인 순매도 강도 완화"
    return "🔴", "외국인 순매도 지속"

def eval_macro(market, idx_chg):
    if idx_chg is None:
        return "🟡", "지수 데이터 없음"
    name = "코스피" if market == "KR" else "나스닥"
    if idx_chg <= -3:  return "🔴", f"{name} {idx_chg:+.1f}% 리스크오프"
    if idx_chg >= 0:   return "🟢", f"{name} {idx_chg:+.1f}% 안정"
    return "🟡", f"{name} {idx_chg:+.1f}% 약세"

def eval_fundamental(h):
    # Phase 1: 밸류 숫자만 표시. 심층 판단은 Phase 3/4.
    parts = []
    if h.get("forward_pe"):   parts.append(f"선행PER {h['forward_pe']:.1f}")
    if h.get("trailing_pe"):  parts.append(f"PER {h['trailing_pe']:.1f}")
    if h.get("ps"):           parts.append(f"P/S {h['ps']:.1f}")
    return "🟡", (", ".join(parts) if parts else "밸류 데이터 없음")

# ---------------------------------------------------------------- 삼성형 진정 체크리스트
def eval_custom_signals(spec, ctx):
    """ctx: dict with foreign_today, foreign_prev, inst_today, index_chg, close_chg, near_high"""
    items = []
    # 1 외국인 순매도 감소/전환
    ok1 = ctx["foreign_today"] > ctx["foreign_prev"]
    items.append(("외국인 순매도 감소/전환", ok1))
    # 2 코스피 플러스 또는 아래꼬리
    ok2 = (ctx["index_chg"] is not None and ctx["index_chg"] > 0) or ctx["near_high"]
    items.append(("코스피 플러스/아래꼬리", ok2))
    # 3 종가 반등
    ok3 = ctx["close_chg"] is not None and ctx["close_chg"] > 0
    items.append(("종가 반등/바닥 다지기", ok3))
    # 4 서킷브레이커 없는 날 (지수 -8% 미도달)
    ok4 = ctx["index_chg"] is None or ctx["index_chg"] > -8
    items.append(("서킷브레이커 없는 날", ok4))
    # 5 외국인·기관 매수 가세
    ok5 = ctx["foreign_today"] > 0 and ctx["inst_today"] > 0
    items.append(("외국인·기관 매수 가세", ok5))
    improved = sum(1 for _, ok in items if ok)
    return {
        "name": spec.get("name", "custom_signals"),
        "rule": spec.get("rule", ""),
        "score": f"{improved}/{len(items)}",
        "verdict": "집행 검토" if improved >= 2 else "관망",
        "items": [{"label": l, "ok": ok} for l, ok in items],
    }

# ---------------------------------------------------------------- confidence
def confidence(lights, data_reliability):
    greens = sum(1 for l in lights if l == "🟢")
    reds   = sum(1 for l in lights if l == "🔴")
    n = len(lights)
    if greens >= max(3, n - 1):     align = "상"
    elif greens >= 2 and reds <= 1: align = "중"
    else:                           align = "하"
    # 데이터 신뢰도가 낮으면 한 단계 강등
    if data_reliability == "low" and align != "하":
        align = {"상": "중", "중": "하"}[align]
    return align

# ---------------------------------------------------------------- reason (Phase1 템플릿 / Phase4 LLM)
def narrate(name, layer_notes, valuation_note):
    """지금은 규칙 기반. Phase 4에서 이 함수 내부를 Claude/Gemini API 호출로 교체."""
    fors, cautions = [], []
    for layer, (light, note) in layer_notes.items():
        if light == "🟢": fors.append(note)
        elif light == "🔴": cautions.append(note)
    if valuation_note: cautions.append(valuation_note)
    return {"for": fors or ["뚜렷한 매수 우위 신호 없음"],
            "caution": cautions or ["특이 리스크 신호 없음"]}

# ---------------------------------------------------------------- per-holding
def process(h, fx, macro_kr_chg, macro_us_chg):
    market = h["market"]
    card = {"ticker": h["ticker"], "name": h.get("name", h["ticker"]),
            "strategy": h.get("strategy", "core")}
    layers, tech, price, close_chg, near_high = {}, {}, None, None, False
    flow = []

    try:
        if market == "KR":
            df = kr_ohlcv(h["ticker"])
            close = df["close"].astype(float)
            tech = rsi_sma(close)
            price = float(close.iloc[-1])
            close_chg = (price / float(close.iloc[-2]) - 1) * 100 if len(close) > 1 else None
            last = df.iloc[-1]
            rng = float(last["high"]) - float(last["low"])
            near_high = rng > 0 and (price - float(last["low"])) / rng > 0.6
            flow = kr_foreign_flow(h["ticker"])
            data_rel = "high"       # 장마감 확정
            price_status = "종가(pykrx)"
        else:  # US
            df = us_history(h["ticker"])
            close = df["close"].astype(float)
            tech = rsi_sma(close)
            price = float(close.iloc[-1])
            close_chg = (price / float(close.iloc[-2]) - 1) * 100 if len(close) > 1 else None
            data_rel = "mid"        # yfinance ~15분 지연
            price_status = "yfinance(~15분 지연)"
    except Exception as e:
        card["error"] = f"데이터 수집 실패: {e}"
        return card

    # 4개 층
    layers["technical"]     = eval_technical(tech)
    layers["supply_demand"] = eval_supply_demand(market, flow)
    layers["macro"]         = eval_macro(market, macro_kr_chg if market == "KR" else macro_us_chg)
    layers["fundamental"]   = eval_fundamental(us_info(h["ticker"]) if market == "US" else {})

    lights = [v[0] for v in layers.values()]
    conf = confidence(lights, data_rel)

    # custom signals (삼성 진정 체크리스트 등)
    custom = None
    if "custom_signals" in h and market == "KR" and flow:
        ctx = {
            "foreign_today": flow[-1][1],
            "foreign_prev":  flow[-2][1] if len(flow) > 1 else 0,
            "inst_today":    flow[-1][2],
            "index_chg":     macro_kr_chg,
            "close_chg":     close_chg,
            "near_high":     near_high,
        }
        custom = eval_custom_signals(h["custom_signals"], ctx)

    reason = narrate(card["name"], layers, h.get("valuation_note"))

    # 신호등 헤드라인 결정 (단순 규칙)
    if custom:
        signal = "🟢" if custom["verdict"] == "집행 검토" else "🟡"
        headline = f"{h['custom_signals'].get('name','')} {custom['score']} · {custom['verdict']}"
    else:
        greens = lights.count("🟢")
        signal = "🟢" if greens >= 3 else ("🟡" if greens >= 1 else "⚪")
        headline = h.get("entry_trigger", "보유")[:40]

    card.update({
        "signal": signal,
        "headline": headline,
        "price": {"value": round(price, 2),
                  "currency": "KRW" if market == "KR" else "USD",
                  "status": price_status},
        "confidence": {"level": conf, "data_reliability": data_rel},
        "technical": tech,
        "reason": reason,
        "layers": {k: {"light": v[0], "note": v[1]} for k, v in layers.items()},
    })
    if custom: card["custom_signals"] = custom
    # 논리 필드 통과(있으면)
    for k in ("thesis", "entry_trigger", "thesis_break_signal", "valuation_note"):
        if h.get(k): card[k] = h[k]
    return card

# ---------------------------------------------------------------- main
def index_change(df):
    try:
        c = df["close"].astype(float)
        return round((float(c.iloc[-1]) / float(c.iloc[-2]) - 1) * 100, 2)
    except Exception:
        return None

def main():
    wl = json.loads(WATCHLIST.read_text(encoding="utf-8"))
    fx = fx_usdkrw()

    # 매크로 지수
    try: kr_chg = index_change(kr_index(KOSPI_CODE))
    except Exception: kr_chg = None
    try: us_chg = index_change(us_history(NASDAQ_TK, period="5d"))
    except Exception: us_chg = None

    cards = []
    for h in wl.get("holdings", []):
        # 스키마 예시용 메타키 스킵
        h = {k: v for k, v in h.items() if not k.startswith("_")}
        if not h.get("ticker"):
            continue
        cards.append(process(h, fx, kr_chg, us_chg))

    # 포트폴리오 합계
    total, invested = 0.0, 0.0
    cash = wl.get("meta", {}).get("cash_krw", 0)
    for c, h in zip(cards, wl.get("holdings", [])):
        pos = h.get("position")
        if not pos or "value" not in c.get("price", {}):
            continue
        px = c["price"]["value"]
        val = px * pos["shares"]
        if pos.get("currency") == "USD" and fx:
            val *= fx
        invested += val
    total = invested + cash

    out = {
        "date": dt.date.today().strftime("%Y-%m-%d"),
        "fx": {"usdkrw": fx, "source": "yfinance", "delay": "~15min"},
        "macro": {"kospi_chg_pct": kr_chg, "nasdaq_chg_pct": us_chg},
        "portfolio": {
            "invested_krw": round(invested),
            "cash_krw": cash,
            "total_krw": round(total),
            "cash_pct": round(cash / total * 100, 1) if total else None,
        },
        "brief": [{"ticker": c["ticker"], "signal": c.get("signal", "⚪"),
                   "line": c.get("headline", "")} for c in cards],
        "cards": cards,
        "_disclaimer": "확신도는 규칙 부합도이지 수익 보장 아님. 정밀 실시간가는 MTS 화면과 대조.",
    }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ {OUTPUT.name} 생성 · 종목 {len(cards)}개 · 환율 {fx}")

if __name__ == "__main__":
    main()
