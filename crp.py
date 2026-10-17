#!/usr/bin/env python3
"""Entry point: python crp.py demo | python crp.py plan --csv customers.csv"""
import sys

from crp_cli import main

if __name__ == "__main__":
    sys.exit(main())
