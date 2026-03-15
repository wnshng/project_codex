"""Unified symbol resolver for crypto, Korean stocks, and US stocks."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import csv
import os
import re
from typing import Optional


_DEFAULT_KRX_MAP = {
    "005930": {
        "name": "삼성전자",
        "exchange": "KRX",
        "market": "KOSPI",
        "yfinance_symbol": "005930.KS",
        "tradingview_symbol": "KRX:005930",
    },
    "000660": {
        "name": "SK하이닉스",
        "exchange": "KRX",
        "market": "KOSPI",
        "yfinance_symbol": "000660.KS",
        "tradingview_symbol": "KRX:000660",
    },
    "263750": {
        "name": "펄어비스",
        "exchange": "KRX",
        "market": "KOSDAQ",
        "yfinance_symbol": "263750.KQ",
        "tradingview_symbol": "KRX:263750",
    },
    "194480": {
        "name": "데브시스터즈",
        "exchange": "KRX",
        "market": "KOSDAQ",
        "yfinance_symbol": "194480.KQ",
        "tradingview_symbol": "KRX:194480",
    },
}

_DEFAULT_US_EXCHANGE_MAP = {
    "AAPL": "NASDAQ",
    "AMD": "NASDAQ",
    "MSFT": "NASDAQ",
    "NVDA": "NASDAQ",
    "TSLA": "NASDAQ",
    "META": "NASDAQ",
    "AMZN": "NASDAQ",
    "PLTR": "NASDAQ",
    "SPY": "AMEX",
}

_CRYPTO_QUOTES = ("USDT", "USD", "BUSD", "BTC", "ETH", "KRW")


def _has_korean(value: str) -> bool:
    return bool(re.search(r"[가-힣]", value))


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", "", value.strip())


@dataclass
class ResolvedTicker:
    """Normalized symbol information used across loaders, UI, and TradingView."""

    raw_input: str
    query_key: str
    asset_class: str
    exchange: str
    display_name: str
    canonical_symbol: str
    tradingview_symbol: str
    provider_symbol: str
    yfinance_symbol: Optional[str] = None
    ccxt_symbol: Optional[str] = None
    krx_code: Optional[str] = None
    market: Optional[str] = None
    base_asset: Optional[str] = None
    quote_asset: Optional[str] = None

    @property
    def cache_key(self) -> str:
        return "|".join(
            [
                self.asset_class,
                self.exchange,
                self.canonical_symbol,
                self.provider_symbol,
            ]
        )

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


class UnifiedSymbolResolver:
    """Resolves a user query into a market-specific symbol with TradingView mapping."""

    def __init__(self, krx_map_path: Optional[str] = None) -> None:
        self.krx_map = dict(_DEFAULT_KRX_MAP)
        self.name_to_code = {
            info["name"]: code for code, info in self.krx_map.items()
        }
        if krx_map_path:
            self._load_external_krx_map(krx_map_path)

    def _load_external_krx_map(self, path: str) -> None:
        """Allows .env-driven KRX symbol expansion without changing code."""
        if not path or not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    code = str(row.get("code", "")).zfill(6)
                    name = str(row.get("name", "")).strip()
                    if not code or not name:
                        continue
                    market = str(row.get("market", "KOSPI")).strip().upper() or "KOSPI"
                    suffix = ".KQ" if market == "KOSDAQ" else ".KS"
                    self.krx_map[code] = {
                        "name": name,
                        "exchange": "KRX",
                        "market": market,
                        "yfinance_symbol": row.get("yfinance_symbol") or f"{code}{suffix}",
                        "tradingview_symbol": row.get("tradingview_symbol") or f"KRX:{code}",
                    }
                    self.name_to_code[name] = code
        except (OSError, csv.Error):
            return

    def resolve(
        self,
        query: str,
        *,
        preferred_exchange: Optional[str] = None,
    ) -> ResolvedTicker:
        """Auto-detects the symbol type and returns the unified mapping."""
        cleaned = _normalize_text(query)
        if not cleaned:
            raise ValueError("종목명 또는 티커를 입력해 주세요.")

        if self._looks_like_crypto(cleaned):
            return self._resolve_crypto(cleaned, preferred_exchange=preferred_exchange)
        if cleaned.isdigit() and len(cleaned) == 6:
            return self._resolve_krx(cleaned)
        if _has_korean(cleaned):
            return self._resolve_krx_name(cleaned)
        return self._resolve_us_stock(cleaned)

    def _resolve_krx_name(self, name: str) -> ResolvedTicker:
        code = self.name_to_code.get(name)
        if not code:
            partial = next(
                (
                    matched_code
                    for matched_name, matched_code in self.name_to_code.items()
                    if name in matched_name or matched_name in name
                ),
                None,
            )
            code = partial
        if not code:
            raise ValueError(f"한국 주식 종목명을 찾지 못했습니다: {name}")
        return self._resolve_krx(code)

    def _resolve_krx(self, code: str) -> ResolvedTicker:
        info = self.krx_map.get(code)
        if info is None:
            suffix = ".KS"
            info = {
                "name": f"KRX {code}",
                "exchange": "KRX",
                "market": "KOSPI",
                "yfinance_symbol": f"{code}{suffix}",
                "tradingview_symbol": f"KRX:{code}",
            }
        return ResolvedTicker(
            raw_input=code,
            query_key=code,
            asset_class="kr_stock",
            exchange="KRX",
            display_name=str(info["name"]),
            canonical_symbol=code,
            tradingview_symbol=str(info["tradingview_symbol"]),
            provider_symbol=str(info["yfinance_symbol"]),
            yfinance_symbol=str(info["yfinance_symbol"]),
            krx_code=code,
            market=str(info.get("market") or "KOSPI"),
        )

    def _resolve_us_stock(self, symbol: str) -> ResolvedTicker:
        normalized = symbol.upper()
        exchange = _DEFAULT_US_EXCHANGE_MAP.get(normalized, "NASDAQ")
        return ResolvedTicker(
            raw_input=symbol,
            query_key=normalized,
            asset_class="us_stock",
            exchange=exchange,
            display_name=normalized,
            canonical_symbol=normalized,
            tradingview_symbol=f"{exchange}:{normalized}",
            provider_symbol=normalized,
            yfinance_symbol=normalized,
            market=exchange,
        )

    def _resolve_crypto(
        self,
        symbol: str,
        *,
        preferred_exchange: Optional[str] = None,
    ) -> ResolvedTicker:
        normalized = symbol.upper().replace("_", "").replace(" ", "")
        exchange = (preferred_exchange or "").upper()

        if "-" in normalized:
            quote, base = normalized.split("-", 1)
            if quote in _CRYPTO_QUOTES:
                exchange = exchange or "UPBIT"
                ccxt_symbol = f"{base}/{quote}"
                provider_symbol = f"{quote}-{base}"
                tv_symbol = f"UPBIT:{quote}{base}"
                return ResolvedTicker(
                    raw_input=symbol,
                    query_key=provider_symbol,
                    asset_class="crypto",
                    exchange="UPBIT",
                    display_name=provider_symbol,
                    canonical_symbol=f"{base}{quote}",
                    tradingview_symbol=tv_symbol,
                    provider_symbol=provider_symbol,
                    ccxt_symbol=ccxt_symbol,
                    base_asset=base,
                    quote_asset=quote,
                )

        if "/" in normalized:
            base, quote = normalized.split("/", 1)
        else:
            base, quote = self._split_compact_crypto_symbol(normalized)

        if quote == "KRW" or exchange == "UPBIT":
            provider_symbol = f"{quote}-{base}"
            return ResolvedTicker(
                raw_input=symbol,
                query_key=provider_symbol,
                asset_class="crypto",
                exchange="UPBIT",
                display_name=provider_symbol,
                canonical_symbol=f"{base}{quote}",
                tradingview_symbol=f"UPBIT:{quote}{base}",
                provider_symbol=provider_symbol,
                ccxt_symbol=f"{base}/{quote}",
                base_asset=base,
                quote_asset=quote,
            )

        provider_symbol = f"{base}{quote}"
        return ResolvedTicker(
            raw_input=symbol,
            query_key=provider_symbol,
            asset_class="crypto",
            exchange="BINANCE",
            display_name=provider_symbol,
            canonical_symbol=provider_symbol,
            tradingview_symbol=f"BINANCE:{provider_symbol}",
            provider_symbol=provider_symbol,
            ccxt_symbol=f"{base}/{quote}",
            base_asset=base,
            quote_asset=quote,
        )

    def _looks_like_crypto(self, value: str) -> bool:
        upper = value.upper()
        if "/" in upper or "-" in upper:
            return True
        return any(upper.endswith(quote) for quote in _CRYPTO_QUOTES if len(upper) > len(quote))

    def _split_compact_crypto_symbol(self, symbol: str) -> tuple[str, str]:
        for quote in _CRYPTO_QUOTES:
            if symbol.endswith(quote) and len(symbol) > len(quote):
                return symbol[: -len(quote)], quote
        return symbol, "USDT"
