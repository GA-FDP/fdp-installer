#!/bin/bash
set -e
source /app/activate.sh
echo "bin/fdp resolves to: $(readlink -f "$(command -v fdp)")"
if fdp -V 2>&1 | grep -qi "graphviz"; then
    echo "ERROR: bin/fdp is graphviz's binary, not the FDP CLI."
    exit 1
fi
fdp --help | grep -qE "\brun\b" || {
    echo "ERROR: 'fdp --help' is not the FDP CLI:"; fdp --help | head -5; exit 1; }
python -m fdp --help > /dev/null
python -c "import toksearch, toksearch_d3d, toksearch_mast, fdp, imas_composer, cmflib, toksearch_cmf, toksearch.llm.mcp"
fdp device list
echo "OK: image self-check passed"
