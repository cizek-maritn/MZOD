conda deactivate
source .venv/bin/activate
export QT_QPA_PLATFORM_PLUGIN_PATH="$(python -c 'import PyQt5, os; print(os.path.join(os.path.dirname(PyQt5.__file__), "Qt5", "plugins", "platforms"))')"
python ./main.py
