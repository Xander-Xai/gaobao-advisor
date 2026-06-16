#!/bin/bash
# Run mypy type checking with strict mode
# Usage: ./scripts/type_check.sh [--watch]

set -euo pipefail

echo "Running mypy type checker (strict mode)..."
echo ""

# Check if mypy is installed
if ! command -v mypy &> /dev/null; then
    echo "Installing mypy..."
    pip install mypy types-redis
fi

# Run mypy
if [[ "${1:-}" == "--watch" ]]; then
    # Watch mode (requires watchfiles)
    pip install watchfiles -q
    echo "Watching for changes... (Ctrl+C to stop)"
    watchfiles 'mypy server/ db/ slots/ quality/ config/' --pattern '*.py'
else
    # One-time check
    mypy server/ db/ slots/ quality/ config/ \
        --config-file mypy.ini \
        --show-error-codes \
        --pretty
    
    EXIT_CODE=$?
    
    echo ""
    if [ $EXIT_CODE -eq 0 ]; then
        echo "✅ Type checking passed!"
    else
        echo "❌ Type checking failed. Fix the errors above."
        echo ""
        echo "Common fixes:"
        echo "  - Add type hints to function parameters and return values"
        echo "  - Use Optional[] for nullable values"
        echo "  - Use Union[] for multiple types"
        echo "  - Add # type: ignore for third-party libraries without stubs"
    fi
    
    exit $EXIT_CODE
fi
