"""
ML Model Training Script
Trains document classifiers using real datasets + synthetic augmentation.

Usage:
    # Train with real dataset (if available) + synthetic fallback:
    python -m app.ml.train

    # Train with synthetic data only (original behavior):
    python -m app.ml.train --synthetic-only

    # Train with real data only (requires datasets to be downloaded):
    python -m app.ml.train --real-only

    # Full pipeline: download → prepare → train:
    python -m app.ml.train --full-pipeline
"""

import argparse
import csv
import json
import os
import random
from pathlib import Path

import joblib
import numpy as np
import structlog
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import MultinomialNB
from sklearn.svm import LinearSVC
from sklearn.model_selection import train_test_split, GridSearchCV, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score

from app.config import settings
from app.ml.text_preprocessor import clean_text

logger = structlog.stdlib.get_logger()

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/
TRAINING_CSV = BASE_DIR / "datasets" / "training" / "train_data.csv"
EVAL_DIR = BASE_DIR / "models" / "evaluation"

# --- Synthetic Training Data ------------------------------------------------
# Fallback data for when real datasets aren't available.

SYNTHETIC_DATA = {
    "bills": [
        "electricity bill payment due date amount kwh units consumed meter reading billing period customer account power supply company tariff charges",
        "water bill monthly charges consumption gallons cubic meter utility municipal corporation sewage charges due date payment",
        "gas bill natural gas consumption therms billing cycle customer account charges fuel cost delivery charges total amount due",
        "telephone bill mobile charges data usage call minutes sms international roaming plan monthly rental amount payable",
        "internet bill broadband charges monthly subscription speed mbps data limit usage statement billing period due date",
        "electricity bill rupees_amount total charges energy consumption previous reading current reading units rate per unit",
        "mobile recharge bill plan details validity days data gb calling minutes sms benefits renewal date operator",
        "cable tv bill entertainment package channels subscription monthly charges premium channels hd service set top box",
        "bill amount total due payment charges service tax applicable period consumption reading meter account number customer",
        "grocery bill supermarket items quantity price total mrp discount savings store receipt purchase date",
        "medical bill hospital charges consultation fee medicines lab tests diagnosis treatment patient name doctor prescription",
        "repair bill service charges labor parts warranty technician complaint number device serial workshop authorized center",
        "utility bill statement account customer charges amount due date late penalty previous balance current period",
        "broadband internet bill connection speed plan charges router rental installation service provider account payment",
        "electricity consumption bill unit rate slab tariff meter reading previous current difference energy charge fixed charge",
        "monthly bill summary total outstanding amount minimum due credit charges interest finance applicable taxes gst",
        "dtd direct to home satellite television monthly subscription package channels amount statement period due date",
        "recurring bill subscription service monthly annually charged auto renewal payment method card ending expiry",
        "bill payment receipt transaction successful amount reference number merchant biller payee date time status confirmed",
        "club membership bill annual charges facility usage gym swimming pool locker room maintenance dues payable",
    ],
    "upi": [
        "upi transaction payment sent received upi_id merchant transfer amount rupees_amount successful completed reference number",
        "google pay payment to merchant store scan qr code amount debited from bank account upi reference transaction id",
        "phonepe transaction money sent to contact person amount rupees_amount debit account bank name upi reference number time",
        "paytm payment wallet transfer to bank upi_id amount rupees_amount transaction successful cashback earned reward points",
        "upi payment request received from person amount accept decline pending expiry time bank account linked",
        "bhim upi transfer beneficiary name bank account ifsc amount rupees_amount status successful transaction reference",
        "amazon pay upi payment order purchase amount debit account cashback offer applied merchant amazon seller",
        "upi autopay mandate registered merchant subscription amount frequency monthly debit date bank account linked",
        "upi transaction failed amount rupees_amount error code bank server timeout retry payment contact bank reference",
        "money received via upi sender name bank amount rupees_amount credited account balance transaction reference number",
        "upi collect request merchant name amount rupees_amount pay decline pending validity bank account approve",
        "upi lite small value transaction enabled balance amount last transaction merchant offline payment mode",
        "daily upi transaction summary total sent received count transactions amount today week month history",
        "split bill upi payment group expense shared amount per person total participants merchant restaurant",
        "refund processed via upi original transaction amount rupees_amount credit account reference merchant return order",
        "upi id registered bank account linked verification completed primary secondary payment method default",
        "scan pay qr code merchant store upi payment amount rupees_amount debit confirmation receipt download",
        "upi international payment remittance cross border transfer amount currency exchange rate beneficiary country",
        "upi payment notification alert debit amount from account balance remaining transaction merchant time",
        "recurring upi autopay subscription streaming music platform amount monthly debit date next payment schedule",
    ],
    "tickets": [
        "flight ticket boarding pass passenger name airline departure arrival terminal gate seat confirmed booking reference pnr",
        "train ticket irctc booking pnr status passenger name train number coach seat berth station departure arrival date",
        "bus ticket booking passenger route departure arrival seat number platform boarding time operator service",
        "movie ticket booking cinema hall screen show time seats row food order amount confirmed barcode",
        "event ticket concert festival venue date time entry gate pass vip general admission seat section",
        "cricket match ticket stadium ipl test series seat stand gate entry date team versus price",
        "parking ticket violation fine amount vehicle number location date time officer meter expired zone",
        "ferry boat ticket passenger route departure arrival deck seat cabin vehicle class fare amount",
        "museum ticket entry admission visitor adult child student senior group guided tour date time",
        "theme park ticket entry wristband ride access fast pass single day annual valid date",
        "conference seminar ticket registration attendee event date venue session speaker schedule amount receipt",
        "lottery ticket draw number serial purchased date time prize winning amount retailer state government",
        "support ticket customer complaint reference number status open resolved pending priority agent assigned category",
        "airline e-ticket itinerary passenger flight booking confirmation pnr departure return baggage class economy business",
        "metro rail ticket journey station origin destination fare token card recharge balance trip single return",
        "water park ticket entry pass visitor pool slide wave ride locker amount date timing batch",
        "zoo ticket entry visitor adult child camcra fee battery vehicle safari guide map schedule timing",
        "sports event ticket match stadium section row seat gate entry team league tournament season date",
        "theatre ticket play drama show performance date time auditorium seat row stall balcony orchestra",
        "travel booking ticket itinerary passenger reservation confirmed journey departure arrival class fare accommodation hotel",
    ],
    "tax": [
        "income tax return itr filing assessment year pan_number gross income deductions section 80c taxable net tax",
        "gst return filing gst_number input credit output tax igst cgst sgst quarterly monthly annual return",
        "tax deducted source tds certificate form 16 employer salary pan_number financial year tax deduction amount",
        "property tax assessment notice municipal corporation land building area value annual payment due date",
        "form 26as tax credit statement annual information pan_number tds tcs advance tax self assessment refund",
        "income tax notice demand assessment officer jurisdiction pan_number amount payable response deadline appeal",
        "advance tax payment challan amount quarter due date pan_number bank branch bsr code receipt",
        "capital gains tax long term short term equity mutual fund property sale purchase cost acquisition",
        "professional tax registration certificate employer employee state annual payment challan enrollment number",
        "gst invoice tax supply goods services hsn sac code taxable value cgst sgst igst cess total",
        "tax planning investment proof submission declaration hra lta mediclaim ppf nps section 80d deduction",
        "tax audit report form 3cd 3ca chartered accountant turnover profit loss balance sheet assessment",
        "stamp duty registration property purchase sale agreement value market government rate payment receipt",
        "tax refund processed credited bank account assessment year amount interest section overpayment intimation",
        "wealth tax net taxable assets valuation date individual huf company return filing assessment",
        "service tax registration number invoice value taxable exempt abatement cenvat credit payment challan",
        "tax exemption certificate section charitable trust educational institution research donation deduction approved",
        "customs duty import export goods declaration bill entry assessment tariff rate cess countervailing",
        "income tax computation gross total income salary house property capital gains other sources business profession",
        "pan card application correction details name date birth father address photo signature documents submitted",
    ],
    "bank": [
        "bank statement account number transaction history debit credit balance opening closing period branch ifsc",
        "savings account statement monthly quarterly transactions deposits withdrawals interest earned average balance minimum",
        "fixed deposit receipt account holder principal amount interest rate tenure maturity date bank branch nominee",
        "loan statement emi payment outstanding principal interest balance tenure remaining prepayment foreclosure charges",
        "credit card statement billing cycle transactions purchases payments dues minimum outstanding interest charges annual fee",
        "bank passbook entry date narration withdrawal deposit balance cheque transfer atm cash branch reference",
        "account opening form kyc documents identity proof address proof photograph signature nominee pan_number aadhaar",
        "demand draft application amount payee bank branch commission charges favour payable at account holder",
        "cheque book request account holder number starting series leaves branch delivery collection acknowledgement",
        "neft rtgs imps transfer transaction reference amount beneficiary name account ifsc bank date time status",
        "atm cash withdrawal transaction slip amount card number date time location branch machine id balance",
        "home loan application property details income salary employer emi tenure interest rate processing fee",
        "demat account statement holdings portfolio shares securities mutual fund units dividend bonus split",
        "bank guarantee letter credit amount beneficiary applicant issuing advising confirming validity expiry terms",
        "recurring deposit account monthly installment maturity amount interest rate tenure auto debit instructions",
        "personal loan sanction letter amount disbursed emi tenure interest rate processing fee insurance premium",
        "overdraft facility account limit utilized drawing power interest charged review period security collateral",
        "bank certificate income proof net worth solvency account holder branch authorized signatory seal stamp",
        "interest certificate savings account fixed deposit recurring deposit financial year tax deduction tds",
        "mobile banking registration activation internet banking credentials user id password otp verification security",
    ],
    "invoices": [
        "invoice number date vendor supplier buyer company address gst_number items quantity rate amount subtotal tax total",
        "proforma invoice quotation estimate items description quantity unit price discount tax shipping total terms validity",
        "commercial invoice international trade export import goods description quantity value weight origin destination customs",
        "tax invoice gst registered dealer supply goods services hsn sac code taxable value cgst sgst igst total",
        "credit note invoice adjustment return defective goods service not rendered original invoice reference amount",
        "debit note invoice additional charges price increase supplementary amount original reference vendor buyer",
        "purchase order company supplier items quantity description unit price delivery date terms conditions payment",
        "invoice payment terms net days bank transfer wire cheque draft account details remittance advice",
        "recurring invoice subscription service monthly billing auto generated sent email payment due date amount",
        "freelance invoice consultant services rendered hours rate project deliverable client company payment terms bank",
        "medical invoice hospital patient treatment procedure medicines charges doctor consultation lab tests pharmacy",
        "legal invoice attorney law firm services hours rate case matter client retainer disbursements total",
        "construction invoice contractor material labor equipment site project progress payment milestone retention",
        "wholesale invoice distributor retailer bulk order items cases pallets discount trade special pricing",
        "utility service invoice maintenance annual contract support hours response time coverage equipment",
        "invoice reminder overdue past due payment amount outstanding balance interest late fee penalty statement",
        "e-invoice irn qr code generated portal validated acknowledgement number date seller buyer supply",
        "export invoice foreign currency amount incoterms fob cif payment letter credit documents customs",
        "vendor invoice accounts payable processing approval workflow coding department general ledger posting",
        "consolidated invoice multiple orders shipments billing period summary charges taxes adjustments total payable",
    ],
}


def generate_augmented_data(
    base_data: dict[str, list[str]], augmentation_factor: int = 3
) -> tuple[list[str], list[str]]:
    """Create augmented training dataset by shuffling and combining base samples."""
    texts = []
    labels = []

    for category, samples in base_data.items():
        for sample in samples:
            # Original
            texts.append(sample)
            labels.append(category)

            # Augmented versions
            for _ in range(augmentation_factor):
                words = sample.split()
                random.shuffle(words)
                # Take random subset (70-100% of words)
                k = random.randint(max(5, int(len(words) * 0.7)), len(words))
                augmented = " ".join(random.sample(words, k))
                texts.append(augmented)
                labels.append(category)

    return texts, labels


def load_real_data() -> tuple[list[str], list[str]] | None:
    """Load real training data from prepared CSV if available."""
    if not TRAINING_CSV.exists():
        logger.info("real_data_not_found", path=str(TRAINING_CSV))
        return None

    texts = []
    labels = []
    valid_categories = {"bills", "upi", "tickets", "tax", "bank", "invoices"}

    with open(TRAINING_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["category"] in valid_categories and row["text"].strip():
                texts.append(row["text"])
                labels.append(row["category"])

    if not texts:
        logger.warning("real_data_empty", path=str(TRAINING_CSV))
        return None

    logger.info("real_data_loaded", total_samples=len(texts))
    return texts, labels


def train_model(mode: str = "auto"):
    """
    Train document classifier and save model + vectorizer.

    Modes:
        auto: Use real data if available, fall back to synthetic
        synthetic: Synthetic data only (original behavior)
        real: Real data only (fails if no CSV)
        combined: Merge real + synthetic (best accuracy)
    """
    logger.info("training_started", mode=mode)

    random.seed(42)
    np.random.seed(42)

    # ── Step 1: Load training data based on mode ──
    logger.info("training_step", step="1/7", action="loading_data")

    real_data = None
    if mode in ("auto", "real", "combined"):
        real_data = load_real_data()

    data_source = "none"

    if mode == "real":
        if real_data is None:
            logger.error("no_real_data", hint="Run: python -m app.ml.datasets.download && python -m app.ml.datasets.prepare")
            return None, None, 0.0
        texts, labels = real_data
        data_source = "real"

    elif mode == "synthetic":
        texts, labels = generate_augmented_data(SYNTHETIC_DATA, augmentation_factor=5)
        data_source = "synthetic"

    elif mode == "combined":
        # Merge real + synthetic with adaptive augmentation
        # Boost synthetic augmentation for categories underrepresented in real data
        syn_texts, syn_labels = generate_augmented_data(SYNTHETIC_DATA, augmentation_factor=10)
        texts = list(syn_texts)
        labels = list(syn_labels)
        if real_data:
            texts.extend(real_data[0])
            labels.extend(real_data[1])
            data_source = "combined"
        else:
            data_source = "synthetic"
            logger.warning("combined_mode_no_real_data", fallback="synthetic only")

    else:  # auto
        if real_data:
            # Use combined: real data + lighter synthetic augmentation
            syn_texts, syn_labels = generate_augmented_data(SYNTHETIC_DATA, augmentation_factor=2)
            texts = list(syn_texts)
            labels = list(syn_labels)
            texts.extend(real_data[0])
            labels.extend(real_data[1])
            data_source = "combined"
        else:
            texts, labels = generate_augmented_data(SYNTHETIC_DATA, augmentation_factor=5)
            data_source = "synthetic"

    logger.info("training_data_loaded", total_samples=len(texts), source=data_source)

    # ── Step 2: Clean texts ──
    logger.info("training_step", step="2/7", action="preprocessing_text")
    all_cleaned = [clean_text(t) for t in texts]

    # Filter out empty texts after cleaning
    valid_pairs = [(t, l) for t, l in zip(all_cleaned, labels) if t.strip()]
    cleaned_texts = [p[0] for p in valid_pairs]
    filtered_labels = [p[1] for p in valid_pairs]
    logger.info("preprocessing_complete", valid_samples=len(cleaned_texts))

    # ── Step 3: Split data ──
    logger.info("training_step", step="3/7", action="splitting_data")
    X_train, X_temp, y_train, y_temp = train_test_split(
        cleaned_texts, filtered_labels, test_size=0.30, random_state=42, stratify=filtered_labels
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.50, random_state=42, stratify=y_temp
    )
    # Convert label lists to numpy arrays (required by CalibratedClassifierCV in sklearn 1.3)
    y_train = np.array(y_train)
    y_val = np.array(y_val)
    y_test = np.array(y_test)
    logger.info(
        "data_split_complete",
        train_size=len(X_train),
        val_size=len(X_val),
        test_size=len(X_test),
    )

    # ── Step 4: TF-IDF Vectorization ──
    logger.info("training_step", step="4/7", action="fitting_tfidf_vectorizer")
    vectorizer = TfidfVectorizer(
        max_features=15000,
        ngram_range=(1, 3),
        min_df=1,
        max_df=0.95,
        sublinear_tf=True,
    )
    X_train_vec = vectorizer.fit_transform(X_train)
    X_val_vec = vectorizer.transform(X_val)
    X_test_vec = vectorizer.transform(X_test)
    logger.info("tfidf_fitted", vocabulary_size=len(vectorizer.vocabulary_))

    # ── Step 5: Train models ──
    logger.info("training_step", step="5/7", action="training_models")

    # Logistic Regression
    logger.info("model_training", model="logistic_regression")
    lr_params = {"C": [0.1, 1.0, 10.0], "max_iter": [500]}
    lr_grid = GridSearchCV(
        LogisticRegression(random_state=42, solver="lbfgs", multi_class="multinomial", class_weight="balanced"),
        lr_params, cv=5, scoring="accuracy", n_jobs=-1,
    )
    lr_grid.fit(X_train_vec, y_train)
    lr_model = lr_grid.best_estimator_
    lr_val_acc = accuracy_score(y_val, lr_model.predict(X_val_vec))
    logger.info(
        "model_evaluated",
        model="logistic_regression",
        best_params=lr_grid.best_params_,
        validation_accuracy=round(lr_val_acc, 4),
    )

    # Naive Bayes
    logger.info("model_training", model="naive_bayes")
    nb_params = {"alpha": [0.1, 0.5, 1.0]}
    nb_grid = GridSearchCV(
        MultinomialNB(), nb_params, cv=5, scoring="accuracy", n_jobs=-1,
    )
    nb_grid.fit(X_train_vec, y_train)
    nb_model = nb_grid.best_estimator_
    nb_val_acc = accuracy_score(y_val, nb_model.predict(X_val_vec))
    logger.info(
        "model_evaluated",
        model="naive_bayes",
        best_params=nb_grid.best_params_,
        validation_accuracy=round(nb_val_acc, 4),
    )

    # Linear SVC
    logger.info("model_training", model="linear_svc")
    # Use StratifiedKFold-safe CV: determine max safe folds from smallest class
    from collections import Counter
    min_class_count = min(Counter(y_train).values())
    svc_inner_cv = 2 if min_class_count < 10 else 3

    # Try multiple C values manually to avoid nested CV issues
    best_svc_model = None
    best_svc_val_acc = -1.0
    best_svc_C = None
    for C_val in [0.1, 1.0, 10.0]:
        try:
            svc_base = LinearSVC(C=C_val, random_state=42, max_iter=2000, class_weight="balanced", dual="auto")
            calibrated = CalibratedClassifierCV(svc_base, cv=svc_inner_cv)
            calibrated.fit(X_train_vec, y_train)
            val_acc = accuracy_score(y_val, calibrated.predict(X_val_vec))
            logger.info("svc_candidate", C=C_val, val_acc=round(val_acc, 4))
            if val_acc > best_svc_val_acc:
                best_svc_val_acc = val_acc
                best_svc_model = calibrated
                best_svc_C = C_val
        except Exception as e:
            logger.warning("svc_fit_failed", C=C_val, error=str(e))
    svc_model = best_svc_model
    svc_val_acc = best_svc_val_acc
    logger.info(
        "model_evaluated",
        model="linear_svc",
        best_C=best_svc_C,
        validation_accuracy=round(svc_val_acc, 4),
    )

    # ── Step 6: Select best model ──
    models = [
        ("Logistic Regression", lr_model, lr_val_acc),
        ("Naive Bayes", nb_model, nb_val_acc),
    ]
    if svc_model is not None:
        models.append(("Linear SVC", svc_model, svc_val_acc))
    else:
        logger.warning("svc_excluded", reason="all C values failed to fit")
        svc_val_acc = 0.0
    best_name, best_model, _ = max(models, key=lambda x: x[2])
    logger.info("best_model_selected", model=best_name)

    # ── Step 7: Final evaluation ──
    logger.info("training_step", step="6/7", action="evaluating_test_set")
    y_pred = best_model.predict(X_test_vec)
    test_acc = accuracy_score(y_test, y_pred)
    report = classification_report(y_test, y_pred, output_dict=True)
    report_str = classification_report(y_test, y_pred)
    cm = confusion_matrix(y_test, y_pred)
    logger.info("test_evaluation_complete", test_accuracy=round(test_acc, 4))

    # Cross-validation
    cv_scores = cross_val_score(best_model, X_train_vec, y_train, cv=5, scoring="accuracy")
    logger.info(
        "cross_validation_complete",
        cv_mean=round(cv_scores.mean(), 4),
        cv_std=round(cv_scores.std(), 4),
    )

    # ── Save model, vectorizer, and evaluation report ──
    logger.info("training_step", step="7/7", action="saving_artifacts")
    os.makedirs(settings.MODEL_DIR, exist_ok=True)
    os.makedirs(EVAL_DIR, exist_ok=True)

    model_path = os.path.join(settings.MODEL_DIR, "document_classifier.pkl")
    vectorizer_path = os.path.join(settings.MODEL_DIR, "tfidf_vectorizer.pkl")
    joblib.dump(best_model, model_path)
    joblib.dump(vectorizer, vectorizer_path)

    # Save evaluation report as JSON
    eval_report = {
        "data_source": data_source,
        "total_samples": len(cleaned_texts),
        "train_size": len(X_train),
        "val_size": len(X_val),
        "test_size": len(X_test),
        "best_model": best_name,
        "test_accuracy": round(test_acc, 4),
        "cv_mean": round(cv_scores.mean(), 4),
        "cv_std": round(cv_scores.std(), 4),
        "vocabulary_size": len(vectorizer.vocabulary_),
        "lr_validation_accuracy": round(lr_val_acc, 4),
        "nb_validation_accuracy": round(nb_val_acc, 4),
        "svc_validation_accuracy": round(svc_val_acc, 4),
        "classification_report": report,
        "confusion_matrix": cm.tolist(),
        "categories": sorted(set(labels)),
    }

    eval_path = EVAL_DIR / "evaluation_report.json"
    with open(eval_path, "w") as f:
        json.dump(eval_report, f, indent=2)

    logger.info(
        "model_saved",
        model_path=model_path,
        vectorizer_path=vectorizer_path,
        eval_path=str(eval_path),
    )

    # Print summary
    print("\n" + "=" * 60)
    print("Training Complete")
    print("=" * 60)
    print(f"  Data source:       {data_source}")
    print(f"  Total samples:     {len(cleaned_texts)}")
    print(f"  Vocabulary size:   {len(vectorizer.vocabulary_)}")
    print(f"  Best model:        {best_name}")
    print(f"  Test accuracy:     {test_acc:.4f}")
    print(f"  CV score:          {cv_scores.mean():.4f} (+/- {cv_scores.std():.4f})")
    print(f"\nValidation accuracies:")
    print(f"  Logistic Regression: {lr_val_acc:.4f}")
    print(f"  Naive Bayes:         {nb_val_acc:.4f}")
    print(f"  Linear SVC:          {svc_val_acc:.4f}")
    print(f"\nPer-category metrics:")
    print(report_str)
    print(f"\nArtifacts saved to: {settings.MODEL_DIR}")
    print(f"Evaluation report:  {eval_path}")
    print("=" * 60)

    logger.info("training_complete")
    return best_model, vectorizer, test_acc


def main():
    parser = argparse.ArgumentParser(description="Train document classifier")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--synthetic-only", action="store_true", help="Train with synthetic data only")
    group.add_argument("--real-only", action="store_true", help="Train with real data only (requires download)")
    group.add_argument("--combined", action="store_true", help="Merge real + synthetic data")
    group.add_argument("--full-pipeline", action="store_true", help="Download → prepare → train")
    args = parser.parse_args()

    if args.full_pipeline:
        print("Running full pipeline: download → prepare → train\n")
        from app.ml.datasets.download import download_all
        from app.ml.datasets.prepare import prepare_training_data
        download_all()
        prepare_training_data()
        train_model(mode="combined")
    elif args.synthetic_only:
        train_model(mode="synthetic")
    elif args.real_only:
        train_model(mode="real")
    elif args.combined:
        train_model(mode="combined")
    else:
        train_model(mode="auto")


if __name__ == "__main__":
    main()
