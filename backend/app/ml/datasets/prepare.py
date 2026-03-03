"""
Data Preparation Pipeline
Converts raw downloaded datasets into a unified text training CSV.

Handles multiple dataset formats:
- Image folders (OCR extraction)
- CSV datasets (text column extraction)
- Mixed datasets with nested category directories

Pipeline: Raw datasets → Category mapping → OCR/Text Extraction → train_data.csv

Usage:
    python -m app.ml.datasets.prepare
    python -m app.ml.datasets.prepare --max-per-category 500
    python -m app.ml.datasets.prepare --skip-ocr  # CSV-only mode (fast)
"""

import argparse
import csv
import os
import random
from pathlib import Path

import structlog

logger = structlog.stdlib.get_logger()

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
RAW_DIR = BASE_DIR / "datasets" / "raw"
TRAINING_DIR = BASE_DIR / "datasets" / "training"

CATEGORIES = ["bills", "upi", "tickets", "tax", "bank", "invoices"]
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"}


# ──── Dataset Processors ────
# Each processor knows how to extract (text, category) pairs from a specific dataset.

def process_financial_document_classification(raw_path: Path, max_per_cat: int) -> list[dict]:
    """Process the 87K image dataset (16 classes, RVL-CDIP style)."""
    rows = []
    # Map their folder names → our categories (only relevant ones)
    folder_map = {
        "invoice": "invoices",
        "budget": "bank",
    }

    for parent_dir in ["Financial_Data/Financial Data", "Financial_data_test/Financial_data_test"]:
        base = raw_path / parent_dir
        if not base.exists():
            continue

        for folder_name, our_category in folder_map.items():
            cat_dir = base / folder_name
            if not cat_dir.exists():
                # Try with underscore variants
                cat_dir = base / folder_name.replace(" ", "_")
                if not cat_dir.exists():
                    continue

            files = list(cat_dir.glob("*.*"))
            random.shuffle(files)
            files = files[:max_per_cat]

            for fpath in files:
                if fpath.suffix.lower() in IMAGE_EXTS:
                    rows.append({"file": fpath, "category": our_category, "source": "financial-doc-classification"})

    logger.info("dataset_mapped", name="financial-document-classification", samples=len(rows))
    return rows


def process_financial_images_india(raw_path: Path, max_per_cat: int) -> list[dict]:
    """Process Indian financial document images (426 images, 5 classes)."""
    rows = []
    folder_map = {
        "Bank Statement": "bank",
        "Check": "bank",
        "ITR_Form 16": "tax",
        "Salary Slip": "bank",
        "Utility": "bills",
    }

    for folder_name, our_category in folder_map.items():
        cat_dir = raw_path / folder_name
        if not cat_dir.exists():
            continue

        files = list(cat_dir.glob("*.*"))
        random.shuffle(files)
        files = files[:max_per_cat]

        for fpath in files:
            if fpath.suffix.lower() in IMAGE_EXTS:
                rows.append({"file": fpath, "category": our_category, "source": "financial-images-india"})

    logger.info("dataset_mapped", name="financial-images-india", samples=len(rows))
    return rows


def process_invoice_ocr(raw_path: Path, max_per_cat: int) -> list[dict]:
    """Process invoice OCR images (8K images, all invoices)."""
    rows = []
    files = []
    for batch_dir in raw_path.glob("batch_*"):
        if batch_dir.is_dir():
            files.extend([f for f in batch_dir.glob("*.*") if f.suffix.lower() in IMAGE_EXTS])

    random.shuffle(files)
    files = files[:max_per_cat]

    for fpath in files:
        rows.append({"file": fpath, "category": "invoices", "source": "invoice-ocr"})

    logger.info("dataset_mapped", name="invoice-ocr", samples=len(rows))
    return rows


def process_rvl_cdip(raw_path: Path, max_per_cat: int) -> list[dict]:
    """Process RVL-CDIP test set (40K tif images, 16 classes)."""
    rows = []
    folder_map = {
        "invoice": "invoices",
        "budget": "bank",
    }

    test_dir = raw_path / "test"
    if not test_dir.exists():
        return rows

    for folder_name, our_category in folder_map.items():
        cat_dir = test_dir / folder_name
        if not cat_dir.exists():
            continue

        files = list(cat_dir.glob("*.*"))
        random.shuffle(files)
        files = files[:max_per_cat]

        for fpath in files:
            if fpath.suffix.lower() in IMAGE_EXTS | {".tif"}:
                rows.append({"file": fpath, "category": our_category, "source": "rvl-cdip"})

    logger.info("dataset_mapped", name="rvl-cdip", samples=len(rows))
    return rows


def process_ocr_multi_type(raw_path: Path, max_per_cat: int) -> list[dict]:
    """Process OCR multi-type documents dataset."""
    rows = []
    folder_map = {
        "invoice": "invoices",
        "form": None,  # skip - not relevant
        "document": None,
        "real_life": "bills",
    }

    for folder_name, our_category in folder_map.items():
        if our_category is None:
            continue
        cat_dir = raw_path / folder_name
        if not cat_dir.exists():
            continue

        files = []
        for root, dirs, fnames in os.walk(cat_dir):
            for fn in fnames:
                fpath = Path(root) / fn
                if fpath.suffix.lower() in IMAGE_EXTS:
                    files.append(fpath)

        random.shuffle(files)
        files = files[:max_per_cat]

        for fpath in files:
            rows.append({"file": fpath, "category": our_category, "source": "ocr-multi-type"})

    logger.info("dataset_mapped", name="ocr-multi-type", samples=len(rows))
    return rows


def process_upi_csv(raw_path: Path, csv_name: str, max_per_cat: int) -> list[dict]:
    """Process UPI transaction CSVs → generate text descriptions for training."""
    rows = []
    csv_path = raw_path / csv_name
    if not csv_path.exists():
        return rows

    try:
        with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            all_rows = list(reader)

        random.shuffle(all_rows)

        for row in all_rows[:max_per_cat]:
            # Build a text description from the CSV columns
            parts = []
            for key, value in row.items():
                if value and value.strip():
                    clean_key = key.strip().replace("\ufeff", "")
                    parts.append(f"{clean_key} {value.strip()}")

            text = " ".join(parts)
            if len(text) > 20:
                # Prefix with UPI context
                text = f"upi transaction payment {text}"
                rows.append({"text": text, "category": "upi", "source": f"upi-csv-{csv_name}"})

    except Exception as e:
        logger.warning("csv_processing_failed", path=str(csv_path), error=str(e))

    logger.info("dataset_mapped", name=f"upi-csv-{csv_name}", samples=len(rows))
    return rows


def process_bank_statements_csv(raw_path: Path, max_per_cat: int) -> list[dict]:
    """Process bank statements CSV → generate text descriptions."""
    rows = []
    csv_path = raw_path / "bankstatements.csv"
    if not csv_path.exists():
        return rows

    try:
        with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            all_rows = list(reader)

        random.shuffle(all_rows)

        for row in all_rows[:max_per_cat]:
            parts = []
            for key, value in row.items():
                if value and value.strip():
                    parts.append(f"{key} {value.strip()}")

            text = " ".join(parts)
            if len(text) > 20:
                text = f"bank statement account transaction {text}"
                rows.append({"text": text, "category": "bank", "source": "bank-statements-csv"})

    except Exception as e:
        logger.warning("csv_processing_failed", path=str(csv_path), error=str(e))

    logger.info("dataset_mapped", name="bank-statements", samples=len(rows))
    return rows


def extract_text_from_file(file_path: Path) -> str:
    """Extract text from an image/document file using existing extractors."""
    ext = file_path.suffix.lower()

    try:
        with open(file_path, "rb") as f:
            file_bytes = f.read()

        if ext == ".pdf":
            from app.ml.pdf_extractor import extract_text_from_pdf
            return extract_text_from_pdf(file_bytes)
        elif ext == ".docx":
            from app.ml.docx_extractor import extract_text_from_docx
            return extract_text_from_docx(file_bytes)
        elif ext in IMAGE_EXTS | {".tif"}:
            from app.ml.ocr import extract_text_from_image
            return extract_text_from_image(file_bytes)
        else:
            return ""

    except Exception as e:
        logger.warning("extraction_failed", path=str(file_path), error=str(e))
        return ""


def prepare_training_data(max_per_category: int = 300, min_text_length: int = 20, skip_ocr: bool = False) -> Path | None:
    """
    Process all raw datasets into a unified training CSV.

    Args:
        max_per_category: Max samples per category per dataset source
        min_text_length: Minimum extracted text length to keep
        skip_ocr: If True, only process CSV datasets (fast mode)
    """
    if not RAW_DIR.exists():
        logger.error("raw_dir_not_found", path=str(RAW_DIR))
        logger.info("hint", message="Run 'python -m app.ml.datasets.download' first")
        return None

    TRAINING_DIR.mkdir(parents=True, exist_ok=True)
    output_path = TRAINING_DIR / "train_data.csv"

    random.seed(42)
    all_items = []  # Items with files to OCR
    csv_rows = []   # Pre-extracted text from CSVs

    # ── Collect image items from each dataset ──
    logger.info("step", step="1/3", action="mapping_datasets")

    ds_dir = RAW_DIR / "financial-document-classification"
    if ds_dir.exists() and not skip_ocr:
        all_items.extend(process_financial_document_classification(ds_dir, max_per_category))

    ds_dir = RAW_DIR / "financial-images-india"
    if ds_dir.exists() and not skip_ocr:
        all_items.extend(process_financial_images_india(ds_dir, max_per_category))

    ds_dir = RAW_DIR / "invoice-ocr"
    if ds_dir.exists() and not skip_ocr:
        all_items.extend(process_invoice_ocr(ds_dir, max_per_category))
    # Also check alternate name
    ds_dir = RAW_DIR / "high-quality-invoice-images-for-ocr"
    if ds_dir.exists() and not skip_ocr:
        all_items.extend(process_invoice_ocr(ds_dir, max_per_category))

    ds_dir = RAW_DIR / "rvl-cdip"
    if ds_dir.exists() and not skip_ocr:
        all_items.extend(process_rvl_cdip(ds_dir, max_per_category))

    ds_dir = RAW_DIR / "ocr-dataset-of-multi-type-documents"
    if ds_dir.exists() and not skip_ocr:
        all_items.extend(process_ocr_multi_type(ds_dir, max_per_category))

    # ── CSV datasets (no OCR needed) ──
    ds_dir = RAW_DIR / "upi-transactions-2024"
    if ds_dir.exists():
        csv_rows.extend(process_upi_csv(ds_dir, "upi_transactions_2024.csv", max_per_category))

    ds_dir = RAW_DIR / "upi-transactions"
    if ds_dir.exists():
        csv_rows.extend(process_upi_csv(ds_dir, "MyTransaction.csv", max_per_category))

    ds_dir = RAW_DIR / "bank-statements"
    if ds_dir.exists():
        csv_rows.extend(process_bank_statements_csv(ds_dir, max_per_category))

    logger.info(
        "datasets_mapped",
        image_items=len(all_items),
        csv_rows=len(csv_rows),
    )

    # ── OCR extraction from images ──
    logger.info("step", step="2/3", action="extracting_text_from_images")
    stats = {cat: {"total": 0, "extracted": 0, "skipped": 0} for cat in CATEGORIES}
    training_rows = []

    for i, item in enumerate(all_items):
        category = item["category"]
        stats[category]["total"] += 1

        if (i + 1) % 25 == 0:
            logger.info("ocr_progress", processed=i + 1, total=len(all_items))

        text = extract_text_from_file(item["file"])

        if not text or len(text.strip()) < min_text_length:
            stats[category]["skipped"] += 1
            continue

        training_rows.append({
            "text": text.strip(),
            "category": category,
            "source_file": item.get("source", "") + "/" + item["file"].name,
        })
        stats[category]["extracted"] += 1

    # Add CSV rows
    for row in csv_rows:
        category = row["category"]
        stats[category]["total"] = stats[category].get("total", 0) + 1
        stats[category]["extracted"] = stats[category].get("extracted", 0) + 1
        training_rows.append({
            "text": row["text"],
            "category": category,
            "source_file": row.get("source", "csv"),
        })

    # ── Write output CSV ──
    logger.info("step", step="3/3", action="writing_training_csv")
    random.shuffle(training_rows)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["text", "category", "source_file"])
        writer.writeheader()
        writer.writerows(training_rows)

    # ── Summary ──
    print("\n" + "=" * 60)
    print("Data Preparation Summary")
    print("=" * 60)
    for cat in CATEGORIES:
        s = stats[cat]
        bar = "█" * min(s["extracted"] // 5, 30)
        print(f"  {cat:<12}  total={s['total']:>5}  extracted={s['extracted']:>5}  skipped={s['skipped']:>5}  {bar}")
    print(f"\n  Total training samples: {len(training_rows)}")
    print(f"  Output: {output_path}")
    print("=" * 60)

    logger.info(
        "preparation_complete",
        total_samples=len(training_rows),
        output=str(output_path),
    )

    return output_path


def main():
    parser = argparse.ArgumentParser(description="Prepare training data from downloaded datasets")
    parser.add_argument("--max-per-category", type=int, default=300,
                        help="Max samples per category per dataset (default: 300)")
    parser.add_argument("--min-text-length", type=int, default=20,
                        help="Minimum extracted text length (default: 20)")
    parser.add_argument("--skip-ocr", action="store_true",
                        help="Skip OCR, only process CSV datasets (fast)")
    args = parser.parse_args()

    prepare_training_data(
        max_per_category=args.max_per_category,
        min_text_length=args.min_text_length,
        skip_ocr=args.skip_ocr,
    )


if __name__ == "__main__":
    main()
