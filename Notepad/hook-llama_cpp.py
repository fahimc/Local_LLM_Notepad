from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

datas = collect_data_files("llama_cpp")
binaries = collect_dynamic_libs("llama_cpp")

# To compile, run the following: 
# pyinstaller --onefile --noconsole --additional-hooks-dir=. main.py
