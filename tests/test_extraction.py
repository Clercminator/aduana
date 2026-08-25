import json
import random
import shutil
from pathlib import Path

from app.llm.classify import classify_text
from app.llm.local_extract import extract_local, pdf_text

ROOT = Path(__file__).parents[1]


def _simple(payload, path):
    current = payload
    for part in path.split("."):
        current = current[int(part)] if part.isdigit() else current[part]
    return current


def test_all_sixteen_pdfs_match_critical_ground_truth():
    truth = json.loads(
        (ROOT / "fixtures" / "EXTRACTION_GROUND_TRUTH.json").read_text(encoding="utf-8")
    )
    count = 0
    for folder, documents in truth.items():
        for filename, expected in documents.items():
            path = ROOT / "fixtures" / folder / filename
            parsed = extract_local(path).model_dump(mode="json")
            assert parsed["doc_type"] == expected["doc_type"]
            serialized = json.dumps(parsed, ensure_ascii=False)
            for value in expected["fields"].values():
                if isinstance(value, list):
                    assert all(str(item) in serialized for item in value)
                elif isinstance(value, bool):
                    assert str(value).lower() in serialized
                else:
                    assert str(value) in serialized
            assert expected["source_text"] in (pdf_text(path)[0])
            count += 1
    assert count == 16


def test_classifier_uses_content_not_filenames(tmp_path):
    paths = list((ROOT / "fixtures" / "scenario_A_clean").glob("*.pdf"))
    random.Random(42).shuffle(paths)
    for index, path in enumerate(paths):
        randomized = tmp_path / f"archivo-aleatorio-{(index * 7919) % 100003}.pdf"
        shutil.copyfile(path, randomized)
        text, _, _ = pdf_text(randomized)
        doc_type, signature = classify_text(text)
        assert doc_type.value != "unknown", f"random-{index}.pdf"
        assert signature
