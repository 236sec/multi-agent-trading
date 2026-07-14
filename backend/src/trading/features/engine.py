"""Feature engineering for daily OHLCV data.

Uses the ``ta`` library (financial standards, well-tested) for core
indicators (SMA, EMA, MACD, RSI, ATR). Returns, volume profile, and
volatility are computed with pandas/numpy since ``ta`` has no equivalent.
Designed for both live agent and notebook usage.
"""

import logging
from typing import Tuple

import numpy as np
import pandas as pd
import ta

logger = logging.getLogger(__name__)

# ── expected OHLCV columns ──────────────────────────────────────────
OHLCV_COLS = {"open", "high", "low", "close", "volume"}


class FeatureEngine:
    """Compute technical indicators from daily OHLCV data.

    Usage::

        engine = FeatureEngine()
        features = engine.compute(ohlcv_df)  # date-indexed, 5 cols
        ok, issues = FeatureEngine.validate_features(features)

    Core indicators (SMA, EMA, MACD, RSI, ATR) delegate to the ``ta``
    library for correct financial formulas. Returns, volume ratios, and
    volatility are computed with pandas/numpy.
    """

    # ── windows ─────────────────────────────────────────────────────
    SMA_WINDOWS: tuple = (5, 10, 20, 50)
    EMA_WINDOWS: tuple = (12, 26)
    RSI_WINDOW: int = 14
    MACD_FAST: int = 12
    MACD_SLOW: int = 26
    MACD_SIGNAL: int = 9
    ATR_WINDOW: int = 14
    VOL_WINDOWS: tuple = (5, 10, 20)
    RET_WINDOWS: tuple = (1, 5, 10, 20)

    # ── public API ──────────────────────────────────────────────────

    def compute(self, ohlcv_df: pd.DataFrame) -> pd.DataFrame:
        """Compute all features from OHLCV DataFrame.

        Args:
            ohlcv_df: Date-indexed DataFrame with columns
                ``open, high, low, close, volume``.

        Returns:
            Date-indexed DataFrame with original 5 cols + 20 feature cols.
            Rows before sufficient warmup will contain NaN for indicators
            that need more history.

        Raises:
            ValueError: If required columns are missing.
        """
        # ── guard ───────────────────────────────────────────────────
        missing = OHLCV_COLS - set(ohlcv_df.columns)
        if missing:
            raise ValueError(
                f"OHLCV DataFrame missing required columns: {missing}"
            )

        n_rows = len(ohlcv_df)
        has_nan = bool(ohlcv_df.isna().any().any())

        logger.info(
            "FeatureEngine.compute: input_rows=%d input_has_nan=%s",
            n_rows,
            has_nan,
        )
        if has_nan:
            logger.warning(
                "Input OHLCV contains NaN values — indicators will "
                "propagate NaN where history is incomplete."
            )

        if n_rows < max(self.SMA_WINDOWS) + self.RSI_WINDOW:
            logger.warning(
                "Only %d rows — need at least %d for stable "
                "indicator values. Early rows will be NaN.",
                n_rows,
                max(self.SMA_WINDOWS) + self.RSI_WINDOW,
            )

        # ── copy to avoid mutating caller ───────────────────────────
        df = ohlcv_df.copy()
        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        # ── returns ─────────────────────────────────────────────────
        df["returns_1d"] = close.pct_change()
        for w in (5, 10, 20):
            df[f"returns_{w}d"] = close.pct_change(w)

        # ── SMA ratios (ta library) ─────────────────────────────────
        for w in self.SMA_WINDOWS:
            sma = ta.trend.sma_indicator(close, window=w, fillna=False)
            df[f"sma_{w}"] = close / sma - 1.0

        # ── EMA ratios (ta library) ─────────────────────────────────
        for w in self.EMA_WINDOWS:
            ema = ta.trend.ema_indicator(close, window=w, fillna=False)
            df[f"ema_{w}"] = close / ema - 1.0

        # ── RSI (ta library — Wilder's smoothing) ───────────────────
        df["rsi"] = ta.momentum.rsi(close, window=self.RSI_WINDOW, fillna=False)

        # ── MACD (ta library) ───────────────────────────────────────
        macd_obj = ta.trend.MACD(
            close,
            window_slow=self.MACD_SLOW,
            window_fast=self.MACD_FAST,
            window_sign=self.MACD_SIGNAL,
            fillna=False,
        )
        df["macd"] = macd_obj.macd()
        df["macd_signal"] = macd_obj.macd_signal()
        df["macd_hist"] = macd_obj.macd_diff()

        # ── ATR normalized by close (ta library) ────────────────────
        atr_raw = ta.volatility.average_true_range(
            high, low, close, window=self.ATR_WINDOW, fillna=False
        )
        df["atr"] = atr_raw / close

        # ── volume profile ──────────────────────────────────────────
        for w in self.VOL_WINDOWS:
            avg_vol = volume.rolling(w, min_periods=w).mean()
            df[f"vol_{w}"] = volume / avg_vol - 1.0

        # ── historical volatility (annualized) ──────────────────────
        for w in self.VOL_WINDOWS:
            df[f"volatility_{w}d"] = (
                df["returns_1d"].rolling(w, min_periods=w).std() * np.sqrt(252)
            )

        # ── log result summary ──────────────────────────────────────
        latest = df.iloc[-1]
        latest_nan_cols = [
            c for c in self.list_features() if pd.isna(latest.get(c))
        ]
        logger.info(
            "FeatureEngine.compute: output_rows=%d feature_count=%d "
            "latest_row_has_nan=%s nan_features=%s",
            len(df),
            len(self.list_features()),
            bool(latest_nan_cols),
            latest_nan_cols if latest_nan_cols else "none",
        )

        return df

    # ── helpers ─────────────────────────────────────────────────────

    @staticmethod
    def list_features() -> list[str]:
        """Feature column names produced by :meth:`compute` (excludes OHLCV)."""
        return [
            # returns
            "returns_1d",
            "returns_5d",
            "returns_10d",
            "returns_20d",
            # sma ratios
            "sma_5",
            "sma_10",
            "sma_20",
            "sma_50",
            # ema ratios
            "ema_12",
            "ema_26",
            # oscillators
            "rsi",
            "macd",
            "macd_signal",
            "macd_hist",
            # atr
            "atr",
            # volume
            "vol_5",
            "vol_10",
            "vol_20",
            # volatility
            "volatility_5d",
            "volatility_10d",
            "volatility_20d",
        ]

    @staticmethod
    def validate_features(features_df: pd.DataFrame) -> Tuple[bool, list[str]]:
        """Check that a features DataFrame is ready for model prediction.

        Args:
            features_df: Output of :meth:`compute` (or compatible).

        Returns:
            ``(is_valid, issues)`` — ``is_valid`` is ``True`` only when
            all required columns are present AND the latest row contains
            no NaN/Inf in any feature column.
        """
        issues: list[str] = []

        # missing columns
        required = FeatureEngine.list_features()
        missing = [f for f in required if f not in features_df.columns]
        if missing:
            issues.append(f"missing_columns={missing}")

        # latest-row quality (the row the model predicts from)
        if len(features_df) == 0:
            issues.append("empty_dataframe")
            return False, issues

        latest = features_df.iloc[-1]
        for col in required:
            if col not in features_df.columns:
                continue  # already flagged
            val = latest[col]
            if pd.isna(val):
                issues.append(f"nan_in_latest_row:{col}")
            elif np.isinf(val):
                issues.append(f"inf_in_latest_row:{col}")

        is_valid = len(issues) == 0
        if not is_valid:
            logger.warning(
                "FeatureEngine.validate_features: FAILED issues=%s", issues
            )
        else:
            logger.info("FeatureEngine.validate_features: OK")

        return is_valid, issues
