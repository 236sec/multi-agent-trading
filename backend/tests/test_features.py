"""Tests for FeatureEngine — 21 technical indicators from OHLCV data."""

import numpy as np
import pandas as pd
import pytest

from trading.features import FeatureEngine


# ── fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def uptrend_df():
    """50 business days of noisy uptrend — RSI >> 70 on last row."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=50, freq="B")
    n = 50
    close = np.linspace(100, 150, n) + np.random.normal(0, 1, n)
    return pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": np.full(n, 1_000_000),
        },
        index=dates,
    )


@pytest.fixture
def downtrend_df():
    """50 business days of noisy downtrend — RSI << 30 on last row."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=50, freq="B")
    n = 50
    close = np.linspace(150, 100, n) + np.random.normal(0, 1, n)
    return pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": np.full(n, 1_000_000),
        },
        index=dates,
    )


@pytest.fixture
def flat_df():
    """50 business days of perfectly flat prices (volatility ~ 0)."""
    dates = pd.date_range("2024-01-01", periods=50, freq="B")
    n = 50
    close = np.full(n, 100.0)
    return pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": np.full(n, 1_000_000),
        },
        index=dates,
    )


@pytest.fixture
def engine():
    """Fresh FeatureEngine instance."""
    return FeatureEngine()


# ── indicator tests ───────────────────────────────────────────────────


class TestIndicators:
    """Verify individual indicator behaviour under known market regimes."""

    def test_rising_prices_rsi_high(self, uptrend_df, engine):
        """Strong uptrend → RSI above 70 (overbought)."""
        features = engine.compute(uptrend_df)
        rsi = features["rsi"].iloc[-1]
        assert rsi > 70, f"Expected RSI > 70 for strong uptrend, got {rsi:.2f}"

    def test_falling_prices_rsi_low(self, downtrend_df, engine):
        """Strong downtrend → RSI below 30 (oversold)."""
        features = engine.compute(downtrend_df)
        rsi = features["rsi"].iloc[-1]
        assert rsi < 30, f"Expected RSI < 30 for strong downtrend, got {rsi:.2f}"

    def test_constant_prices_returns_zero(self, flat_df, engine):
        """Flat prices → daily returns are ~0 and volatility ~0."""
        features = engine.compute(flat_df)

        # daily returns identical 0 (first row is NaN from pct_change)
        np.testing.assert_allclose(features["returns_1d"].iloc[1:], 0.0, atol=1e-10)

        # all volatility columns ~0 (first rows are NaN — need warmup)
        vol_cols = [c for c in features.columns if "volatility" in c]
        for c in vol_cols:
            assert features[c].notna().any(), f"{c} is all NaN on flat data"
            np.testing.assert_allclose(features[c].dropna(), 0.0, atol=1e-10)


# ── structural tests ──────────────────────────────────────────────────


class TestStructure:
    """Verify DataFrame shape, columns, and index preservation."""

    def test_output_shape(self, uptrend_df, engine):
        """compute() returns a DataFrame with original + feature columns."""
        features = engine.compute(uptrend_df)

        assert isinstance(features, pd.DataFrame)
        assert list(features.index) == list(uptrend_df.index)

        # original OHLCV columns preserved
        for c in ("open", "high", "low", "close", "volume"):
            assert c in features.columns, f"Missing original column: {c}"

        # all feature columns present
        for c in engine.list_features():
            assert c in features.columns, f"Missing feature column: {c}"

        # total columns
        expected_count = 5 + len(engine.list_features())  # 5 + 20 = 25
        assert features.shape[1] == expected_count, (
            f"Expected {expected_count} columns, got {features.shape[1]}"
        )

    def test_list_features_matches_output(self, uptrend_df, engine):
        """list_features() returns 21 items, all are subset of compute() columns."""
        feature_list = engine.list_features()
        assert len(feature_list) == 21, (
            f"Expected 21 features, got {len(feature_list)}"
        )

        features = engine.compute(uptrend_df)
        for f in feature_list:
            assert f in features.columns, f"{f} missing from compute() output"


# ── validation tests ──────────────────────────────────────────────────


class TestValidate:
    """FeatureEngine.validate_features behaviour."""

    def test_validate_features_passes(self, uptrend_df, engine):
        """validate returns True for a valid features DataFrame."""
        features = engine.compute(uptrend_df)
        valid, issues = engine.validate_features(features)
        assert valid, f"Expected valid=True, got issues: {issues}"

    def test_validate_features_fails_missing_column(self, uptrend_df, engine):
        """validate returns False when a feature column is missing."""
        features = engine.compute(uptrend_df)
        features.drop(columns=["rsi"], inplace=True)

        valid, issues = engine.validate_features(features)
        assert not valid, "Expected valid=False when 'rsi' column is missing"
        assert any("missing" in i.lower() for i in issues), (
            f"Issues should mention missing columns: {issues}"
        )

    def test_validate_features_fails_nan_in_latest(self, uptrend_df, engine):
        """validate returns False when the latest row contains NaN."""
        features = engine.compute(uptrend_df)
        features.iloc[-1, features.columns.get_loc("rsi")] = np.nan

        valid, issues = engine.validate_features(features)
        assert not valid, "Expected valid=False when latest row has NaN"
        assert any("nan_in_latest_row" in i for i in issues), (
            f"Issues should mention NaN in latest row: {issues}"
        )


# ── error handling tests ──────────────────────────────────────────────


class TestErrorHandling:
    """Graceful failure modes on invalid input."""

    def test_missing_columns_raises(self, uptrend_df, engine):
        """compute() raises ValueError when OHLCV columns are missing."""
        bad_df = uptrend_df.drop(columns=["volume"])

        with pytest.raises(ValueError, match="missing required columns"):
            engine.compute(bad_df)
