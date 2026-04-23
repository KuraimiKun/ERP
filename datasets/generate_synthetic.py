#!/usr/bin/env python
"""
Generate Synthetic Datasets for ERP AI/ML Research

Creates four CSV files that fill the data gaps not covered by
IBM HR Attrition and Olist E-Commerce datasets:

  1. crm_leads_dataset.csv          – ~5,000 leads with won/lost outcomes
  2. expense_claims_dataset.csv     – ~10,000 expenses with injected anomalies
  3. supplier_procurement_dataset.csv – ~3,000 POs + supplier invoices
  4. attendance_timeseries_dataset.csv – ~50,000 daily check-in/out records

Statistical properties:
  - Log-normal distributions for monetary amounts
  - Seasonal patterns (weekly, monthly, yearly)
  - Realistic class imbalance (~25% lead conversion, ~5% anomaly rate)
  - Correlated features (value ↔ conversion, tenure ↔ attendance)

Usage:
    python datasets/generate_synthetic.py
    python datasets/generate_synthetic.py --seed 42
"""

import argparse
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# ── Reproducibility ────────────────────────────────────────────────────────
DEFAULT_SEED = 42
OUTPUT_DIR = Path(__file__).resolve().parent


# ════════════════════════════════════════════════════════════════════════════
#  1.  CRM LEAD SCORING DATASET
# ════════════════════════════════════════════════════════════════════════════


def generate_leads(rng: np.random.Generator, n: int = 5000) -> pd.DataFrame:
    """
    Generates synthetic CRM leads with realistic conversion patterns.

    Features that influence conversion:
      - Higher estimated value → slightly lower conversion (harder deals)
      - More activities → higher conversion
      - Referral/walk-in sources → higher conversion than cold_call
      - Has company name (B2B) → higher conversion
      - Has email + phone → higher conversion
    """
    print(f"[1/4] Generating {n} CRM leads …")

    sources = ["website", "referral", "social", "advertisement", "exhibition", "cold_call", "walk_in", "email", "other"]
    source_weights = [0.20, 0.18, 0.12, 0.10, 0.08, 0.10, 0.07, 0.10, 0.05]

    # Source-specific base conversion rates
    source_conversion = {
        "website": 0.12,
        "referral": 0.24,
        "social": 0.06,
        "advertisement": 0.10,
        "exhibition": 0.18,
        "cold_call": 0.04,
        "walk_in": 0.20,
        "email": 0.11,
        "other": 0.08,
    }

    services = [
        "Web Development",
        "Mobile App",
        "Cloud Migration",
        "ERP Implementation",
        "Data Analytics",
        "Cybersecurity",
        "IT Support",
        "Digital Marketing",
        "AI/ML Consulting",
        "DevOps Setup",
        "Network Infrastructure",
    ]

    first_names = [
        "Ahmed",
        "Mohammed",
        "Ali",
        "Omar",
        "Khalid",
        "Sara",
        "Fatima",
        "Noura",
        "Hassan",
        "Yusuf",
        "Layla",
        "Aisha",
        "Ibrahim",
        "Tariq",
        "Salma",
        "Rami",
        "Dina",
        "Karim",
        "Nadia",
        "Zaid",
        "Hana",
        "Samir",
        "Lina",
        "Faisal",
        "Mona",
        "Jamal",
        "Reem",
        "Waleed",
        "Amina",
        "Bilal",
        "Yasmin",
        "Adel",
        "Mariam",
        "Hamza",
        "Samira",
    ]
    last_names = [
        "Al-Rashid",
        "Al-Hashimi",
        "Al-Farsi",
        "Al-Sayed",
        "Al-Mahmoud",
        "Al-Qahtani",
        "Al-Dosari",
        "Al-Harbi",
        "Al-Otaibi",
        "Al-Ghamdi",
        "Al-Zahrani",
        "Al-Shehri",
        "Al-Balushi",
        "Al-Tamimi",
        "Al-Mazrui",
        "Nasser",
        "Abbas",
        "Malik",
        "Hussain",
        "Rahman",
    ]
    companies_b2b = [
        "TechCorp LLC",
        "Gulf Enterprises",
        "Horizon Trading",
        "Delta Systems",
        "Pinnacle Solutions",
        "BlueStar IT",
        "Sahara Group",
        "Falcon Industries",
        "Quantum Digital",
        "Nexus Advisory",
        "Oasis Technologies",
        "Vanguard Ltd.",
        "Atlas Holdings",
        "Emerald Consulting",
        "Zenith Partners",
        "",
        "",
        "",
        "",
        "",
    ]
    cities = [
        "Dubai",
        "Abu Dhabi",
        "Riyadh",
        "Jeddah",
        "Muscat",
        "Doha",
        "Kuwait City",
        "Manama",
        "Amman",
        "Cairo",
    ]

    records = []
    base_date = date(2022, 1, 1)

    for i in range(n):
        source = rng.choice(sources, p=source_weights)
        created_days = int(rng.uniform(0, 900))  # spread over 2.5 years
        created_at = base_date + timedelta(days=created_days)

        first_name = rng.choice(first_names)
        last_name = rng.choice(last_names)
        email = f"{first_name.lower()}.{last_name.lower().replace('-', '').replace(' ', '')}@example.com"

        has_phone = rng.random() > 0.25
        has_mobile = rng.random() > 0.30
        company_name = rng.choice(companies_b2b)
        has_company = len(company_name) > 0

        # Estimated value: log-normal, mean ~$15k, higher values are rarer
        estimated_value = round(float(rng.lognormal(mean=9.5, sigma=0.8)), 2)
        estimated_value = min(estimated_value, 500000)  # cap

        service = rng.choice(services)
        city = rng.choice(cities)

        # Activity count: Poisson with mean depending on source
        activity_mean = {"referral": 5, "walk_in": 4, "exhibition": 4, "cold_call": 2, "website": 3}.get(source, 3)
        activity_count = int(rng.poisson(activity_mean))

        # Days in pipeline
        days_in_pipeline = int(rng.exponential(45)) + 1
        days_in_pipeline = min(days_in_pipeline, 365)

        # ── Conversion probability (logistic with correlated features) ──
        base_rate = source_conversion[source]

        # Activity boost (more activities → higher conversion)
        activity_boost = min(activity_count * 0.025, 0.15)

        # B2B boost
        b2b_boost = 0.04 if has_company else 0.0

        # Contact completeness boost
        contact_boost = 0.02 * (has_phone + has_mobile)

        # Value effect: very large deals convert less
        value_penalty = -0.10 if estimated_value > 80000 else 0.0

        # Pipeline delay penalty: longer pipelines lose momentum
        delay_penalty = -min(days_in_pipeline / 500, 0.15)

        # Seasonal effect: Q4 has higher conversion
        month = created_at.month
        seasonal = 0.05 if month >= 10 else -0.03 if month <= 3 else 0.0

        prob = np.clip(
            base_rate
            + activity_boost
            + b2b_boost
            + contact_boost
            + value_penalty
            + delay_penalty
            + seasonal
            + rng.normal(0, 0.08),  # noise
            0.02,
            0.95,
        )

        # Outcome
        won = rng.random() < prob
        status = (
            "won"
            if won
            else rng.choice(
                ["lost", "lost", "lost", "inactive"],
            )
        )

        # Conversion date for won leads
        conversion_date = ""
        if won:
            conversion_date = (created_at + timedelta(days=days_in_pipeline)).isoformat()

        # Last contact and follow-up
        last_contact_days = int(rng.uniform(0, min(days_in_pipeline, 60)))
        last_contact = created_at + timedelta(days=last_contact_days)

        records.append(
            {
                "lead_number": f"LD-{10000 + i}",
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "phone": f"+971-{rng.integers(50, 59)}-{rng.integers(1000000, 9999999)}" if has_phone else "",
                "mobile": f"+971-{rng.integers(50, 59)}-{rng.integers(1000000, 9999999)}" if has_mobile else "",
                "company_name": company_name,
                "job_title": rng.choice(["Manager", "Director", "CEO", "CTO", "VP", "Analyst", ""])
                if has_company
                else "",
                "city": city,
                "country": "UAE"
                if city in ["Dubai", "Abu Dhabi"]
                else rng.choice(["Saudi Arabia", "Oman", "Qatar", "Kuwait", "Bahrain", "Jordan", "Egypt"]),
                "source": source,
                "service_interest": service,
                "estimated_value": estimated_value,
                "probability": int(prob * 100),
                "status": status,
                "activity_count": activity_count,
                "days_in_pipeline": days_in_pipeline,
                "created_at": created_at.isoformat(),
                "last_contact_date": last_contact.isoformat(),
                "conversion_date": conversion_date,
            }
        )

    df = pd.DataFrame(records)
    won_rate = df["status"].eq("won").mean()
    print(f"  → {n} leads, conversion rate = {won_rate:.1%}")
    return df


# ════════════════════════════════════════════════════════════════════════════
#  2.  EXPENSE CLAIMS DATASET
# ════════════════════════════════════════════════════════════════════════════


def generate_expenses(rng: np.random.Generator, n: int = 10000) -> pd.DataFrame:
    """
    Generates synthetic expense claims with ~5% injected anomalies.

    Anomaly types:
      - Unusually large amounts (> 3σ from category mean)
      - Weekend submissions
      - Duplicate-like amounts within same week
      - Unusual category-time combinations
    """
    print(f"[2/4] Generating {n} expense claims …")

    categories = {
        "Travel": {"mean": 450, "std": 200, "freq": 0.18},
        "Office Supplies": {"mean": 85, "std": 40, "freq": 0.15},
        "Software": {"mean": 250, "std": 150, "freq": 0.10},
        "Meals & Entertain": {"mean": 65, "std": 30, "freq": 0.12},
        "Equipment": {"mean": 800, "std": 500, "freq": 0.08},
        "Professional Svcs": {"mean": 1200, "std": 600, "freq": 0.07},
        "Utilities": {"mean": 350, "std": 100, "freq": 0.08},
        "Marketing": {"mean": 600, "std": 350, "freq": 0.06},
        "Training": {"mean": 500, "std": 250, "freq": 0.06},
        "Maintenance": {"mean": 300, "std": 150, "freq": 0.05},
        "Miscellaneous": {"mean": 120, "std": 80, "freq": 0.05},
    }
    cat_names = list(categories.keys())
    cat_probs = [categories[c]["freq"] for c in cat_names]

    departments = ["Sales", "R&D", "HR", "Finance", "Operations", "Marketing", "IT"]
    statuses = ["approved", "approved", "approved", "approved", "approved", "rejected", "paid", "paid"]

    employee_ids = [f"EMP-{i:04d}" for i in range(1, 201)]

    records = []
    anomaly_flags = []
    base_date = date(2022, 1, 1)

    for i in range(n):
        cat = rng.choice(cat_names, p=cat_probs)
        cat_info = categories[cat]
        expense_days = int(rng.uniform(0, 900))
        expense_date = base_date + timedelta(days=expense_days)
        employee = rng.choice(employee_ids)
        dept = rng.choice(departments)
        status = rng.choice(statuses)

        # Normal amount: truncated normal
        amount = max(5.0, float(rng.normal(cat_info["mean"], cat_info["std"])))

        is_anomaly = False

        # ~5% anomaly injection
        if rng.random() < 0.05:
            anomaly_type = rng.choice(["large_amount", "weekend", "duplicate_like", "odd_category"])

            if anomaly_type == "large_amount":
                # Extreme amount: 4-10x the category mean
                amount = float(cat_info["mean"] * rng.uniform(4, 10))
                is_anomaly = True

            elif anomaly_type == "weekend":
                # Shift to weekend
                dow = expense_date.weekday()
                if dow < 5:
                    expense_date = expense_date + timedelta(days=(5 - dow))
                is_anomaly = True

            elif anomaly_type == "duplicate_like":
                # Round suspicious amount
                amount = round(amount / 100) * 100 + 0.00
                is_anomaly = True

            elif anomaly_type == "odd_category":
                # Unusually high for a typically low category
                if cat in ["Office Supplies", "Meals & Entertain", "Miscellaneous"]:
                    amount = float(rng.uniform(2000, 8000))
                    is_anomaly = True

        amount = round(amount, 2)
        tax = round(amount * 0.05, 2) if rng.random() > 0.3 else 0.0

        records.append(
            {
                "expense_number": f"EXP-{20000 + i}",
                "expense_date": expense_date.isoformat(),
                "category": cat,
                "department": dept,
                "employee_id": employee,
                "description": f"{cat} expense - {expense_date.strftime('%B %Y')}",
                "amount": amount,
                "tax_amount": tax,
                "total_amount": round(amount + tax, 2),
                "status": status,
                "day_of_week": expense_date.strftime("%A"),
                "is_anomaly": int(is_anomaly),
            }
        )
        anomaly_flags.append(is_anomaly)

    df = pd.DataFrame(records)
    anomaly_rate = sum(anomaly_flags) / n
    print(f"  → {n} expenses, anomaly rate = {anomaly_rate:.1%}")
    return df


# ════════════════════════════════════════════════════════════════════════════
#  3.  SUPPLIER PROCUREMENT DATASET
# ════════════════════════════════════════════════════════════════════════════


def generate_procurement(rng: np.random.Generator, n_suppliers: int = 80, n_pos: int = 3000) -> pd.DataFrame:
    """
    Generates supplier + purchase order + supplier invoice data.

    Features for cash-flow forecasting:
      - Diverse payment terms (15/30/45/60/90 days)
      - Seasonal ordering patterns
      - Variable lead times per supplier type
      - Payment status distribution (on-time / late / partial)
    """
    print(f"[3/4] Generating {n_suppliers} suppliers + {n_pos} purchase orders …")

    supplier_types = ["airline", "hotel", "transport", "visa", "insurance", "tour_operator", "dmc", "other"]
    type_config = {
        "airline": {"avg_amount": 5000, "lead_time": 7, "terms": 30},
        "hotel": {"avg_amount": 3000, "lead_time": 3, "terms": 30},
        "transport": {"avg_amount": 1500, "lead_time": 5, "terms": 15},
        "visa": {"avg_amount": 800, "lead_time": 14, "terms": 15},
        "insurance": {"avg_amount": 2000, "lead_time": 7, "terms": 45},
        "tour_operator": {"avg_amount": 8000, "lead_time": 21, "terms": 60},
        "dmc": {"avg_amount": 6000, "lead_time": 14, "terms": 45},
        "other": {"avg_amount": 1200, "lead_time": 10, "terms": 30},
    }

    # Generate suppliers
    supplier_names = [
        "Global Air Services",
        "Gulf Hotels Group",
        "Desert Transport Co",
        "Fast Visa Agency",
        "Shield Insurance",
        "Adventure Tours LLC",
        "Oasis DMC Partners",
        "TechParts Supply",
        "Premium Logistics",
        "Star Airlines",
        "Seaside Resorts",
        "City Cab Transit",
    ]
    cities = ["Dubai", "Abu Dhabi", "Riyadh", "Jeddah", "Muscat", "Doha"]

    suppliers = []
    for i in range(n_suppliers):
        stype = rng.choice(supplier_types)
        config = type_config[stype]
        name_base = rng.choice(supplier_names)
        suppliers.append(
            {
                "supplier_id": f"SUP-{1000 + i}",
                "supplier_type": stype,
                "name": f"{name_base} {rng.choice(['Inc', 'LLC', 'Co', 'Ltd'])} #{i}",
                "city": rng.choice(cities),
                "payment_terms": int(
                    rng.choice([config["terms"], config["terms"], config["terms"] + 15, config["terms"] - 15])
                ),
                "rating": int(rng.integers(2, 6)),
                "avg_amount": config["avg_amount"],
                "avg_lead_time": config["lead_time"],
            }
        )
    suppliers_df = pd.DataFrame(suppliers)

    # Generate purchase orders
    base_date = date(2022, 1, 1)
    po_records = []

    for i in range(n_pos):
        supplier = suppliers[rng.integers(0, len(suppliers))]
        order_days = int(rng.uniform(0, 900))
        order_date = base_date + timedelta(days=order_days)

        # Seasonal pattern: more orders in Q3-Q4 (travel season for Gulf)
        month = order_date.month
        seasonal_mul = 1.3 if month in [6, 7, 8, 9, 10] else 0.8

        # Amount: log-normal around supplier's typical
        avg = supplier["avg_amount"] * seasonal_mul
        amount = round(float(rng.lognormal(mean=np.log(avg), sigma=0.5)), 2)
        amount = min(amount, 200000)

        tax = round(amount * 0.05, 2)
        total = round(amount + tax, 2)

        # Lead time with noise
        lead_time = max(1, int(supplier["avg_lead_time"] + rng.normal(0, supplier["avg_lead_time"] * 0.3)))
        expected_date = order_date + timedelta(days=lead_time)

        # Payment terms
        terms = supplier["payment_terms"]
        due_date = order_date + timedelta(days=max(terms, 7))

        # Status
        now_ref = date(2024, 9, 1)
        if order_date > now_ref:
            status = rng.choice(["draft", "pending", "approved", "sent"])
            paid_amount = 0.0
        else:
            status = rng.choice(
                [
                    "received",
                    "received",
                    "received",
                    "received",
                    "partial",
                    "approved",
                    "sent",
                ]
            )
            if status == "received":
                # Payment timing
                actual_pay_delay = int(rng.normal(terms, terms * 0.3))
                _paid_on_time = actual_pay_delay <= terms
                paid_amount = total if rng.random() < 0.85 else round(total * rng.uniform(0.3, 0.9), 2)
            elif status == "partial":
                paid_amount = round(total * rng.uniform(0.2, 0.7), 2)
            else:
                paid_amount = 0.0

        balance_due = round(total - paid_amount, 2)

        # Line items (1-5 per PO)
        n_lines = int(rng.integers(1, 6))

        po_records.append(
            {
                "po_number": f"PO-{30000 + i}",
                "supplier_id": supplier["supplier_id"],
                "supplier_type": supplier["supplier_type"],
                "supplier_name": supplier["name"],
                "order_date": order_date.isoformat(),
                "expected_date": expected_date.isoformat(),
                "due_date": due_date.isoformat(),
                "lead_time_days": lead_time,
                "payment_terms_days": terms,
                "subtotal": amount,
                "tax_amount": tax,
                "total_amount": total,
                "paid_amount": paid_amount,
                "balance_due": balance_due,
                "status": status,
                "n_lines": n_lines,
                "order_month": month,
                "order_quarter": f"Q{(month - 1) // 3 + 1}",
            }
        )

    po_df = pd.DataFrame(po_records)
    print(f"  → {n_suppliers} suppliers, {n_pos} POs, total value = ${po_df['total_amount'].sum():,.0f}")
    return suppliers_df, po_df


# ════════════════════════════════════════════════════════════════════════════
#  4.  ATTENDANCE TIME-SERIES DATASET
# ════════════════════════════════════════════════════════════════════════════


def generate_attendance(rng: np.random.Generator, n_employees: int = 200, n_days: int = 365) -> pd.DataFrame:
    """
    Generates realistic daily attendance time-series with anomalies.

    Features:
      - Normal work hours (8-9h) with per-employee baselines
      - Shift patterns (morning/afternoon)
      - Friday/Saturday off (Gulf work week)
      - Seasonal variation (Ramadan reduced hours)
      - Injected anomalies: chronic lateness, ghost check-ins, overtime abuse
    """
    print(f"[4/4] Generating attendance for {n_employees} employees × {n_days} days …")

    base_date = date(2023, 7, 1)
    departments = ["Sales", "R&D", "HR", "Finance", "Operations", "Marketing", "IT"]

    # Per-employee profiles
    employee_profiles = []
    for i in range(n_employees):
        dept = rng.choice(departments)
        # Normal check-in time: mean 8:00 AM, std 15 min
        # Some employees are consistently late
        is_chronically_late = rng.random() < 0.08  # 8% are late-comers
        check_in_mean = 9.5 if is_chronically_late else rng.normal(8.0, 0.25)
        check_in_std = 0.5 if is_chronically_late else rng.uniform(0.1, 0.3)

        # Work duration: mean 8.5h, some do excessive overtime
        is_overtime_abuser = rng.random() < 0.05  # 5% log excessive hours
        work_hours_mean = rng.uniform(10, 14) if is_overtime_abuser else rng.normal(8.5, 0.3)
        work_hours_std = 1.0 if is_overtime_abuser else rng.uniform(0.2, 0.5)

        # Absence rate
        absence_rate = rng.beta(2, 20)  # most employees ~5-10% absence
        if is_chronically_late:
            absence_rate = min(absence_rate + 0.10, 0.40)

        # Ghost check-in: extremely rare, always anomalous
        is_ghost = rng.random() < 0.03  # 3% ghost profiles

        employee_profiles.append(
            {
                "employee_id": f"EMP-{i + 1:04d}",
                "department": dept,
                "check_in_mean": check_in_mean,
                "check_in_std": check_in_std,
                "work_hours_mean": work_hours_mean,
                "work_hours_std": work_hours_std,
                "absence_rate": absence_rate,
                "is_chronically_late": is_chronically_late,
                "is_overtime_abuser": is_overtime_abuser,
                "is_ghost": is_ghost,
            }
        )

    records = []
    for day_offset in range(n_days):
        current_date = base_date + timedelta(days=day_offset)
        dow = current_date.weekday()  # 0=Monday

        # Skip Friday & Saturday (Gulf work week)
        if dow in [4, 5]:  # Friday=4, Saturday=5
            continue

        # Ramadan: reduced hours (approximate: March-April 2024)
        is_ramadan = (current_date.month == 3 and current_date.day >= 11) or (
            current_date.month == 4 and current_date.day <= 9
        )

        for emp in employee_profiles:
            # Absent?
            if rng.random() < emp["absence_rate"]:
                records.append(
                    {
                        "employee_id": emp["employee_id"],
                        "department": emp["department"],
                        "date": current_date.isoformat(),
                        "check_in": "",
                        "check_out": "",
                        "hours_worked": 0.0,
                        "overtime_hours": 0.0,
                        "is_present": False,
                        "is_late": False,
                        "is_anomaly": False,
                        "anomaly_type": "",
                    }
                )
                continue

            # Check-in time
            check_in_hour = rng.normal(emp["check_in_mean"], emp["check_in_std"])
            check_in_hour = np.clip(check_in_hour, 6.0, 12.0)

            # Work hours
            work_hours = rng.normal(emp["work_hours_mean"], emp["work_hours_std"])
            if is_ramadan:
                work_hours *= 0.75  # reduced Ramadan hours
            work_hours = np.clip(work_hours, 2.0, 16.0)

            check_out_hour = check_in_hour + work_hours
            check_out_hour = min(check_out_hour, 23.5)

            actual_hours = check_out_hour - check_in_hour
            overtime = max(0, actual_hours - 8.0)

            # Determine if late (after 8:30)
            is_late = check_in_hour > 8.5

            # Ghost check-in anomaly: minimal hours but logged
            is_anomaly = False
            anomaly_type = ""
            if emp["is_ghost"] and rng.random() < 0.3:
                # Ghost: check in, check out within 30 min
                work_hours = rng.uniform(0.1, 0.5)
                check_out_hour = check_in_hour + work_hours
                actual_hours = work_hours
                overtime = 0
                is_anomaly = True
                anomaly_type = "ghost_checkin"
            elif emp["is_chronically_late"] and is_late:
                is_anomaly = True
                anomaly_type = "chronic_lateness"
            elif emp["is_overtime_abuser"] and overtime > 4:
                is_anomaly = True
                anomaly_type = "excessive_overtime"

            # Format times
            ci_h = int(check_in_hour)
            ci_m = int((check_in_hour - ci_h) * 60)
            co_h = int(check_out_hour)
            co_m = int((check_out_hour - co_h) * 60)

            records.append(
                {
                    "employee_id": emp["employee_id"],
                    "department": emp["department"],
                    "date": current_date.isoformat(),
                    "check_in": f"{ci_h:02d}:{ci_m:02d}",
                    "check_out": f"{co_h:02d}:{co_m:02d}",
                    "hours_worked": round(actual_hours, 2),
                    "overtime_hours": round(overtime, 2),
                    "is_present": True,
                    "is_late": is_late,
                    "is_anomaly": is_anomaly,
                    "anomaly_type": anomaly_type,
                }
            )

    df = pd.DataFrame(records)
    present = df["is_present"].sum()
    anomalies = df["is_anomaly"].sum()
    print(f"  → {len(df)} records ({present} present), anomaly rate = {anomalies / max(present, 1):.1%}")
    return df


# ════════════════════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic ERP datasets")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--leads", type=int, default=5000)
    parser.add_argument("--expenses", type=int, default=10000)
    parser.add_argument("--pos", type=int, default=3000)
    parser.add_argument("--employees", type=int, default=200)
    parser.add_argument("--days", type=int, default=365)
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)

    print(f"{'=' * 60}")
    print(f"  Synthetic ERP Dataset Generator (seed={args.seed})")
    print(f"{'=' * 60}\n")

    # 1. CRM Leads
    leads_df = generate_leads(rng, args.leads)
    leads_path = OUTPUT_DIR / "crm_leads_dataset.csv"
    leads_df.to_csv(leads_path, index=False)
    print(f"  Saved → {leads_path}\n")

    # 2. Expense Claims
    expenses_df = generate_expenses(rng, args.expenses)
    expenses_path = OUTPUT_DIR / "expense_claims_dataset.csv"
    expenses_df.to_csv(expenses_path, index=False)
    print(f"  Saved → {expenses_path}\n")

    # 3. Supplier Procurement
    suppliers_df, po_df = generate_procurement(rng, n_pos=args.pos)
    suppliers_path = OUTPUT_DIR / "supplier_procurement_suppliers.csv"
    po_path = OUTPUT_DIR / "supplier_procurement_orders.csv"
    suppliers_df.to_csv(suppliers_path, index=False)
    po_df.to_csv(po_path, index=False)
    print(f"  Saved → {suppliers_path}")
    print(f"  Saved → {po_path}\n")

    # 4. Attendance Time-Series
    attendance_df = generate_attendance(rng, args.employees, args.days)
    attendance_path = OUTPUT_DIR / "attendance_timeseries_dataset.csv"
    attendance_df.to_csv(attendance_path, index=False)
    print(f"  Saved → {attendance_path}\n")

    # Summary
    print(f"{'=' * 60}")
    print("  ALL DATASETS GENERATED SUCCESSFULLY")
    print(f"{'=' * 60}")
    print(f"  crm_leads_dataset.csv          : {len(leads_df):>8,} rows")
    print(f"  expense_claims_dataset.csv     : {len(expenses_df):>8,} rows")
    print(f"  supplier_procurement_suppliers.csv : {len(suppliers_df):>5,} rows")
    print(f"  supplier_procurement_orders.csv: {len(po_df):>8,} rows")
    print(f"  attendance_timeseries_dataset.csv : {len(attendance_df):>8,} rows")
    print()


if __name__ == "__main__":
    main()
