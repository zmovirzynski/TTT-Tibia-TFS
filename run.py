#!/usr/bin/env python3
"""
TTT - Tibia TFS Transpiler
Run this file to start the converter.

Usage:
    Interactive:  python run.py
    CLI:          python run.py -i ./data -o ./output -f tfs03 -t tfs1x
"""

from ttt.main import main

if __name__ == "__main__":
    main()
