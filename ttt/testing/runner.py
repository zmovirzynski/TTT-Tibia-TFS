"""
Executor de testes para scripts OTServ.
"""
import unittest
import sys
import os

def run_tests(test_path):
    """Executa todos os testes unitários no diretório especificado."""
    loader = unittest.TestLoader()
    suite = loader.discover(test_path)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="TTT Test Runner")
    parser.add_argument("path", help="Diretório ou arquivo de testes")
    args = parser.parse_args()
    run_tests(args.path)
