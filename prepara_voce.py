"""Explicit online preparation; capture never performs this download."""
from pathlib import Path
import sys


def main():
    try:
        from faster_whisper import WhisperModel
        from faster_whisper.utils import download_model
    except ImportError:
        print("Esegui prima INSTALLA_AUDIO.bat.")
        return 1
    destination = Path(__file__).resolve().parent / "models" / "whisper-base"
    print("Scarico il modello multilingue base da Hugging Face.")
    print("Serve Internet. Nessun audio viene acquisito o inviato.")
    try:
        download_model("base", output_dir=str(destination))
        model = WhisperModel(str(destination), device="cpu", compute_type="int8", local_files_only=True)
        del model
    except Exception as exc:
        print(f"Preparazione fallita: {exc}")
        return 1
    print("Modello verificato e pronto per l'uso locale.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
