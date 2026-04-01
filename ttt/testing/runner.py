"""Executor de testes para scripts OTServ."""

import os
import unittest
from dataclasses import dataclass
from typing import List


@dataclass
class TestRunReport:
    """Resumo de execução de testes."""

    tests_run: int = 0
    failures: int = 0
    errors: int = 0
    skipped: int = 0
    expected_failures: int = 0
    unexpected_successes: int = 0
    successful: bool = False

    @property
    def return_code(self) -> int:
        return 0 if self.successful else 1


def _to_report(result: unittest.TestResult) -> TestRunReport:
    return TestRunReport(
        tests_run=result.testsRun,
        failures=len(result.failures),
        errors=len(result.errors),
        skipped=len(getattr(result, "skipped", [])),
        expected_failures=len(getattr(result, "expectedFailures", [])),
        unexpected_successes=len(getattr(result, "unexpectedSuccesses", [])),
        successful=result.wasSuccessful(),
    )


def run_tests(
    test_path: str, pattern: str = "test*.py", verbosity: int = 2
) -> TestRunReport:
    """Executa testes para diretório ou arquivo e devolve relatório resumido."""
    loader = unittest.TestLoader()
    abs_path = os.path.abspath(test_path)

    if os.path.isdir(abs_path):
        suite = loader.discover(start_dir=abs_path, pattern=pattern)
    elif os.path.isfile(abs_path):
        suite = loader.discover(
            start_dir=os.path.dirname(abs_path),
            pattern=os.path.basename(abs_path),
        )
    else:
        raise FileNotFoundError(f"Test path not found: {test_path}")

    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    return _to_report(result)


def format_test_report(report: TestRunReport) -> str:
    """Formata relatório de execução em texto."""
    lines: List[str] = []
    lines.append("TTT Test Report")
    lines.append("=" * 32)
    lines.append(f"Tests run:            {report.tests_run}")
    lines.append(f"Failures:             {report.failures}")
    lines.append(f"Errors:               {report.errors}")
    lines.append(f"Skipped:              {report.skipped}")
    lines.append(f"Expected failures:    {report.expected_failures}")
    lines.append(f"Unexpected successes: {report.unexpected_successes}")
    lines.append(f"Status:               {'PASS' if report.successful else 'FAIL'}")
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="TTT Test Runner")
    parser.add_argument(
        "path", nargs="?", default="tests", help="Diretório ou arquivo de testes"
    )
    parser.add_argument("--pattern", default="test*.py", help="Padrão de descoberta")
    parser.add_argument("--quiet", action="store_true", help="Saída resumida")
    args = parser.parse_args()

    report = run_tests(
        args.path, pattern=args.pattern, verbosity=1 if args.quiet else 2
    )
    print(format_test_report(report))
    raise SystemExit(report.return_code)
