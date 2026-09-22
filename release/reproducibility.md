# Reproduction Guide

To reproduce all experiments, tables, models, and figures from scratch:

```bash
# 1. Check environment and dependencies
python scripts/check_environment.py

# 2. Verify model artifacts and schemas
python scripts/verify_artifacts.py

# 3. Run complete reproduction pipeline (Stages 1 through 5)
python scripts/reproduce.py --all

# 4. Validate all headline research claims
python scripts/validate_research_claims.py

# 5. Run full test suite
python -m unittest discover -s tests -p "test_*.py" -v
```
