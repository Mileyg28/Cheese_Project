#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    env = os.getenv('DJANGO_ENV', 'local')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', f'config.settings.{env}')

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()