

## Issue #10: Delta India Order Size Precision (2025-09-01)

**Problem**: Bot was sending 0.1 BTC directly to Delta, but Delta needs 100 lots (where 1 lot = 0.001 BTC).

**Error**: 'delta amount of BTC/USD:USD must be greater than minimum amount precision of 1'

**Fix**: Multiply POSITION_BTC_SIZE by 1000 to convert BTC to contract lots:
- orders/manager.py lines 489, 690
- execution.py lines 119, 145

```python
# Before:
amount = POSITION_BTC_SIZE  # 0.1 (rejected by Delta)

# After:
amount = int(POSITION_BTC_SIZE * 1000)  # 100 lots (accepted)
```

