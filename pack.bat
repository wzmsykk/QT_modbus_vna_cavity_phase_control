set PYTHONPATH=.\imports;%PYTHONPATH%
nuitka --jobs=8 --msvc=latest --onefile --standalone --enable-plugin=pyqt5,implicit-imports --follow-imports --include-plugin-directory=imports --include-data-files=data/CONVERTF.EXE=data/CONVERTF.EXE  main.py 
pause