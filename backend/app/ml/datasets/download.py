"""
Dataset Download Script
Downloads and organizes training datasets from Kaggle for document classification.

Usage:
    # Download all datasets:
    python -m app.ml.datasets.download

    # Download specific dataset:
    python -m app.ml.datasets.download --dataset financial-docs

    # List available datasets:
    python -m app.ml.datasets.download --list

Prerequisites:
    pip install kaggle
    Set KAGGLE_USERNAME and KAGGLE_KEY env vars, or place kaggle.json in ~/.kaggle/
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

import structlog

logger = structlog.stdlib.get_logger()

# Base directory for all datasets
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent  # backend/
DATASETS_DIR = BASE_DIR / "datasets"
RAW_DIR = DATASETS_DIR / "raw"
PROCESSED_DIR = DATASETS_DIR / "processed"

# ──── Dataset Registry ────
# Maps dataset names to Kaggle dataset slugs and category mappings.
# category_map: maps source folder/label names → our 6 project categories

DATASET_REGISTRY = {
    "rvl-cdip": {
        "kaggle_slug": "pdavpoojan/the-rvlcdip-dataset-test",
        "description": "RVL-CDIP Document Classification (400K docs, 16 classes)",
        "category_map": {
            "letter": None,
            "form": None,
            "email": None,
            "handwritten": None,
            "advertisement": None,
            "scientific_report": None,
            "scientific_publication": None,
            "specification": None,
            "file_folder": None,
            "news_article": None,
            "budget": "bank",
            "invoice": "invoices",
            "presentation": None,
            "questionnaire": None,
            "resume": None,
            "memo": None,
        },
    },
    "financial-doc-classification": {
        "kaggle_slug": "swatigupta555/financial-document-classification",
        "description": "Financial Document Classification - Indian documents",
        "category_map": {
            "invoice": "invoices",
            "invoices": "invoices",
            "bill": "bills",
            "bills": "bills",
            "receipt": "bills",
            "receipts": "bills",
            "bank_statement": "bank",
            "bank": "bank",
            "tax": "tax",
            "tax_form": "tax",
            "ticket": "tickets",
            "tickets": "tickets",
            "upi": "upi",
            "payment": "upi",
        },
    },
    "financial-images-india": {
        "kaggle_slug": "mehaksingal/personal-financial-dataset-for-india",
        "description": "Financial Document Image Dataset for India",
        "category_map": {
            "invoice": "invoices",
            "bill": "bills",
            "receipt": "bills",
            "bank_statement": "bank",
            "cheque": "bank",
            "tax_document": "tax",
            "pan_card": "tax",
            "aadhar": "tax",
        },
    },
    "invoice-ocr": {
        "kaggle_slug": "osamahosamabdellatif/high-quality-invoice-images-for-ocr",
        "description": "High-Quality Invoice Images for OCR",
        "category_map": {
            "invoice": "invoices",
            "default": "invoices",
        },
    },
    "upi-transactions-2024": {
        "kaggle_slug": "skullagos5246/upi-transactions-2024-dataset",
        "description": "UPI Transactions 2024 Dataset",
        "category_map": {
            "default": "upi",
        },
        "type": "csv",
    },
    "upi-transactions": {
        "kaggle_slug": "bijitda/upi-transactions-dataset",
        "description": "UPI Transactions Dataset",
        "category_map": {
            "default": "upi",
        },
        "type": "csv",
    },
    "bank-statements": {
        "kaggle_slug": "abutalhadmaniyar/bank-statements-dataset",
        "description": "Bank Statements Dataset",
        "category_map": {
            "default": "bank",
        },
    },
}


def ensure_kaggle_api():
    """Check that kaggle API is available and authenticated."""
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi

        api = KaggleApi()
        api.authenticate()
        return api
    except ImportError:
        logger.error(
            "kaggle_not_installed",
            help="Install with: pip install kaggle",
        )
        sys.exit(1)
    except Exception as e:
        logger.error(
            "kaggle_auth_failed",
            error=str(e),
            help=(
                "Set KAGGLE_USERNAME and KAGGLE_KEY environment variables, "
                "or place kaggle.json in ~/.kaggle/"
            ),
        )
        sys.exit(1)


def download_dataset(api, dataset_name: str) -> Path | None:
    """Download a single dataset from Kaggle."""
    if dataset_name not in DATASET_REGISTRY:
        logger.error("unknown_dataset", name=dataset_name, available=list(DATASET_REGISTRY.keys()))
        return None

    info = DATASET_REGISTRY[dataset_name]
    dest = RAW_DIR / dataset_name

    if dest.exists() and any(dest.iterdir()):
        logger.info("dataset_already_downloaded", name=dataset_name, path=str(dest))
        return dest

    dest.mkdir(parents=True, exist_ok=True)
    logger.info("downloading_dataset", name=dataset_name, slug=info["kaggle_slug"])

    try:
        api.dataset_download_files(info["kaggle_slug"], path=str(dest), unzip=True)
        logger.info("download_complete", name=dataset_name, path=str(dest))
        return dest
    except Exception as e:
        logger.error("download_failed", name=dataset_name, error=str(e))
        return None


def organize_dataset(dataset_name: str) -> dict[str, int]:
    """
    Organize raw downloaded dataset into processed category folders.
    Returns count of files per category.
    """
    if dataset_name not in DATASET_REGISTRY:
        return {}

    info = DATASET_REGISTRY[dataset_name]
    raw_path = RAW_DIR / dataset_name
    category_map = info["category_map"]

    if not raw_path.exists():
        logger.error("raw_data_not_found", name=dataset_name, path=str(raw_path))
        return {}

    counts = {}
    image_exts = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".pdf"}

    # Walk raw directory looking for image/document files
    for root, dirs, files in os.walk(raw_path):
        # Determine source category from directory name
        dir_name = Path(root).name.lower().replace(" ", "_").replace("-", "_")

        # Map to our category
        target_category = category_map.get(dir_name)

        # Try "default" mapping if no specific mapping found
        if target_category is None and "default" in category_map:
            target_category = category_map["default"]

        # Skip if category not mapped or explicitly set to None
        if target_category is None:
            continue

        # Create target directory
        target_dir = PROCESSED_DIR / target_category
        target_dir.mkdir(parents=True, exist_ok=True)

        # Copy relevant files
        for fname in files:
            ext = Path(fname).suffix.lower()
            if ext in image_exts:
                src = Path(root) / fname
                # Prefix with dataset name to avoid conflicts
                dest = target_dir / f"{dataset_name}_{fname}"
                if not dest.exists():
                    shutil.copy2(src, dest)
                    counts[target_category] = counts.get(target_category, 0) + 1

    logger.info("dataset_organized", name=dataset_name, counts=counts)
    return counts


def list_datasets():
    """Print available datasets."""
    print("\nAvailable Datasets:")
    print("=" * 70)
    for name, info in DATASET_REGISTRY.items():
        raw_path = RAW_DIR / name
        status = "Downloaded" if raw_path.exists() and any(raw_path.iterdir()) else "Not downloaded"
        print(f"  {name:<25} [{status}]")
        print(f"    Kaggle: {info['kaggle_slug']}")
        print(f"    {info['description']}")
        print()

    # Show processed stats
    if PROCESSED_DIR.exists():
        print("Processed Data:")
        print("-" * 40)
        for cat_dir in sorted(PROCESSED_DIR.iterdir()):
            if cat_dir.is_dir():
                count = len(list(cat_dir.iterdir()))
                print(f"  {cat_dir.name:<15} {count:>5} files")
        print()


def download_all():
    """Download and organize all registered datasets."""
    api = ensure_kaggle_api()

    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    total_counts = {}

    for name in DATASET_REGISTRY:
        path = download_dataset(api, name)
        if path:
            counts = organize_dataset(name)
            for cat, count in counts.items():
                total_counts[cat] = total_counts.get(cat, 0) + count

    logger.info("all_datasets_processed", total_counts=total_counts)

    # Print summary
    print("\n" + "=" * 50)
    print("Dataset Download Summary")
    print("=" * 50)
    for cat in ["bills", "upi", "tickets", "tax", "bank", "invoices"]:
        count = total_counts.get(cat, 0)
        bar = "#" * min(count // 10, 30)
        print(f"  {cat:<12} {count:>5} files  {bar}")
    print(f"\n  Total: {sum(total_counts.values())} files")
    print(f"  Location: {PROCESSED_DIR}")


def main():
    parser = argparse.ArgumentParser(description="Download training datasets for document classifier")
    parser.add_argument("--dataset", type=str, help="Download specific dataset by name")
    parser.add_argument("--list", action="store_true", help="List available datasets")
    parser.add_argument("--organize-only", action="store_true", help="Re-organize already downloaded data")
    args = parser.parse_args()

    if args.list:
        list_datasets()
        return

    if args.organize_only:
        for name in DATASET_REGISTRY:
            organize_dataset(name)
        list_datasets()
        return

    if args.dataset:
        api = ensure_kaggle_api()
        os.makedirs(RAW_DIR, exist_ok=True)
        os.makedirs(PROCESSED_DIR, exist_ok=True)
        path = download_dataset(api, args.dataset)
        if path:
            organize_dataset(args.dataset)
        return

    download_all()


if __name__ == "__main__":
    main()
