# Contributing

Contributions are welcome through GitHub issues and pull requests.

1. Use synthetic data only in tests and examples.
2. Do not add cloud calls, telemetry, or external data transmission to the default local workflow.
3. Add tests for recognizer or protection changes.
4. Run `python -m pytest` before opening a pull request.
5. Describe false-positive and false-negative tradeoffs for new recognizers.

The browser demo is intentionally illustrative. Changes must not describe it as equivalent to the Microsoft Presidio desktop engine.
