#!/bin/zsh
cd "${0:A:h}"
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv || exit 1
  .venv/bin/pip install -r mark1/requirements.txt || exit 1
fi
cd mark1
../.venv/bin/python app.py
