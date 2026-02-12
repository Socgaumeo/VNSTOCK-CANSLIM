# VNSTOCK-CANSLIM Project

## Project Overview

Hệ thống phân tích cổ phiếu Việt Nam theo phương pháp CANSLIM với AI (Claude & Gemini).

## Tech Stack

- **Language:** Python 3.12
- **Data Source:** vnstock library (Vietnam stock market data)
- **AI Providers:** Claude (Anthropic), Gemini (Google)
- **Notification:** Telegram Bot
- **Cache:** JSON file-based caching

## Project Structure

```
v2_optimized/           # Main codebase
├── config.py           # Configuration management
├── data_collector.py   # Stock data fetching & processing
├── module1_market_timing_v2.py    # Market timing analysis
├── module2_sector_rotation_v3.py  # Sector rotation
├── module3_stock_screener_v1.py   # Stock screening
├── ai_providers.py     # AI integration (Claude/Gemini)
├── telegram_bot.py     # Telegram bot interface
├── history_manager.py  # Historical data & recommendations tracking
├── historical_price_tracker.py    # Price history (30 days)
├── historical_foreign_tracker.py  # Foreign investor tracking
├── cache/              # Cached data
│   └── historical/     # Historical tracking data
└── output/             # Generated reports
```

## Key Components

### Data Collection
- `EnhancedDataCollector` - Fetches stock data with technical indicators
- `VolumeProfileCalculator` - Volume Profile analysis (POC, VAH, VAL)
- Multi-source fallback (vnstock, SSI)

### Analysis Modules
1. **Market Timing** - VN-Index health score (0-100)
2. **Sector Rotation** - Industry ranking by RS
3. **Stock Screener** - CANSLIM scoring & pattern detection

### Tracking System
- `HistoricalPriceTracker` - 30-day price snapshots
- `HistoricalForeignTracker` - 20-day rolling foreign flow
- `RecommendationHistoryTracker` - Win rate tracking

### AI Integration
- Claude Sonnet 4 for deep analysis
- Gemini 2.0 Flash for fast screening
- VSA (Volume Spread Analysis) prompts

## Coding Standards

### Python Style
- Follow PEP8
- Use type hints for function signatures
- Vietnamese comments are acceptable
- Docstrings in English or Vietnamese

### Error Handling
- Silent fail for optional features (historical tracking)
- Graceful degradation for API failures
- Log errors but don't crash the pipeline

### Data Caching
- Use JSON for simple cache
- TTL-based cache invalidation
- Separate cache directories by data type

## Common Tasks

### Run Full Pipeline
```bash
cd v2_optimized
python run_simultaneous_debate.py
```

### Run Telegram Bot
```bash
cd v2_optimized
python telegram_bot.py
```

### Test Single Stock
```bash
cd v2_optimized
python data_collector.py  # Tests VCB
```

## Important Notes

1. **API Keys** - Store in config.py or environment variables
2. **Rate Limiting** - vnstock has rate limits, use caching
3. **Market Hours** - VN market: 9:00-11:30, 13:00-14:45 (UTC+7)
4. **Data Freshness** - Cache TTL varies by data type

## Agent Guidelines

### When Planning
- Focus on data pipeline stability
- Consider API rate limits
- Test with single stock before batch

### When Debugging
- Check cache first
- Verify API connectivity
- Review error logs in output/

### When Testing
- Test during market hours for real-time data
- Use mock data for unit tests
- Validate against known stock values

## File Restrictions

### Read-Only (Don't modify without asking)
- `config.py` - Configuration
- `*.json` in cache/ - Cached data

### Sensitive Files
- API keys in config.py
- Telegram bot token

## Current Development Focus

- Historical Data Tracking System (Phase 5 completed)
- Telegram Bot enhancement
- Win rate tracking & backtest reports
