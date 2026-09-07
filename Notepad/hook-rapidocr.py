from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files("rapidocr")
hiddenimports = ["rapidocr.main", "rapidocr.inference_engine.onnxruntime"]
excludedimports = [
    "torch",
    "torchvision",
    "triton",
    "paddle",
    "openvino",
    "tensorrt",
    "MNN",
    "rapidocr.inference_engine.pytorch",
    "rapidocr.inference_engine.paddle",
    "rapidocr.inference_engine.openvino",
    "rapidocr.inference_engine.tensorrt",
    "rapidocr.inference_engine.mnn",
]
