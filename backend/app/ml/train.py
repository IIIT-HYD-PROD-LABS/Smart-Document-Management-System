"""
ML Model Training Script
Generates synthetic training data and trains document classifiers.
Usage: python -m app.ml.train
"""

import os
import random
import numpy as np
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import MultinomialNB
from sklearn.model_selection import train_test_split, GridSearchCV, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score

from app.config import settings
from app.ml.text_preprocessor import clean_text

# ─── Synthetic Training Data ─────────────────────────────────────────────────
# Each category has realistic text patterns that mimic real documents.

TRAINING_DATA = {
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


def train_model():
    """Train document classifier and save model + vectorizer."""
    print("=" * 60)
    print("  Smart Document Management System - Model Training")
    print("=" * 60)

    # Generate training data
    print("\n[1/6] Generating augmented training data...")
    random.seed(42)
    np.random.seed(42)
    texts, labels = generate_augmented_data(TRAINING_DATA, augmentation_factor=5)
    print(f"  Total samples: {len(texts)}")

    # Clean texts
    print("[2/6] Preprocessing text...")
    cleaned_texts = [clean_text(t) for t in texts]

    # Split data
    print("[3/6] Splitting data (70% train, 15% val, 15% test)...")
    X_train, X_temp, y_train, y_temp = train_test_split(
        cleaned_texts, labels, test_size=0.30, random_state=42, stratify=labels
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.50, random_state=42, stratify=y_temp
    )
    print(f"  Train: {len(X_train)}, Validation: {len(X_val)}, Test: {len(X_test)}")

    # TF-IDF Vectorization
    print("[4/6] Fitting TF-IDF vectorizer...")
    vectorizer = TfidfVectorizer(
        max_features=5000,
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.95,
        sublinear_tf=True,
    )
    X_train_vec = vectorizer.fit_transform(X_train)
    X_val_vec = vectorizer.transform(X_val)
    X_test_vec = vectorizer.transform(X_test)
    print(f"  Vocabulary size: {len(vectorizer.vocabulary_)}")

    # Train Logistic Regression
    print("[5/6] Training models...")
    print("\n  --- Logistic Regression ---")
    lr_params = {"C": [0.1, 1.0, 10.0], "max_iter": [500]}
    lr_grid = GridSearchCV(
        LogisticRegression(random_state=42, solver="lbfgs", multi_class="multinomial"),
        lr_params, cv=5, scoring="accuracy", n_jobs=-1,
    )
    lr_grid.fit(X_train_vec, y_train)
    lr_model = lr_grid.best_estimator_
    lr_val_acc = accuracy_score(y_val, lr_model.predict(X_val_vec))
    print(f"  Best params: {lr_grid.best_params_}")
    print(f"  Validation accuracy: {lr_val_acc:.4f}")

    # Train Naive Bayes
    print("\n  --- Naive Bayes ---")
    nb_params = {"alpha": [0.1, 0.5, 1.0]}
    nb_grid = GridSearchCV(
        MultinomialNB(), nb_params, cv=5, scoring="accuracy", n_jobs=-1,
    )
    nb_grid.fit(X_train_vec, y_train)
    nb_model = nb_grid.best_estimator_
    nb_val_acc = accuracy_score(y_val, nb_model.predict(X_val_vec))
    print(f"  Best params: {nb_grid.best_params_}")
    print(f"  Validation accuracy: {nb_val_acc:.4f}")

    # Select best model
    best_model = lr_model if lr_val_acc >= nb_val_acc else nb_model
    best_name = "Logistic Regression" if lr_val_acc >= nb_val_acc else "Naive Bayes"
    print(f"\n  ✓ Best model: {best_name}")

    # Final evaluation on test set
    print("\n[6/6] Evaluating on test set...")
    y_pred = best_model.predict(X_test_vec)
    test_acc = accuracy_score(y_test, y_pred)
    print(f"\n  Test Accuracy: {test_acc:.4f}")
    print("\n  Classification Report:")
    print(classification_report(y_test, y_pred))
    print("  Confusion Matrix:")
    print(confusion_matrix(y_test, y_pred))

    # Cross-validation score
    cv_scores = cross_val_score(best_model, X_train_vec, y_train, cv=5, scoring="accuracy")
    print(f"\n  5-Fold CV Accuracy: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")

    # Save model and vectorizer
    os.makedirs(settings.MODEL_DIR, exist_ok=True)
    model_path = os.path.join(settings.MODEL_DIR, "document_classifier.pkl")
    vectorizer_path = os.path.join(settings.MODEL_DIR, "tfidf_vectorizer.pkl")
    joblib.dump(best_model, model_path)
    joblib.dump(vectorizer, vectorizer_path)
    print(f"\n  ✓ Model saved to: {model_path}")
    print(f"  ✓ Vectorizer saved to: {vectorizer_path}")
    print("\n" + "=" * 60)
    print("  Training complete!")
    print("=" * 60)

    return best_model, vectorizer, test_acc


if __name__ == "__main__":
    train_model()
