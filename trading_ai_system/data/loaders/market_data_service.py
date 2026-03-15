"""Market data service with optional live providers and a deterministic fallback."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import math
import os
import random
from typing import Optional

from trading_ai_system.data.loaders.symbol_resolver import ResolvedTicker


_TIMEFRAME_TO_INTERVAL = {
    "1m": "1m",
    "15m": "15m",
    "30m": "30m",
    "1h": "60m",
    "4h": "4h",
    "1d": "1d",
    "1w": "1wk",
}

_TIMEFRAME_TO_MINUTES = {
    "1m": 1,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "4h": 240,
    "1d": 1440,
    "1w": 10080,
}


class MarketDataService:
    """Loads OHLCV data and falls back to deterministic demo candles when needed."""

    def load_latest_quote(
        self,
        resolved: ResolvedTicker,
        *,
        fallback_frame=None,
    ) -> dict[str, object]:
        """Loads the latest tradeable price separately from analysis candles."""
        try:
            if resolved.asset_class == "crypto":
                return self._load_crypto_quote(resolved)
            return self._load_stock_quote(resolved)
        except Exception:
            price = None
            timestamp = datetime.now(timezone.utc)
            if fallback_frame is not None and len(fallback_frame) > 0:
                try:
                    price = float(fallback_frame["close"].iloc[-1])
                    timestamp = fallback_frame["timestamp"].iloc[-1]
                except Exception:
                    price = None
            if price is None:
                price = self._base_price_for(resolved)
            return {
                "price": price,
                "timestamp": timestamp,
                "source": "fallback",
            }

    def load_history(
        self,
        resolved: ResolvedTicker,
        *,
        timeframe: str = "1h",
        limit: int = 300,
        mode: str = "historical",
    ):
        """Loads candles for one timeframe with provider-specific routing."""
        try:
            if resolved.asset_class == "crypto":
                return self._load_crypto_history(resolved, timeframe=timeframe, limit=limit, mode=mode)
            return self._load_stock_history(resolved, timeframe=timeframe, limit=limit, mode=mode)
        except Exception:
            return self._generate_demo_history(resolved, timeframe=timeframe, limit=limit, mode=mode)

    def load_multi_timeframe_history(
        self,
        resolved: ResolvedTicker,
        *,
        timeframes: Optional[list[str]] = None,
        limit: int = 300,
        mode: str = "historical",
    ) -> dict[str, object]:
        """Loads all required timeframes for MTF scoring and simulation."""
        frames: dict[str, object] = {}
        for timeframe in timeframes or ["1m", "15m", "30m", "1h", "4h", "1d", "1w"]:
            frames[timeframe] = self.load_history(
                resolved,
                timeframe=timeframe,
                limit=limit,
                mode=mode,
            )
        return frames

    def _load_stock_history(
        self,
        resolved: ResolvedTicker,
        *,
        timeframe: str,
        limit: int,
        mode: str,
    ):
        """Loads stock candles from yfinance when available."""
        import pandas as pd

        try:
            import yfinance as yf
        except ImportError as exc:
            raise RuntimeError("yfinance가 설치되어 있지 않습니다.") from exc

        interval = _TIMEFRAME_TO_INTERVAL.get(timeframe, "60m")
        period = self._history_period_for(timeframe=timeframe, limit=limit)
        data = yf.download(
            resolved.yfinance_symbol or resolved.provider_symbol,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=False,
            threads=False,
        )
        if data is None or data.empty:
            raise RuntimeError("주식 데이터를 받아오지 못했습니다.")

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [str(column[0]).lower() for column in data.columns]
        else:
            data.columns = [str(column).lower() for column in data.columns]

        frame = data.rename(
            columns={
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "adj close": "close",
                "volume": "volume",
            }
        )[["open", "high", "low", "close", "volume"]].reset_index()
        frame.columns = [str(column).lower().replace(" ", "_") for column in frame.columns]
        frame = frame.rename(columns={"date": "timestamp", "datetime": "timestamp"})
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        frame = frame.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").tail(limit).reset_index(drop=True)
        frame["is_confirmed"] = True
        if mode == "realtime" and not frame.empty:
            frame.loc[frame.index[-1], "is_confirmed"] = False
        return frame

    def _load_stock_quote(self, resolved: ResolvedTicker) -> dict[str, object]:
        """Loads the latest stock price from yfinance intraday data."""
        try:
            import yfinance as yf
        except ImportError as exc:
            raise RuntimeError("yfinance가 설치되어 있지 않습니다.") from exc

        ticker = yf.Ticker(resolved.yfinance_symbol or resolved.provider_symbol)
        price = None
        timestamp = datetime.now(timezone.utc)

        try:
            fast_info = getattr(ticker, "fast_info", None)
            if fast_info:
                price = fast_info.get("lastPrice") or fast_info.get("last_price")
        except Exception:
            price = None

        if price is None:
            intraday = ticker.history(period="1d", interval="1m")
            if intraday is None or intraday.empty:
                raise RuntimeError("주식 현재가를 받아오지 못했습니다.")
            timestamp = intraday.index[-1].to_pydatetime()
            column_name = "Close" if "Close" in intraday.columns else intraday.columns[-1]
            price = float(intraday.iloc[-1][column_name])

        return {
            "price": float(price),
            "timestamp": timestamp,
            "source": "live_stock",
        }

    def _load_crypto_history(
        self,
        resolved: ResolvedTicker,
        *,
        timeframe: str,
        limit: int,
        mode: str,
    ):
        """Loads crypto candles from ccxt when available."""
        import pandas as pd

        try:
            import ccxt
        except ImportError as exc:
            raise RuntimeError("ccxt가 설치되어 있지 않습니다.") from exc

        exchange_name = "upbit" if resolved.exchange == "UPBIT" else "binance"
        exchange_class = getattr(ccxt, exchange_name)
        exchange = exchange_class({"enableRateLimit": True})
        candles = exchange.fetch_ohlcv(resolved.ccxt_symbol or resolved.provider_symbol, timeframe=timeframe, limit=limit)
        if not candles:
            raise RuntimeError("가상자산 데이터를 받아오지 못했습니다.")

        frame = pd.DataFrame(
            candles,
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        )
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
        frame = frame.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
        frame["is_confirmed"] = True
        if mode == "realtime" and not frame.empty:
            frame.loc[frame.index[-1], "is_confirmed"] = False
        return frame

    def _load_crypto_quote(self, resolved: ResolvedTicker) -> dict[str, object]:
        """Loads the latest crypto trade price from ccxt ticker endpoint."""
        try:
            import ccxt
        except ImportError as exc:
            raise RuntimeError("ccxt가 설치되어 있지 않습니다.") from exc

        exchange_name = "upbit" if resolved.exchange == "UPBIT" else "binance"
        exchange_class = getattr(ccxt, exchange_name)
        exchange = exchange_class({"enableRateLimit": True})
        ticker = exchange.fetch_ticker(resolved.ccxt_symbol or resolved.provider_symbol)
        last_price = ticker.get("last") or ticker.get("close")
        timestamp_value = ticker.get("timestamp")
        if last_price is None:
            raise RuntimeError("가상자산 현재가를 받아오지 못했습니다.")
        timestamp = (
            datetime.fromtimestamp(timestamp_value / 1000, tz=timezone.utc)
            if timestamp_value
            else datetime.now(timezone.utc)
        )
        return {
            "price": float(last_price),
            "timestamp": timestamp,
            "source": "live_crypto",
        }

    def _generate_demo_history(
        self,
        resolved: ResolvedTicker,
        *,
        timeframe: str,
        limit: int,
        mode: str,
    ):
        """Generates deterministic candles so the app still works offline."""
        import pandas as pd

        step_minutes = _TIMEFRAME_TO_MINUTES.get(timeframe, 60)
        seed_text = f"{resolved.cache_key}|{timeframe}"
        seed = int(hashlib.md5(seed_text.encode("utf-8")).hexdigest()[:12], 16)
        rng = random.Random(seed)
        base_price = self._base_price_for(resolved)
        start = datetime.now(timezone.utc) - timedelta(minutes=step_minutes * (limit - 1))
        rows = []
        previous_close = base_price
        for idx in range(limit):
            drift = math.sin(idx / 11.0) * (base_price * 0.003)
            trend = math.cos(idx / 37.0) * (base_price * 0.0018)
            noise = (rng.random() - 0.5) * (base_price * 0.0045)
            close = max(0.1, previous_close + drift + trend + noise)
            open_price = previous_close
            high = max(open_price, close) + abs(rng.random()) * (base_price * 0.002)
            low = min(open_price, close) - abs(rng.random()) * (base_price * 0.002)
            volume = abs(1000 + (idx % 21) * 45 + rng.random() * 700)
            rows.append(
                {
                    "timestamp": start + timedelta(minutes=step_minutes * idx),
                    "open": round(open_price, 6),
                    "high": round(high, 6),
                    "low": round(max(0.01, low), 6),
                    "close": round(close, 6),
                    "volume": round(volume, 3),
                    "is_confirmed": True,
                }
            )
            previous_close = close
        frame = pd.DataFrame(rows)
        if mode == "realtime" and not frame.empty:
            frame.loc[frame.index[-1], "is_confirmed"] = False
        return frame

    def _history_period_for(self, *, timeframe: str, limit: int) -> str:
        minutes = _TIMEFRAME_TO_MINUTES.get(timeframe, 60) * limit
        days = max(7, int(minutes / 1440) + 5)
        if timeframe == "1w":
            days = max(days, 365 * 5)
        elif timeframe == "1d":
            days = max(days, 365 * 2)
        return f"{days}d"

    def _base_price_for(self, resolved: ResolvedTicker) -> float:
        if resolved.asset_class == "crypto":
            if (resolved.base_asset or "").upper() == "BTC":
                return 65000.0
            if (resolved.base_asset or "").upper() == "ETH":
                return 3400.0
            return 100.0
        if resolved.asset_class == "kr_stock":
            return 85000.0
        return 250.0
