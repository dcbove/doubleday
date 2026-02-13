"""Tests for main module."""

from doubleday.main import main


def test_main_runs_without_error():
    """Test that main() executes without raising an exception."""
    # This is a trivial test - main() should run successfully
    try:
        main()
    except Exception as e:
        raise AssertionError(f"main() raised an exception: {e}") from e


def test_main_exists():
    """Test that main function exists and is callable."""
    assert callable(main), "main should be a callable function"
