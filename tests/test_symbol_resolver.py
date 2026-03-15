from trading_ai_system.data.loaders.symbol_resolver import UnifiedSymbolResolver


def test_resolver_supports_crypto_and_tradingview_mapping() -> None:
    resolver = UnifiedSymbolResolver()
    resolved = resolver.resolve("BTCUSDT")

    assert resolved.asset_class == "crypto"
    assert resolved.exchange == "BINANCE"
    assert resolved.tradingview_symbol == "BINANCE:BTCUSDT"


def test_resolver_supports_korean_stock_name_lookup() -> None:
    resolver = UnifiedSymbolResolver()
    resolved = resolver.resolve("펄어비스")

    assert resolved.asset_class == "kr_stock"
    assert resolved.canonical_symbol == "263750"
    assert resolved.tradingview_symbol == "KRX:263750"


def test_resolver_supports_us_stock_symbol_lookup() -> None:
    resolver = UnifiedSymbolResolver()
    resolved = resolver.resolve("TSLA")

    assert resolved.asset_class == "us_stock"
    assert resolved.exchange == "NASDAQ"
    assert resolved.tradingview_symbol == "NASDAQ:TSLA"
