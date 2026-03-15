"""Korean-language Streamlit dashboard for the trading AI system scaffold."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import math

from trading_ai_system.dashboard.context_builder import build_context_from_histories
from trading_ai_system.dashboard.forecast_chart import (
    build_actual_price_chart,
    build_projection_bundle,
    build_forecast_chart,
    build_trade_review_chart,
)
from trading_ai_system.dashboard.state_manager import (
    build_selection_key,
    ensure_session_defaults,
    reset_symbol_scoped_state,
)
from trading_ai_system.dashboard.tradingview_chart import render_tradingview_chart
from trading_ai_system.data.loaders import MarketDataService, ResolvedTicker, UnifiedSymbolResolver
from trading_ai_system.data.schemas.market import MarketContext, ModelProbabilities, TimeframeState
from trading_ai_system.models.predictor import FinalPrediction, run_pipeline
from trading_ai_system.portfolio.balance_manager import BalanceManager
from trading_ai_system.simulation.trade_simulator import (
    TradeInput,
    simulate_trade,
    summarize_trade_results,
)

ACTION_LABELS = {
    "STRONG_LONG": "강한 상승 시나리오",
    "WEAK_LONG": "약한 상승 시나리오",
    "NEUTRAL": "중립 / 관망",
    "WEAK_SHORT": "약한 하락 시나리오",
    "STRONG_SHORT": "강한 하락 시나리오",
    "NO_TRADE": "진입 보류",
}

거래소_라벨 = {
    "자동": "AUTO",
    "바이낸스": "BINANCE",
    "업비트": "UPBIT",
    "나스닥": "NASDAQ",
    "뉴욕증권거래소": "NYSE",
    "한국거래소": "KRX",
}

분석모드_라벨 = {
    "실시간": "realtime",
    "과거분석": "historical",
    "백테스트": "backtest",
}

이벤트리스크_라벨 = {
    "보통": "normal",
    "높음": "high",
    "극단적": "extreme",
}

자산분류_표시 = {
    "crypto": "가상자산",
    "kr_stock": "한국 주식",
    "us_stock": "미국 주식",
}

거래소_표시 = {
    "BINANCE": "바이낸스",
    "UPBIT": "업비트",
    "NASDAQ": "나스닥",
    "NYSE": "뉴욕증권거래소",
    "AMEX": "아멕스",
    "KRX": "한국거래소",
    "AUTO": "자동",
}

CLASS_LABELS = {
    "up": "상승",
    "down": "하락",
    "side": "횡보",
}

CONFIDENCE_LABELS = {
    "HIGH": "높음",
    "MEDIUM": "보통",
    "LOW": "낮음",
}

ENTRY_DECISION_LABELS = {
    "allow_full": "본대 진입 허용",
    "allow_probe": "선발대만 허용",
    "reject": "진입 거부",
}

ENTRY_TYPE_LABELS = {
    "confirmed_breakout": "확인 돌파 진입",
    "pullback_entry": "눌림목 진입",
    "reversal_probe": "반전 탐색 진입",
    "none": "해당 없음",
}

DIRECTION_LABELS = {
    "long": "롱 관점",
    "short": "숏 관점",
    "neutral": "중립",
}

RISK_GRADE_LABELS = {
    "LOW": "낮음",
    "MEDIUM": "보통",
    "HIGH": "높음",
}

규칙_라벨 = {
    "stop_clear": "손절 기준 명확성",
    "no_chasing": "추격 진입 금지",
    "pattern_confirmed": "패턴 확인 후 진입",
    "fourth_touch_risk": "4번째 터치 위험 회피",
    "target_overlap_warning": "중첩 타겟 구간 경계",
    "higher_tf_priority": "상위 프레임 우선",
    "lower_tf_exit_priority": "하위 프레임 청산 우선",
    "split_execution": "분할 진입 / 분할 익절",
    "countertrend_probe_only": "역추세 선발대 제한",
    "one_candle_one_trade": "한 봉 한 번만 매매",
    "event_volatility_filter": "이벤트 변동성 필터",
    "reward_risk_floor": "기대수익비 최소 기준",
}

활성근거_라벨 = {
    "rsi14": "상대강도지수 14",
    "macd_line": "이동평균 수렴확산 선",
    "macd_signal": "신호선",
    "macd_histogram": "오실레이터 막대",
    "adx": "추세강도지수",
    "bb_width": "볼린저 밴드 폭",
    "atr14": "평균진폭",
    "vwap_distance": "거래량가중평균가 이격",
    "ema_20_50_spread": "지수이동평균 20-50 간격",
    "volume_to_ma20": "거래량 대비 20평균 비율",
    "consensus_score": "프레임 합의 점수",
    "stop_distance_ratio": "손절 거리 비율",
    "nearest_target_distance": "최근 목표가까지 거리",
    "higher_tf_trend_strength": "상위 프레임 추세 강도",
    "alignment_1d_4h": "일봉-4시간 정합",
    "alignment_4h_1h": "4시간-1시간 정합",
    "alignment_1h_15m": "1시간-15분 정합",
    "bullish_divergence_flag": "상승 다이버전스",
    "bearish_divergence_flag": "하락 다이버전스",
    "common_zone_hit_flag": "공통구간 도달",
    "fifth_wave_exhaustion_flag": "5파 소진 신호",
    "triangle_breakout_flag": "삼각수렴 돌파",
    "flag_pattern_confirmed": "플래그 패턴 확인",
    "split_entry_recommended_flag": "분할 진입 권장",
    "stop_is_clear_flag": "손절선 명확",
    "chasing_risk_flag": "추격 위험",
    "fourth_touch_break_risk_flag": "4번째 터치 붕괴 위험",
    "no_trade_flag": "진입 보류 신호",
}


@dataclass
class PriceLevel:
    label: str
    value: float
    reason: str


@dataclass
class TradeLevelSummary:
    supports: list[PriceLevel]
    resistances: list[PriceLevel]
    entries: list[PriceLevel]
    take_profits: list[PriceLevel]
    stop_loss: PriceLevel
    wave_label: str
    wave_note: str
    pattern_label: str
    pattern_note: str
    regime_note: str


@dataclass
class RecommendedTradePlan:
    allowed: bool
    side: str
    entry_price: float
    stop_loss: float
    target_price: float
    reward_risk_ratio: float
    quantity: float
    risk_amount: float
    target_profit_amount: float
    expected_value: float
    reason: str
    glenn_reasons: list[str]
    fee_rate: float = 0.0005
    leverage: float = 1.0


def _build_timeframe_state(timeframe: str, bias: float, confidence: float) -> TimeframeState:
    raw = bias * 12
    return TimeframeState(
        timeframe=timeframe,
        trend_score=raw * 0.35,
        momentum_score=raw * 0.18,
        volatility_score=raw * 0.08,
        volume_score=raw * 0.08,
        pattern_score=raw * 0.18,
        target_score=raw * 0.13,
        confidence=confidence,
        regime="trend" if abs(bias) > 0.35 else "transition",
        signals={
            "rsi14": 58 + bias * 18,
            "macd_line": bias * 1.2,
            "macd_signal": bias * 0.8,
            "macd_histogram": bias * 0.4,
            "adx": 18 + abs(bias) * 20,
            "volume_to_ma20": 1.0 + abs(bias) * 0.6,
            "bb_width": 0.04 + abs(bias) * 0.03,
            "atr14": 0.9 + abs(bias),
            "atr_close_ratio": 0.01 + abs(bias) * 0.015,
            "vwap_distance": bias * 0.02,
            "ema5": 101 + bias * 4,
            "ema20": 100 + bias * 2,
            "ema50": 99 + bias,
            "ema200": 95,
            "return_1_bar": bias * 0.01,
            "return_3_bar": bias * 0.015,
            "return_5_bar": bias * 0.02,
            "return_10_bar": bias * 0.03,
            "bullish_divergence_flag": bias > 0.45,
            "bearish_divergence_flag": bias < -0.45,
            "price_above_ema20_flag": bias > 0,
            "price_above_ema50_flag": bias > 0.1,
            "psar_trend_flag": bias > 0,
            "estimated_wave_stage": "impulse"
            if bias > 0.35
            else "corrective"
            if bias < -0.35
            else "transition",
            "impulse_candidate_flag": bias > 0.35,
            "corrective_candidate_flag": bias < -0.35,
            "fib_retracement_zone_class": "0.382~0.618",
            "fib_extension_zone_class": "1.618",
            "common_zone_hit_flag": abs(bias) > 0.18,
            "fifth_wave_exhaustion_flag": abs(bias) > 0.58,
            "flag_pattern_confirmed": abs(bias) > 0.28,
            "triangle_breakout_flag": abs(bias) > 0.33,
            "wedge_breakout_flag": abs(bias) > 0.42,
            "wave_two_retracement_ratio": 0.50 if abs(bias) > 0.2 else 0.68,
            "wave_three_extension_ratio": 1.618 if abs(bias) > 0.35 else 1.272,
            "wave_four_overlap_risk": abs(bias) < 0.18,
            "wave_five_extension_ratio": 1.618 if abs(bias) > 0.45 else 1.0,
            "triangle_e_undershoot_flag": abs(bias) < 0.22,
            "diagonal_candidate_flag": 0.18 < abs(bias) < 0.35,
            "wedge_volume_decline_flag": abs(bias) > 0.28,
            "flat_b_retracement_ratio": 0.82,
            "zigzag_b_retracement_ratio": 0.70,
            "wave_five_failure_risk": abs(bias) > 0.62,
        },
    )


def _build_context(
    *,
    symbol: str,
    asset_type: str,
    exchange: str,
    mode: str,
    higher_tf_bias: float,
    lower_tf_bias: float,
    breakout_confirmed: bool,
    retest_success: bool,
    stop_clear: bool,
    chasing_risk: bool,
    fourth_touch_risk: bool,
    overlap_zone: bool,
    countertrend: bool,
    event_risk: str,
    reward_risk_ratio: float,
    xgb_up: float,
    lstm_up: float,
    rf_up: float,
) -> MarketContext:
    xgb_down = max(0.0, 1 - xgb_up - 0.15)
    lstm_down = max(0.0, 1 - lstm_up - 0.20)
    rf_down = max(0.0, 1 - rf_up - 0.25)

    timeframes = {
        "1w": _build_timeframe_state("1w", higher_tf_bias, 0.95),
        "1d": _build_timeframe_state("1d", higher_tf_bias, 0.92),
        "4h": _build_timeframe_state("4h", (higher_tf_bias + lower_tf_bias) / 2, 0.88),
        "1h": _build_timeframe_state("1h", lower_tf_bias, 0.84),
        "30m": _build_timeframe_state("30m", lower_tf_bias * 0.9, 0.80),
        "15m": _build_timeframe_state("15m", lower_tf_bias * 0.85, 0.78),
        "1m": _build_timeframe_state("1m", lower_tf_bias * 0.65, 0.72),
    }

    for timeframe in ("4h", "1h", "15m"):
        state = timeframes[timeframe]
        state.signals.update(
            {
                "triangle_breakout_flag": breakout_confirmed,
                "flag_pattern_confirmed": breakout_confirmed,
                "common_zone_hit_flag": retest_success or overlap_zone,
                "fifth_wave_exhaustion_flag": fourth_touch_risk or abs(lower_tf_bias) > 0.55,
                "bullish_divergence_flag": lower_tf_bias > 0.45 and not countertrend,
                "bearish_divergence_flag": lower_tf_bias < -0.45 and not countertrend,
            }
        )

    return MarketContext(
        symbol=symbol,
        asset_type=asset_type,
        exchange=exchange,
        mode=mode,
        current_price=100.0,
        timeframes=timeframes,
        strategy_state={
            "breakout_confirmed_flag": breakout_confirmed,
            "pattern_confirmed": breakout_confirmed or retest_success,
            "confirmation_entry": breakout_confirmed or retest_success,
            "retest_success_flag": retest_success,
            "stop_is_clear": stop_clear,
            "stop_distance_ratio": 0.012 if stop_clear else 0.05,
            "chasing_risk": chasing_risk,
            "fourth_touch_break_risk": fourth_touch_risk,
            "sr_touch_count": 4 if fourth_touch_risk else 2,
            "overlapping_target_zone": overlap_zone,
            "caution_zone_flag": overlap_zone,
            "countertrend": countertrend,
            "event_volatility_risk": event_risk,
            "reward_risk_ratio": reward_risk_ratio,
            "lower_tf_exit_priority": True,
            "split_entry_recommended": True,
            "entry_signal_on_3m": breakout_confirmed,
            "entry_signal_on_5m": retest_success,
            "entry_signal_on_15m": higher_tf_bias > 0.2,
            "nearest_target_distance": 0.008 if overlap_zone else 0.025,
            "lower_tf_conflict_flag": higher_tf_bias * lower_tf_bias < 0,
            "target_reached_recently": fourth_touch_risk,
        },
        model_outputs={
            "xgboost": ModelProbabilities("xgboost", up=xgb_up, down=xgb_down, side=0.15),
            "lstm": ModelProbabilities("lstm", up=lstm_up, down=lstm_down, side=0.20),
            "random_forest": ModelProbabilities("random_forest", up=rf_up, down=rf_down, side=0.25),
        },
    )


def _format_probability(probability: float) -> str:
    return f"{probability * 100:.1f}%"


def _format_price(value: float) -> str:
    return f"{value:,.2f}"


def _market_price_unit(resolved) -> str:
    if getattr(resolved, "asset_class", "") == "crypto":
        return "USDT"
    if getattr(resolved, "exchange", "") == "KRX" or getattr(resolved, "asset_class", "") == "kr_stock":
        return "원"
    return "달러"


def _format_market_price(value: float, resolved) -> str:
    unit = _market_price_unit(resolved)
    if unit == "원":
        return f"{value:,.0f} {unit}"
    return f"{value:,.2f} {unit}"


def _label_for(value: str, mapping: dict[str, str]) -> str:
    return mapping.get(value, value)


def _화면문구(text: object) -> str:
    rendered = str(text)
    replacements = {
        "FOMO": "추격 심리",
        "TF": "프레임",
        "no-trade": "진입 보류",
        "No timeframe state available": "타임프레임 상태가 없습니다.",
        "Overlapping target zone detected": "중첩 타겟 구간이 감지되었습니다.",
        "Lower timeframe noise conflict detected": "하위 프레임 잡음 충돌이 감지되었습니다.",
        "Event volatility risk is elevated": "이벤트 변동성 경계 구간입니다.",
        "historical": "과거분석",
        "realtime": "실시간",
        "backtest": "백테스트",
        "crypto": "가상자산",
        "kr_stock": "한국 주식",
        "us_stock": "미국 주식",
        "BINANCE": "바이낸스",
        "UPBIT": "업비트",
        "NASDAQ": "나스닥",
        "NYSE": "뉴욕증권거래소",
        "KRX": "한국거래소",
        "AMEX": "아멕스",
        "live_stock": "실시간 주식 호가",
        "live_crypto": "실시간 가상자산 시세",
        "fallback": "최근 종가 대체값",
        "HIGH": "높음",
        "MEDIUM": "보통",
        "LOW": "낮음",
        "long": "롱 관점",
        "short": "숏 관점",
        "neutral": "중립",
    }
    for before, after in replacements.items():
        rendered = rendered.replace(before, after)
    return rendered


def _anchor_state(context: MarketContext) -> TimeframeState:
    for timeframe in ("1h", "4h", "1d", "15m", "30m", "1m", "1w"):
        state = context.timeframe(timeframe)
        if state is not None:
            return state
    raise ValueError("No timeframe state available")


def _direction_sign(prediction: FinalPrediction) -> int:
    if prediction.probabilities["up"] > prediction.probabilities["down"]:
        return 1
    if prediction.probabilities["down"] > prediction.probabilities["up"]:
        return -1
    return 0


def build_trade_levels(
    context: MarketContext,
    prediction: FinalPrediction,
) -> TradeLevelSummary:
    anchor = _anchor_state(context)
    price = float(context.current_price or 100.0)
    atr = max(anchor.get_float("atr14", 1.0), 0.5)
    direction = _direction_sign(prediction)
    impulse = anchor.get_bool("impulse_candidate_flag")
    corrective = anchor.get_bool("corrective_candidate_flag")
    overlap_zone = context.get_state_bool("overlapping_target_zone")
    breakout_confirmed = context.get_state_bool("breakout_confirmed_flag")
    retest_success = context.get_state_bool("retest_success_flag")
    fourth_touch = context.get_state_bool("fourth_touch_break_risk") or context.get_state_float("sr_touch_count") >= 4
    wave_two_ratio = anchor.get_float("wave_two_retracement_ratio", 0.5)
    wave_three_ratio = anchor.get_float("wave_three_extension_ratio", 1.618)
    wave_five_ratio = anchor.get_float("wave_five_extension_ratio", 1.0)
    flat_b_ratio = anchor.get_float("flat_b_retracement_ratio", 0.82)
    zigzag_b_ratio = anchor.get_float("zigzag_b_retracement_ratio", 0.70)
    primary_pullback = min(max(wave_two_ratio, 0.382), 0.786)
    confirm_pullback = min(max((wave_two_ratio + zigzag_b_ratio) / 2, 0.5), 0.786)
    structural_support_ratio = min(max(flat_b_ratio, 0.786), 1.0)
    terminal_target_ratio = max(wave_three_ratio + (wave_five_ratio * 0.618), 1.618)

    wave_label = "글렌닐리식 임펄스 진행 후보" if impulse else "글렌닐리식 조정 파동 후보" if corrective else "전이 구간 / 구조 재확인 필요"
    wave_note = (
        "임펄스에서는 2파 되돌림과 3파 확장 비율, 4파-1파 비중첩 여부를 우선 확인합니다."
        if impulse
        else "조정 파동은 ABC 또는 플랫·지그재그·삼각수렴 구조를 0.382~0.618, 0.786~0.88 비율로 검증합니다."
        if corrective
        else "상위 프레임 구조가 전이 구간이라 모노웨이브/세부 카운팅 재점검이 필요합니다."
    )
    pattern_label = "글렌닐리 구조 확인 완료" if breakout_confirmed and retest_success else "글렌닐리 구조 재확인 필요"
    pattern_note = (
        "다이아고날 예외가 아니라면 4파 중첩 없이 2파 되돌림과 3파 확장 비율이 먼저 맞아야 합니다."
        if breakout_confirmed and retest_success
        else "선진입보다 0.382~0.618 되돌림 반응, 4파 중첩 회피, E파 미도달 여부를 먼저 확인합니다."
    )
    regime_note = (
        "중첩 구간이라면 카운팅은 맞아도 진입보다 경계가 우선입니다."
        if overlap_zone
        else "4번째 터치 위험이 있으면 정상 임펄스보다 다이아고날 또는 붕괴 가능성을 더 경계해야 합니다."
        if fourth_touch
        else "상위 구조와 하위 되돌림이 함께 맞아 떨어질 때만 진입을 검토합니다."
    )

    if direction >= 0:
        entry_core = price - atr * (primary_pullback if impulse else 0.382)
        entry_confirm = price - atr * (confirm_pullback if impulse else 0.5)
        stop_value = price - atr * (structural_support_ratio + 0.236)
        support_values = [
            price - atr * primary_pullback,
            price - atr * structural_support_ratio,
            price - atr * (structural_support_ratio + 0.382),
        ]
        resistance_values = [
            price + atr * 1.0,
            price + atr * wave_three_ratio,
            price + atr * terminal_target_ratio,
        ]
        take_profit_values = [
            price + atr * (1.0 if corrective else 1.272),
            price + atr * wave_three_ratio,
            price + atr * terminal_target_ratio,
        ]
    else:
        entry_core = price + atr * (primary_pullback if impulse else 0.382)
        entry_confirm = price + atr * (confirm_pullback if impulse else 0.5)
        stop_value = price + atr * (structural_support_ratio + 0.236)
        support_values = [
            price - atr * 1.0,
            price - atr * wave_three_ratio,
            price - atr * terminal_target_ratio,
        ]
        resistance_values = [
            price + atr * primary_pullback,
            price + atr * structural_support_ratio,
            price + atr * (structural_support_ratio + 0.382),
        ]
        take_profit_values = [
            price - atr * (1.0 if corrective else 1.272),
            price - atr * wave_three_ratio,
            price - atr * terminal_target_ratio,
        ]

    supports = [
        PriceLevel("지지 1", support_values[0], "최근 스윙 기준 1차 방어 구간"),
        PriceLevel("지지 2", support_values[1], "0.382~0.618 공통구간과 겹칠 가능성이 높은 2차 지지"),
        PriceLevel("지지 3", support_values[2], "구조 붕괴 전 마지막 방어선"),
    ]
    resistances = [
        PriceLevel("저항 1", resistance_values[0], "단기 채널 상단/하단 첫 반응 구간"),
        PriceLevel("저항 2", resistance_values[1], "1.618 확장 또는 되돌림 목표 구간"),
        PriceLevel("저항 3", resistance_values[2], "추세 연장 시 최종 확인 저항"),
    ]
    entries = [
        PriceLevel("진입 대기 1", entry_core, "0.382 되돌림 또는 리테스트 대기"),
        PriceLevel("진입 대기 2", entry_confirm, "0.618 공통구간 + 확인 진입 우선"),
    ]
    take_profits = [
        PriceLevel("익절 1", take_profit_values[0], "1차 반익 구간"),
        PriceLevel("익절 2", take_profit_values[1], "1.618 확장 목표"),
        PriceLevel("익절 3", take_profit_values[2], "추세 연장 시 최종 목표"),
    ]
    stop_loss = PriceLevel(
        "손절 기준",
        stop_value,
        "구조 무효화 지점. 손절이 짧고 명확할 때만 진입",
    )

    return TradeLevelSummary(
        supports=supports,
        resistances=resistances,
        entries=entries,
        take_profits=take_profits,
        stop_loss=stop_loss,
        wave_label=wave_label,
        wave_note=wave_note,
        pattern_label=pattern_label,
        pattern_note=pattern_note,
        regime_note=regime_note,
    )


def _level_rows(levels: list[PriceLevel], resolved) -> list[dict[str, str]]:
    return [
        {
            "구분": level.label,
            "가격": _format_market_price(level.value, resolved),
            "근거": level.reason,
        }
        for level in levels
    ]


def _build_chart(context: MarketContext, prediction: FinalPrediction, level_summary: TradeLevelSummary):
    import plotly.graph_objects as go

    anchor = _anchor_state(context)
    price = float(context.current_price or 100.0)
    atr = max(anchor.get_float("atr14", 1.0), 0.5)
    bias = prediction.mtf_summary.composite_score
    now = datetime.now()

    timestamps: list[datetime] = []
    opens: list[float] = []
    highs: list[float] = []
    lows: list[float] = []
    closes: list[float] = []

    previous_close = price - bias * atr * 12
    for idx in range(72):
        timestamps.append(now - timedelta(hours=71 - idx))
        drift = bias * atr * 0.09
        cycle = math.sin(idx / 6) * atr * 0.45 + math.sin(idx / 13) * atr * 0.22
        close = previous_close + drift + cycle * 0.18
        open_price = previous_close + math.sin(idx / 4) * atr * 0.08
        high = max(open_price, close) + abs(math.cos(idx / 5)) * atr * 0.28
        low = min(open_price, close) - abs(math.sin(idx / 5)) * atr * 0.28
        opens.append(open_price)
        highs.append(high)
        lows.append(low)
        closes.append(close)
        previous_close = close

    shift = price - closes[-1]
    opens = [value + shift for value in opens]
    highs = [value + shift for value in highs]
    lows = [value + shift for value in lows]
    closes = [value + shift for value in closes]

    fig = go.Figure(
        data=[
            go.Candlestick(
                x=timestamps,
                open=opens,
                high=highs,
                low=lows,
                close=closes,
                name="가격",
                increasing_line_color="#0ea5e9",
                decreasing_line_color="#ef4444",
            )
        ]
    )

    fig.add_scatter(
        x=timestamps,
        y=[sum(closes[max(0, idx - 4) : idx + 1]) / len(closes[max(0, idx - 4) : idx + 1]) for idx in range(len(closes))],
        mode="lines",
        name="지수이동평균 5",
        line={"color": "#22c55e", "width": 1.5},
    )
    fig.add_scatter(
        x=timestamps,
        y=[sum(closes[max(0, idx - 19) : idx + 1]) / len(closes[max(0, idx - 19) : idx + 1]) for idx in range(len(closes))],
        mode="lines",
        name="지수이동평균 20",
        line={"color": "#f59e0b", "width": 1.5},
    )

    color_map = {
        "지지": "#10b981",
        "저항": "#ef4444",
        "진입": "#2563eb",
        "익절": "#a855f7",
        "손절": "#f97316",
    }

    for level in level_summary.supports:
        fig.add_hline(y=level.value, line_dash="dot", line_color=color_map["지지"], opacity=0.7)
    for level in level_summary.resistances:
        fig.add_hline(y=level.value, line_dash="dot", line_color=color_map["저항"], opacity=0.7)
    for level in level_summary.entries:
        fig.add_hline(y=level.value, line_dash="dash", line_color=color_map["진입"], opacity=0.85)
    for level in level_summary.take_profits:
        fig.add_hline(y=level.value, line_dash="dash", line_color=color_map["익절"], opacity=0.85)
    fig.add_hline(y=level_summary.stop_loss.value, line_dash="solid", line_color=color_map["손절"], opacity=0.9)

    annotations = (
        level_summary.supports[:1]
        + level_summary.resistances[:1]
        + level_summary.entries
        + level_summary.take_profits[:2]
        + [level_summary.stop_loss]
    )
    for level in annotations:
        fig.add_annotation(
            x=timestamps[-1],
            y=level.value,
            text=f"{level.label} {_format_price(level.value)}",
            showarrow=False,
            xanchor="left",
            bgcolor="rgba(15, 23, 42, 0.85)",
            font={"color": "#e5e7eb", "size": 11},
        )

    fig.update_layout(
        title="예상 차트 시나리오와 핵심 가격 레벨",
        xaxis_title="시간",
        yaxis_title="가격",
        template="plotly_dark",
        height=620,
        margin={"l": 20, "r": 20, "t": 60, "b": 20},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0},
    )
    fig.update_xaxes(rangeslider_visible=False)
    return fig


def _translated_entry_plan(prediction: FinalPrediction) -> dict[str, object]:
    단계_라벨 = {
        "probe": "선발대",
        "reserve": "대기 물량",
        "starter": "초기 진입",
        "main": "본대 진입",
        "add": "추가 진입",
    }
    return {
        "진입 판단": _label_for(prediction.entry_plan.decision, ENTRY_DECISION_LABELS),
        "방향": _label_for(prediction.entry_plan.direction, DIRECTION_LABELS),
        "진입 타입": _label_for(prediction.entry_plan.entry_type, ENTRY_TYPE_LABELS),
        "근거": [_화면문구(reason) for reason in prediction.entry_plan.reasons],
        "분할 진입 계획": [
            {
                "단계": 단계_라벨.get(str(item.get("stage")), str(item.get("stage"))),
                "비중": item.get("ratio"),
                "조건": _화면문구(item.get("trigger")),
            }
            for item in prediction.entry_plan.split_entry_plan
        ],
    }


def _translated_exit_risk(prediction: FinalPrediction) -> dict[str, object]:
    손절정책 = prediction.exit_plan.stop_loss_policy
    return {
        "리스크 등급": _label_for(prediction.risk_assessment.risk_grade, RISK_GRADE_LABELS),
        "리스크 포인트": prediction.risk_assessment.risk_points,
        "손절 정책": {
            "방향": _label_for(str(손절정책.get("direction", "")), DIRECTION_LABELS),
            "기준선": 손절정책.get("anchor"),
            "손절 거리 비율": 손절정책.get("stop_distance_ratio"),
            "시간 손절 기준 봉 수": 손절정책.get("time_stop_bars"),
            "구조 손절": 손절정책.get("structural_exit"),
        },
        "익절 계획": [
            {
                "단계": {"TP1": "1차 익절", "TP2": "2차 익절", "TP3": "3차 익절", "TP4": "4차 익절"}.get(str(item.get("level")), str(item.get("level"))),
                "비중": item.get("ratio"),
                "근거": _화면문구(item.get("reason")),
            }
            for item in prediction.exit_plan.take_profit_plan
        ],
        "경고": [_화면문구(item) for item in prediction.risk_assessment.warnings + prediction.exit_plan.warnings],
    }


def _neely_setting_rows(context: MarketContext) -> list[dict[str, str]]:
    anchor = _anchor_state(context)
    wave_stage = str(anchor.signals.get("estimated_wave_stage", "transition"))
    wave_stage_label = {
        "impulse": "임펄스 진행형",
        "corrective": "조정 진행형",
        "transition": "전이 / 카운팅 재확인",
    }.get(wave_stage, "전이 / 카운팅 재확인")

    rows = [
        {
            "세부 항목": "파동 단계",
            "현재 설정": wave_stage_label,
            "글렌닐리 기준": "임펄스 / 조정 / 전이 구간을 분리해 해석",
        },
        {
            "세부 항목": "2파 되돌림",
            "현재 설정": f"{anchor.get_float('wave_two_retracement_ratio'):.3f}",
            "글렌닐리 기준": "1파 100% 되돌림 금지, 일반적으로 0.382~0.618 우선",
        },
        {
            "세부 항목": "3파 확장",
            "현재 설정": f"{anchor.get_float('wave_three_extension_ratio'):.3f}",
            "글렌닐리 기준": "3파는 가장 짧지 않으며 1.618~2.618 확장 우선 확인",
        },
        {
            "세부 항목": "4파 중첩 위험",
            "현재 설정": "주의" if anchor.get_bool("wave_four_overlap_risk") else "양호",
            "글렌닐리 기준": "4파와 1파 중첩은 다이아고날 예외로만 허용",
        },
        {
            "세부 항목": "5파 연장 / 소진",
            "현재 설정": (
                f"확장 {anchor.get_float('wave_five_extension_ratio'):.3f}, "
                + ("소진 경고" if anchor.get_bool("wave_five_failure_risk") else "정상")
            ),
            "글렌닐리 기준": "5파는 1.0 또는 1.618 목표, 과확장 시 절단과 소진도 함께 점검",
        },
        {
            "세부 항목": "지그재그 B 되돌림",
            "현재 설정": f"{anchor.get_float('zigzag_b_retracement_ratio'):.3f}",
            "글렌닐리 기준": "B파는 주로 A파의 0.618~0.786 범위",
        },
        {
            "세부 항목": "플랫 B 되돌림",
            "현재 설정": f"{anchor.get_float('flat_b_retracement_ratio'):.3f}",
            "글렌닐리 기준": "레귤러 플랫 B는 0.786~0.88, 익스팬디드 플랫은 더 깊어질 수 있음",
        },
        {
            "세부 항목": "삼각수렴 E파",
            "현재 설정": "미도달 가능성 큼" if anchor.get_bool("triangle_e_undershoot_flag") else "일반 전개",
            "글렌닐리 기준": "E파가 추세선에 닿지 못하고 끝나는 경우를 우선 경계",
        },
        {
            "세부 항목": "다이아고날 후보",
            "현재 설정": "후보" if anchor.get_bool("diagonal_candidate_flag") else "낮음",
            "글렌닐리 기준": "리딩/엔딩 다이아고날은 1-4 중첩과 추세선 수렴 여부를 같이 점검",
        },
        {
            "세부 항목": "웻지 거래량",
            "현재 설정": "감소형" if anchor.get_bool("wedge_volume_decline_flag") else "불명확",
            "글렌닐리 기준": "웻지는 거래량 감소, 다이아고날은 거래량이 들쑥날쑥한 경우가 많음",
        },
    ]
    return rows


def _translated_rule_rows(prediction: FinalPrediction) -> list[dict[str, object]]:
    return [
        {
            "규칙": 규칙_라벨.get(result.name, result.name),
            "통과": "예" if result.passed else "아니오",
            "영향도": round(result.score_impact, 2),
            "사유": _화면문구(result.reason or ""),
        }
        for result in prediction.rule_outcome.results
    ]


def _translated_active_reasons(prediction: FinalPrediction) -> list[str]:
    translated: list[str] = []
    for feature_name in prediction.features.active_features:
        label = 활성근거_라벨.get(feature_name)
        if label and label not in translated:
            translated.append(label)
    return translated[:20]


def _format_datetime(value: object) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    rendered = str(value)
    if "T" in rendered:
        return rendered.replace("T", " ")[:16]
    return rendered


def _currency_price(value: float, currency: str) -> str:
    return f"{value:,.2f} {currency}"


def _resolved_rows(resolved) -> list[dict[str, str]]:
    return [
        {"항목": "입력값", "내용": _화면문구(resolved.raw_input)},
        {"항목": "표시 이름", "내용": _화면문구(resolved.display_name)},
        {"항목": "자산 분류", "내용": 자산분류_표시.get(resolved.asset_class, resolved.asset_class)},
        {"항목": "거래소", "내용": 거래소_표시.get(resolved.exchange, resolved.exchange)},
        {"항목": "가격 단위", "내용": _market_price_unit(resolved)},
        {"항목": "내부 심볼", "내용": _화면문구(resolved.canonical_symbol)},
        {"항목": "트레이딩뷰 심볼", "내용": _화면문구(resolved.tradingview_symbol)},
    ]


def _portfolio_rows(snapshot) -> list[dict[str, str]]:
    return [
        {"항목": "초기 잔고", "내용": _currency_price(snapshot.initial_balance, snapshot.currency)},
        {"항목": "현재 잔고", "내용": _currency_price(snapshot.cash_balance, snapshot.currency)},
        {"항목": "가용 자금", "내용": _currency_price(snapshot.available_balance, snapshot.currency)},
        {"항목": "사용 중 자금", "내용": _currency_price(snapshot.used_margin, snapshot.currency)},
        {"항목": "누적 실현손익", "내용": _currency_price(snapshot.realized_pnl, snapshot.currency)},
        {"항목": "평가손익", "내용": _currency_price(snapshot.unrealized_pnl, snapshot.currency)},
        {"항목": "총자산", "내용": _currency_price(snapshot.total_equity, snapshot.currency)},
        {"항목": "누적 거래 수", "내용": str(snapshot.trade_count)},
        {"항목": "승률", "내용": f"{snapshot.win_rate * 100:.1f}%"},
    ]


def _trade_result_rows(result, currency: str) -> list[dict[str, str]]:
    return [
        {"항목": "진입 시각", "내용": _format_datetime(result.entry_time)},
        {"항목": "청산 시각", "내용": _format_datetime(result.exit_time)},
        {"항목": "방향", "내용": "롱" if result.side == "long" else "숏"},
        {"항목": "수량", "내용": f"{result.quantity:,.6f}"},
        {"항목": "총 손익", "내용": _currency_price(result.gross_pnl, currency)},
        {"항목": "수수료", "내용": _currency_price(result.fee_paid, currency)},
        {"항목": "실손익", "내용": _currency_price(result.net_pnl, currency)},
        {"항목": "손익률", "내용": f"{result.return_pct * 100:.2f}%"},
        {"항목": "최대 유리 변동", "내용": f"{result.mfe_pct * 100:.2f}%"},
        {"항목": "최대 불리 변동", "내용": f"{result.mae_pct * 100:.2f}%"},
        {"항목": "청산 사유", "내용": _화면문구(result.exit_reason)},
    ]


def _trade_history_rows(trade_results: list[object], current_symbol: str, currency: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for result in trade_results:
        if getattr(result, "symbol", None) != current_symbol:
            continue
        rows.append(
            {
                "진입": _format_datetime(result.entry_time),
                "청산": _format_datetime(result.exit_time),
                "방향": "롱" if result.side == "long" else "숏",
                "실손익": _currency_price(result.net_pnl, currency),
                "손익률": f"{result.return_pct * 100:.2f}%",
                "사유": _화면문구(result.exit_reason),
            }
        )
    return rows


def _safe_value(value: float, default: float) -> float:
    try:
        if value != value:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _primary_neely_state(context: MarketContext) -> TimeframeState:
    return context.timeframe("1h") or context.timeframe("4h") or _anchor_state(context)


def _glenn_entry_reasons(context: MarketContext) -> list[str]:
    anchor = _primary_neely_state(context)
    reasons: list[str] = []
    wave_stage = str(anchor.signals.get("estimated_wave_stage", "transition"))
    wave_two = anchor.get_float("wave_two_retracement_ratio", 0.0)
    wave_three = anchor.get_float("wave_three_extension_ratio", 0.0)
    if wave_stage == "impulse" and 0.382 <= wave_two <= 0.618:
        reasons.append("2파 되돌림이 0.382~0.618 선호 구간에 들어왔습니다.")
    if wave_stage == "corrective" and 0.62 <= anchor.get_float("zigzag_b_retracement_ratio", 0.0) <= 0.82:
        reasons.append("조정 B파 비율이 지그재그 기준 범위에 있습니다.")
    if wave_three >= 1.618:
        reasons.append("3파 확장 비율이 1.618 이상으로 구조 지속 조건에 가깝습니다.")
    if not anchor.get_bool("wave_four_overlap_risk"):
        reasons.append("4파와 1파 중첩 위험이 낮아 일반 임펄스 해석에 유리합니다.")
    if anchor.get_bool("triangle_e_undershoot_flag"):
        reasons.append("E파 미도달 가능성이 있어 삼각수렴 종결 시나리오를 경계합니다.")
    if anchor.get_bool("diagonal_candidate_flag"):
        reasons.append("다이아고날 후보라면 중첩 예외 구조로만 접근해야 합니다.")
    if anchor.get_bool("common_zone_hit_flag"):
        reasons.append("공통구간 반응이 나와 비율 기반 진입 대기 조건이 맞춰졌습니다.")
    return reasons[:4]


def _glenn_reason_groups(
    context: MarketContext,
    prediction: FinalPrediction,
    trade_plan: RecommendedTradePlan,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    anchor = _primary_neely_state(context)
    bullish: list[dict[str, object]] = []
    bearish: list[dict[str, object]] = []
    wave_stage = str(anchor.signals.get("estimated_wave_stage", "transition"))
    wave_two = anchor.get_float("wave_two_retracement_ratio", 0.0)
    wave_three = anchor.get_float("wave_three_extension_ratio", 0.0)
    flat_b = anchor.get_float("flat_b_retracement_ratio", 0.0)
    zigzag_b = anchor.get_float("zigzag_b_retracement_ratio", 0.0)

    if wave_stage == "impulse":
        bullish.append({"title": "임펄스 유지", "detail": "상위 구조가 임펄스로 유지되고 있습니다.", "weight": 0.96})
    else:
        bearish.append({"title": "전이 / 조정 구조", "detail": "임펄스 지속보다 조정 또는 전이 구조 가능성이 큽니다.", "weight": 0.90})

    if 0.382 <= wave_two <= 0.618:
        bullish.append({"title": "2파 비율 적합", "detail": "2파 되돌림이 0.382~0.618 선호 구간에 있습니다.", "weight": 0.94})
    elif wave_two > 0.618:
        bearish.append({"title": "2파 과심화", "detail": "2파 되돌림이 깊어 구조 재확인이 필요합니다.", "weight": 0.88})

    if wave_three >= 1.618:
        bullish.append({"title": "3파 확장 확인", "detail": "3파 확장 비율이 1.618 이상입니다.", "weight": 0.92})
    else:
        bearish.append({"title": "3파 확장 부족", "detail": "3파가 충분히 확장되지 않아 추세 지속 근거가 약합니다.", "weight": 0.82})

    if not anchor.get_bool("wave_four_overlap_risk"):
        bullish.append({"title": "4파 중첩 회피", "detail": "4파와 1파 중첩 위험이 낮습니다.", "weight": 0.89})
    else:
        bearish.append({"title": "4파 중첩 경고", "detail": "4파-1파 중첩 위험이 커서 일반 임펄스 해석이 약해집니다.", "weight": 0.95})

    if anchor.get_bool("common_zone_hit_flag"):
        bullish.append({"title": "공통구간 반응", "detail": "공통구간 반응이 나와 비율 기반 진입 대기 조건이 맞춰졌습니다.", "weight": 0.84})
    else:
        bearish.append({"title": "공통구간 미확인", "detail": "공통구간 반응이 확인되지 않아 진입 타점 신뢰도가 낮습니다.", "weight": 0.78})

    if anchor.get_bool("diagonal_candidate_flag"):
        bearish.append({"title": "다이아고날 후보", "detail": "중첩 예외 구조일 수 있어 정상 추세보다 보수적으로 봐야 합니다.", "weight": 0.87})

    if anchor.get_bool("triangle_e_undershoot_flag"):
        bearish.append({"title": "E파 미도달 경고", "detail": "삼각수렴 종결 과정에서 미도달 가능성이 있습니다.", "weight": 0.83})

    if anchor.get_bool("wave_five_failure_risk"):
        bearish.append({"title": "5파 실패 위험", "detail": "5파 소진 또는 절단 가능성이 커 추세 마무리 리스크가 있습니다.", "weight": 0.86})

    if wave_stage == "corrective" and 0.62 <= zigzag_b <= 0.82:
        bullish.append({"title": "지그재그 B 비율", "detail": "조정 B파 비율이 지그재그 기준 범위에 있습니다.", "weight": 0.78})
    if wave_stage == "corrective" and 0.78 <= flat_b <= 0.98:
        bullish.append({"title": "플랫 B 비율", "detail": "플랫 B파 되돌림이 글렌닐리 기준 범위에 있습니다.", "weight": 0.76})

    if not trade_plan.allowed:
        bearish.append({"title": "진입 제외", "detail": trade_plan.reason, "weight": 0.97})

    if prediction.predicted_class == "down":
        bearish.append({"title": "하락 우세", "detail": "예측 확률이 하락 쪽으로 기울어 있습니다.", "weight": 0.80})
    elif prediction.predicted_class == "up":
        bullish.append({"title": "상승 우세", "detail": "예측 확률이 상승 쪽으로 기울어 있습니다.", "weight": 0.80})

    bullish = sorted(bullish, key=lambda item: float(item["weight"]), reverse=True)[:3]
    bearish = sorted(bearish, key=lambda item: float(item["weight"]), reverse=True)[:3]
    return bullish, bearish


def _render_reason_cards(st, title: str, items: list[dict[str, object]], *, tone: str) -> None:
    accent = "#16a34a" if tone == "bull" else "#dc2626"
    background = "rgba(22,163,74,0.12)" if tone == "bull" else "rgba(220,38,38,0.12)"
    border = "rgba(22,163,74,0.35)" if tone == "bull" else "rgba(220,38,38,0.35)"
    st.markdown(f"**{title}**")
    if not items:
        st.caption("현재 두드러진 근거가 없습니다.")
        return
    for item in items:
        st.markdown(
            f"""
            <div style="
                background:{background};
                border:1px solid {border};
                border-left:6px solid {accent};
                padding:12px 14px;
                border-radius:12px;
                margin-bottom:10px;
            ">
              <div style="font-weight:700; color:{accent}; margin-bottom:4px;">{item['title']}</div>
              <div style="font-size:13px; line-height:1.45;">{item['detail']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _build_recommended_trade_plan(
    context: MarketContext,
    prediction: FinalPrediction,
    level_summary: TradeLevelSummary,
    *,
    account_equity: float,
    min_reward_risk: float = 2.0,
    fee_rate: float = 0.0005,
    leverage: float = 1.0,
) -> RecommendedTradePlan:
    glenn_reasons = _glenn_entry_reasons(context)
    if prediction.final_action in {"NO_TRADE", "NEUTRAL"}:
        return RecommendedTradePlan(
            allowed=False,
            side="중립",
            entry_price=0.0,
            stop_loss=0.0,
            target_price=0.0,
            reward_risk_ratio=0.0,
            quantity=0.0,
            risk_amount=0.0,
            target_profit_amount=0.0,
            expected_value=0.0,
            reason="현재 구조는 진입보다 관망이 우선입니다.",
            glenn_reasons=glenn_reasons,
            fee_rate=fee_rate,
            leverage=leverage,
        )

    is_long = prediction.predicted_class == "up"
    entry_level = min(level_summary.entries, key=lambda item: abs(item.value - float(context.current_price or 0.0)))
    stop_level = level_summary.stop_loss
    candidates = [
        level
        for level in level_summary.take_profits
        if (level.value > entry_level.value if is_long else level.value < entry_level.value)
    ]

    chosen_target = None
    chosen_rr = 0.0
    risk_per_unit = abs(entry_level.value - stop_level.value)
    if risk_per_unit <= 0:
        return RecommendedTradePlan(
            allowed=False,
            side="롱" if is_long else "숏",
            entry_price=entry_level.value,
            stop_loss=stop_level.value,
            target_price=0.0,
            reward_risk_ratio=0.0,
            quantity=0.0,
            risk_amount=0.0,
            target_profit_amount=0.0,
            expected_value=0.0,
            reason="손절 기준과 진입가가 겹쳐 시뮬레이션이 불가능합니다.",
            glenn_reasons=glenn_reasons,
            fee_rate=fee_rate,
            leverage=leverage,
        )

    for candidate in candidates:
        reward_per_unit = abs(candidate.value - entry_level.value)
        fee_cost_per_unit = (entry_level.value + candidate.value + stop_level.value) * fee_rate
        reward_risk_ratio = max((reward_per_unit - fee_cost_per_unit), 0.0) / (risk_per_unit + fee_cost_per_unit)
        if reward_risk_ratio >= min_reward_risk:
            chosen_target = candidate
            chosen_rr = reward_risk_ratio
            break

    if chosen_target is None:
        return RecommendedTradePlan(
            allowed=False,
            side="롱" if is_long else "숏",
            entry_price=entry_level.value,
            stop_loss=stop_level.value,
            target_price=0.0,
            reward_risk_ratio=chosen_rr,
            quantity=0.0,
            risk_amount=0.0,
            target_profit_amount=0.0,
            expected_value=0.0,
            reason="손익비 2:1 이상이 나오는 목표가가 없어 진입 제외입니다.",
            glenn_reasons=glenn_reasons,
            fee_rate=fee_rate,
            leverage=leverage,
        )

    risk_capital = max(account_equity, 0.0) * 0.01
    raw_quantity = risk_capital / risk_per_unit
    max_notional = max(account_equity, 0.0) * max(leverage, 1.0)
    quantity = raw_quantity
    if max_notional > 0:
        quantity = min(raw_quantity, max_notional / entry_level.value)

    risk_amount = quantity * risk_per_unit
    target_profit_amount = quantity * abs(chosen_target.value - entry_level.value)
    direction_probability = prediction.probabilities["up"] if is_long else prediction.probabilities["down"]
    adverse_probability = prediction.probabilities["down"] if is_long else prediction.probabilities["up"]
    expected_value = (direction_probability * target_profit_amount) - (adverse_probability * risk_amount)

    if len(glenn_reasons) < 2:
        return RecommendedTradePlan(
            allowed=False,
            side="롱" if is_long else "숏",
            entry_price=entry_level.value,
            stop_loss=stop_level.value,
            target_price=chosen_target.value,
            reward_risk_ratio=chosen_rr,
            quantity=quantity,
            risk_amount=risk_amount,
            target_profit_amount=target_profit_amount,
            expected_value=expected_value,
            reason="글렌닐리 구조 근거가 부족해 자동 진입 시뮬레이션을 보류합니다.",
            glenn_reasons=glenn_reasons,
            fee_rate=fee_rate,
            leverage=leverage,
        )

    return RecommendedTradePlan(
        allowed=True,
        side="롱" if is_long else "숏",
        entry_price=entry_level.value,
        stop_loss=stop_level.value,
        target_price=chosen_target.value,
        reward_risk_ratio=chosen_rr,
        quantity=quantity,
        risk_amount=risk_amount,
        target_profit_amount=target_profit_amount,
        expected_value=expected_value,
        reason="글렌닐리 구조 근거와 손익비 2:1 조건을 통과했습니다.",
        glenn_reasons=glenn_reasons,
        fee_rate=fee_rate,
        leverage=leverage,
    )


def _find_fill_slice(frame, entry_price: float):
    for index, row in frame.iterrows():
        if float(row["low"]) <= entry_price <= float(row["high"]):
            return frame.iloc[index:].copy()
    return None


def _simulate_projection_scenarios(plan: RecommendedTradePlan, projection_bundle):
    scenario_results: list[dict[str, object]] = []
    if not plan.allowed:
        return scenario_results

    for scenario_name, frame in projection_bundle["frames"].items():
        fill_slice = _find_fill_slice(frame, plan.entry_price)
        if fill_slice is None or fill_slice.empty:
            scenario_results.append(
                {
                    "시나리오": scenario_name,
                    "체결": "대기",
                    "손익": 0.0,
                    "손익률": 0.0,
                    "사유": "진입가 미도달",
                    "result": None,
                    "frame": frame,
                }
            )
            continue
        trade_input = TradeInput(
            symbol="projection",
            side="long" if plan.side == "롱" else "short",
            entry_time=fill_slice.iloc[0]["timestamp"],
            entry_price=plan.entry_price,
            quantity=plan.quantity,
            stop_loss=plan.stop_loss,
            take_profit=plan.target_price,
            exit_time=fill_slice.iloc[-1]["timestamp"],
            exit_price=float(fill_slice.iloc[-1]["close"]),
            fee_rate=plan.fee_rate,
            leverage=plan.leverage,
        )
        result = simulate_trade(trade_input, fill_slice)
        scenario_results.append(
            {
                "시나리오": scenario_name,
                "체결": "진입",
                "손익": result.net_pnl,
                "손익률": result.return_pct,
                "사유": result.exit_reason,
                "result": result,
                "frame": fill_slice,
            }
        )
    return scenario_results


def main() -> None:
    try:
        import streamlit as st
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("streamlit is required to run the dashboard") from exc

    st.set_page_config(page_title="트레이딩 AI 분석기", layout="wide")
    st.title("트레이딩 AI 분석기")
    st.caption("티커 변경 즉시 반영, 실제 차트와 예상 차트 분리, 사용자 지정 매매 시뮬레이션, 잔고 연동을 한 화면에서 다루는 대시보드")

    ensure_session_defaults(st)

    @st.cache_resource
    def _resolver_resource():
        import os

        return UnifiedSymbolResolver(krx_map_path=os.getenv("KRX_SYMBOL_MAP_PATH"))

    @st.cache_resource
    def _data_service_resource():
        return MarketDataService()

    @st.cache_data(ttl=120, show_spinner=False)
    def _load_histories_cached(resolved_payload: dict[str, object], mode: str, timeframes: tuple[str, ...], limit: int):
        resolved_obj = ResolvedTicker(**resolved_payload)
        service = _data_service_resource()
        return service.load_multi_timeframe_history(
            resolved_obj,
            timeframes=list(timeframes),
            limit=limit,
            mode=mode,
        )

    @st.cache_data(ttl=5, show_spinner=False)
    def _load_latest_quote_cached(resolved_payload: dict[str, object], refresh_nonce: int):
        resolved_obj = ResolvedTicker(**resolved_payload)
        service = _data_service_resource()
        fallback = service.load_history(resolved_obj, timeframe="1m", limit=5, mode="realtime")
        return service.load_latest_quote(resolved_obj, fallback_frame=fallback)

    with st.sidebar:
        st.subheader("종목 선택")
        query = st.text_input("종목명 또는 티커", value="BTCUSDT")
        preferred_exchange_label = st.selectbox("시장 우선순위", options=list(거래소_라벨.keys()), index=0)
        mode_label = st.selectbox("분석 모드", options=list(분석모드_라벨.keys()), index=0)
        analysis_timeframe = st.selectbox("기준 프레임", options=["15m", "1h", "4h", "1d"], index=1)
        lookback_bars = st.slider("불러올 봉 수", min_value=160, max_value=720, value=320, step=40)

        st.subheader("잔고 설정")
        initial_balance = st.number_input("초기 잔고", min_value=0.0, value=1000000.0, step=10000.0)
        balance_currency = st.text_input("잔고 통화", value="KRW")
        reset_balance = st.button("잔고 초기화", use_container_width=True)
        refresh_quote = st.button("현재가 새로고침", use_container_width=True)

    if refresh_quote:
        st.session_state.quote_refresh_nonce = int(st.session_state.get("quote_refresh_nonce", 0)) + 1

    manager = BalanceManager.from_state(
        st.session_state.portfolio_state,
        initial_balance=initial_balance,
        currency=balance_currency,
    )
    if st.session_state.portfolio_state is None or reset_balance:
        manager.reset(initial_balance=initial_balance, currency=balance_currency)
        st.session_state.portfolio_state = manager.state
        st.session_state.trade_results = []
    snapshot = manager.snapshot()

    resolver = _resolver_resource()
    preferred_exchange = 거래소_라벨[preferred_exchange_label]
    try:
        resolved = resolver.resolve(
            query,
            preferred_exchange=None if preferred_exchange == "AUTO" else preferred_exchange,
        )
    except ValueError as exc:
        st.error(str(exc))
        return

    selection_key = build_selection_key(
        resolved,
        mode=분석모드_라벨[mode_label],
        analysis_timeframe=analysis_timeframe,
    )
    reset_symbol_scoped_state(st, selection_key)
    st.session_state.resolved_ticker = resolved

    required_timeframes = ("1m", "15m", "30m", "1h", "4h", "1d", "1w")
    try:
        histories = _load_histories_cached(
            resolved.as_dict(),
            분석모드_라벨[mode_label],
            required_timeframes,
            lookback_bars,
        )
    except Exception as exc:  # pragma: no cover
        st.error(f"시세 데이터를 불러오지 못했습니다: {exc}")
        return

    try:
        context = build_context_from_histories(
            resolved,
            histories,
            mode=분석모드_라벨[mode_label],
            account_equity=snapshot.total_equity,
        )
        latest_quote = _load_latest_quote_cached(
            resolved.as_dict(),
            int(st.session_state.get("quote_refresh_nonce", 0)),
        )
        if latest_quote:
            context.current_price = float(latest_quote.get("price") or context.current_price or 0.0)
            context.timestamp = str(latest_quote.get("timestamp") or context.timestamp or "")
            context.strategy_state["current_price"] = context.current_price
            context.strategy_state["quote_source"] = str(latest_quote.get("source") or "")
        prediction = run_pipeline(context)
        level_summary = build_trade_levels(context, prediction)
    except Exception as exc:
        st.error(f"분석 파이프라인 계산에 실패했습니다: {exc}")
        return

    st.session_state.analysis_context = context
    st.session_state.analysis_prediction = prediction
    st.session_state.analysis_levels = level_summary
    st.session_state.history_frames = histories

    history_frame = histories.get(analysis_timeframe)
    if history_frame is None:
        history_frame = histories.get("1h")
    price_unit = _market_price_unit(resolved)

    trade_plan = _build_recommended_trade_plan(
        context,
        prediction,
        level_summary,
        account_equity=snapshot.total_equity,
    )
    projection_bundle = build_projection_bundle(
        history_frame,
        prediction,
        level_summary,
        resolved,
        trade_plan=trade_plan,
    )
    scenario_results = _simulate_projection_scenarios(trade_plan, projection_bundle)

    summary_cols = st.columns(6)
    summary_cols[0].metric("최종 액션", _label_for(prediction.final_action, ACTION_LABELS))
    summary_cols[1].metric("현재가", _format_market_price(float(context.current_price or 0.0), resolved))
    summary_cols[2].metric("추천 진입가", _format_market_price(trade_plan.entry_price, resolved) if trade_plan.entry_price else "-")
    summary_cols[3].metric("손절가", _format_market_price(trade_plan.stop_loss, resolved) if trade_plan.stop_loss else "-")
    summary_cols[4].metric("목표가", _format_market_price(trade_plan.target_price, resolved) if trade_plan.target_price else "-")
    summary_cols[5].metric("손익비", f"{trade_plan.reward_risk_ratio:.2f}:1" if trade_plan.reward_risk_ratio else "-")

    prob_cols = st.columns(4)
    prob_cols[0].metric("상승 확률", _format_probability(prediction.probabilities["up"]))
    prob_cols[1].metric("하락 확률", _format_probability(prediction.probabilities["down"]))
    prob_cols[2].metric("횡보 확률", _format_probability(prediction.probabilities["side"]))
    prob_cols[3].metric("신뢰도", _label_for(prediction.confidence_grade, CONFIDENCE_LABELS))
    st.caption(f"현재가 기준 시각: {_format_datetime(context.timestamp)} / 반영 소스: {_화면문구(context.get_state_str('quote_source', ''))}")

    if trade_plan.allowed:
        st.success(f"{trade_plan.reason} 예상 이익 {_currency_price(trade_plan.target_profit_amount, balance_currency)} / 최대 손실 {_currency_price(trade_plan.risk_amount, balance_currency)}")
    else:
        st.warning(trade_plan.reason)

    tab_actual, tab_forecast, tab_simulation, tab_portfolio = st.tabs(
        ["실제 차트", "예상 차트", "자동 시뮬레이션", "잔고 / 거래이력"]
    )

    with tab_actual:
        st.subheader("실제 차트")
        if resolved.asset_class == "kr_stock":
            st.caption("한국거래소 종목은 내부 캔들차트로 표시합니다.")
            try:
                st.plotly_chart(
                    build_actual_price_chart(
                        history_frame,
                        resolved,
                        level_summary=level_summary,
                        title="실제 차트",
                        price_unit=price_unit,
                    ),
                    use_container_width=True,
                )
            except Exception as exc:
                st.warning(f"실제 차트를 그리지 못했습니다: {exc}")
        else:
            render_tradingview_chart(
                st,
                resolved,
                interval=analysis_timeframe,
                theme="dark",
                height=640,
                key=selection_key,
            )
        with st.expander("세부 종목 정보"):
            st.dataframe(_resolved_rows(resolved), use_container_width=True, hide_index=True)

    with tab_forecast:
        st.subheader("예상 차트")
        try:
            st.plotly_chart(
                build_forecast_chart(
                    history_frame,
                    prediction,
                    level_summary,
                    resolved,
                    trade_plan=trade_plan,
                    projection_bundle=projection_bundle,
                    price_unit=price_unit,
                ),
                use_container_width=True,
            )
        except Exception as exc:
            st.warning(f"예상 차트를 그리지 못했습니다: {exc}")

        bullish_reasons, bearish_reasons = _glenn_reason_groups(context, prediction, trade_plan)
        reason_left, reason_right = st.columns(2)
        with reason_left:
            _render_reason_cards(st, "상승 / 진입 근거", bullish_reasons, tone="bull")
        with reason_right:
            _render_reason_cards(st, "하락 / 진입 금지 근거", bearish_reasons, tone="bear")

        with st.expander("세부 구조 보기"):
            st.dataframe(_neely_setting_rows(context), use_container_width=True, hide_index=True)
            detail_left, detail_right = st.columns(2)
            with detail_left:
                st.dataframe(
                    _level_rows(level_summary.supports + level_summary.entries, resolved),
                    use_container_width=True,
                    hide_index=True,
                )
            with detail_right:
                st.dataframe(
                    _level_rows(level_summary.resistances + level_summary.take_profits + [level_summary.stop_loss], resolved),
                    use_container_width=True,
                    hide_index=True,
                )

        with st.expander("프레임 / 규칙 세부 보기"):
            st.dataframe(
                [
                    {
                        "타임프레임": timeframe.upper(),
                        "원점수": round(score.raw_score, 3),
                        "정규화": round(score.normalized_score, 3),
                        "방향": {"bull": "상승", "bear": "하락", "neutral": "중립"}[score.bias],
                        "가중치": score.weight,
                    }
                    for timeframe, score in prediction.mtf_summary.timeframe_scores.items()
                ],
                use_container_width=True,
                hide_index=True,
            )
            st.dataframe(_translated_rule_rows(prediction), use_container_width=True, hide_index=True)

    with tab_simulation:
        st.subheader("자동 시뮬레이션")
        metric_cols = st.columns(5)
        metric_cols[0].metric("방향", trade_plan.side)
        metric_cols[1].metric("추천 수량", f"{trade_plan.quantity:,.4f}" if trade_plan.quantity else "-")
        metric_cols[2].metric("최대 손실", _currency_price(trade_plan.risk_amount, balance_currency))
        metric_cols[3].metric("목표 이익", _currency_price(trade_plan.target_profit_amount, balance_currency))
        metric_cols[4].metric("기대값", _currency_price(trade_plan.expected_value, balance_currency))

        if scenario_results:
            scenario_cols = st.columns(len(scenario_results))
            for idx, scenario in enumerate(scenario_results):
                scenario_cols[idx].metric(
                    scenario["시나리오"],
                    _currency_price(float(scenario["손익"]), balance_currency),
                    f"{float(scenario['손익률']) * 100:.2f}%",
                )
                scenario_cols[idx].caption(f"{scenario['체결']} / {_화면문구(scenario['사유'])}")

            weighted_result = 0.0
            scenario_weight_map = {
                "상승": prediction.probabilities["up"],
                "하락": prediction.probabilities["down"],
                "횡보": prediction.probabilities["side"],
                "가중": 0.0,
            }
            for scenario in scenario_results:
                weighted_result += float(scenario["손익"]) * scenario_weight_map.get(str(scenario["시나리오"]), 0.0)
            st.caption(f"확률 가중 기대 손익: {_currency_price(weighted_result, balance_currency)}")

            primary_scenario = next(
                (item for item in scenario_results if item["시나리오"] == ("상승" if trade_plan.side == "롱" else "하락") and item["result"] is not None),
                None,
            ) or next((item for item in scenario_results if item["result"] is not None), None)

            if primary_scenario is not None:
                result = primary_scenario["result"]
                st.dataframe(
                    _trade_result_rows(result, balance_currency),
                    use_container_width=True,
                    hide_index=True,
                )
                try:
                    st.plotly_chart(
                        build_trade_review_chart(
                            primary_scenario["frame"],
                            TradeInput(
                                symbol=resolved.canonical_symbol,
                                side="long" if trade_plan.side == "롱" else "short",
                                entry_time=result.entry_time,
                                entry_price=trade_plan.entry_price,
                                quantity=trade_plan.quantity,
                                stop_loss=trade_plan.stop_loss,
                                take_profit=trade_plan.target_price,
                                exit_time=result.exit_time,
                                exit_price=result.exit_price,
                            ),
                            result,
                            price_unit=price_unit,
                        ),
                        use_container_width=True,
                    )
                except Exception as exc:
                    st.warning(f"시뮬레이션 차트를 그리지 못했습니다: {exc}")

        apply_button_disabled = (not trade_plan.allowed) or not any(item.get("result") is not None for item in scenario_results)
        if st.button("추천 시나리오를 잔고에 반영", use_container_width=True, disabled=apply_button_disabled):
            chosen_result = next(
                (
                    item["result"]
                    for item in scenario_results
                    if item["시나리오"] == ("상승" if trade_plan.side == "롱" else "하락")
                    and item["result"] is not None
                ),
                None,
            ) or next((item["result"] for item in scenario_results if item["result"] is not None), None)
            if chosen_result is not None:
                st.session_state.simulation_preview = chosen_result
                st.session_state.trade_results = st.session_state.trade_results + [chosen_result]
                manager = BalanceManager.from_state(
                    st.session_state.portfolio_state,
                    initial_balance=initial_balance,
                    currency=balance_currency,
                )
                manager.apply_closed_trade(chosen_result)
                st.session_state.portfolio_state = manager.state
                st.success("추천 시나리오가 잔고에 반영되었습니다.")

        with st.expander("세부 계산 보기"):
            st.write(f"- 진입 근거: {' / '.join(trade_plan.glenn_reasons) if trade_plan.glenn_reasons else '구조 근거 부족'}")
            st.write(f"- 손익비 기준: 최소 2.00:1")
            st.write(f"- 자동 판단: {trade_plan.reason}")

    with tab_portfolio:
        manager = BalanceManager.from_state(
            st.session_state.portfolio_state,
            initial_balance=initial_balance,
            currency=balance_currency,
        )
        snapshot = manager.snapshot()
        portfolio_cols = st.columns(4)
        portfolio_cols[0].metric("현재 잔고", _currency_price(snapshot.cash_balance, balance_currency))
        portfolio_cols[1].metric("가용 자금", _currency_price(snapshot.available_balance, balance_currency))
        portfolio_cols[2].metric("누적 실현손익", _currency_price(snapshot.realized_pnl, balance_currency))
        portfolio_cols[3].metric("총자산", _currency_price(snapshot.total_equity, balance_currency))

        aggregate = summarize_trade_results(st.session_state.trade_results)
        st.caption(
            f"누적 거래 {aggregate.trade_count}회 / 승률 {aggregate.win_rate * 100:.1f}% / 누적 실손익 {_currency_price(aggregate.cumulative_net_pnl, balance_currency)}"
        )

        with st.expander("거래 이력 보기"):
            trade_rows = _trade_history_rows(
                st.session_state.trade_results,
                resolved.canonical_symbol,
                balance_currency,
            )
            if trade_rows:
                st.dataframe(trade_rows, use_container_width=True, hide_index=True)
            else:
                st.info("현재 종목에 대해 아직 반영된 시뮬레이션이 없습니다.")
